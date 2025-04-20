import json
import os
import base64
import threading
from config import MY_ID, DOWNLOAD_DIR
from routing.router import router
from routing.cache import message_cache, file_cache
from utils.logger import log_message, log_routing, log_file_transfer, network_logger
from utils.encryption import decrypt_data
from client.sender import forward_packet
from client.gateway_discovery import handle_gateway_update

def handle_file_transfer(conn, addr):
    with open(f"received_file_{addr[1]}.dat", "wb") as f:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            f.write(data)
    print(f"[INFO] File received from {addr}")

def handle_packet(data, addr, conn=None):
    """Handle an incoming packet"""
    try:
        # Get the source IP
        source_ip = addr[0]
        
        # Try to decrypt the data
        try:
            decrypted_data = decrypt_data(data)
            if isinstance(decrypted_data, bytes):
                data = decrypted_data
            else:
                data = decrypted_data.encode()
        except Exception as e:
            network_logger.warning(f"Failed to decrypt packet from {source_ip}: {e}")
        
        # Parse JSON packet
        packet = json.loads(data.decode())
        
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
        elif packet_type == "file":
            handle_file_transfer(conn, addr)
        elif packet_type == "gateway_update":
            handle_gateway_update(packet, source_ip)
        else:
            network_logger.warning(f"Unknown packet type '{packet_type}' from {source_ip}")
            
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

