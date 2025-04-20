import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TextInput,
  TouchableOpacity,
  Alert,
  Modal,
  FlatList,
} from 'react-native';
import { Button, Card, List, Divider } from 'react-native-paper';
import { MaterialCommunityIcons } from 'react-native-vector-icons';
import DeviceInfo from 'react-native-device-info';
import { MY_ID, PORT, KNOWN_PEERS } from '../config/constants';
import { startServer, stopServer, isServerRunning } from '../services/discovery/server';
import router from '../services/routing/router';
import { discoverPeers, broadcastRouting } from '../services/discovery/client';
import { messageCache, fileCache } from '../services/routing/cache';
import TcpSocket from 'react-native-tcp-socket';

const SettingsScreen = () => {
  const [deviceName, setDeviceName] = useState('');
  const [myIp, setMyIp] = useState('');
  const [serverActive, setServerActive] = useState(false);
  const [manualIpInput, setManualIpInput] = useState('');
  const [manualPortInput, setManualPortInput] = useState(PORT.toString());
  const [isAddPeerModalVisible, setIsAddPeerModalVisible] = useState(false);
  const [knownPeers, setKnownPeers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  useEffect(() => {
    // Load device information
    loadDeviceInfo();
    
    // Check server status
    checkServerStatus();
    
    // Update peer list
    updatePeerList();
    
    // Set up interval to refresh data
    const interval = setInterval(() => {
      loadDeviceInfo();
      checkServerStatus();
      updatePeerList();
    }, 5000);
    
    return () => clearInterval(interval);
  }, []);
  
  const loadDeviceInfo = async () => {
    try {
      // Get device name
      const name = await DeviceInfo.getDeviceName();
      setDeviceName(name);
      
      // Get IP address
      setMyIp(router.myIP || 'Unknown');
    } catch (error) {
      console.error('Error loading device info:', error);
    }
  };
  
  const checkServerStatus = async () => {
    setServerActive(isServerRunning());
  };
  
  const updatePeerList = () => {
    // Combine known peers from storage and routing table
    const routingPeers = Array.from(router.neighbors);
    const allPeers = [...new Set([...KNOWN_PEERS, ...routingPeers])];
    setKnownPeers(allPeers);
  };
  
  const toggleServer = async () => {
    try {
      if (serverActive) {
        // Stop server
        stopServer();
        setServerActive(false);
      } else {
        // Start server
        await startServer();
        setServerActive(true);
      }
    } catch (error) {
      console.error('Error toggling server:', error);
      Alert.alert('Error', `Failed to ${serverActive ? 'stop' : 'start'} server`);
    }
  };
  
  const handleDiscover = async () => {
    setIsLoading(true);
    try {
      await discoverPeers();
      updatePeerList();
      Alert.alert('Discovery Complete', `Found ${knownPeers.length} peers`);
    } catch (error) {
      console.error('Discovery error:', error);
      Alert.alert('Error', 'Failed to discover peers');
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleBroadcast = async () => {
    setIsLoading(true);
    try {
      await broadcastRouting();
      Alert.alert('Success', 'Routing information broadcast successfully');
    } catch (error) {
      console.error('Broadcast error:', error);
      Alert.alert('Error', 'Failed to broadcast routing information');
    } finally {
      setIsLoading(false);
    }
  };
  
  const addManualPeer = () => {
    // Validate IP format
    const ipRegex = /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    if (!ipRegex.test(manualIpInput)) {
      Alert.alert('Invalid IP', 'Please enter a valid IP address');
      return;
    }
    
    // Check if peer already exists
    if (knownPeers.includes(manualIpInput)) {
      Alert.alert('Duplicate Peer', 'This peer is already in your known peers list');
      return;
    }
    
    // Add to known peers
    KNOWN_PEERS.push(manualIpInput);
    updatePeerList();
    setIsAddPeerModalVisible(false);
    setManualIpInput('');
    
    // Try to connect to the peer
    testPeerConnection(manualIpInput, parseInt(manualPortInput, 10));
  };
  
  const testPeerConnection = (ip, port) => {
    try {
      // Create client socket with short timeout
      const client = TcpSocket.createConnection({
        host: ip,
        port: port || PORT,
        tls: false,
        timeout: 2000 // 2 second timeout
      }, () => {
        console.log(`Successfully connected to ${ip}:${port}`);
        Alert.alert('Success', `Successfully connected to ${ip}:${port}`);
        client.destroy();
      });
      
      // Handle errors
      client.on('error', (error) => {
        console.error(`Connection error to ${ip}:${port}:`, error);
        Alert.alert('Connection Failed', `Could not connect to ${ip}:${port}. The peer might not be online or the port might be incorrect.`);
        client.destroy();
      });
      
      // Handle timeout
      client.on('timeout', () => {
        console.error(`Connection timeout to ${ip}:${port}`);
        Alert.alert('Connection Timeout', `Connection to ${ip}:${port} timed out`);
        client.destroy();
      });
    } catch (error) {
      console.error('Error testing connection:', error);
      Alert.alert('Error', 'Failed to test connection');
    }
  };
  
  const removePeer = (ip) => {
    Alert.alert(
      'Remove Peer',
      `Are you sure you want to remove ${ip} from your known peers?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Remove', 
          style: 'destructive',
          onPress: () => {
            const index = KNOWN_PEERS.indexOf(ip);
            if (index !== -1) {
              KNOWN_PEERS.splice(index, 1);
              updatePeerList();
            }
          }
        }
      ]
    );
  };
  
  const clearCache = () => {
    Alert.alert(
      'Clear Cache',
      'Are you sure you want to clear all message and file caches? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Clear', 
          style: 'destructive',
          onPress: () => {
            messageCache.clearCache();
            // Clear file cache (recreate empty cache)
            fileCache.getAllFileIds().forEach(id => fileCache.removeFile(id));
            Alert.alert('Cache Cleared', 'All message and file caches have been cleared');
          }
        }
      ]
    );
  };
  
  const renderPeerItem = ({ item }) => (
    <List.Item
      title={item}
      left={props => <List.Icon {...props} icon="access-point" />}
      right={props => (
        <TouchableOpacity onPress={() => removePeer(item)}>
          <List.Icon {...props} icon="delete" color="red" />
        </TouchableOpacity>
      )}
    />
  );
  
  return (
    <ScrollView style={styles.container}>
      {/* Device Information */}
      <Card style={styles.card}>
        <Card.Title
          title="Device Information"
          left={(props) => <MaterialCommunityIcons {...props} name="cellphone" size={24} color="#0066cc" />}
        />
        <Card.Content>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Device Name:</Text>
            <Text style={styles.infoValue}>{deviceName}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Node ID:</Text>
            <Text style={styles.infoValue}>{MY_ID}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>IP Address:</Text>
            <Text style={styles.infoValue}>{myIp}</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Port:</Text>
            <Text style={styles.infoValue}>{PORT}</Text>
          </View>
        </Card.Content>
      </Card>
      
      {/* Network Controls */}
      <Card style={styles.card}>
        <Card.Title
          title="Network Controls"
          left={(props) => <MaterialCommunityIcons {...props} name="server-network" size={24} color="#0066cc" />}
        />
        <Card.Content>
          <View style={styles.switchRow}>
            <Text style={styles.switchLabel}>Server Active</Text>
            <Switch
              value={serverActive}
              onValueChange={toggleServer}
              trackColor={{ false: '#d3d3d3', true: '#81b0ff' }}
              thumbColor={serverActive ? '#0066cc' : '#f4f3f4'}
            />
          </View>
          
          <View style={styles.buttonRow}>
            <Button
              mode="contained"
              icon="access-point-network"
              onPress={handleDiscover}
              style={styles.button}
              loading={isLoading}
              disabled={isLoading}
            >
              Discover
            </Button>
            
            <Button
              mode="contained"
              icon="broadcast"
              onPress={handleBroadcast}
              style={styles.button}
              loading={isLoading}
              disabled={isLoading}
            >
              Broadcast
            </Button>
          </View>
        </Card.Content>
      </Card>
      
      {/* Known Peers */}
      <Card style={styles.card}>
        <Card.Title
          title="Known Peers"
          left={(props) => <MaterialCommunityIcons {...props} name="account-group" size={24} color="#0066cc" />}
        />
        <Card.Content>
          {knownPeers.length > 0 ? (
            <FlatList
              data={knownPeers}
              renderItem={renderPeerItem}
              keyExtractor={(item) => item}
              scrollEnabled={false}
            />
          ) : (
            <View style={styles.emptyState}>
              <MaterialCommunityIcons name="account-off" size={40} color="#ccc" />
              <Text style={styles.emptyText}>No peers found</Text>
            </View>
          )}
          
          <Button
            mode="outlined"
            icon="plus"
            onPress={() => setIsAddPeerModalVisible(true)}
            style={styles.addButton}
          >
            Add Peer
          </Button>
        </Card.Content>
      </Card>
      
      {/* Cache Controls */}
      <Card style={styles.card}>
        <Card.Title
          title="Cache Controls"
          left={(props) => <MaterialCommunityIcons {...props} name="cached" size={24} color="#0066cc" />}
        />
        <Card.Content>
          <Button
            mode="outlined"
            icon="delete"
            onPress={clearCache}
            style={styles.dangerButton}
            color="#ff3b30"
          >
            Clear All Caches
          </Button>
        </Card.Content>
      </Card>
      
      {/* Version Information */}
      <Card style={styles.card}>
        <Card.Title
          title="Application Information"
          left={(props) => <MaterialCommunityIcons {...props} name="information" size={24} color="#0066cc" />}
        />
        <Card.Content>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Version:</Text>
            <Text style={styles.infoValue}>1.0.0</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Build:</Text>
            <Text style={styles.infoValue}>1</Text>
          </View>
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Mesh Protocol:</Text>
            <Text style={styles.infoValue}>HSLS v1.0</Text>
          </View>
        </Card.Content>
      </Card>
      
      {/* Add Peer Modal */}
      <Modal
        visible={isAddPeerModalVisible}
        transparent={true}
        animationType="slide"
        onRequestClose={() => setIsAddPeerModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Add Peer</Text>
            
            <Text style={styles.inputLabel}>IP Address:</Text>
            <TextInput
              style={styles.input}
              value={manualIpInput}
              onChangeText={setManualIpInput}
              placeholder="192.168.1.100"
              keyboardType="numeric"
              autoCapitalize="none"
            />
            
            <Text style={styles.inputLabel}>Port (optional):</Text>
            <TextInput
              style={styles.input}
              value={manualPortInput}
              onChangeText={setManualPortInput}
              placeholder={PORT.toString()}
              keyboardType="numeric"
            />
            
            <View style={styles.modalButtons}>
              <Button onPress={() => setIsAddPeerModalVisible(false)}>
                Cancel
              </Button>
              <Button
                mode="contained"
                onPress={addManualPeer}
                disabled={!manualIpInput.trim()}
              >
                Add
              </Button>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16,
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  infoLabel: {
    fontWeight: 'bold',
    color: '#555',
  },
  infoValue: {
    color: '#333',
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  switchLabel: {
    fontSize: 16,
    color: '#333',
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  button: {
    flex: 1,
    marginHorizontal: 4,
    backgroundColor: '#0066cc',
  },
  addButton: {
    marginTop: 16,
    borderColor: '#0066cc',
  },
  dangerButton: {
    borderColor: '#ff3b30',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  emptyText: {
    marginTop: 8,
    color: '#999',
    textAlign: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 8,
    width: '90%',
    padding: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 16,
    color: '#333',
  },
  inputLabel: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 4,
    padding: 8,
    marginBottom: 16,
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
});

export default SettingsScreen; 