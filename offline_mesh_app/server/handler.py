import json
import os
import base64
import threading
import time
import uuid
from config import MY_ID, DOWNLOAD_DIR
from routing.router import router
from routing.cache import message_cache, file_cache
from utils.logger import log_message, log_routing, log_file_transfer, network_logger
from utils.encryption import decrypt_data
from client.sender import forward_packet
from client.gateway_discovery import handle_gateway_update

def handle_file_transfer(conn, addr):
    """Handle an incoming file transfer"""
    try:
        # Create a local copy of the connection to avoid it being closed elsewhere
        local_conn = conn
        
        # First check if this is a direct file transfer with a header
        try:
            # Try to read the first 4 bytes which might be a length header
            header_data = local_conn.recv(4)
            if len(header_data) == 4:
                # Extract data length from header
                data_length = int.from_bytes(header_data, byteorder='big')
                
                # Read the marker packet
                marker_data = b''
                remaining = data_length
                while remaining > 0:
                    chunk = local_conn.recv(min(remaining, 4096))
                    if not chunk:
                        break
                    marker_data += chunk
                    remaining -= len(chunk)
                
                # Try to parse as JSON to see if it's a marker packet
                try:
                    marker_packet = json.loads(marker_data.decode('utf-8'))
                    packet_type = marker_packet.get("type", "")
                    
                    if packet_type == "direct_file_transfer":
                        # This is a direct file transfer, get metadata
                        file_id = marker_packet.get("file_id", str(uuid.uuid4()))
                        source_id = marker_packet.get("src", "unknown")
                        
                        # Look up file information if available
                        file_info = None
                        for cached_id in file_cache.files:
                            if cached_id == file_id:
                                file_info = file_cache[cached_id]
                                break
                        
                        filename = "unknown.dat"
                        if file_info:
                            filename = file_info.get("filename", filename)
                        
                        # Create a temporary file
                        temp_dir = os.path.join(DOWNLOAD_DIR, "temp")
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Generate a unique filename
                        temp_filename = f"incoming_{addr[0]}_{int(time.time())}.dat"
                        temp_path = os.path.join(temp_dir, temp_filename)
                        
                        # Receive the file data
                        total_received = 0
                        with open(temp_path, "wb") as f:
                            while True:
                                try:
                                    chunk = local_conn.recv(8192)
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    total_received += len(chunk)
                                except Exception as e:
                                    network_logger.error(f"Error receiving direct file chunk: {e}")
                                    # Don't break here, try to read more data if possible
                        
                        network_logger.info(f"Direct file transfer received from {addr[0]}: {total_received} bytes")
                        
                        # Move to final location
                        import shutil
                        safe_filename = os.path.basename(filename)
                        name_parts = os.path.splitext(safe_filename)
                        new_filename = f"{name_parts[0]}_{int(time.time())}{name_parts[1]}"
                        dest_path = os.path.join(DOWNLOAD_DIR, new_filename)
                        shutil.move(temp_path, dest_path)
                        
                        network_logger.info(f"File saved to {dest_path}")
                        
                        # Log the file transfer
                        log_file_transfer(filename, source_id, MY_ID, "COMPLETED", 
                                         f"Size: {total_received} bytes, Saved to {dest_path}")
                        
                        return
                except:
                    # Not a valid marker packet, continue with regular file transfer
                    network_logger.debug(f"Received data from {addr[0]} is not a valid direct transfer marker")
        except Exception as e:
            network_logger.debug(f"Error checking for direct file transfer header: {e}")
        
        # Create a temporary file
        temp_dir = os.path.join(DOWNLOAD_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate a unique filename
        temp_filename = f"incoming_{addr[0]}_{int(time.time())}.dat"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Track data received
        total_received = 0
        
        # Receive the file in chunks
        with open(temp_path, "wb") as f:
            # Write header data if we already read it
            if 'header_data' in locals() and header_data:
                f.write(header_data)
                total_received += len(header_data)
            
            # Write marker data if we already read it
            if 'marker_data' in locals() and marker_data:
                f.write(marker_data)
                total_received += len(marker_data)
            
            # Continue reading the rest of the data
            while True:
                try:
                    if local_conn is None:
                        network_logger.warning("Connection is None, stopping file reception")
                        break
                        
                    chunk = local_conn.recv(4096)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_received += len(chunk)
                except Exception as e:
                    network_logger.error(f"Error receiving file chunk: {e}")
                    # Don't break immediately, try next iteration
                    # This makes the transfer more resilient to temporary errors
                    if "not a socket" in str(e) or "Bad file descriptor" in str(e):
                        break
        
        network_logger.info(f"File received from {addr[0]}: {total_received} bytes")
        
        # Now process the file - in a real implementation, you would need to
        # determine which file_id this belongs to and add it to the correct file cache
        # For now, we'll just move it to the downloads directory
        
        # Check if there's a pending file in the cache that needs this data
        # This is a simple implementation - in practice you would need a more robust way
        # to match binary data with file_info packets
        import shutil
        dest_path = os.path.join(DOWNLOAD_DIR, f"received_file_{int(time.time())}.dat")
        shutil.move(temp_path, dest_path)
        
        network_logger.info(f"File saved to {dest_path}")
    except Exception as e:
        network_logger.error(f"Error handling file transfer from {addr}: {e}")
        
    finally:
        # Only close the connection if we're the ones who should be closing it
        # and if it hasn't been closed already
        if conn:
            try:
                conn.close()
            except Exception as e:
                network_logger.debug(f"Error closing connection: {e}")
                pass

def handle_packet(data, addr, conn=None):
    """Handle an incoming packet"""
    try:
        # Get the source IP
        source_ip = addr[0]
        
        # First, check if this might be binary file data
        try:
            # Try to decode as JSON to see if it's a valid packet
            json_packet = None
            try:
                # Try to decrypt the data if it's encrypted
                try:
                    decrypted_data = decrypt_data(data)
                    if isinstance(decrypted_data, bytes):
                        data = decrypted_data
                    else:
                        data = decrypted_data.encode()
                except Exception as e:
                    network_logger.debug(f"Failed to decrypt packet from {source_ip}, may be binary data: {e}")
                
                # Now try to parse as JSON
                json_packet = json.loads(data.decode('utf-8'))
                
            except UnicodeDecodeError:
                # This is likely binary data, handle as file transfer
                network_logger.debug(f"Received binary data from {source_ip}, treating as file transfer")
                handle_file_transfer(conn, addr)
                return
            except json.JSONDecodeError:
                # This is likely binary data, handle as file transfer
                network_logger.debug(f"Received data that's not valid JSON from {source_ip}, treating as file transfer")
                handle_file_transfer(conn, addr)
                return
            
            # If we get here, we have a valid JSON packet
            packet = json_packet
            
            # Extract packet type
            packet_type = packet.get("type", "unknown")
            
            # Handle different packet types
            if packet_type == "routing":
                handle_routing_packet(packet, source_ip)
            elif packet_type == "message":
                handle_message_packet(packet, source_ip)
            elif packet_type == "broadcast":
                handle_broadcast_packet(packet, source_ip)
            elif packet_type == "file_info":
                handle_file_info_packet(packet, source_ip)
            elif packet_type == "file_chunk":
                handle_file_chunk_packet(packet, source_ip)
            elif packet_type == "gateway_update":
                handle_gateway_update(packet, source_ip)
            elif packet_type == "file":
                handle_file_transfer(conn, addr)
            else:
                network_logger.warning(f"Unknown packet type '{packet_type}' from {source_ip}")
                
        except Exception as e:
            # If all parsing fails, try to handle as a file transfer
            network_logger.debug(f"Error processing packet data, trying as file transfer: {e}")
            handle_file_transfer(conn, addr)
            
    except Exception as e:
        network_logger.error(f"Error handling packet from {addr}: {e}")

def handle_routing_packet(packet, source_ip):
    """Handle a routing update packet"""
    try:
        source_id = packet.get("src", "unknown")
        link_state = packet.get("link_state", {})
        seq_num = packet.get("seq", 0)
        ttl = packet.get("ttl", 0)
        
        # Update routing table
        was_updated = router.update_link_state(source_id, source_ip, link_state, seq_num, ttl)
        
        # Forward if TTL allows and it was a new update
        if was_updated and ttl > 1:
            # Decrease TTL
            packet["ttl"] = ttl - 1
            
            # Forward to all neighbors except the source
            forward_packet(packet, source_ip)
        
    except Exception as e:
        network_logger.error(f"Error handling routing packet: {e}")

def handle_message_packet(packet, source_ip):
    """Handle a message packet"""
    try:
        source_id = packet.get("src", "unknown")
        dest_id = packet.get("dst", "unknown")
        content = packet.get("content", "")
        message_type = packet.get("message_type", "text")
        message_id = packet.get("id", "")
        
        # If we've already seen this message, skip processing
        if message_cache.has_message(message_id):
            return
        
        # Add to message cache
        message_cache.add_message(message_id, packet)
        
        # If we are the intended recipient
        if dest_id == MY_ID or dest_id == "ALL":
            log_message(source_id, MY_ID, content, message_type)
            network_logger.info(f"Received message from {source_id}: {content}")
        
        # Forward if needed
        forward_packet(packet, source_ip)
            
    except Exception as e:
        network_logger.error(f"Error handling message packet: {e}")

def handle_broadcast_packet(packet, source_ip):
    """Handle a broadcast message packet"""
    try:
        source_id = packet.get("src", "unknown")
        content = packet.get("content", "")
        message_type = packet.get("message_type", "text")
        message_id = packet.get("id", "")
        
        # If we've already seen this broadcast, skip processing
        if message_cache.has_message(message_id):
            return
        
        # Add to message cache
        message_cache.add_message(message_id, packet)
        
        # Log the broadcast
        log_message(source_id, "ALL", content, message_type)
        network_logger.info(f"Received broadcast from {source_id}: {content}")
        
        # Forward if needed
        forward_packet(packet, source_ip)
            
    except Exception as e:
        network_logger.error(f"Error handling broadcast packet: {e}")

def handle_file_info_packet(packet, source_ip):
    """Handle a file info packet (beginning of file transfer)"""
    try:
        source_id = packet.get("src", "unknown")
        dest_id = packet.get("dst", "unknown")
        file_id = packet.get("id", "")
        filename = packet.get("filename", "unknown")
        filesize = packet.get("filesize", 0)
        total_chunks = packet.get("total_chunks", 0)
        
        # If we are the intended recipient
        if dest_id == MY_ID:
            log_file_transfer(filename, source_id, MY_ID, "STARTED", 
                             f"Size: {filesize} bytes, Chunks: {total_chunks}")
            network_logger.info(f"Receiving file {filename} from {source_id}")
        else:
            # Forward if needed
            forward_packet(packet, source_ip)
            
    except Exception as e:
        network_logger.error(f"Error handling file info packet: {e}")

def handle_file_chunk_packet(packet, source_ip):
    """Handle a file chunk packet"""
    try:
        source_id = packet.get("src", "unknown")
        dest_id = packet.get("dst", "unknown")
        file_id = packet.get("file_id", "")
        chunk_index = packet.get("chunk_index", 0)
        total_chunks = packet.get("total_chunks", 0)
        chunk_data = packet.get("data", "")
        
        # If we are the intended recipient
        if dest_id == MY_ID:
            # Decode base64 chunk data
            try:
                binary_data = base64.b64decode(chunk_data)
            except:
                binary_data = chunk_data.encode() if isinstance(chunk_data, str) else chunk_data
            
            # Get filename from packet or use file_id
            filename = packet.get("filename", f"received_{file_id}.bin")
            
            # Add chunk to file cache
            is_complete = file_cache.add_file_chunk(file_id, chunk_index, binary_data, total_chunks, filename)
            
            # If file is complete, save it
            if is_complete:
                output_path = file_cache.save_complete_file(file_id)
                if output_path:
                    log_file_transfer(filename, source_id, MY_ID, "COMPLETED", f"Saved to {output_path}")
        else:
            # Forward if needed
            forward_packet(packet, source_ip)
            
    except Exception as e:
        network_logger.error(f"Error handling file chunk packet: {e}")

# Optional: Implement a thread that periodically cleans up old cached messages and files
def start_cleanup_thread():
    """Start a thread to periodically clean up old cached items"""
    def cleanup_task():
        import time
        while True:
            try:
                # Clean up old messages (older than 1 hour)
                msg_count = message_cache.remove_old_messages(3600)
                if msg_count > 0:
                    network_logger.info(f"Removed {msg_count} old cached messages")
                
                # Clean up old file transfers (older than 3 hours)
                file_count = file_cache.remove_old_files(10800)
                if file_count > 0:
                    network_logger.info(f"Removed {file_count} old cached files")
            except Exception as e:
                network_logger.error(f"Error in cleanup thread: {e}")
            
            # Sleep for 15 minutes
            time.sleep(900)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

# Start cleanup thread
start_cleanup_thread()

