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

def get_all_network_interfaces():
    """Get all network interfaces IP addresses"""
    try:
        # List to store all interfaces
        interfaces = []
        
        # Get all local IPs using socket 
        local_ips = []
        
        # Try to get all network interfaces
        hostname = socket.gethostname()
        local_ips.append(socket.gethostbyname(hostname))
        
        # Special case for Windows with multiple adapters
        try:
            # Try this method to get all adapters
            addresses = socket.getaddrinfo(socket.gethostname(), None)
            for addr in addresses:
                if addr[0] == socket.AF_INET:  # Only IPv4
                    ip = addr[4][0]
                    if ip not in local_ips and not ip.startswith('127.'):
                        local_ips.append(ip)
        except:
            pass
        
        # Also try a more reliable method to get a non-loopback IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # This doesn't actually establish a connection
            s.connect(('8.8.8.8', 53))
            ip = s.getsockname()[0]
            s.close()
            if ip not in local_ips:
                local_ips.append(ip)
        except:
            pass
        
        # Log all found IPs
        routing_logger.info(f"Found local IPs: {', '.join(local_ips)}")
        
        # Create a subnet for each IP
        for ip in local_ips:
            if not ip.startswith('127.'):  # Skip loopback addresses
                ip_parts = ip.split('.')
                subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
                if subnet not in interfaces:
                    interfaces.append(subnet)
                    
        # Add common private network ranges
        common_subnets = [
            "192.168.0.0/24",
            "192.168.1.0/24", 
            "10.0.0.0/24",
            "172.16.0.0/24",
            "169.254.0.0/16"  # APIPA range
        ]
        
        for subnet in common_subnets:
            if subnet not in interfaces:
                interfaces.append(subnet)
        
        routing_logger.info(f"Subnets to scan: {', '.join(interfaces)}")
        return interfaces
    except Exception as e:
        routing_logger.error(f"Failed to get network interfaces: {e}")
        # Return common private network ranges as fallback
        return ["192.168.0.0/24", "192.168.1.0/24", "169.254.0.0/16"]

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
    """Actively discover peers on all possible local network interfaces"""
    global KNOWN_PEERS
    
    # Get all network interfaces
    subnets = get_all_network_interfaces()
    
    # Track newly discovered peers
    new_peers = []
    peers_lock = threading.Lock()
    
    # For each subnet, scan for peers
    for subnet in subnets:
        try:
            network = ipaddress.IPv4Network(subnet, strict=False)
            
            # Calculate how many hosts to scan in this subnet
            # For /16 networks (like 169.254.0.0/16), limit the scan to avoid performance issues
            if network.prefixlen <= 16:
                # For large networks, just scan the subnet of our own IP if we have one in this range
                matching_ips = [ip for ip in [MY_IP] if ip.startswith(subnet.split('.')[0])]
                if matching_ips:
                    ip_parts = matching_ips[0].split('.')
                    subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
                    routing_logger.info(f"Large network detected, narrowing scan to: {subnet}")
                    network = ipaddress.IPv4Network(subnet, strict=False)
                else:
                    # Skip large networks where we don't have an IP
                    routing_logger.info(f"Skipping large network {subnet} - too many hosts to scan")
                    continue
            
            # Skip first (network) and last (broadcast) addresses
            ip_list = [str(ip) for ip in network.hosts()]
            
            # Skip our own IP
            if MY_IP in ip_list:
                ip_list.remove(MY_IP)
            
            routing_logger.info(f"Scanning subnet {subnet} ({len(ip_list)} hosts)")
            
            # Scan each IP in the subnet
            threads = []
            
            # Function to scan a single host
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
                
        except Exception as e:
            routing_logger.error(f"Error scanning subnet {subnet}: {e}")
    
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
