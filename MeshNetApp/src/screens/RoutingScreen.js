import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  FlatList,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Card, Divider, Button } from 'react-native-paper';
import { MaterialCommunityIcons } from 'react-native-vector-icons';
import { MY_ID } from '../config/constants';
import router from '../services/routing/router';
import { broadcastRouting, discoverPeers } from '../services/discovery/client';

const RoutingScreen = () => {
  const [routes, setRoutes] = useState({});
  const [neighbors, setNeighbors] = useState([]);
  const [myIp, setMyIp] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);
  
  // Load routes and update periodically
  useEffect(() => {
    loadRoutingInfo();
    
    // Update every 5 seconds
    const interval = setInterval(loadRoutingInfo, 5000);
    
    return () => clearInterval(interval);
  }, []);
  
  const loadRoutingInfo = () => {
    // Get all routes
    const allRoutes = router.getAllRoutes();
    setRoutes(allRoutes);
    
    // Get direct neighbors
    setNeighbors(Array.from(router.neighbors));
    
    // Get our IP
    setMyIp(router.myIP || 'Unknown');
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    loadRoutingInfo();
    setRefreshing(false);
  };
  
  const handleDiscover = async () => {
    if (discovering) return;
    
    setDiscovering(true);
    try {
      await discoverPeers();
      loadRoutingInfo();
    } catch (error) {
      console.error('Discovery error:', error);
      Alert.alert('Error', 'Failed to discover peers');
    } finally {
      setDiscovering(false);
    }
  };
  
  const handleBroadcast = async () => {
    if (broadcasting) return;
    
    setBroadcasting(true);
    try {
      await broadcastRouting();
      loadRoutingInfo();
    } catch (error) {
      console.error('Broadcast error:', error);
      Alert.alert('Error', 'Failed to broadcast routing information');
    } finally {
      setBroadcasting(false);
    }
  };
  
  const renderRouteItem = ({ item }) => {
    const nodeId = item.key;
    const route = item.value;
    
    return (
      <Card style={styles.routeCard}>
        <Card.Content>
          <View style={styles.routeHeader}>
            <Text style={styles.nodeIdText}>{nodeId}</Text>
            <Text style={styles.hopCountText}>
              {route.ttl} hop{route.ttl !== 1 ? 's' : ''}
            </Text>
          </View>
          
          <Divider style={styles.divider} />
          
          <View style={styles.routeDetails}>
            <View style={styles.routeInfoItem}>
              <MaterialCommunityIcons name="access-point-network" size={18} color="#666" />
              <Text style={styles.routeInfoText}>Via: {route.nextHop}</Text>
            </View>
            
            <View style={styles.routeInfoItem}>
              <MaterialCommunityIcons name="clock-outline" size={18} color="#666" />
              <Text style={styles.routeInfoText}>Age: {route.age}s</Text>
            </View>
          </View>
        </Card.Content>
      </Card>
    );
  };
  
  const renderNeighborItem = ({ item }) => (
    <View style={styles.neighborItem}>
      <MaterialCommunityIcons name="access-point" size={18} color="#0066cc" />
      <Text style={styles.neighborText}>{item}</Text>
    </View>
  );
  
  const routeItems = Object.entries(routes).map(([key, value]) => ({
    key,
    value
  }));
  
  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Node info section */}
        <Card style={styles.infoCard}>
          <Card.Title
            title="Node Information"
            left={(props) => <MaterialCommunityIcons {...props} name="information-outline" size={24} color="#0066cc" />}
          />
          <Card.Content>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Node ID:</Text>
              <Text style={styles.infoValue}>{MY_ID}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>IP Address:</Text>
              <Text style={styles.infoValue}>{myIp}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Direct Neighbors:</Text>
              <Text style={styles.infoValue}>{neighbors.length}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Known Nodes:</Text>
              <Text style={styles.infoValue}>{Object.keys(routes).length}</Text>
            </View>
          </Card.Content>
        </Card>
        
        {/* Actions section */}
        <View style={styles.actionsContainer}>
          <Button
            mode="contained"
            onPress={handleDiscover}
            style={styles.actionButton}
            loading={discovering}
            disabled={discovering}
            icon={({ size, color }) => (
              <MaterialCommunityIcons name="access-point-network" size={size} color={color} />
            )}
          >
            Discover Peers
          </Button>
          
          <Button
            mode="contained"
            onPress={handleBroadcast}
            style={styles.actionButton}
            loading={broadcasting}
            disabled={broadcasting}
            icon={({ size, color }) => (
              <MaterialCommunityIcons name="broadcast" size={size} color={color} />
            )}
          >
            Broadcast Routes
          </Button>
        </View>
        
        {/* Direct neighbors section */}
        <Card style={styles.card}>
          <Card.Title
            title="Direct Neighbors"
            left={(props) => <MaterialCommunityIcons {...props} name="access-point" size={24} color="#0066cc" />}
          />
          <Card.Content>
            {neighbors.length > 0 ? (
              <FlatList
                data={neighbors}
                renderItem={renderNeighborItem}
                keyExtractor={(item) => item}
                scrollEnabled={false}
              />
            ) : (
              <View style={styles.emptyState}>
                <MaterialCommunityIcons name="access-point-network-off" size={40} color="#ccc" />
                <Text style={styles.emptyText}>No direct neighbors found</Text>
              </View>
            )}
          </Card.Content>
        </Card>
        
        {/* Routes section */}
        <Card style={styles.card}>
          <Card.Title
            title="Routing Table"
            left={(props) => <MaterialCommunityIcons {...props} name="table-network" size={24} color="#0066cc" />}
          />
          <Card.Content>
            {routeItems.length > 0 ? (
              <FlatList
                data={routeItems}
                renderItem={renderRouteItem}
                keyExtractor={(item) => item.key}
                scrollEnabled={false}
              />
            ) : (
              <View style={styles.emptyState}>
                <MaterialCommunityIcons name="table-off" size={40} color="#ccc" />
                <Text style={styles.emptyText}>No routes found</Text>
              </View>
            )}
          </Card.Content>
        </Card>
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  scrollContent: {
    padding: 16,
  },
  infoCard: {
    marginBottom: 16,
    elevation: 2,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  infoLabel: {
    fontWeight: 'bold',
    color: '#555',
  },
  infoValue: {
    color: '#333',
  },
  actionsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  actionButton: {
    flex: 1,
    marginHorizontal: 4,
    backgroundColor: '#0066cc',
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  routeCard: {
    marginBottom: 8,
    elevation: 1,
  },
  routeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  nodeIdText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  hopCountText: {
    backgroundColor: '#0066cc',
    color: 'white',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    fontSize: 12,
  },
  divider: {
    marginVertical: 8,
  },
  routeDetails: {
    marginTop: 4,
  },
  routeInfoItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  routeInfoText: {
    marginLeft: 8,
    color: '#666',
  },
  neighborItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 4,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  neighborText: {
    marginLeft: 8,
    color: '#333',
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
});

export default RoutingScreen; 