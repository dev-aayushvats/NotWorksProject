import socket
from config import PORT
import os
import json
import time
import uuid
import base64
import threading
from tqdm import tqdm
from config import CHUNK_SIZE, MY_ID, MY_IP, MAX_TTL
from routing.router import router
from routing.cache import message_cache, file_cache
from utils.logger import log_message, log_file_transfer, network_logger
from utils.encryption import encrypt_data


def chunk_file(file_path, chunk_size=1024):
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk

def send_file_to_peer(ip, file_path):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, PORT))

        for chunk in chunk_file(file_path):
            s.sendall(chunk)
        
        s.close()
        print(f"[INFO] File sent to {ip}")
    except Exception as e:
        print(f"[ERROR] Could not send file to {ip}: {e}")


def send_to_peer(ip, data, retry=1):
    """Send data to a specific peer"""
    for attempt in range(retry + 1):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, PORT))
            
            # Convert data to bytes if it's not already
            if isinstance(data, str):
                data = data.encode()
                
            s.sendall(data)
            s.close()
            return True
        except Exception as e:
            if attempt < retry:
                time.sleep(1)  # Wait before retry
            else:
                network_logger.error(f"Failed to send to {ip}: {e}")
                return False

def send_message(destination_id, content, message_type="text"):
    """Send a message to a specific node"""
    # Generate a unique message ID
    message_id = str(uuid.uuid4())
    
    # Create message packet
    packet = {
        "type": "message",
        "id": message_id,
        "src": MY_ID,
        "src_ip": MY_IP,
        "dst": destination_id,
        "content": content,
        "message_type": message_type,
        "ttl": MAX_TTL,
        "timestamp": time.time()
    }
    
    # Convert to JSON
    json_data = json.dumps(packet)
    
    # Encrypt for transmission
    encrypted_data = encrypt_data(json_data)
    
    # Log the outgoing message
    log_message(MY_ID, destination_id, content, message_type)
    
    # Get next hop(s) from router
    next_hop = router.get_next_hop(destination_id)
    
    # If no specific route, send to all neighbors
    if isinstance(next_hop, list):
        network_logger.info(f"No direct route to {destination_id}, flooding to {len(next_hop)} neighbors")
        success = False
        for ip in next_hop:
            if send_to_peer(ip, encrypted_data):
                success = True
        return success
    
    # If we have a specific next hop, send there
    elif next_hop:
        network_logger.info(f"Sending message to {destination_id} via {next_hop}")
        return send_to_peer(next_hop, encrypted_data)
    
    # If destination is ourselves or no route available
    else:
        network_logger.warning(f"No route to {destination_id}")
        return False

def broadcast_message(content, message_type="text"):
    """Broadcast a message to all known peers"""
    # Generate a unique message ID
    message_id = str(uuid.uuid4())
    
    # Create message packet
    packet = {
        "type": "broadcast",
        "id": message_id,
        "src": MY_ID,
        "src_ip": MY_IP,
        "content": content,
        "message_type": message_type,
        "ttl": MAX_TTL,
        "timestamp": time.time()
    }
    
    # Convert to JSON
    json_data = json.dumps(packet)
    
    # Encrypt for transmission
    encrypted_data = encrypt_data(json_data)
    
    # Log the outgoing broadcast
    log_message(MY_ID, "ALL", content, message_type)
    
    # Send to all neighbors
    success_count = 0
    neighbors = list(router.neighbors)
    
    network_logger.info(f"Broadcasting message to {len(neighbors)} neighbors")
    
    for ip in neighbors:
        if send_to_peer(ip, encrypted_data):
            success_count += 1
    
    return success_count > 0

def send_file(destination_id, file_path):
    """Send a file to a destination node by chunking it"""
    if not os.path.exists(file_path):
        network_logger.error(f"File not found: {file_path}")
        return False
    
    try:
        # Generate a unique file ID
        file_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        # Calculate number of chunks
        num_chunks = (filesize + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        log_file_transfer(filename, MY_ID, destination_id, "STARTED", 
                         f"Size: {filesize} bytes, Chunks: {num_chunks}")
        
        # Show progress bar
        with tqdm(total=num_chunks, desc=f"Sending {filename}", unit="chunk") as pbar:
            # Send file info first
            info_packet = {
                "type": "file_info",
                "id": file_id,
                "src": MY_ID,
                "dst": destination_id,
                "filename": filename,
                "filesize": filesize,
                "total_chunks": num_chunks,
                "ttl": MAX_TTL,
                "timestamp": time.time()
            }
            
            # Convert to JSON and encrypt
            json_data = json.dumps(info_packet)
            encrypted_data = encrypt_data(json_data)
            
            # Get next hop for destination
            next_hop = router.get_next_hop(destination_id)
            
            # If no route, abort
            if not next_hop or (isinstance(next_hop, list) and not next_hop):
                network_logger.error(f"No route to {destination_id} for file transfer")
                return False
            
            # If multiple routes, choose first one for file transfer
            if isinstance(next_hop, list):
                next_hop = next_hop[0] if next_hop else None
            
            # Send file info
            if not send_to_peer(next_hop, encrypted_data):
                network_logger.error(f"Failed to send file info to {destination_id}")
                return False
            
            # Send chunks
            success = True
            with open(file_path, "rb") as f:
                for chunk_index in range(num_chunks):
                    chunk_data = f.read(CHUNK_SIZE)
                    
                    # Base64 encode binary data for JSON
                    encoded_chunk = base64.b64encode(chunk_data).decode('utf-8')
                    
                    # Create chunk packet
                    chunk_packet = {
                        "type": "file_chunk",
                        "file_id": file_id,
                        "src": MY_ID,
                        "dst": destination_id,
                        "chunk_index": chunk_index,
                        "total_chunks": num_chunks,
                        "data": encoded_chunk,
                        "ttl": MAX_TTL,
                        "timestamp": time.time()
                    }
                    
                    # Convert to JSON and encrypt
                    json_data = json.dumps(chunk_packet)
                    encrypted_data = encrypt_data(json_data)
                    
                    # Send chunk with retry
                    if not send_to_peer(next_hop, encrypted_data, retry=2):
                        network_logger.error(f"Failed to send chunk {chunk_index} to {destination_id}")
                        success = False
                        break
                    
                    # Update progress
                    pbar.update(1)
                    
                    # Small delay to avoid overwhelming the network
                    time.sleep(0.01)
            
            if success:
                log_file_transfer(filename, MY_ID, destination_id, "COMPLETED", f"Size: {filesize} bytes")
            else:
                log_file_transfer(filename, MY_ID, destination_id, "FAILED", "Chunk transfer failed")
            
            return success
    except Exception as e:
        network_logger.error(f"Error sending file: {e}")
        return False

def forward_packet(packet, received_from):
    """Forward a packet based on routing information"""
    try:
        # Extract packet data
        packet_type = packet.get("type", "")
        source_id = packet.get("src", "")
        ttl = packet.get("ttl", 0) - 1  # Decrement TTL
        
        # Skip forwarding if TTL expired or it's from us
        if ttl <= 0 or source_id == MY_ID:
            return False
        
        # Update TTL in packet
        packet["ttl"] = ttl
        
        # Handle different packet types
        if packet_type == "message":
            dest_id = packet.get("dst", "")
            
            # If we're the destination, don't forward
            if dest_id == MY_ID:
                return False
            
            # Check if we've seen this message before
            message_id = packet.get("id", "")
            if not router.should_forward_message(message_id, ttl):
                return False
            
            # Get next hop
            next_hop = router.get_next_hop(dest_id)
            
            # Don't send back to where it came from
            if isinstance(next_hop, list):
                if received_from in next_hop:
                    next_hop.remove(received_from)
            elif next_hop == received_from:
                # No alternative route
                return False
            
            # Forward packet
            if next_hop:
                json_data = json.dumps(packet)
                encrypted_data = encrypt_data(json_data)
                
                if isinstance(next_hop, list):
                    for ip in next_hop:
                        send_to_peer(ip, encrypted_data)
                    return True
                else:
                    return send_to_peer(next_hop, encrypted_data)
        
        elif packet_type == "broadcast":
            # Check if we've seen this broadcast before
            message_id = packet.get("id", "")
            if not router.should_forward_message(message_id, ttl):
                return False
            
            # Forward to all neighbors except the one we received from
            neighbors = list(router.neighbors)
            if received_from in neighbors:
                neighbors.remove(received_from)
            
            if neighbors:
                json_data = json.dumps(packet)
                encrypted_data = encrypt_data(json_data)
                
                for ip in neighbors:
                    send_to_peer(ip, encrypted_data)
                return True
        
        elif packet_type in ["file_info", "file_chunk"]:
            dest_id = packet.get("dst", "")
            
            # If we're the destination, don't forward
            if dest_id == MY_ID:
                return False
            
            # Get next hop
            next_hop = router.get_next_hop(dest_id)
            
            # Don't send back to where it came from
            if isinstance(next_hop, list):
                if received_from in next_hop:
                    next_hop.remove(received_from)
                if next_hop:
                    next_hop = next_hop[0]  # Pick first for file transfers
                else:
                    return False
            elif next_hop == received_from:
                # No alternative route
                return False
            
            # Forward packet
            if next_hop:
                json_data = json.dumps(packet)
                encrypted_data = encrypt_data(json_data)
                return send_to_peer(next_hop, encrypted_data)
        
        return False
        
    except Exception as e:
        network_logger.error(f"Error forwarding packet: {e}")
        return False
