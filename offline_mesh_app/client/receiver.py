import socket
import threading
import json
import uuid
import time
import os
import base64
from config import PORT, MY_ID, MY_IP, DOWNLOAD_DIR
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
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            
            # Get clean filename (avoid path traversal)
            safe_filename = os.path.basename(file_info["filename"])
            save_path = os.path.join(DOWNLOAD_DIR, safe_filename)
            
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
        client_socket.settimeout(15)  # Increased timeout for larger messages
        
        # Buffer to collect data
        data_buffer = b""
        
        # First try to parse as a JSON packet
        try:
            # Receive data
            start_time = time.time()
            while True:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        # Connection closed normally
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
                        
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Could be incomplete data or binary file, continue receiving
                        # Check if buffer is very large, might be a binary file
                        if len(data_buffer) > 10240:  # 10KB
                            # This is likely a binary file transfer
                            network_logger.info(f"Large binary data detected from {client_address[0]}, treating as file transfer")
                            handle_binary_file(data_buffer, client_socket, client_address)
                            return
                        
                        # If we've been receiving for too long without valid data, assume binary file
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 5 and len(data_buffer) > 1024:  # More than 5 seconds and some data
                            network_logger.info(f"Long receive with {len(data_buffer)} bytes from {client_address[0]}, treating as file transfer")
                            handle_binary_file(data_buffer, client_socket, client_address)
                            return
                except socket.timeout:
                    # If we timed out while waiting for more data
                    if data_buffer:
                        network_logger.info(f"Timeout with {len(data_buffer)} bytes from {client_address[0]}, treating as file transfer")
                        handle_binary_file(data_buffer, client_socket, client_address)
                        return
                    else:
                        network_logger.warning(f"Connection from {client_address} timed out with no data")
                        break
                        
        except Exception as e:
            # If we encounter an error during receive, but have data, it might be a binary file
            if data_buffer:
                network_logger.info(f"Error during receive, but have {len(data_buffer)} bytes from {client_address[0]}, treating as file transfer")
                handle_binary_file(data_buffer, client_socket, client_address)
                return
            else:
                network_logger.error(f"Error handling connection from {client_address}: {e}")
                
    except Exception as e:
        network_logger.error(f"Error handling connection from {client_address}: {e}")
        
    finally:
        try:
            client_socket.close()
        except:
            pass


def handle_binary_file(initial_data, client_socket, client_address):
    """Handle binary file data"""
    try:
        # Check if we have any pending file info packets waiting for binary data
        pending_files = []
        for file_id, file_data in file_cache.items():
            # Check if this is a file from this source
            if file_data.get("src_id") == client_address[0]:
                # Check if we have the file info but no chunks yet
                if file_data.get("chunks") and len(file_data["chunks"]) == 0:
                    pending_files.append(file_id)
        
        # Create a temporary file to store the binary data
        import tempfile
        import os
        
        # Create directory if it doesn't exist
        temp_dir = os.path.join(DOWNLOAD_DIR, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create a temporary file
        temp_path = os.path.join(temp_dir, f"binary_{client_address[0]}_{int(time.time())}.dat")
        
        # Write the initial data first
        total_bytes = len(initial_data)
        with open(temp_path, "wb") as f:
            f.write(initial_data)
            
            # Continue receiving data
            try:
                while True:
                    client_socket.settimeout(5)
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_bytes += len(chunk)
            except socket.timeout:
                # Just stop reading if we timeout
                pass
        
        network_logger.info(f"Received binary file from {client_address[0]}: {total_bytes} bytes")
        
        # Now check if we need to do something with this file
        if pending_files:
            # Use the first pending file
            file_id = pending_files[0]
            file_info = file_cache[file_id]
            
            # Move the file to the downloads directory
            import shutil
            filename = file_info.get("filename", f"received_{file_id}.bin")
            safe_filename = os.path.basename(filename)
            
            # Add timestamp to avoid overwrites
            name_parts = os.path.splitext(safe_filename)
            new_filename = f"{name_parts[0]}_{int(time.time())}{name_parts[1]}"
            
            # Ensure download directory exists
            if not os.path.exists(DOWNLOAD_DIR):
                os.makedirs(DOWNLOAD_DIR)
                
            dest_path = os.path.join(DOWNLOAD_DIR, new_filename)
            shutil.move(temp_path, dest_path)
            
            # Log the successful transfer
            log_file_transfer(filename, file_info.get("src_id", "unknown"), MY_ID, "COMPLETED", 
                             f"Saved to {dest_path}")
            
            # Remove from cache
            del file_cache[file_id]
        else:
            # No pending file info, just save with a generic name
            import shutil
            dest_path = os.path.join(DOWNLOAD_DIR, f"received_binary_{int(time.time())}.dat")
            shutil.move(temp_path, dest_path)
            
            network_logger.info(f"Saved binary file from {client_address[0]} to {dest_path}")
            
    except Exception as e:
        network_logger.error(f"Error handling binary file: {e}")
    
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