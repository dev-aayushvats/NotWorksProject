import time
import json
import threading
from config import MY_ID, MY_IP, KNOWN_PEERS, MAX_TTL, ROUTING_TIMEOUT
from utils.logger import log_routing

class Router:
    def __init__(self):
        self.routing_table = {}  # {node_id: {"next_hop": ip, "ttl": remaining_ttl, "seq": sequence_num, "timestamp": time}}
        self.sequence_numbers = {}  # {node_id: latest_sequence_number}
        self.neighbors = set()  # Direct neighbors (1-hop)
        self.message_ids_seen = set()  # Track message IDs to prevent loops
        self.lock = threading.RLock()  # Lock for thread safety
    
    def update_link_state(self, sender_id, sender_ip, link_state, seq_num, ttl):
        """Update routing table with new link state information"""
        with self.lock:
            # Update direct neighbor
            if sender_ip not in self.neighbors:
                self.neighbors.add(sender_ip)
                log_routing(sender_id, "NEW_NEIGHBOR", f"IP: {sender_ip}")
            
            # Check if this is a newer update
            if sender_id not in self.sequence_numbers or seq_num > self.sequence_numbers[sender_id]:
                self.sequence_numbers[sender_id] = seq_num
                
                # Update routing information
                for node, routes in link_state.items():
                    # Skip if this is our own ID
                    if node == MY_ID:
                        continue
                    
                    # Calculate new TTL
                    new_ttl = ttl - 1
                    
                    # Only update if the route is valid (TTL > 0) or it's a direct neighbor
                    if new_ttl > 0 or sender_id == node:
                        # For direct neighbors, always set the next hop to their IP
                        next_hop = sender_ip if sender_id == node else sender_ip
                        
                        # Update or add routing entry
                        if node not in self.routing_table or self.routing_table[node]["seq"] < routes["seq"]:
                            self.routing_table[node] = {
                                "next_hop": next_hop,
                                "ttl": new_ttl,
                                "seq": routes["seq"],
                                "timestamp": time.time()
                            }
                            log_routing(node, "ROUTE_UPDATE", f"Via {next_hop}, TTL: {new_ttl}")
                
                return True  # Return True if routing table was updated
            
            return False  # Return False if no update was needed
    
    def get_link_state(self):
        """Get our current link state information for broadcasting"""
        with self.lock:
            link_state = {}
            
            # Add ourselves with the latest sequence number
            my_seq = self.sequence_numbers.get(MY_ID, 0) + 1
            self.sequence_numbers[MY_ID] = my_seq
            
            link_state[MY_ID] = {
                "ip": MY_IP,
                "seq": my_seq,
                "neighbors": list(self.neighbors)
            }
            
            # Add information about other nodes we know
            for node_id, route in self.routing_table.items():
                # Only include fresh routes
                if time.time() - route["timestamp"] <= ROUTING_TIMEOUT:
                    link_state[node_id] = {
                        "seq": route["seq"],
                        "next_hop": route["next_hop"]
                    }
            
            return link_state
    
    def get_next_hop(self, destination_id):
        """Get the next hop for a given destination"""
        with self.lock:
            # If it's our ID, no routing needed
            if destination_id == MY_ID:
                return None
            
            # Check if we have a route and it's still valid
            if destination_id in self.routing_table:
                route = self.routing_table[destination_id]
                
                # Check if the route is still valid
                if time.time() - route["timestamp"] <= ROUTING_TIMEOUT:
                    return route["next_hop"]
            
            # If we don't have a valid route, return all neighbors for flooding
            return list(self.neighbors)
    
    def get_all_routes(self):
        """Get all active routes in the routing table"""
        with self.lock:
            active_routes = {}
            current_time = time.time()
            
            for node_id, route in self.routing_table.items():
                # Only include fresh routes
                if current_time - route["timestamp"] <= ROUTING_TIMEOUT:
                    active_routes[node_id] = {
                        "next_hop": route["next_hop"],
                        "ttl": route["ttl"],
                        "age": int(current_time - route["timestamp"])
                    }
            
            return active_routes
    
    def should_forward_message(self, message_id, ttl):
        """Check if a message should be forwarded based on TTL and message ID"""
        with self.lock:
            # If we've seen this message before, don't forward it
            if message_id in self.message_ids_seen:
                return False
            
            # If TTL is 0 or less, don't forward
            if ttl <= 0:
                return False
            
            # Add message ID to seen set
            self.message_ids_seen.add(message_id)
            
            # Limit the size of the seen set to prevent memory issues
            if len(self.message_ids_seen) > 1000:
                # Remove oldest 20% of entries
                to_remove = int(len(self.message_ids_seen) * 0.2)
                for _ in range(to_remove):
                    self.message_ids_seen.pop()
            
            return True
    
    def cleanup_stale_routes(self):
        """Remove stale routes from the routing table"""
        with self.lock:
            current_time = time.time()
            stale_nodes = []
            
            for node_id, route in self.routing_table.items():
                if current_time - route["timestamp"] > ROUTING_TIMEOUT:
                    stale_nodes.append(node_id)
            
            for node_id in stale_nodes:
                del self.routing_table[node_id]
                log_routing(node_id, "ROUTE_EXPIRED")
            
            return len(stale_nodes)


# Create a global router instance
router = Router()

