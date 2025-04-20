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


def send_to_peer(ip, data, retry=3):
    """Send data to a specific peer with enhanced retry logic"""
    for attempt in range(retry + 1):
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, PORT))
            
            # Convert data to bytes if it's not already
            if isinstance(data, str):
                data = data.encode()
                
            s.sendall(data)
            return True
        except ConnectionRefusedError:
            # This means the peer is not listening - critical failure
            if attempt < retry:
                backoff_time = (attempt + 1) * 1.5
                network_logger.warning(f"Connection refused by {ip}, retrying in {backoff_time}s (attempt {attempt+1}/{retry})")
                time.sleep(backoff_time)  # Increasing backoff
            else:
                network_logger.error(f"Connection refused by {ip} after {retry} retries")
                return False
        except (socket.timeout, TimeoutError):
            # Timeout - peer might be busy
            if attempt < retry:
                backoff_time = (attempt + 1) * 2.0  # Longer backoff for timeouts
                network_logger.warning(f"Connection to {ip} timed out, retrying in {backoff_time}s (attempt {attempt+1}/{retry})")
                time.sleep(backoff_time)
            else:
                network_logger.error(f"Connection to {ip} timed out after {retry} retries")
                return False
        except Exception as e:
            # Other errors
            if attempt < retry:
                backoff_time = (attempt + 1) * 1.5
                network_logger.warning(f"Failed to send to {ip}, retrying in {backoff_time}s (attempt {attempt+1}/{retry}): {e}")
                time.sleep(backoff_time)  # Increasing backoff
            else:
                network_logger.error(f"Failed to send to {ip} after {retry} retries: {e}")
                return False
        finally:
            # Always ensure socket is closed properly
            if s:
                try:
                    s.close()
                except:
                    pass

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
        "timestamp": time.time(),
        "hops": [],  # Track the path the message takes
        "multi_hop": True  # Flag to indicate this is for a multi-hop network
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
        if not next_hop:
            network_logger.warning(f"No neighbors available to send message to {destination_id}")
            return False
            
        network_logger.info(f"No direct route to {destination_id}, flooding to {len(next_hop)} neighbors")
        success = False
        
        # Try bridge nodes first if available
        bridge_attempts = []
        regular_attempts = []
        
        # Separate bridge nodes from regular nodes
        for ip in next_hop:
            for node_id, route in router.get_all_routes().items():
                if route["next_hop"] == ip and route.get("via_bridge", False):
                    bridge_attempts.append(ip)
                    break
            else:
                regular_attempts.append(ip)
        
        # Log the strategy
        if bridge_attempts:
            network_logger.info(f"Trying {len(bridge_attempts)} bridge nodes first: {bridge_attempts}")
        
        # First try bridge nodes
        for ip in bridge_attempts:
            if send_to_peer(ip, encrypted_data, retry=2):
                network_logger.info(f"Successfully sent via bridge node {ip}")
                success = True
        
        # If bridge nodes failed or don't exist, try all regular nodes
        if not success:
            for ip in regular_attempts:
                if send_to_peer(ip, encrypted_data):
                    success = True
        
        return success
    
    # If we have a specific next hop, send there
    elif next_hop:
        network_logger.info(f"Sending message to {destination_id} via {next_hop}")
        return send_to_peer(next_hop, encrypted_data, retry=2)
    
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
        "timestamp": time.time(),
        "hops": [],  # Track the path the message takes
        "multi_hop": True  # Flag to indicate this is for a multi-hop network
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
        if send_to_peer(ip, encrypted_data, retry=1):
            success_count += 1
    
    return success_count > 0

def send_file(destination_id, file_path):
    """Send a file to a destination node by chunking it"""
    if not os.path.exists(file_path):
        network_logger.error(f"File not found: {file_path}")
        return False
    
    try:
        # Get file info
        file_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        # Calculate number of chunks - more reliably
        num_chunks = (filesize + CHUNK_SIZE - 1) // CHUNK_SIZE if filesize > 0 else 1
        
        network_logger.info(f"Sending file {filename} to {destination_id}. " + 
                         f"Size: {filesize} bytes, Chunks: {num_chunks}")
        
        # Get next hop for destination
        next_hop = router.get_next_hop(destination_id)
        
        # If no route, abort
        if not next_hop or (isinstance(next_hop, list) and not next_hop):
            network_logger.error(f"No route to {destination_id} for file transfer")
            return False
        
        # If multiple routes, choose first one for file transfer
        # Prioritize bridge nodes for multi-hop networks
        if isinstance(next_hop, list):
            # Look for bridge nodes
            bridge_ip = None
            for ip in next_hop:
                for node_id, route in router.get_all_routes().items():
                    if route["next_hop"] == ip and route.get("via_bridge", False):
                        bridge_ip = ip
                        break
                if bridge_ip:
                    break
            
            if bridge_ip:
                network_logger.info(f"Using bridge node {bridge_ip} for file transfer")
                next_hop = bridge_ip
            else:
                next_hop = next_hop[0] if next_hop else None
        
        # First option: Try sending the file directly over a socket (this is faster for one-hop transfers)
        try:
            # Check if this is a direct connection (one hop)
            is_direct_connection = False
            # Check if destination is a direct neighbor
            if destination_id in router.routing_table:
                route = router.routing_table[destination_id]
                if route["ttl"] == 1:  # TTL of 1 means direct neighbor
                    is_direct_connection = True
            
            if is_direct_connection:
                network_logger.info(f"Attempting direct file transfer to {destination_id} at {next_hop}")
                
                # Send file info first with normal method (to prepare receiver)
                info_packet = {
                    "type": "file_info",
                    "id": file_id,
                    "src": MY_ID,
                    "dst": destination_id,
                    "filename": filename,
                    "filesize": filesize,
                    "total_chunks": num_chunks,
                    "ttl": MAX_TTL,
                    "timestamp": time.time(),
                    "multi_hop": True
                }
                
                # Convert to JSON and encrypt
                json_data = json.dumps(info_packet)
                encrypted_data = encrypt_data(json_data)
                
                # Send file info to prepare receiver
                if not send_to_peer(next_hop, encrypted_data, retry=2):
                    network_logger.error(f"Failed to send file info to {destination_id}")
                    # Fall back to chunked method later
                else:
                    # Wait a brief moment for the receiver to process the file info
                    time.sleep(0.5)
                    
                    # Now send the actual file directly with binary transfer
                    # This is much faster for large files
                    s = None
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(15)  # Longer timeout for file transfer
                        s.connect((next_hop, PORT))
                        
                        # Show progress bar
                        bytes_sent = 0
                        with open(file_path, "rb") as f, tqdm(total=filesize, desc=f"Sending {filename}", unit="B", unit_scale=True) as pbar:
                            buffer_size = min(CHUNK_SIZE, 8192)  # Use smaller buffer to improve progress updates
                            while True:
                                chunk = f.read(buffer_size)
                                if not chunk:
                                    break
                                s.sendall(chunk)
                                bytes_sent += len(chunk)
                                pbar.update(len(chunk))
                                
                                # For large files, log progress occasionally
                                if bytes_sent % (1024 * 1024) == 0:  # Log every 1MB
                                    network_logger.debug(f"Sent {bytes_sent // (1024*1024)}MB of {filesize // (1024*1024)}MB")
                        
                        # Wait for data to finish sending
                        time.sleep(0.5)
                        network_logger.info(f"Direct file transfer completed to {destination_id}, sent {bytes_sent} bytes")
                        log_file_transfer(filename, MY_ID, destination_id, "COMPLETED", f"Size: {filesize} bytes")
                        return True
                    except Exception as e:
                        network_logger.error(f"Error in direct file transfer: {e}")
                        # Continue to chunked method
                    finally:
                        # Ensure socket is closed even if an exception occurs
                        if s is not None:
                            try:
                                s.close()
                            except:
                                pass
        except Exception as e:
            network_logger.warning(f"Direct file transfer failed, falling back to chunked method: {e}")
            # Fall back to the chunked method below
        
        # If we reach here, direct transfer failed or was not attempted. Use chunked method
        network_logger.info(f"Using chunked file transfer for {filename} to {destination_id}")
        
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
                "timestamp": time.time(),
                "multi_hop": True  # Flag to indicate this is for a multi-hop network
            }
            
            # Convert to JSON and encrypt
            json_data = json.dumps(info_packet)
            encrypted_data = encrypt_data(json_data)
            
            # Send file info
            info_sent = False
            for attempt in range(3):  # Retry sending info packet up to 3 times
                if send_to_peer(next_hop, encrypted_data, retry=3):
                    info_sent = True
                    break
                time.sleep(1)  # Wait between retries
            
            if not info_sent:
                network_logger.error(f"Failed to send file info to {destination_id}")
                return False
            
            # Wait for receiver to process the file info
            time.sleep(1)
            
            # Send chunks with retries for individual chunks
            success = True
            chunks_sent = 0
            
            with open(file_path, "rb") as f:
                for chunk_index in range(num_chunks):
                    # Read chunk from file
                    chunk_data = f.read(CHUNK_SIZE)
                    
                    # Break if we reach end of file unexpectedly
                    if not chunk_data and chunk_index < num_chunks - 1:
                        network_logger.warning(f"Reached end of file earlier than expected at chunk {chunk_index}/{num_chunks}")
                        break
                    
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
                        "timestamp": time.time(),
                        "multi_hop": True  # Flag to indicate this is for a multi-hop network
                    }
                    
                    # Convert to JSON and encrypt
                    json_data = json.dumps(chunk_packet)
                    encrypted_data = encrypt_data(json_data)
                    
                    # Try to send the chunk with multiple retries
                    chunk_sent = False
                    max_retries = 5  # More retries for reliable delivery
                    
                    for retry in range(max_retries):
                        if send_to_peer(next_hop, encrypted_data, retry=2):
                            chunk_sent = True
                            chunks_sent += 1
                            break
                        
                        network_logger.warning(f"Retry {retry+1}/{max_retries} for chunk {chunk_index}")
                        time.sleep((retry + 1) * 0.5)  # Increasing backoff between retries
                    
                    if not chunk_sent:
                        network_logger.error(f"Failed to send chunk {chunk_index} to {destination_id} after {max_retries} retries")
                        success = False
                        break
                    
                    # Update progress
                    pbar.update(1)
                    
                    # Log progress for large files
                    if chunk_index % 10 == 0 or chunk_index == num_chunks - 1:
                        network_logger.info(f"Sent chunk {chunk_index+1}/{num_chunks} to {destination_id}")
                    
                    # Small delay to avoid overwhelming the network
                    # The delay is proportional to the number of chunks to avoid excessive delays for small files
                    if num_chunks > 50:
                        time.sleep(0.1)  # Longer delay for large files
                    else:
                        time.sleep(0.05)  # Shorter delay for small files
            
            if success:
                log_file_transfer(filename, MY_ID, destination_id, "COMPLETED", 
                                f"Size: {filesize} bytes, Sent {chunks_sent}/{num_chunks} chunks")
                network_logger.info(f"Successfully sent all {chunks_sent} chunks of {filename} to {destination_id}")
            else:
                log_file_transfer(filename, MY_ID, destination_id, "FAILED", 
                                f"Chunk transfer failed: sent only {chunks_sent}/{num_chunks} chunks")
                network_logger.error(f"Failed to send complete file {filename} to {destination_id}")
            
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
        
        # Skip processing if it's from ourselves
        if source_id == MY_ID:
            return False
        
        # Get and validate TTL
        ttl = packet.get("ttl", 0)
        if ttl <= 0:
            network_logger.debug(f"Dropping packet with expired TTL: {ttl}")
            return False
            
        # Decrement TTL for forwarding
        ttl -= 1
        packet["ttl"] = ttl
        
        # If TTL is now 0, don't forward further
        if ttl <= 0:
            network_logger.debug(f"Not forwarding packet - TTL would expire")
            return False
        
        # Initialize hops list if not present
        if "hops" not in packet and packet.get("multi_hop", False):
            packet["hops"] = []
            
        # Add ourselves to the hop list if this is a multi-hop packet
        if packet.get("multi_hop", False) and "hops" in packet:
            if MY_ID not in packet["hops"]:
                packet["hops"].append(MY_ID)
        
        # Handle different packet types
        if packet_type == "message":
            dest_id = packet.get("dst", "")
            
            # If we're the destination, don't forward
            if dest_id == MY_ID:
                return False
            
            # Check if we've seen this message before to prevent loops
            message_id = packet.get("id", "")
            if not message_id:
                # Missing message ID, generate one to prevent loops
                message_id = str(uuid.uuid4())
                packet["id"] = message_id
                
            if not router.should_forward_message(message_id, ttl):
                network_logger.debug(f"Not forwarding message {message_id} - already seen")
                return False
            
            # Get next hop
            next_hop = router.get_next_hop(dest_id)
            if not next_hop:
                network_logger.warning(f"No route to {dest_id} for message forwarding")
                return False
            
            # Don't send back to where it came from
            if isinstance(next_hop, list):
                if received_from in next_hop:
                    next_hop.remove(received_from)
                if not next_hop:  # If removing received_from leaves an empty list
                    network_logger.debug(f"No alternative routes for {dest_id} other than source {received_from}")
                    return False
            elif next_hop == received_from:
                # Check for alternative routes via bridge nodes
                bridge_routes = []
                for bridge_id in router.bridge_nodes:
                    if bridge_id in router.routing_table:
                        bridge_route = router.routing_table[bridge_id]
                        if bridge_route["next_hop"] != received_from:
                            bridge_routes.append(bridge_route["next_hop"])
                
                if bridge_routes:
                    network_logger.info(f"Using alternative bridge route for {dest_id}: {bridge_routes}")
                    next_hop = bridge_routes
                else:
                    # No alternative route
                    network_logger.debug(f"No alternative routes to {dest_id} available")
                    return False
            
            # Forward packet
            network_logger.debug(f"Forwarding message {message_id} to {dest_id} via {next_hop}, TTL: {ttl}")
            
            # Convert to JSON and encrypt
            json_data = json.dumps(packet)
            encrypted_data = encrypt_data(json_data)
            
            if isinstance(next_hop, list):
                success = False
                for ip in next_hop:
                    if send_to_peer(ip, encrypted_data, retry=2):
                        success = True
                return success
            else:
                return send_to_peer(next_hop, encrypted_data, retry=2)
        
        elif packet_type == "broadcast":
            # Check if we've seen this broadcast before
            message_id = packet.get("id", "")
            if not message_id:
                # Missing message ID, generate one
                message_id = str(uuid.uuid4())
                packet["id"] = message_id
                
            if not router.should_forward_message(message_id, ttl):
                network_logger.debug(f"Not forwarding broadcast {message_id} - already seen")
                return False
            
            # Forward to all neighbors except the one we received from
            neighbors = list(router.neighbors)
            if received_from in neighbors:
                neighbors.remove(received_from)
            
            if not neighbors:
                network_logger.debug("No neighbors to forward broadcast to")
                return False
                
            network_logger.debug(f"Forwarding broadcast {message_id} to {len(neighbors)} neighbors, TTL: {ttl}")
            
            # Convert to JSON and encrypt
            json_data = json.dumps(packet)
            encrypted_data = encrypt_data(json_data)
            
            success = False
            for ip in neighbors:
                if send_to_peer(ip, encrypted_data):
                    success = True
            return success
        
        elif packet_type in ["file_info", "file_chunk"]:
            dest_id = packet.get("dst", "")
            
            # If we're the destination, don't forward
            if dest_id == MY_ID:
                return False
            
            # Get next hop
            next_hop = router.get_next_hop(dest_id)
            if not next_hop:
                network_logger.warning(f"No route to {dest_id} for file transfer forwarding")
                return False
            
            # Don't send back to where it came from
            if isinstance(next_hop, list):
                if received_from in next_hop:
                    next_hop.remove(received_from)
                if not next_hop:  # If removing received_from leaves an empty list
                    network_logger.debug(f"No alternative routes for file to {dest_id}")
                    return False
                
                # For file transfers, pick the best node (prioritize bridge nodes)
                bridge_ip = None
                for ip in next_hop:
                    for node_id, route in router.get_all_routes().items():
                        if route["next_hop"] == ip and route.get("via_bridge", False):
                            bridge_ip = ip
                            break
                    if bridge_ip:
                        break
                
                if bridge_ip:
                    next_hop = bridge_ip
                elif next_hop:
                    next_hop = next_hop[0]  # Pick first for file transfers
                else:
                    return False
            elif next_hop == received_from:
                # Check for alternative routes via bridge nodes
                bridge_ip = None
                for bridge_id in router.bridge_nodes:
                    if bridge_id in router.routing_table:
                        bridge_route = router.routing_table[bridge_id]
                        if bridge_route["next_hop"] != received_from:
                            bridge_ip = bridge_route["next_hop"]
                            break
                
                if bridge_ip:
                    next_hop = bridge_ip
                else:
                    # No alternative route
                    network_logger.debug(f"No alternative routes for file to {dest_id}")
                    return False
            
            # Forward packet with higher retry count for file transfers
            network_logger.debug(f"Forwarding {packet_type} to {dest_id} via {next_hop}, TTL: {ttl}")
            
            # Convert to JSON and encrypt
            json_data = json.dumps(packet)
            encrypted_data = encrypt_data(json_data)
            return send_to_peer(next_hop, encrypted_data, retry=3)
        
        # Unknown packet type
        network_logger.warning(f"Unknown packet type for forwarding: {packet_type}")
        return False
        
    except Exception as e:
        network_logger.error(f"Error forwarding packet: {e}")
        return False
