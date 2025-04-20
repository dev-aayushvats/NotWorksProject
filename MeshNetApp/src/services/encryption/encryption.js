import Aes from 'react-native-aes-crypto';
import { AES_KEY, AES_MODE, USE_ENCRYPTION } from '../../config/constants';

/**
 * Encrypts data using AES encryption
 * @param {string} data - Data to encrypt (as JSON string)
 * @returns {Promise<{data: string, iv: string}>} - Encrypted data and initialization vector
 */
export const encryptData = async (data) => {
  if (!USE_ENCRYPTION) return { data, iv: null };
  
  try {
    // Generate random initialization vector
    const iv = await Aes.randomKey(16);
    
    // Encrypt the data
    const encrypted = await Aes.encrypt(
      data,
      AES_KEY,
      iv,
      AES_MODE
    );
    
    return { data: encrypted, iv };
  } catch (error) {
    console.error('Encryption error:', error);
    // In case of encryption failure, return original data
    return { data, iv: null };
  }
};

/**
 * Decrypts data using AES encryption
 * @param {string} encryptedData - Data to decrypt
 * @param {string} iv - Initialization vector used for encryption
 * @returns {Promise<string>} - Decrypted data as JSON string
 */
export const decryptData = async (encryptedData, iv) => {
  if (!USE_ENCRYPTION || !iv) return encryptedData;
  
  try {
    const decrypted = await Aes.decrypt(
      encryptedData,
      AES_KEY,
      iv,
      AES_MODE
    );
    
    return decrypted;
  } catch (error) {
    console.error('Decryption error:', error);
    // In case of decryption failure, return encrypted data
    return encryptedData;
  }
};

/**
 * Utility to handle encryption/decryption of packets
 * @param {Object} packet - Packet object to encrypt/decrypt
 * @param {boolean} isEncrypting - True if encrypting, false if decrypting
 * @returns {Promise<Object>} - Processed packet
 */
export const processPacket = async (packet, isEncrypting = true) => {
  if (!USE_ENCRYPTION) return packet;
  
  try {
    if (isEncrypting) {
      // Don't encrypt routing packets
      if (packet.type === 'ROUTING' || packet.type === 'DISCOVERY') {
        return packet;
      }
      
      // Convert payload to string if it's an object
      const payloadStr = typeof packet.payload === 'object' 
        ? JSON.stringify(packet.payload) 
        : packet.payload;
      
      // Encrypt the payload
      const { data, iv } = await encryptData(payloadStr);
      
      return {
        ...packet,
        payload: data,
        iv: iv
      };
    } else {
      // Decrypting
      // Skip if not encrypted
      if (!packet.iv || packet.type === 'ROUTING' || packet.type === 'DISCOVERY') {
        return packet;
      }
      
      // Decrypt the payload
      const decrypted = await decryptData(packet.payload, packet.iv);
      
      // Parse the payload back to object if it's JSON
      try {
        const parsedPayload = JSON.parse(decrypted);
        return {
          ...packet,
          payload: parsedPayload,
          iv: null // Remove IV after decryption
        };
      } catch (e) {
        // If not valid JSON, return as string
        return {
          ...packet,
          payload: decrypted,
          iv: null
        };
      }
    }
  } catch (error) {
    console.error('Error processing packet:', error);
    return packet; // Return original packet on error
  }
}; 