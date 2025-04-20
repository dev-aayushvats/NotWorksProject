import { MY_ID } from '../../config/constants';
import router from '../routing/router';
import { messageCache } from '../routing/cache';
import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';

// Create event emitter for message events
export const messageEvents = new EventEmitter();

/**
 * Handle a received packet
 * @param {Object} packet - Received packet
 * @param {Object} sender - Sender information
 * @param {Object} socket - Socket connection
 */
export const handlePacket = (packet, sender, socket) => {
  try {
    // Check if packet has required fields
    if (!packet || !packet.type || !packet.source) {
      console.error('Invalid packet received');
      return;
    }
    
    console.log(`Handling ${packet.type} packet from ${packet.source}`);
    
    // Process based on packet type
    switch (packet.type) {
      case 'TEXT':
        handleTextMessage(packet, sender);
        break;
      case 'ROUTING':
        handleRoutingUpdate(packet, sender);
        break;
      case 'DISCOVERY':
        handleDiscovery(packet, sender, socket);
        break;
      case 'ACK':
        handleAcknowledgment(packet);
        break;
      default:
        console.log(`Unknown packet type: ${packet.type}`);
    }
  } catch (error) {
    console.error('Error handling packet:', error);
  }
};

/**
 * Handle text message packet
 * @param {Object} packet - Message packet
 * @param {Object} sender - Sender information
 */
const handleTextMessage = (packet, sender) => {
  try {
    // Check if this message is for us
    if (packet.destination === MY_ID) {
      // This message is for us
      console.log(`Received message from ${packet.source}: ${packet.payload}`);
      
      // Emit message event
      messageEvents.emit('message', {
        id: packet.id || uuidv4(),
        source: packet.source,
        text: packet.payload,
        timestamp: packet.timestamp || Date.now()
      });
      
      // Send acknowledgment
      sendAcknowledgment(packet.id, packet.source);
    } else if (packet.destination === 'BROADCAST') {
      // Broadcast message
      console.log(`Received broadcast from ${packet.source}: ${packet.payload}`);
      
      // Emit broadcast event
      messageEvents.emit('broadcast', {
        id: packet.id || uuidv4(),
        source: packet.source,
        text: packet.payload,
        timestamp: packet.timestamp || Date.now()
      });
      
      // Forward broadcast to all neighbors except the sender
      forwardPacket(packet, sender.ip);
    } else {
      // Message is for someone else, check if we should forward
      if (router.shouldForwardMessage(packet.id, packet.ttl)) {
        console.log(`Forwarding message from ${packet.source} to ${packet.destination}`);
        forwardPacket(packet);
      }
    }
  } catch (error) {
    console.error('Error handling text message:', error);
  }
};

/**
 * Handle routing update packet
 * @param {Object} packet - Routing packet
 * @param {Object} sender - Sender information
 */
const handleRoutingUpdate = (packet, sender) => {
  try {
    // Extract routing information
    const { source, payload, seq, ttl } = packet;
    
    // Update routing table
    const updated = router.updateLinkState(
      source, 
      sender.ip, 
      payload, 
      seq, 
      ttl
    );
    
    // Forward routing update if it was new information and TTL allows
    if (updated && ttl > 1) {
      // Create new packet with decremented TTL
      const forwardPacket = {
        ...packet,
        ttl: ttl - 1
      };
      
      // Forward to all neighbors except the sender
      forwardRoutingUpdate(forwardPacket, sender.ip);
    }
  } catch (error) {
    console.error('Error handling routing update:', error);
  }
};

/**
 * Handle discovery packet
 * @param {Object} packet - Discovery packet
 * @param {Object} sender - Sender information
 * @param {Object} socket - Socket connection
 */
const handleDiscovery = (packet, sender, socket) => {
  try {
    // Add sender to routing table as direct neighbor
    router.updateLinkState(
      packet.source,
      sender.ip,
      { [packet.source]: { ip: sender.ip, seq: packet.seq || 1 } },
      packet.seq || 1,
      1
    );
    
    // Send response to discovery
    respondToDiscovery(socket, packet.source);
    
    console.log(`Responded to discovery from ${packet.source} (${sender.ip})`);
  } catch (error) {
    console.error('Error handling discovery:', error);
  }
};

/**
 * Handle acknowledgment packet
 * @param {Object} packet - Acknowledgment packet
 */
const handleAcknowledgment = (packet) => {
  try {
    // Extract message ID that was acknowledged
    const { messageId } = packet.payload;
    
    console.log(`Received acknowledgment for message ${messageId}`);
    
    // Emit acknowledgment event
    messageEvents.emit('ack', {
      messageId,
      source: packet.source
    });
    
    // Remove from cache if it was cached
    messageCache.removeMessage(messageId);
  } catch (error) {
    console.error('Error handling acknowledgment:', error);
  }
};

/**
 * Forward a packet to the next hop
 * @param {Object} packet - Packet to forward
 * @param {string} [excludeIp] - IP to exclude from forwarding
 */
const forwardPacket = (packet, excludeIp) => {
  try {
    // Get next hop
    const nextHop = router.getNextHop(packet.destination);
    
    // Create forwarded packet with decremented TTL
    const forwardedPacket = {
      ...packet,
      ttl: packet.ttl - 1
    };
    
    // If nextHop is an array, send to all except excludeIp
    if (Array.isArray(nextHop)) {
      nextHop.forEach(ip => {
        if (ip !== excludeIp) {
          // Use client.sendToNode from client.js
          // This will be imported and used when implemented
          console.log(`Forwarding to ${ip}`);
        }
      });
    } else if (nextHop && nextHop !== excludeIp) {
      // Send to specific next hop
      console.log(`Forwarding to ${nextHop}`);
    }
  } catch (error) {
    console.error('Error forwarding packet:', error);
  }
};

/**
 * Forward routing update to all neighbors
 * @param {Object} packet - Routing packet
 * @param {string} excludeIp - IP to exclude from forwarding
 */
const forwardRoutingUpdate = (packet, excludeIp) => {
  try {
    // Get all neighbors
    const neighbors = Array.from(router.neighbors);
    
    // Forward to all neighbors except the sender
    neighbors.forEach(ip => {
      if (ip !== excludeIp) {
        // Use client.sendToNode from client.js
        // This will be imported and used when implemented
        console.log(`Forwarding routing update to ${ip}`);
      }
    });
  } catch (error) {
    console.error('Error forwarding routing update:', error);
  }
};

/**
 * Send acknowledgment for a message
 * @param {string} messageId - ID of the message to acknowledge
 * @param {string} destination - Node ID to send acknowledgment to
 */
const sendAcknowledgment = (messageId, destination) => {
  try {
    // Create acknowledgment packet
    const ackPacket = {
      id: uuidv4(),
      type: 'ACK',
      source: MY_ID,
      destination: destination,
      ttl: 3,
      timestamp: Date.now(),
      payload: {
        messageId: messageId
      }
    };
    
    // Get next hop
    const nextHop = router.getNextHop(destination);
    
    // Send acknowledgment
    if (nextHop) {
      // Use client.sendToNode from client.js
      // This will be imported and used when implemented
      console.log(`Sending acknowledgment to ${destination} via ${nextHop}`);
    }
  } catch (error) {
    console.error('Error sending acknowledgment:', error);
  }
};

/**
 * Respond to a discovery request
 * @param {Object} socket - Socket to respond on
 * @param {string} sourceId - ID of the discovering node
 */
const respondToDiscovery = (socket, sourceId) => {
  try {
    // Create response packet
    const responsePacket = {
      id: uuidv4(),
      type: 'DISCOVERY',
      source: MY_ID,
      destination: sourceId,
      ttl: 1,
      timestamp: Date.now(),
      payload: {
        isResponse: true,
        neighbors: Array.from(router.neighbors)
      }
    };
    
    // Send response directly through the socket
    const responseStr = JSON.stringify(responsePacket);
    socket.write(responseStr);
  } catch (error) {
    console.error('Error responding to discovery:', error);
  }
}; 