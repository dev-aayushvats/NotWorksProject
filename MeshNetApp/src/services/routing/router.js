import { MY_ID, MAX_TTL, ROUTING_TIMEOUT } from '../../config/constants';
import { getWifiIPAddress } from '../../config/constants';

/**
 * Router class implementing HSLS routing protocol
 * Manages routing table and handles routing decisions
 */
class Router {
  constructor() {
    this.routingTable = {};  // {nodeId: {nextHop: ip, ttl: remaining_ttl, seq: sequenceNum, timestamp: time}}
    this.sequenceNumbers = {};  // {nodeId: latestSequenceNumber}
    this.neighbors = new Set();  // Direct neighbors (1-hop)
    this.messageIdsSeen = new Set();  // Track message IDs to prevent loops
    this.myIP = null;
    
    // Initialize with current IP
    this.initializeIP();
  }
  
  async initializeIP() {
    this.myIP = await getWifiIPAddress();
  }
  
  /**
   * Update routing table with new link state information
   * @param {string} senderId - ID of the node sending update
   * @param {string} senderIp - IP of the node sending update
   * @param {Object} linkState - Link state information
   * @param {number} seqNum - Sequence number
   * @param {number} ttl - Time to live
   * @returns {boolean} - True if routing table was updated
   */
  updateLinkState(senderId, senderIp, linkState, seqNum, ttl) {
    // Update direct neighbor
    if (!this.neighbors.has(senderIp)) {
      this.neighbors.add(senderIp);
      console.log(`NEW_NEIGHBOR: ${senderId} (IP: ${senderIp})`);
    }
    
    // Check if this is a newer update
    if (!(senderId in this.sequenceNumbers) || seqNum > this.sequenceNumbers[senderId]) {
      this.sequenceNumbers[senderId] = seqNum;
      
      // Update routing information
      for (const [node, routes] of Object.entries(linkState)) {
        // Skip if this is our own ID
        if (node === MY_ID) continue;
        
        // Calculate new TTL
        const newTtl = ttl - 1;
        
        // Only update if the route is valid (TTL > 0) or it's a direct neighbor
        if (newTtl > 0 || senderId === node) {
          // For direct neighbors, always set the next hop to their IP
          const nextHop = senderId === node ? senderIp : senderIp;
          
          // Update or add routing entry
          if (!(node in this.routingTable) || this.routingTable[node].seq < routes.seq) {
            this.routingTable[node] = {
              nextHop: nextHop,
              ttl: newTtl,
              seq: routes.seq,
              timestamp: Date.now()
            };
            console.log(`ROUTE_UPDATE: ${node} via ${nextHop}, TTL: ${newTtl}`);
          }
        }
      }
      
      return true; // Return true if routing table was updated
    }
    
    return false; // Return false if no update was needed
  }
  
  /**
   * Get link state information for broadcasting
   * @returns {Object} - Current link state
   */
  getLinkState() {
    const linkState = {};
    
    // Add ourselves with the latest sequence number
    const mySeq = (this.sequenceNumbers[MY_ID] || 0) + 1;
    this.sequenceNumbers[MY_ID] = mySeq;
    
    linkState[MY_ID] = {
      ip: this.myIP,
      seq: mySeq,
      neighbors: Array.from(this.neighbors)
    };
    
    // Add information about other nodes we know
    for (const [nodeId, route] of Object.entries(this.routingTable)) {
      // Only include fresh routes
      if (Date.now() - route.timestamp <= ROUTING_TIMEOUT) {
        linkState[nodeId] = {
          seq: route.seq,
          nextHop: route.nextHop
        };
      }
    }
    
    return linkState;
  }
  
  /**
   * Get the next hop for a given destination
   * @param {string} destinationId - ID of the destination node
   * @returns {string|string[]|null} - Next hop IP or array of neighbor IPs for flooding
   */
  getNextHop(destinationId) {
    // If it's our ID, no routing needed
    if (destinationId === MY_ID) {
      return null;
    }
    
    // Check if we have a route and it's still valid
    if (destinationId in this.routingTable) {
      const route = this.routingTable[destinationId];
      
      // Check if the route is still valid
      if (Date.now() - route.timestamp <= ROUTING_TIMEOUT) {
        return route.nextHop;
      }
    }
    
    // If we don't have a valid route, return all neighbors for flooding
    return Array.from(this.neighbors);
  }
  
  /**
   * Get all active routes in the routing table
   * @returns {Object} - Active routes
   */
  getAllRoutes() {
    const activeRoutes = {};
    const currentTime = Date.now();
    
    for (const [nodeId, route] of Object.entries(this.routingTable)) {
      // Only include fresh routes
      if (currentTime - route.timestamp <= ROUTING_TIMEOUT) {
        activeRoutes[nodeId] = {
          nextHop: route.nextHop,
          ttl: route.ttl,
          age: Math.floor((currentTime - route.timestamp) / 1000) // Convert to seconds
        };
      }
    }
    
    return activeRoutes;
  }
  
  /**
   * Check if a message should be forwarded based on TTL and message ID
   * @param {string} messageId - Unique ID of the message
   * @param {number} ttl - Time to live
   * @returns {boolean} - True if message should be forwarded
   */
  shouldForwardMessage(messageId, ttl) {
    // If we've seen this message before, don't forward it
    if (this.messageIdsSeen.has(messageId)) {
      return false;
    }
    
    // If TTL is 0 or less, don't forward
    if (ttl <= 0) {
      return false;
    }
    
    // Add message ID to seen set
    this.messageIdsSeen.add(messageId);
    
    // Limit the size of the seen set to prevent memory issues
    if (this.messageIdsSeen.size > 1000) {
      // Remove oldest 20% of entries
      const toRemove = Math.floor(this.messageIdsSeen.size * 0.2);
      const entriesToRemove = Array.from(this.messageIdsSeen).slice(0, toRemove);
      entriesToRemove.forEach(entry => this.messageIdsSeen.delete(entry));
    }
    
    return true;
  }
  
  /**
   * Remove stale routes from the routing table
   * @returns {number} - Number of routes removed
   */
  cleanupStaleRoutes() {
    const currentTime = Date.now();
    const staleNodes = [];
    
    for (const [nodeId, route] of Object.entries(this.routingTable)) {
      if (currentTime - route.timestamp > ROUTING_TIMEOUT) {
        staleNodes.push(nodeId);
      }
    }
    
    for (const nodeId of staleNodes) {
      delete this.routingTable[nodeId];
      console.log(`ROUTE_EXPIRED: ${nodeId}`);
    }
    
    return staleNodes.length;
  }
  
  /**
   * Update the router's IP address
   * @param {string} newIP - New IP address
   */
  updateIP(newIP) {
    this.myIP = newIP;
  }
}

// Create a global router instance
const router = new Router();

export default router; 