import TcpSocket from 'react-native-tcp-socket';
import { MY_ID, PORT, MAX_TTL, KNOWN_PEERS } from '../../config/constants';
import { v4 as uuidv4 } from 'uuid';
import router from '../routing/router';
import { messageCache } from '../routing/cache';
import { processPacket } from '../encryption/encryption';
import { EventEmitter } from 'events';

// Create event emitter for client events
export const clientEvents = new EventEmitter();

/**
 * Send data to a specific node
 * @param {string} ip - IP address of the node
 * @param {Object} packet - Packet to send
 * @returns {Promise<boolean>} - True if sent successfully
 */
export const sendToNode = async (ip, packet) => {
  return new Promise((resolve, reject) => {
    try {
      // Process packet (encrypt if needed)
      processPacket(packet, true)
        .then(processedPacket => {
          // Create client socket
          const client = TcpSocket.createConnection({
            host: ip,
            port: PORT,
            tls: false,
            timeout: 5000
          }, () => {
            console.log(`Connected to ${ip}:${PORT}`);
            
            // Send the data
            const data = JSON.stringify(processedPacket);
            client.write(data);
            
            // Successfully sent
            clientEvents.emit('sent', { ip, packet: processedPacket });
            
            // Cache message for reliability if it's not a routing packet
            if (processedPacket.type !== 'ROUTING' && processedPacket.type !== 'DISCOVERY') {
              messageCache.addMessage(processedPacket.id, processedPacket);
            }
            
            // Close the connection
            client.end();
            resolve(true);
          });
          
          // Handle errors
          client.on('error', (error) => {
            console.error(`Error connecting to ${ip}:`, error);
            clientEvents.emit('error', { ip, error });
            
            // If this was a direct neighbor, remove from neighbors
            if (router.neighbors.has(ip)) {
              console.log(`Removing unreachable neighbor: ${ip}`);
              router.neighbors.delete(ip);
            }
            
            reject(error);
          });
          
          // Handle timeout
          client.on('timeout', () => {
            console.error(`Connection to ${ip} timed out`);
            client.destroy();
            reject(new Error('Connection timeout'));
          });
        })
        .catch(error => {
          console.error('Error processing packet:', error);
          reject(error);
        });
    } catch (error) {
      console.error('Error sending to node:', error);
      reject(error);
    }
  });
};

/**
 * Send a text message to a specific node
 * @param {string} text - Message text
 * @param {string} destinationId - ID of the destination node
 * @returns {Promise<boolean>} - True if sent successfully
 */
export const sendMessage = async (text, destinationId) => {
  try {
    // Create message packet
    const messagePacket = {
      id: uuidv4(),
      type: 'TEXT',
      source: MY_ID,
      destination: destinationId,
      ttl: MAX_TTL,
      timestamp: Date.now(),
      payload: text
    };
    
    // Get next hop
    const nextHop = router.getNextHop(destinationId);
    
    // If broadcast, send to all neighbors
    if (destinationId === 'BROADCAST') {
      const neighbors = Array.from(router.neighbors);
      
      if (neighbors.length === 0) {
        console.log('No neighbors to broadcast to');
        return false;
      }
      
      // Send to all neighbors
      const promises = neighbors.map(ip => sendToNode(ip, messagePacket));
      
      // Wait for all to complete
      await Promise.allSettled(promises);
      
      // Message sent event
      clientEvents.emit('messageSent', {
        id: messagePacket.id,
        text,
        destination: 'BROADCAST'
      });
      
      return true;
    } else if (nextHop) {
      // Send to next hop
      if (Array.isArray(nextHop)) {
        // If flooding (no specific route), send to all neighbors
        if (nextHop.length === 0) {
          console.log('No route to destination, message not sent');
          return false;
        }
        
        const promises = nextHop.map(ip => sendToNode(ip, messagePacket));
        await Promise.allSettled(promises);
      } else {
        // Send to specific next hop
        await sendToNode(nextHop, messagePacket);
      }
      
      // Message sent event
      clientEvents.emit('messageSent', {
        id: messagePacket.id,
        text,
        destination: destinationId
      });
      
      return true;
    } else {
      console.log('No route to destination, message not sent');
      return false;
    }
  } catch (error) {
    console.error('Error sending message:', error);
    return false;
  }
};

/**
 * Discover peers on the network
 * @returns {Promise<string[]>} - Array of discovered IPs
 */
export const discoverPeers = async () => {
  try {
    // Get subnet from device IP
    const myIP = await router.myIP;
    if (!myIP || myIP === '127.0.0.1') {
      console.error('Could not determine device IP');
      return [];
    }
    
    const subnet = getSubnetFromIP(myIP);
    console.log(`Scanning subnet: ${subnet}`);
    
    // Create discovery packet
    const discoveryPacket = {
      id: uuidv4(),
      type: 'DISCOVERY',
      source: MY_ID,
      destination: 'BROADCAST',
      ttl: 1,
      timestamp: Date.now(),
      payload: {
        isResponse: false
      }
    };
    
    // Scan IP range
    const discoveredPeers = [];
    const promises = [];
    
    // Scan the last octet range (1-254)
    for (let i = 1; i <= 254; i++) {
      const ip = subnet + i;
      
      // Skip own IP
      if (ip === myIP) continue;
      
      // Try to connect to each IP
      const promise = new Promise(resolve => {
        // Create client socket with short timeout
        const client = TcpSocket.createConnection({
          host: ip,
          port: PORT,
          tls: false,
          timeout: 500 // Short timeout for faster scanning
        }, () => {
          console.log(`Discovered peer at ${ip}`);
          
          // Add to discovered peers
          discoveredPeers.push(ip);
          
          // Send discovery packet
          const data = JSON.stringify(discoveryPacket);
          client.write(data);
          
          // Wait briefly for response
          setTimeout(() => {
            client.destroy();
            resolve();
          }, 100);
        });
        
        // Handle errors (node not found or not responding)
        client.on('error', () => {
          client.destroy();
          resolve();
        });
        
        // Handle timeout
        client.on('timeout', () => {
          client.destroy();
          resolve();
        });
      });
      
      promises.push(promise);
    }
    
    // Wait for all scans to complete, but limit concurrency
    const BATCH_SIZE = 10;
    for (let i = 0; i < promises.length; i += BATCH_SIZE) {
      const batch = promises.slice(i, i + BATCH_SIZE);
      await Promise.all(batch);
    }
    
    // Add discovered peers to known peers
    discoveredPeers.forEach(ip => {
      if (!KNOWN_PEERS.includes(ip)) {
        KNOWN_PEERS.push(ip);
      }
    });
    
    // Emit discovery event
    clientEvents.emit('discovered', {
      count: discoveredPeers.length,
      peers: discoveredPeers
    });
    
    return discoveredPeers;
  } catch (error) {
    console.error('Error discovering peers:', error);
    return [];
  }
};

/**
 * Broadcast routing information to all neighbors
 */
export const broadcastRouting = async () => {
  try {
    // Get link state
    const linkState = router.getLinkState();
    
    // Create routing packet
    const routingPacket = {
      id: uuidv4(),
      type: 'ROUTING',
      source: MY_ID,
      destination: 'BROADCAST',
      ttl: MAX_TTL,
      timestamp: Date.now(),
      seq: router.sequenceNumbers[MY_ID] || 1,
      payload: linkState
    };
    
    // Get all neighbors
    const neighbors = Array.from(router.neighbors);
    
    // Send to all neighbors
    for (const ip of neighbors) {
      try {
        await sendToNode(ip, routingPacket);
      } catch (error) {
        console.error(`Failed to send routing update to ${ip}:`, error);
      }
    }
    
    console.log(`Sent routing update to ${neighbors.length} neighbors`);
    
    // Cleanup stale routes
    const removed = router.cleanupStaleRoutes();
    if (removed > 0) {
      console.log(`Removed ${removed} stale routes`);
    }
  } catch (error) {
    console.error('Error broadcasting routing information:', error);
  }
};

/**
 * Get subnet from IP address
 * @param {string} ip - IP address
 * @returns {string} - Subnet in format "xxx.xxx.xxx."
 */
const getSubnetFromIP = (ip) => {
  const parts = ip.split('.');
  if (parts.length !== 4) return '192.168.1.';
  return `${parts[0]}.${parts[1]}.${parts[2]}.`;
}; 