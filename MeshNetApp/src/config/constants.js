import DeviceInfo from 'react-native-device-info';
import { Platform } from 'react-native';
import 'react-native-get-random-values';
import { v4 as uuidv4 } from 'uuid';

// Network settings
export const PORT = 5000;
export const BUFFER_SIZE = 4096;
export const BROADCAST_INTERVAL = 10000; // milliseconds
export const DISCOVERY_INTERVAL = 30000; // milliseconds

// Node identification
export const MY_ID = uuidv4().substring(0, 8); // Generate a unique ID for this node

// Routing settings
export const MAX_TTL = 3; // Maximum number of hops for a message
export const ROUTING_TIMEOUT = 60000; // milliseconds before route is considered stale

// Encryption settings
export const USE_ENCRYPTION = true;
export const AES_KEY = 'ThisIsA16ByteKey'; // 16-byte key for AES
export const AES_MODE = 'CBC';

// Cache settings
export const MESSAGE_CACHE_SIZE = 100;

// Message types
export const MESSAGE_TYPES = {
  TEXT: 'TEXT',
  ROUTING: 'ROUTING',
  DISCOVERY: 'DISCOVERY',
  ACK: 'ACK'
};

// Get device unique info
export const getDeviceName = async () => {
  return DeviceInfo.getDeviceName();
};

// Function to get WiFi IP address
export const getWifiIPAddress = async () => {
  try {
    // Different approaches based on platform
    if (Platform.OS === 'android') {
      return DeviceInfo.getIpAddress();
    } else {
      // Fallback
      return '127.0.0.1';
    }
  } catch (error) {
    console.error('Failed to get IP address:', error);
    return '127.0.0.1';
  }
};

// Known peers initially empty, will be populated through discovery
export const KNOWN_PEERS = []; 