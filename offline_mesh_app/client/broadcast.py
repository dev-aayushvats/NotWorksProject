import json
import time
import uuid
import socket
import threading
import ipaddress
from client.sender import send_to_peer
from config import (
    MY_ID, MY_IP, KNOWN_PEERS,
    MAX_TTL, BROADCAST_INTERVAL, DISCOVERY_INTERVAL,
    PORT, save_config
)
from routing.router import router
from utils.logger import log_routing, routing_logger
from utils.encryption import encrypt_data, decrypt_data

def get_local_subnet():
    """Get the local subnet for network scanning without using netifaces"""
    try:
        # Get host IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
        s.close()
        
        # Log the detected IP for debugging
        routing_logger.info(f"Detected local IP: {ip}")
        
        # For simplicity, assume a /24 subnet (most home networks)
        ip_parts = ip.split('.')
        subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
        
        routing_logger.info(f"Using subnet for scanning: {subnet}")
        return subnet
    except Exception as e:
        routing_logger.error(f"Failed to get subnet: {e}")
        # Fallback to common home network
        return "192.168.1.0/24"

def discover_peers():
    """Actively discover peers on the local network"""
    global KNOWN_PEERS
    subnet = get_local_subnet()
    
    # Convert subnet to list of IPs
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        
        # Skip first (network) and last (broadcast) addresses
        ip_list = [str(ip) for ip in network.hosts()]
        
        # Skip our own IP
        if MY_IP in ip_list:
            ip_list.remove(MY_IP)
        
        routing_logger.info(f"Scanning subnet {subnet} ({len(ip_list)} hosts)")
        routing_logger.info(f"My IP is {MY_IP}, will not scan self")
        
        # Track newly discovered peers
        new_peers = []
        
        # Scan in parallel for faster discovery
        def scan_host(ip):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)  # Short timeout for faster scanning
                routing_logger.debug(f"Attempting to connect to {ip}:{PORT}")
                result = s.connect_ex((ip, PORT))
                s.close()
                
                if result == 0:  # Port is open
                    routing_logger.info(f"Found open port on {ip}:{PORT}")
                    if ip not in KNOWN_PEERS:
                        with peers_lock:
                            KNOWN_PEERS.append(ip)
                            new_peers.append(ip)
                            log_routing(ip, "PEER_DISCOVERED")
                else:
                    routing_logger.debug(f"No response from {ip}:{PORT}, error code: {result}")
            except Exception as e:
                routing_logger.debug(f"Scan error for {ip}: {e}")
        
        # Use threading for parallel scanning
        threads = []
        peers_lock = threading.Lock()
        
        for ip in ip_list:
            t = threading.Thread(target=scan_host, args=(ip,))
            threads.append(t)
            t.start()
            
            # Limit concurrent threads to avoid overwhelming network
            if len(threads) >= 20:
                for t in threads:
                    t.join()
                threads = []
        
        # Wait for remaining threads
        for t in threads:
            t.join()
        
        # Log results
        if new_peers:
            routing_logger.info(f"Discovered {len(new_peers)} new peers: {', '.join(new_peers)}")
            # Save updated peers to config
            save_config()
            
            # Send an immediate routing update to announce to new peers
            broadcast_routing_update()
        else:
            routing_logger.info(f"No new peers discovered. Current peers: {', '.join(KNOWN_PEERS) if KNOWN_PEERS else 'None'}")
        
        return new_peers
    except Exception as e:
        routing_logger.error(f"Peer discovery failed: {e}")
        return []

def periodic_discovery():
    """Run peer discovery periodically"""
    while True:
        try:
            discover_peers()
        except Exception as e:
            routing_logger.error(f"Error in periodic discovery: {e}")
        
        # Sleep between discovery runs
        time.sleep(DISCOVERY_INTERVAL)

def broadcast_routing_update():
    """Send a single routing update to known peers"""
    # Get current link state from router
    link_state = router.get_link_state()
    
    # Create routing packet
    message_id = str(uuid.uuid4())
    packet = {
        "type": "routing",
        "id": message_id,
        "src": MY_ID,
        "link_state": link_state,
        "seq": link_state[MY_ID]["seq"],
        "ttl": MAX_TTL,
        "timestamp": time.time()
    }
    
    # Convert to JSON
    json_data = json.dumps(packet)
    
    # Encrypt if needed
    encrypted_data = encrypt_data(json_data)
    
    # Send to all known peers
    for peer in KNOWN_PEERS:
        try:
            send_to_peer(peer, encrypted_data)
            log_routing(peer, "ROUTING_SENT")
        except Exception as e:
            routing_logger.error(f"Failed to send routing update to {peer}: {e}")

def broadcast_routing():
    """Periodically broadcast routing updates"""
    while True:
        try:
            broadcast_routing_update()
            
            # Cleanup stale routes
            stale_count = router.cleanup_stale_routes()
            if stale_count > 0:
                routing_logger.info(f"Removed {stale_count} stale routes")
                
        except Exception as e:
            routing_logger.error(f"Error in routing broadcast: {e}")
            
        # Sleep between broadcasts
        time.sleep(BROADCAST_INTERVAL)
