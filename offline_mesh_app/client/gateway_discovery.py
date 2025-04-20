import threading
import time
import json
import socket
from config import PORT, MY_ID, MY_IP, IS_HOTSPOT_HOST, GATEWAY_BROADCAST_INTERVAL
from routing.router import router
from utils.logger import network_logger
from utils.encryption import encrypt_data
from client.sender import send_to_peer

def share_peers_with_gateways():
    """Share our known peers with other gateway nodes"""
    if not IS_HOTSPOT_HOST:
        return
    
    while True:
        try:
            # Get our current peer list
            peer_list = list(router.neighbors)
            
            # Get all gateway nodes we know about
            gateways = []
            with router.lock:
                for node_id, route in router.routing_table.items():
                    if route.get("is_gateway", False) and time.time() - route["timestamp"] <= 60:
                        gateways.append(route["next_hop"])
            
            if gateways:
                network_logger.info(f"Sharing peer list with {len(gateways)} other gateway nodes")
                
                # Create gateway update packet
                gateway_packet = {
                    "type": "gateway_update",
                    "src": MY_ID,
                    "src_ip": MY_IP,
                    "is_gateway": True,
                    "peers": peer_list,
                    "timestamp": time.time()
                }
                
                # Convert to JSON and encrypt
                json_data = json.dumps(gateway_packet)
                encrypted_data = encrypt_data(json_data)
                
                # Share with other gateways
                for gateway_ip in gateways:
                    send_to_peer(gateway_ip, encrypted_data, retry=2)
            
            # Run this function periodically
            time.sleep(GATEWAY_BROADCAST_INTERVAL)
            
        except Exception as e:
            network_logger.error(f"Error in gateway peer sharing: {e}")
            time.sleep(GATEWAY_BROADCAST_INTERVAL)

def handle_gateway_update(packet, source_ip):
    """Handle gateway update packet containing peer information"""
    try:
        source_id = packet.get("src", "unknown")
        is_gateway = packet.get("is_gateway", False)
        peers = packet.get("peers", [])
        
        # Update routing table with gateway information
        router.update_link_state(
            source_id, 
            source_ip, 
            {"is_gateway": is_gateway},
            0,  # No sequence number for gateway updates
            2   # TTL of 2 for gateway updates
        )
        
        # Mark this node as a gateway in the routing table
        with router.lock:
            if source_id in router.routing_table:
                router.routing_table[source_id]["is_gateway"] = True
        
        network_logger.info(f"Received gateway update from {source_id} with {len(peers)} peers")
        
        # Add these peers to our routing table if we don't know them yet
        for peer_ip in peers:
            if peer_ip not in router.neighbors and peer_ip != MY_IP:
                network_logger.info(f"Adding peer {peer_ip} from gateway update")
                # Try to connect to the peer
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((peer_ip, PORT))
                    s.close()
                    router.neighbors.add(peer_ip)
                except Exception as e:
                    network_logger.warning(f"Could not connect to peer {peer_ip} from gateway update: {e}")
        
    except Exception as e:
        network_logger.error(f"Error handling gateway update packet: {e}")

def start_gateway_service():
    """Start the gateway service if this node is a hotspot host"""
    if IS_HOTSPOT_HOST:
        network_logger.info("Starting gateway service for hotspot host")
        gateway_thread = threading.Thread(target=share_peers_with_gateways, daemon=True)
        gateway_thread.start()
        return True
    return False 