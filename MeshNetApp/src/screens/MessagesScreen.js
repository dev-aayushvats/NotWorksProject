import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { FAB } from 'react-native-paper';
import { MaterialCommunityIcons } from 'react-native-vector-icons';
import { MY_ID } from '../config/constants';
import { sendMessage } from '../services/discovery/client';
import { messageEvents } from '../services/discovery/handler';
import router from '../services/routing/router';
import { messageCache } from '../services/routing/cache';

const MessagesScreen = () => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [selectedPeer, setSelectedPeer] = useState('BROADCAST');
  const [showPeerList, setShowPeerList] = useState(false);
  const [peers, setPeers] = useState([]);
  const [sending, setSending] = useState(false);
  
  const flatListRef = useRef(null);
  
  // Load initial messages from cache and listen for new ones
  useEffect(() => {
    // Load any cached messages
    const loadCachedMessages = () => {
      const cachedMsgIds = messageCache.getAllMessageIds();
      const cachedMessages = cachedMsgIds
        .map(id => messageCache.getMessage(id))
        .filter(msg => msg && (msg.type === 'TEXT' || msg.type === 'BROADCAST'))
        .map(msg => ({
          id: msg.id,
          text: msg.payload,
          sender: msg.source,
          timestamp: msg.timestamp,
          isSelf: msg.source === MY_ID,
        }))
        .sort((a, b) => a.timestamp - b.timestamp);
      
      setMessages(prevMessages => {
        // Combine with existing messages, avoid duplicates
        const allMessages = [...prevMessages, ...cachedMessages];
        const uniqueMessages = allMessages.filter((msg, index, self) => 
          index === self.findIndex(m => m.id === msg.id)
        );
        return uniqueMessages.sort((a, b) => a.timestamp - b.timestamp);
      });
    };
    
    loadCachedMessages();
    
    // Listen for new messages
    const handleNewMessage = (msg) => {
      setMessages(prevMessages => [
        ...prevMessages.filter(m => m.id !== msg.id), // Remove if duplicate
        {
          id: msg.id,
          text: msg.text,
          sender: msg.source,
          timestamp: msg.timestamp,
          isSelf: msg.source === MY_ID,
        }
      ].sort((a, b) => a.timestamp - b.timestamp));
    };
    
    // Listen for broadcasts
    const handleBroadcast = (msg) => {
      setMessages(prevMessages => [
        ...prevMessages.filter(m => m.id !== msg.id), // Remove if duplicate
        {
          id: msg.id,
          text: msg.text,
          sender: msg.source,
          timestamp: msg.timestamp,
          isBroadcast: true,
          isSelf: msg.source === MY_ID,
        }
      ].sort((a, b) => a.timestamp - b.timestamp));
    };
    
    // Listen for sent messages
    const handleMessageSent = (msg) => {
      setMessages(prevMessages => [
        ...prevMessages.filter(m => m.id !== msg.id), // Remove if duplicate
        {
          id: msg.id,
          text: msg.text,
          sender: MY_ID,
          destination: msg.destination,
          timestamp: Date.now(),
          isSelf: true,
          isBroadcast: msg.destination === 'BROADCAST',
        }
      ].sort((a, b) => a.timestamp - b.timestamp));
      
      setSending(false);
    };
    
    // Add event listeners
    messageEvents.on('message', handleNewMessage);
    messageEvents.on('broadcast', handleBroadcast);
    messageEvents.on('messageSent', handleMessageSent);
    
    // Cleanup function
    return () => {
      messageEvents.off('message', handleNewMessage);
      messageEvents.off('broadcast', handleBroadcast);
      messageEvents.off('messageSent', handleMessageSent);
    };
  }, []);
  
  // Keep peer list updated
  useEffect(() => {
    const updatePeers = () => {
      // Get all known peers from routing table
      const routes = router.getAllRoutes();
      const peerList = Object.keys(routes).map(id => ({
        id,
        nextHop: routes[id].nextHop,
        ttl: routes[id].ttl,
      }));
      
      // Always include broadcast option
      const allPeers = [
        { id: 'BROADCAST', name: 'EVERYONE' },
        ...peerList
      ];
      
      setPeers(allPeers);
    };
    
    // Update immediately and every 5 seconds
    updatePeers();
    const interval = setInterval(updatePeers, 5000);
    
    return () => clearInterval(interval);
  }, []);
  
  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (flatListRef.current && messages.length > 0) {
      flatListRef.current.scrollToEnd({ animated: true });
    }
  }, [messages]);
  
  const handleSend = async () => {
    if (!inputText.trim()) return;
    
    // Prevent double-sending
    if (sending) return;
    setSending(true);
    
    try {
      const destination = selectedPeer;
      await sendMessage(inputText, destination);
      
      // Clear input
      setInputText('');
    } catch (error) {
      console.error('Failed to send message:', error);
      Alert.alert('Error', 'Failed to send message. Please try again.');
      setSending(false);
    }
  };
  
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };
  
  const renderMessage = ({ item }) => {
    const isMyMessage = item.isSelf;
    
    return (
      <View 
        style={[
          styles.messageContainer, 
          isMyMessage ? styles.myMessageContainer : styles.theirMessageContainer
        ]}
      >
        {!isMyMessage && (
          <Text style={styles.senderText}>
            {item.sender} {item.isBroadcast ? '(Broadcast)' : ''}
          </Text>
        )}
        <View 
          style={[
            styles.messageBubble, 
            isMyMessage ? styles.myMessageBubble : styles.theirMessageBubble,
            item.isBroadcast && styles.broadcastBubble
          ]}
        >
          <Text style={styles.messageText}>{item.text}</Text>
        </View>
        <Text style={styles.timeText}>{formatTime(item.timestamp)}</Text>
      </View>
    );
  };
  
  const renderEmptyMessages = () => (
    <View style={styles.emptyContainer}>
      <MaterialCommunityIcons name="chat-outline" size={50} color="#B0B0B0" />
      <Text style={styles.emptyText}>No messages yet</Text>
      <Text style={styles.emptySubText}>
        Start a conversation by sending a message to another device or broadcast to everyone.
      </Text>
    </View>
  );
  
  const renderPeerItem = ({ item }) => (
    <TouchableOpacity 
      style={[
        styles.peerItem,
        selectedPeer === item.id && styles.selectedPeerItem
      ]}
      onPress={() => {
        setSelectedPeer(item.id);
        setShowPeerList(false);
      }}
    >
      <MaterialCommunityIcons 
        name={item.id === 'BROADCAST' ? 'broadcast' : 'account'} 
        size={24} 
        color={selectedPeer === item.id ? '#0066cc' : '#444'} 
      />
      <Text style={[
        styles.peerText,
        selectedPeer === item.id && styles.selectedPeerText
      ]}>
        {item.id === 'BROADCAST' ? 'EVERYONE' : item.id}
      </Text>
      {item.ttl && (
        <Text style={styles.peerTtl}>
          {item.ttl} hop{item.ttl !== 1 ? 's' : ''}
        </Text>
      )}
    </TouchableOpacity>
  );
  
  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : null}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 0}
    >
      <FlatList
        ref={flatListRef}
        style={styles.messagesList}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={item => item.id}
        ListEmptyComponent={renderEmptyMessages}
      />
      
      <View style={styles.inputContainer}>
        <TouchableOpacity 
          style={styles.peerSelector} 
          onPress={() => setShowPeerList(!showPeerList)}
        >
          <Text style={styles.peerButtonText}>
            {selectedPeer === 'BROADCAST' ? 'EVERYONE' : selectedPeer}
          </Text>
          <MaterialCommunityIcons 
            name={showPeerList ? 'chevron-up' : 'chevron-down'} 
            size={20} 
            color="#0066cc" 
          />
        </TouchableOpacity>
        
        <TextInput
          style={styles.input}
          placeholder="Type a message..."
          value={inputText}
          onChangeText={setInputText}
          multiline
        />
        
        <TouchableOpacity 
          style={[styles.sendButton, (!inputText.trim() || sending) && styles.disabledSendButton]} 
          onPress={handleSend}
          disabled={!inputText.trim() || sending}
        >
          {sending ? (
            <ActivityIndicator size="small" color="#ffffff" />
          ) : (
            <MaterialCommunityIcons name="send" size={20} color="#fff" />
          )}
        </TouchableOpacity>
      </View>
      
      {showPeerList && (
        <View style={styles.peerListContainer}>
          <FlatList
            data={peers}
            renderItem={renderPeerItem}
            keyExtractor={item => item.id}
            style={styles.peerList}
          />
        </View>
      )}
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  messagesList: {
    flex: 1,
    padding: 10,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
    marginTop: 100,
  },
  emptyText: {
    fontSize: 18,
    color: '#888',
    marginTop: 10,
  },
  emptySubText: {
    fontSize: 14,
    color: '#888',
    textAlign: 'center',
    marginTop: 5,
  },
  messageContainer: {
    marginVertical: 5,
    maxWidth: '80%',
  },
  myMessageContainer: {
    alignSelf: 'flex-end',
  },
  theirMessageContainer: {
    alignSelf: 'flex-start',
  },
  senderText: {
    fontSize: 12,
    color: '#888',
    marginBottom: 2,
    marginLeft: 12,
  },
  messageBubble: {
    padding: 10,
    borderRadius: 20,
    marginBottom: 2,
  },
  myMessageBubble: {
    backgroundColor: '#0066cc',
    borderTopRightRadius: 4,
  },
  theirMessageBubble: {
    backgroundColor: '#e5e5ea',
    borderTopLeftRadius: 4,
  },
  broadcastBubble: {
    backgroundColor: '#9c27b0',
  },
  messageText: {
    color: '#000',
    fontSize: 16,
  },
  myMessageBubble: {
    backgroundColor: '#0066cc',
  },
  theirMessageBubble: {
    backgroundColor: '#e5e5ea',
  },
  broadcastBubble: {
    backgroundColor: '#9c27b0',
  },
  messageText: {
    fontSize: 16,
    color: '#000',
  },
  myMessageBubble: {
    backgroundColor: '#0066cc',
  },
  messageText: {
    fontSize: 16,
  },
  myMessageBubble: {
    backgroundColor: '#0066cc',
  },
  theirMessageBubble: {
    backgroundColor: '#e5e5ea',
  },
  broadcastBubble: {
    backgroundColor: '#9c27b0',
  },
  messageText: {
    fontSize: 16,
  },
  myMessageText: {
    color: '#fff',
  },
  theirMessageText: {
    color: '#000',
  },
  timeText: {
    fontSize: 10,
    color: '#888',
    alignSelf: 'flex-end',
    marginRight: 5,
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 10,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderTopColor: '#e5e5e5',
    alignItems: 'center',
  },
  peerSelector: {
    backgroundColor: '#f0f0f0',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
    marginRight: 10,
    flexDirection: 'row',
    alignItems: 'center',
  },
  peerButtonText: {
    color: '#0066cc',
    marginRight: 5,
    fontSize: 12,
    fontWeight: 'bold',
  },
  input: {
    flex: 1,
    backgroundColor: '#f0f0f0',
    borderRadius: 20,
    paddingHorizontal: 15,
    paddingVertical: 10,
    maxHeight: 100,
  },
  sendButton: {
    backgroundColor: '#0066cc',
    borderRadius: 20,
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 10,
  },
  disabledSendButton: {
    backgroundColor: '#b0c4de',
  },
  peerListContainer: {
    position: 'absolute',
    bottom: 70,
    left: 10,
    right: 10,
    backgroundColor: '#fff',
    borderRadius: 10,
    maxHeight: 200,
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
  },
  peerList: {
    padding: 5,
  },
  peerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  selectedPeerItem: {
    backgroundColor: '#f0f8ff',
  },
  peerText: {
    marginLeft: 10,
    fontSize: 16,
    color: '#444',
  },
  selectedPeerText: {
    color: '#0066cc',
    fontWeight: 'bold',
  },
  peerTtl: {
    marginLeft: 'auto',
    fontSize: 12,
    color: '#888',
  },
});

export default MessagesScreen; 