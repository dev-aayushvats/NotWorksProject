import socket
import threading
import json
import uuid
import time
import os
import base64
from config import PORT, MY_ID, MY_IP
from routing.router import router
from routing.cache import message_cache, file_cache
from client.sender import forward_packet
from utils.logger import log_message, log_file_transfer, network_logger
from utils.encryption import decrypt_data
from utils.parser import parse_message


def handle_file_info(packet):
    """Handle file info packet"""
    src_id = packet.get("src", "")
    file_id = packet.get("id", "")
    filename = packet.get("filename", "")
    filesize = packet.get("filesize", 0)
    total_chunks = packet.get("total_chunks", 0)
    
    if src_id == MY_ID:
        return
    
    # Check if this is being forwarded
    dst_id = packet.get("dst", "")
    if dst_id != MY_ID:
        # Forward to next hop
        src_ip = packet.get("src_ip", "")
        forward_packet(packet, src_ip)
        return
    
    # Initialize file cache
    file_cache[file_id] = {
        "filename": filename,
        "filesize": filesize,
        "total_chunks": total_chunks,
        "received_chunks": 0,
        "chunks": {},
        "src_id": src_id,
        "timestamp": time.time()
    }
    
    log_file_transfer(filename, src_id, MY_ID, "INCOMING", 
                      f"Size: {filesize} bytes, Chunks: {total_chunks}")
    
    network_logger.info(f"Receiving file '{filename}' from {src_id}, expecting {total_chunks} chunks")


def handle_file_chunk(packet):
    """Handle file chunk packet"""
    file_id = packet.get("file_id", "")
    src_id = packet.get("src", "")
    chunk_index = packet.get("chunk_index", 0)
    total_chunks = packet.get("total_chunks", 0)
    encoded_data = packet.get("data", "")
    
    if src_id == MY_ID:
        return
    
    # Check if this is being forwarded
    dst_id = packet.get("dst", "")
    if dst_id != MY_ID:
        # Forward to next hop
        src_ip = packet.get("src_ip", "") if "src_ip" in packet else ""
        forward_packet(packet, src_ip)
        return
    
    # Check if we have this file in our cache
    if file_id not in file_cache:
        network_logger.warning(f"Received chunk for unknown file ID: {file_id}")
        return
    
    # Decode the chunk
    try:
        chunk_data = base64.b64decode(encoded_data)
    except Exception as e:
        network_logger.error(f"Error decoding chunk: {e}")
        return
    
    # Store the chunk
    file_info = file_cache[file_id]
    file_info["chunks"][chunk_index] = chunk_data
    file_info["received_chunks"] += 1
    
    # If progress reporting is needed
    if file_info["received_chunks"] % 10 == 0:
        progress = (file_info["received_chunks"] / file_info["total_chunks"]) * 100
        network_logger.info(f"File transfer progress: {progress:.1f}% ({file_info['received_chunks']}/{file_info['total_chunks']} chunks)")
    
    # Check if all chunks received
    if file_info["received_chunks"] == file_info["total_chunks"]:
        # Save the file
        try:
            # Create directory if needed
            os.makedirs("downloads", exist_ok=True)
            
            # Get clean filename (avoid path traversal)
            safe_filename = os.path.basename(file_info["filename"])
            save_path = os.path.join("downloads", safe_filename)
            
            # Write all chunks in order
            with open(save_path, "wb") as f:
                for i in range(file_info["total_chunks"]):
                    if i in file_info["chunks"]:
                        f.write(file_info["chunks"][i])
            
            network_logger.info(f"File saved to {save_path}")
            log_file_transfer(safe_filename, src_id, MY_ID, "COMPLETED", 
                             f"Saved to: {save_path}")
            
            # Clean up the cache
            del file_cache[file_id]
            
        except Exception as e:
            network_logger.error(f"Error saving file: {e}")
            log_file_transfer(file_info["filename"], src_id, MY_ID, "FAILED", 
                             f"Error: {e}")


def handle_message(packet, sender_ip):
    """Handle incoming message packet"""
    message_type = packet.get("type", "")
    src_id = packet.get("src", "")
    
    # Skip processing if it's from ourselves
    if src_id == MY_ID:
        return
    
    # Store link state info - node is active
    router.update_link_state(src_id, sender_ip)
    
    # Check for hops information
    if packet.get("multi_hop", False) and "hops" in packet:
        hops = packet.get("hops", [])
        if hops:
            # Update routing information about intermediary nodes
            router.update_bridge_information(src_id, hops)
            network_logger.debug(f"Message from {src_id} traveled through {len(hops)} hops: {hops}")
    
    # Process message based on type
    if message_type == "message":
        dst_id = packet.get("dst", "")
        content = packet.get("content", "")
        msg_type = packet.get("message_type", "text")
        message_id = packet.get("id", "")
        
        # Check if message is for us
        if dst_id == MY_ID:
            # Don't process duplicates
            if message_cache.is_duplicate(message_id):
                return
            
            # Log and parse the message
            log_message(src_id, MY_ID, content, msg_type)
            parse_message(src_id, content, msg_type)
            
            # Cache message to avoid duplicates
            message_cache.add_message(message_id)
            
        else:
            # Forward to next hop if needed
            forward_packet(packet, sender_ip)
    
    elif message_type == "broadcast":
        content = packet.get("content", "")
        msg_type = packet.get("message_type", "text")
        message_id = packet.get("id", "")
        
        # Don't process duplicates
        if message_cache.is_duplicate(message_id):
            return
        
        # Log and parse the message
        log_message(src_id, "ALL", content, msg_type)
        parse_message(src_id, content, msg_type)
        
        # Cache message to avoid duplicates
        message_cache.add_message(message_id)
        
        # Forward broadcast
        forward_packet(packet, sender_ip)
    
    elif message_type == "file_info":
        handle_file_info(packet)
    
    elif message_type == "file_chunk":
        handle_file_chunk(packet)


def handle_client(client_socket, client_address):
    """Handle incoming client connection"""
    try:
        # Set a timeout to prevent hanging
        client_socket.settimeout(10)
        
        # Buffer to collect data
        data_buffer = b""
        
        # Receive data
        while True:
            data = client_socket.recv(4096)
            if not data:
                break
            
            data_buffer += data
            
            # Try to extract complete JSON messages
            try:
                # Decrypt the data
                decrypted_data = decrypt_data(data_buffer)
                packet = json.loads(decrypted_data)
                
                # Record the sender IP for routing
                sender_ip = client_address[0]
                
                # Handle the message
                handle_message(packet, sender_ip)
                
                # Clear buffer after successful processing
                data_buffer = b""
                
            except Exception as e:
                # Could be incomplete data, continue receiving
                pass
                
    except socket.timeout:
        network_logger.warning(f"Connection from {client_address} timed out")
        
    except json.JSONDecodeError:
        network_logger.error(f"Invalid JSON from {client_address}")
        
    except Exception as e:
        network_logger.error(f"Error handling connection from {client_address}: {e}")
        
    finally:
        client_socket.close()


def start_server():
    """Start the server to listen for incoming connections"""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to all interfaces
        server.bind(('0.0.0.0', PORT))
        server.listen(10)
        
        network_logger.info(f"Server started on 0.0.0.0:{PORT}")
        
        while True:
            client_socket, client_address = server.accept()
            network_logger.debug(f"Connection from {client_address}")
            
            # Handle client in a new thread
            client_thread = threading.Thread(
                target=handle_client, 
                args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except Exception as e:
        network_logger.error(f"Server error: {e}")
        
    finally:
        server.close()
        network_logger.info("Server stopped") 