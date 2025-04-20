import TcpSocket from 'react-native-tcp-socket';
import { PORT, BUFFER_SIZE } from '../../config/constants';
import { processPacket } from '../encryption/encryption';
import { handlePacket } from './handler';
import { EventEmitter } from 'events';

// Create event emitter for server events
export const serverEvents = new EventEmitter();

// Global server instance
let server = null;

/**
 * Start the TCP server to listen for incoming connections
 * @returns {Promise<boolean>} - True if server started successfully
 */
export const startServer = async () => {
  return new Promise((resolve, reject) => {
    try {
      // Close existing server if it exists
      if (server) {
        try {
          server.close();
        } catch (e) {
          console.log('Error closing existing server:', e);
        }
      }
      
      // Create new server
      server = TcpSocket.createServer((socket) => {
        console.log(`New connection from ${socket.remoteAddress}:${socket.remotePort}`);
        serverEvents.emit('connection', { ip: socket.remoteAddress, port: socket.remotePort });
        
        // Set up data handling
        handleConnection(socket);
      });
      
      // Listen for connections
      server.listen({ port: PORT, host: '0.0.0.0' }, () => {
        console.log(`Server listening on port ${PORT}`);
        serverEvents.emit('started', { port: PORT });
        resolve(true);
      });
      
      // Handle server errors
      server.on('error', (error) => {
        console.error('Server error:', error);
        serverEvents.emit('error', { error });
        reject(error);
      });
    } catch (error) {
      console.error('Failed to start server:', error);
      serverEvents.emit('error', { error });
      reject(error);
    }
  });
};

/**
 * Stop the TCP server
 */
export const stopServer = () => {
  if (server) {
    try {
      server.close(() => {
        console.log('Server closed');
        serverEvents.emit('stopped');
      });
    } catch (error) {
      console.error('Error stopping server:', error);
    }
    server = null;
  }
};

/**
 * Check if the server is running
 * @returns {boolean} - True if server is running
 */
export const isServerRunning = () => {
  return server !== null;
};

/**
 * Handle a single client connection
 * @param {Object} socket - TCP socket connection
 */
const handleConnection = (socket) => {
  let data = Buffer.from('');
  
  // Set timeout to avoid hanging
  socket.setTimeout(5000);
  
  // Handle received data
  socket.on('data', async (chunk) => {
    try {
      // Append chunk to data buffer
      data = Buffer.concat([data, chunk]);
      
      // If size is less than buffer, we likely have all the data
      if (chunk.length < BUFFER_SIZE) {
        console.log(`Received ${data.length} bytes from ${socket.remoteAddress}`);
        
        // Process the data
        const rawData = data.toString('utf8');
        try {
          // Parse the JSON packet
          const packet = JSON.parse(rawData);
          
          // Decrypt the packet if needed
          const decryptedPacket = await processPacket(packet, false);
          
          // Handle the packet
          handlePacket(decryptedPacket, {
            ip: socket.remoteAddress,
            port: socket.remotePort
          }, socket);
        } catch (e) {
          console.error('Error processing packet:', e);
        }
        
        // Reset the data buffer
        data = Buffer.from('');
      }
    } catch (error) {
      console.error('Error handling data:', error);
    }
  });
  
  // Handle connection timeout
  socket.on('timeout', () => {
    console.log(`Connection timeout from ${socket.remoteAddress}`);
    socket.end();
  });
  
  // Handle connection close
  socket.on('close', (hasError) => {
    if (hasError) {
      console.log(`Connection closed with error from ${socket.remoteAddress}`);
    } else {
      console.log(`Connection closed from ${socket.remoteAddress}`);
    }
  });
  
  // Handle errors
  socket.on('error', (error) => {
    console.error(`Socket error from ${socket.remoteAddress}:`, error);
  });
}; 