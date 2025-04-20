import { MESSAGE_CACHE_SIZE } from '../../config/constants';
import { MMKV } from 'react-native-mmkv';

// Create storage instance
const messageStorage = new MMKV({
  id: 'messages-cache',
  encryptionKey: 'message-encryption-key'
});

/**
 * Message cache for storing and retrieving messages
 * Implements store-and-forward functionality
 */
class MessageCache {
  constructor() {
    this.messageIds = [];
    this.loadMessageIds();
  }
  
  // Load cached message IDs from storage
  loadMessageIds() {
    try {
      const storedIds = messageStorage.getString('message-ids');
      if (storedIds) {
        this.messageIds = JSON.parse(storedIds);
      }
    } catch (error) {
      console.error('Failed to load message IDs:', error);
      this.messageIds = [];
    }
  }
  
  // Save message IDs to storage
  saveMessageIds() {
    try {
      messageStorage.set('message-ids', JSON.stringify(this.messageIds));
    } catch (error) {
      console.error('Failed to save message IDs:', error);
    }
  }
  
  /**
   * Add a message to the cache
   * @param {string} messageId - Unique ID of the message
   * @param {Object} message - Message object to cache
   */
  addMessage(messageId, message) {
    try {
      // Store the message in MMKV
      messageStorage.set(messageId, JSON.stringify(message));
      
      // Add message ID to the list if not already present
      if (!this.messageIds.includes(messageId)) {
        this.messageIds.push(messageId);
        
        // Ensure we don't exceed the cache size
        if (this.messageIds.length > MESSAGE_CACHE_SIZE) {
          const oldestId = this.messageIds.shift();
          messageStorage.delete(oldestId);
        }
        
        // Save updated IDs
        this.saveMessageIds();
      }
    } catch (error) {
      console.error('Failed to cache message:', error);
    }
  }
  
  /**
   * Get a message from the cache
   * @param {string} messageId - ID of the message to retrieve
   * @returns {Object|null} - Retrieved message or null if not found
   */
  getMessage(messageId) {
    try {
      const message = messageStorage.getString(messageId);
      if (message) {
        return JSON.parse(message);
      }
      return null;
    } catch (error) {
      console.error('Failed to retrieve message:', error);
      return null;
    }
  }
  
  /**
   * Get all messages for a specific destination
   * @param {string} destinationId - ID of the destination node
   * @returns {Array} - Array of messages for the destination
   */
  getMessagesForDestination(destinationId) {
    try {
      const messages = [];
      
      for (const messageId of this.messageIds) {
        const message = this.getMessage(messageId);
        if (message && message.destination === destinationId) {
          messages.push(message);
        }
      }
      
      return messages;
    } catch (error) {
      console.error('Failed to get messages for destination:', error);
      return [];
    }
  }
  
  /**
   * Remove a message from the cache
   * @param {string} messageId - ID of the message to remove
   */
  removeMessage(messageId) {
    try {
      // Remove from storage
      messageStorage.delete(messageId);
      
      // Remove from IDs list
      const index = this.messageIds.indexOf(messageId);
      if (index !== -1) {
        this.messageIds.splice(index, 1);
        this.saveMessageIds();
      }
    } catch (error) {
      console.error('Failed to remove message:', error);
    }
  }
  
  /**
   * Get all cached message IDs
   * @returns {Array} - Array of message IDs
   */
  getAllMessageIds() {
    return [...this.messageIds];
  }
  
  /**
   * Clear the entire message cache
   */
  clearCache() {
    try {
      for (const messageId of this.messageIds) {
        messageStorage.delete(messageId);
      }
      this.messageIds = [];
      this.saveMessageIds();
    } catch (error) {
      console.error('Failed to clear message cache:', error);
    }
  }
}

// Create singleton instance
export const messageCache = new MessageCache(); 