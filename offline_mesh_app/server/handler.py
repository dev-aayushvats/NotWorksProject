import json
import os
import base64
import threading
import time
import socket
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
        # Make sure we have a valid connection
        if not conn:
            network_logger.error(f"Invalid connection from {addr}")
            return
            
        # Create a unique filename based on source and timestamp
        import tempfile
        from datetime import datetime
        
        # Create a temporary file
        temp_dir = os.path.join(DOWNLOAD_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate a unique filename
        temp_filename = f"incoming_{addr[0]}_{int(time.time())}.dat"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Track data received
        total_received = 0
        
        # Receive the file in chunks
        network_logger.info(f"Starting to receive file data from {addr[0]}")
        conn.settimeout(30)  # Set a longer timeout for file transfers
        
        with open(temp_path, "wb") as f:
            while True:
                try:
                    chunk = conn.recv(8192)  # Use larger chunks for efficiency
                    if not chunk:
                        network_logger.debug(f"End of data from {addr[0]}")
                        break
                    f.write(chunk)
                    total_received += len(chunk)
                    # Log progress for large files
                    if total_received % (1024 * 1024) == 0:  # Log every 1MB
                        network_logger.debug(f"Received {total_received // (1024*1024)}MB from {addr[0]}")
                except socket.timeout:
                    network_logger.warning(f"Socket timeout receiving data from {addr[0]}")
                    break
                except Exception as e:
                    network_logger.error(f"Error receiving file chunk from {addr[0]}: {e}")
                    break
        
        # Check if we received any data
        if total_received == 0:
            network_logger.warning(f"Received empty file from {addr[0]}")
            os.remove(temp_path)
            return
            
        network_logger.info(f"File received from {addr[0]}: {total_received} bytes")
        
        # Now process the file - in a real implementation, you would need to
        # determine which file_id this belongs to and add it to the correct file cache
        # For now, we'll just move it to the downloads directory
        
        # Move the file to the downloads directory
        import shutil
        dest_path = os.path.join(DOWNLOAD_DIR, f"received_file_{int(time.time())}.dat")
        shutil.move(temp_path, dest_path)
        
        network_logger.info(f"File saved to {dest_path}")
    except Exception as e:
        network_logger.error(f"Error handling file transfer from {addr}: {e}")
        
    finally:
        # Make sure the connection is properly closed
        if conn:
            try:
                conn.close()
            except:
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
            # Initialize the file in the cache
            if not file_cache.has_file(file_id):
                file_cache.initialize_file(file_id, filename, total_chunks)
                
            log_file_transfer(filename, source_id, MY_ID, "STARTED", 
                             f"Size: {filesize} bytes, Chunks: {total_chunks}")
            network_logger.info(f"Receiving file {filename} ({filesize} bytes, {total_chunks} chunks) from {source_id}")
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
        
        # Skip processing if we're missing critical information
        if not file_id or chunk_data == "":
            network_logger.warning(f"Invalid file chunk packet from {source_id}: missing file_id or data")
            return
        
        # If we are the intended recipient
        if dest_id == MY_ID:
            # Log receipt of chunks at intervals to avoid log spam
            if chunk_index % 5 == 0 or chunk_index == total_chunks - 1:
                network_logger.info(f"Received chunk {chunk_index+1}/{total_chunks} for file {file_id} from {source_id}")
                
            # Decode base64 chunk data
            try:
                binary_data = base64.b64decode(chunk_data)
            except Exception as e:
                network_logger.error(f"Error decoding chunk {chunk_index} from {source_id}: {e}")
                # Try using data as-is if decoding fails
                binary_data = chunk_data.encode() if isinstance(chunk_data, str) else chunk_data
            
            # Get filename from packet or use file_id
            filename = packet.get("filename", f"received_{file_id}.bin")
            
            # Add chunk to file cache
            is_complete = file_cache.add_file_chunk(file_id, chunk_index, binary_data, total_chunks, filename)
            
            # If file is complete, save it
            if is_complete:
                network_logger.info(f"All chunks received for file {filename} from {source_id}")
                output_path = file_cache.save_complete_file(file_id)
                if output_path:
                    log_file_transfer(filename, source_id, MY_ID, "COMPLETED", f"Saved to {output_path}")
                else:
                    network_logger.error(f"Failed to save complete file {filename} from {source_id}")
            
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

