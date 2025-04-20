import React, { useEffect, useState } from 'react';
import { SafeAreaView, StatusBar, StyleSheet, View, Text, Alert } from 'react-native';
import { Provider as PaperProvider } from 'react-native-paper';
import { requestMultiple, PERMISSIONS, RESULTS } from 'react-native-permissions';
import { startServer } from './src/services/discovery/server';
import { discoverPeers, broadcastRouting } from './src/services/discovery/client';
import AppNavigator from './src/navigation';

// Main app component
const App = () => {
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState(null);

  // Initialize mesh network on app start
  useEffect(() => {
    const initMeshNetwork = async () => {
      try {
        // Request permissions first
        const permissionResult = await requestPermissions();
        
        if (!permissionResult) {
          setError('Required permissions not granted. Some features may not work properly.');
          setInitializing(false);
          return;
        }
        
        // Start server
        await startServer();
        console.log('Mesh server started successfully');
        
        // Discover peers (run in background)
        discoverPeers().then(() => {
          console.log('Peer discovery completed');
          
          // Broadcast routing information
          return broadcastRouting();
        }).then(() => {
          console.log('Routing information broadcasted');
        }).catch(err => {
          console.error('Background network initialization error:', err);
        });
        
        // Setup periodic routing broadcasts
        const routingInterval = setInterval(() => {
          broadcastRouting().catch(err => {
            console.error('Periodic routing broadcast error:', err);
          });
        }, 30000); // Every 30 seconds
        
        // Setup periodic peer discovery
        const discoveryInterval = setInterval(() => {
          discoverPeers().catch(err => {
            console.error('Periodic peer discovery error:', err);
          });
        }, 60000); // Every 60 seconds
        
        // Cleanup function
        return () => {
          clearInterval(routingInterval);
          clearInterval(discoveryInterval);
        };
      } catch (err) {
        console.error('Error initializing mesh network:', err);
        setError('Failed to initialize mesh network. Please restart the app.');
      } finally {
        setInitializing(false);
      }
    };
    
    initMeshNetwork();
  }, []);
  
  // Request required permissions
  const requestPermissions = async () => {
    try {
      // Determine which permissions to request based on platform
      const permissions = [
        PERMISSIONS.ANDROID.ACCESS_FINE_LOCATION,
        PERMISSIONS.ANDROID.ACCESS_WIFI_STATE,
        PERMISSIONS.ANDROID.CHANGE_WIFI_STATE,
      ];
      
      // Request permissions
      const results = await requestMultiple(permissions);
      
      // Check results
      const allGranted = Object.values(results).every(
        result => result === RESULTS.GRANTED || result === RESULTS.LIMITED
      );
      
      if (!allGranted) {
        // Show alert if permissions not granted
        Alert.alert(
          'Permissions Required',
          'This app requires location and WiFi permissions to function properly.',
          [{ text: 'OK' }]
        );
        return false;
      }
      
      return true;
    } catch (error) {
      console.error('Error requesting permissions:', error);
      return false;
    }
  };
  
  // Show loading screen while initializing
  if (initializing) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="dark-content" backgroundColor="#f5f5f5" />
        <View style={styles.centerContent}>
          <Text style={styles.loadingText}>Initializing Mesh Network...</Text>
        </View>
      </SafeAreaView>
    );
  }
  
  // Show main app
  return (
    <PaperProvider>
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="dark-content" backgroundColor="#0066cc" />
        {error ? (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}
        <AppNavigator />
      </SafeAreaView>
    </PaperProvider>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  loadingText: {
    fontSize: 18,
    color: '#0066cc',
    textAlign: 'center',
  },
  errorContainer: {
    backgroundColor: '#ffcccc',
    padding: 10,
    margin: 10,
    borderRadius: 5,
  },
  errorText: {
    color: '#cc0000',
    textAlign: 'center',
  },
});

export default App; 