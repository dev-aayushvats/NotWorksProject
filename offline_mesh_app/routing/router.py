import time
import json
import threading
import uuid
from config import MY_ID, MY_IP, KNOWN_PEERS, MAX_TTL, ROUTING_TIMEOUT, IS_HOTSPOT_HOST
from utils.logger import log_routing, routing_logger

class Router:
    def __init__(self):
        self.routing_table = {}  # {node_id: {"next_hop": ip, "ttl": remaining_ttl, "seq": sequence_num, "timestamp": time}}
        self.sequence_numbers = {}  # {node_id: latest_sequence_number}
        self.neighbors = set()  # Direct neighbors (1-hop)
        self.message_ids_seen = set()  # Track message IDs to prevent loops
        self.secondary_routes = {}  # Backup routes for resilience
        self.lock = threading.RLock()  # Lock for thread safety
        self.bridge_nodes = set()  # Nodes that can bridge between networks
        self.gateway_nodes = set()  # Nodes that act as hotspot hosts (gateways)
    
    def update_link_state(self, sender_id, sender_ip, link_state, seq_num, ttl):
        """Update routing table with new link state information"""
        with self.lock:
            # Update direct neighbor
            if sender_ip not in self.neighbors:
                self.neighbors.add(sender_ip)
                log_routing(sender_id, "NEW_NEIGHBOR", f"IP: {sender_ip}")
            
            # Check if this is a gateway node
            if link_state.get("is_gateway", False) or (sender_id in self.gateway_nodes):
                self.gateway_nodes.add(sender_id)
                routing_logger.info(f"Node {sender_id} identified as a gateway/hotspot host")
                # Also update in routing table
                if sender_id in self.routing_table:
                    self.routing_table[sender_id]["is_gateway"] = True
            
            # Check if this is a newer update
            if sender_id not in self.sequence_numbers or seq_num > self.sequence_numbers[sender_id]:
                self.sequence_numbers[sender_id] = seq_num
                
                # Extract any bridging information from the link state
                if "bridges" in link_state and link_state["bridges"]:
                    # This node connects to multiple networks - mark it as a bridge
                    self.bridge_nodes.add(sender_id)
                    routing_logger.info(f"Node {sender_id} identified as a bridge between networks")
                
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
                            # Record the old route as a secondary if it exists
                            if node in self.routing_table:
                                self.secondary_routes[node] = self.routing_table[node].copy()
                            
                            self.routing_table[node] = {
                                "next_hop": next_hop,
                                "ttl": new_ttl,
                                "seq": routes["seq"],
                                "timestamp": time.time(),
                                "via_bridge": sender_id in self.bridge_nodes,
                                "is_gateway": sender_id in self.gateway_nodes
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
            
            # Determine if we're a bridge between networks
            is_bridge = self.detect_bridge_status()
            
            link_state[MY_ID] = {
                "ip": MY_IP,
                "seq": my_seq,
                "neighbors": list(self.neighbors),
                "bridges": is_bridge,
                "is_gateway": IS_HOTSPOT_HOST
            }
            
            # Add information about other nodes we know
            for node_id, route in self.routing_table.items():
                # Only include fresh routes
                if time.time() - route["timestamp"] <= ROUTING_TIMEOUT:
                    link_state[node_id] = {
                        "seq": route["seq"],
                        "next_hop": route["next_hop"],
                        "is_gateway": route.get("is_gateway", False)
                    }
            
            return link_state
    
    def detect_bridge_status(self):
        """Detect if this node bridges between networks"""
        # Check if we connect to nodes on different subnets
        network_prefixes = set()
        for neighbor in self.neighbors:
            # Extract the network prefix (first two octets as a simple heuristic)
            prefix = '.'.join(neighbor.split('.')[:2])
            network_prefixes.add(prefix)
        
        # If we connect to multiple networks, we're a bridge
        is_bridge = len(network_prefixes) > 1
        if is_bridge:
            routing_logger.info(f"This node is a bridge between networks: {', '.join(network_prefixes)}")
        return is_bridge
    
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
            
            # If we don't have a valid primary route, check secondary routes
            if destination_id in self.secondary_routes:
                sec_route = self.secondary_routes[destination_id]
                if time.time() - sec_route["timestamp"] <= ROUTING_TIMEOUT * 1.5:  # Give secondary routes longer validity
                    routing_logger.info(f"Using secondary route to {destination_id} via {sec_route['next_hop']}")
                    return sec_route["next_hop"]
            
            # Check if any gateway nodes can help reach the destination
            if self.gateway_nodes:
                routing_logger.info(f"No direct route to {destination_id}, checking gateway nodes: {self.gateway_nodes}")
                for gateway_id in self.gateway_nodes:
                    if gateway_id in self.routing_table:
                        gateway_route = self.routing_table[gateway_id]
                        if time.time() - gateway_route["timestamp"] <= ROUTING_TIMEOUT:
                            routing_logger.info(f"Routing via gateway node {gateway_id} at {gateway_route['next_hop']}")
                            return gateway_route["next_hop"]
            
            # Check if any bridge nodes can help reach the destination
            if self.bridge_nodes:
                routing_logger.info(f"No direct route to {destination_id}, checking bridge nodes: {self.bridge_nodes}")
                for bridge_id in self.bridge_nodes:
                    if bridge_id in self.routing_table:
                        bridge_route = self.routing_table[bridge_id]
                        if time.time() - bridge_route["timestamp"] <= ROUTING_TIMEOUT:
                            routing_logger.info(f"Routing via bridge node {bridge_id} at {bridge_route['next_hop']}")
                            return bridge_route["next_hop"]
            
            # If we don't have any specific route, return all neighbors for flooding
            all_neighbors = list(self.neighbors)
            
            # Prioritize gateways for flooding if no specific route
            gateway_neighbors = []
            for neighbor_ip in all_neighbors:
                for node_id, route in self.routing_table.items():
                    if route["next_hop"] == neighbor_ip and route.get("is_gateway", False):
                        gateway_neighbors.append(neighbor_ip)
                        break
            
            if gateway_neighbors:
                routing_logger.info(f"No specific route, but found gateway neighbors to try: {gateway_neighbors}")
                return gateway_neighbors
            
            # Next prioritize bridges for flooding if no specific route
            bridge_neighbors = []
            for neighbor_ip in all_neighbors:
                for node_id, route in self.routing_table.items():
                    if route["next_hop"] == neighbor_ip and route.get("via_bridge", False):
                        bridge_neighbors.append(neighbor_ip)
                        break
            
            if bridge_neighbors:
                routing_logger.info(f"No specific route, but found bridge neighbors to try: {bridge_neighbors}")
                return bridge_neighbors
            
            routing_logger.info(f"No specific route, flooding to all neighbors: {all_neighbors}")
            return all_neighbors
    
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
                        "age": int(current_time - route["timestamp"]),
                        "via_bridge": route.get("via_bridge", False),
                        "is_gateway": route.get("is_gateway", False)
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
                oldest = list(self.message_ids_seen)[:to_remove]
                for msg_id in oldest:
                    self.message_ids_seen.remove(msg_id)
            
            return True
    
    def cleanup_stale_routes(self):
        """Remove stale routes from the routing table"""
        with self.lock:
            current_time = time.time()
            stale_nodes = []
            
            for node_id, route in self.routing_table.items():
                if current_time - route["timestamp"] > ROUTING_TIMEOUT:
                    stale_nodes.append(node_id)
                    # Move to secondary routes before removing
                    self.secondary_routes[node_id] = route.copy()
            
            for node_id in stale_nodes:
                del self.routing_table[node_id]
                log_routing(node_id, "ROUTE_EXPIRED")
            
            # Also clean up very old secondary routes
            stale_secondary = []
            for node_id, route in self.secondary_routes.items():
                if current_time - route["timestamp"] > ROUTING_TIMEOUT * 3:  # Keep secondary routes longer
                    stale_secondary.append(node_id)
            
            for node_id in stale_secondary:
                del self.secondary_routes[node_id]
            
            # Update bridge and gateway nodes set
            stale_bridges = []
            for bridge_id in self.bridge_nodes:
                if bridge_id not in self.routing_table and bridge_id not in self.secondary_routes:
                    stale_bridges.append(bridge_id)
            
            for bridge_id in stale_bridges:
                self.bridge_nodes.remove(bridge_id)
                
            # Update gateway nodes set
            stale_gateways = []
            for gateway_id in self.gateway_nodes:
                if gateway_id not in self.routing_table and gateway_id not in self.secondary_routes:
                    stale_gateways.remove(gateway_id)
            
            for gateway_id in stale_gateways:
                self.gateway_nodes.remove(gateway_id)
            
            return len(stale_nodes)


# Create a global router instance
router = Router()

