import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  Alert,
  RefreshControl,
  Modal,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Card, Button, Divider, FAB, Portal, ProgressBar } from 'react-native-paper';
import { MaterialCommunityIcons } from 'react-native-vector-icons';
import DocumentPicker from 'react-native-document-picker';
import RNFS from 'react-native-fs';
import { MY_ID } from '../config/constants';
import { sendFile } from '../services/discovery/client';
import { messageEvents } from '../services/discovery/handler';
import router from '../services/routing/router';
import { fileCache } from '../services/routing/cache';
import {
  saveReceivedFile,
  getDownloadedFiles,
  openFile,
  deleteFile,
} from '../services/files/fileTransfer';

const FilesScreen = () => {
  const [downloadedFiles, setDownloadedFiles] = useState([]);
  const [incomingFiles, setIncomingFiles] = useState([]);
  const [peers, setPeers] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [pickerVisible, setPickerVisible] = useState(false);
  const [selectedPeer, setSelectedPeer] = useState(null);
  const [sending, setSending] = useState(false);
  const [fileProgress, setFileProgress] = useState({});
  
  // Load files and listen for new ones
  useEffect(() => {
    loadFiles();
    
    // Listen for incoming files
    const handleFileStart = (file) => {
      setIncomingFiles(prev => [
        ...prev.filter(f => f.id !== file.id), // Remove duplicate if exists
        {
          ...file,
          status: 'receiving',
          progress: 0,
        }
      ]);
    };
    
    const handleFileProgress = (progress) => {
      setIncomingFiles(prev => 
        prev.map(file => 
          file.id === progress.id
            ? { ...file, progress: progress.progress, status: 'receiving' }
            : file
        )
      );
    };
    
    const handleFileComplete = (file) => {
      // Update incoming file status
      setIncomingFiles(prev => 
        prev.map(f => 
          f.id === file.id
            ? { ...f, status: 'complete', progress: 1 }
            : f
        )
      );
      
      // Save the file
      saveReceivedFile(file.id)
        .then(filePath => {
          if (filePath) {
            // Reload downloaded files
            loadFiles();
            
            // Alert user
            Alert.alert(
              'File Received',
              `${file.fileName} has been received and saved successfully.`,
              [
                { text: 'OK' },
                { 
                  text: 'Open',
                  onPress: () => openFile(filePath) 
                }
              ]
            );
          }
        });
    };
    
    // Add event listeners
    messageEvents.on('fileStart', handleFileStart);
    messageEvents.on('fileProgress', handleFileProgress);
    messageEvents.on('fileComplete', handleFileComplete);
    
    // Load known peers
    updatePeers();
    const peerInterval = setInterval(updatePeers, 5000);
    
    // Cleanup
    return () => {
      messageEvents.off('fileStart', handleFileStart);
      messageEvents.off('fileProgress', handleFileProgress);
      messageEvents.off('fileComplete', handleFileComplete);
      clearInterval(peerInterval);
    };
  }, []);
  
  const loadFiles = async () => {
    try {
      // Get downloaded files
      const files = await getDownloadedFiles();
      
      // Map files to more user-friendly format
      const fileList = await Promise.all(
        files.map(async (path) => {
          const stat = await RNFS.stat(path);
          const fileName = path.split('/').pop();
          return {
            id: path,
            name: fileName,
            path,
            size: stat.size,
            timestamp: stat.mtime || new Date(),
          };
        })
      );
      
      // Sort by time (newest first)
      fileList.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      
      setDownloadedFiles(fileList);
      
      // Get ongoing file transfers from cache
      const fileIds = fileCache.getAllFileIds();
      const ongoingFiles = fileIds
        .map(id => {
          const metadata = fileCache.getFileMetadata(id);
          if (!metadata) return null;
          
          // Calculate progress
          const progress = metadata.receivedChunks / metadata.totalChunks;
          
          return {
            id,
            fileName: metadata.fileName,
            fileSize: metadata.fileSize,
            source: metadata.source,
            status: progress === 1 ? 'complete' : 'receiving',
            progress,
          };
        })
        .filter(Boolean);
      
      setIncomingFiles(ongoingFiles);
    } catch (error) {
      console.error('Error loading files:', error);
    }
  };
  
  const updatePeers = () => {
    // Get all known peers from routing
    const routes = router.getAllRoutes();
    const peerList = Object.keys(routes).map(id => ({
      id,
      nextHop: routes[id].nextHop,
    }));
    
    setPeers(peerList);
  };
  
  const onRefresh = async () => {
    setRefreshing(true);
    await loadFiles();
    setRefreshing(false);
  };
  
  const openFilePicker = (peer) => {
    setSelectedPeer(peer);
    setPickerVisible(true);
  };
  
  const cancelFilePicker = () => {
    setSelectedPeer(null);
    setPickerVisible(false);
  };
  
  const selectAndSendFile = async () => {
    if (!selectedPeer) return;
    
    try {
      // Pick a file
      const result = await DocumentPicker.pick({
        type: [DocumentPicker.types.allFiles],
      });
      
      // Get file path
      const uri = result[0].uri;
      const filePath = Platform.OS === 'ios' 
        ? uri.replace('file://', '')
        : uri;
      
      // Close picker
      setPickerVisible(false);
      
      // Start sending
      setSending(true);
      
      // Track progress
      const fileId = `sending-${Date.now()}`;
      setFileProgress(prev => ({
        ...prev,
        [fileId]: {
          fileName: result[0].name,
          fileSize: result[0].size,
          progress: 0,
          destination: selectedPeer.id,
        }
      }));
      
      // Progress callback
      const onProgress = (progress, sentChunks, totalChunks) => {
        setFileProgress(prev => ({
          ...prev,
          [fileId]: {
            ...prev[fileId],
            progress,
          }
        }));
      };
      
      // Send the file
      const success = await sendFile(filePath, selectedPeer.id, onProgress);
      
      if (success) {
        Alert.alert('Success', `File sent to ${selectedPeer.id}`);
      } else {
        Alert.alert('Error', 'Failed to send file');
      }
      
      // Cleanup
      setTimeout(() => {
        setFileProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[fileId];
          return newProgress;
        });
      }, 3000);
    } catch (error) {
      if (!DocumentPicker.isCancel(error)) {
        console.error('Error picking file:', error);
        Alert.alert('Error', 'Failed to pick file');
      }
    } finally {
      setSending(false);
      setSelectedPeer(null);
    }
  };
  
  const handleDeleteFile = async (filePath) => {
    try {
      Alert.alert(
        'Delete File',
        'Are you sure you want to delete this file?',
        [
          { text: 'Cancel', style: 'cancel' },
          { 
            text: 'Delete', 
            style: 'destructive',
            onPress: async () => {
              const deleted = await deleteFile(filePath);
              if (deleted) {
                setDownloadedFiles(prev => prev.filter(file => file.path !== filePath));
              }
            }
          }
        ]
      );
    } catch (error) {
      console.error('Error deleting file:', error);
      Alert.alert('Error', 'Failed to delete file');
    }
  };
  
  const handleOpenFile = async (filePath) => {
    try {
      await openFile(filePath);
    } catch (error) {
      console.error('Error opening file:', error);
      Alert.alert('Error', 'Failed to open file');
    }
  };
  
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    return `${parseFloat((bytes / Math.pow(1024, i)).toFixed(2))} ${sizes[i]}`;
  };
  
  const renderDownloadedItem = ({ item }) => (
    <Card style={styles.fileCard}>
      <Card.Content>
        <View style={styles.fileHeader}>
          <MaterialCommunityIcons 
            name={getFileIcon(item.name)} 
            size={24} 
            color="#0066cc" 
          />
          <Text style={styles.fileName} numberOfLines={1}>{item.name}</Text>
        </View>
        
        <View style={styles.fileDetails}>
          <Text style={styles.fileSize}>{formatBytes(item.size)}</Text>
        </View>
      </Card.Content>
      
      <Card.Actions>
        <Button 
          icon="open-in-new" 
          onPress={() => handleOpenFile(item.path)}
        >
          Open
        </Button>
        <Button 
          icon="delete" 
          onPress={() => handleDeleteFile(item.path)}
        >
          Delete
        </Button>
      </Card.Actions>
    </Card>
  );
  
  const renderTransferItem = ({ item }) => (
    <Card style={styles.transferCard}>
      <Card.Content>
        <View style={styles.fileHeader}>
          <MaterialCommunityIcons 
            name={getFileIcon(item.fileName)} 
            size={24} 
            color="#0066cc" 
          />
          <Text style={styles.fileName} numberOfLines={1}>{item.fileName}</Text>
          <Text style={[
            styles.statusBadge, 
            item.status === 'complete' ? styles.completeBadge : styles.receivingBadge
          ]}>
            {item.status === 'complete' ? 'Complete' : 'Receiving'}
          </Text>
        </View>
        
        <Text style={styles.transferInfo}>
          {item.status === 'receiving' 
            ? `Receiving from ${item.source || 'unknown'}`
            : `From ${item.source || 'unknown'}`
          }
        </Text>
        
        <View style={styles.progressContainer}>
          <ProgressBar 
            progress={item.progress} 
            color={item.status === 'complete' ? '#4CAF50' : '#0066cc'} 
            style={styles.progressBar}
          />
          <Text style={styles.progressText}>
            {Math.round(item.progress * 100)}%
          </Text>
        </View>
      </Card.Content>
    </Card>
  );
  
  const renderPeerItem = ({ item }) => (
    <TouchableOpacity
      style={styles.peerItem}
      onPress={() => openFilePicker(item)}
    >
      <MaterialCommunityIcons name="account" size={24} color="#444" />
      <Text style={styles.peerText}>{item.id}</Text>
      <MaterialCommunityIcons name="send" size={20} color="#0066cc" />
    </TouchableOpacity>
  );
  
  // Get appropriate icon based on file extension
  const getFileIcon = (fileName) => {
    const ext = (fileName || '').split('.').pop().toLowerCase();
    
    switch (ext) {
      case 'pdf':
        return 'file-pdf-box';
      case 'doc':
      case 'docx':
        return 'file-word-box';
      case 'xls':
      case 'xlsx':
        return 'file-excel-box';
      case 'ppt':
      case 'pptx':
        return 'file-powerpoint-box';
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
        return 'file-image-box';
      case 'mp3':
      case 'wav':
      case 'ogg':
        return 'file-music-box';
      case 'mp4':
      case 'mov':
      case 'avi':
        return 'file-video-box';
      case 'zip':
      case 'rar':
        return 'file-zip-box';
      default:
        return 'file-outline';
    }
  };
  
  // Render ongoing file transfers
  const renderSendingItems = () => {
    const sendingFiles = Object.entries(fileProgress).map(([id, file]) => (
      <Card key={id} style={styles.transferCard}>
        <Card.Content>
          <View style={styles.fileHeader}>
            <MaterialCommunityIcons 
              name={getFileIcon(file.fileName)} 
              size={24} 
              color="#0066cc" 
            />
            <Text style={styles.fileName} numberOfLines={1}>{file.fileName}</Text>
            <Text style={styles.statusBadge}>Sending</Text>
          </View>
          
          <Text style={styles.transferInfo}>
            To {file.destination}
          </Text>
          
          <View style={styles.progressContainer}>
            <ProgressBar 
              progress={file.progress} 
              color="#4CAF50" 
              style={styles.progressBar}
            />
            <Text style={styles.progressText}>
              {Math.round(file.progress * 100)}%
            </Text>
          </View>
        </Card.Content>
      </Card>
    ));
    
    return sendingFiles;
  };
  
  return (
    <View style={styles.container}>
      <FlatList
        data={downloadedFiles}
        renderItem={renderDownloadedItem}
        keyExtractor={item => item.id}
        ListHeaderComponent={() => (
          <>
            {/* Transfers section */}
            {(incomingFiles.length > 0 || Object.keys(fileProgress).length > 0) && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Ongoing Transfers</Text>
                
                {/* Render sending files */}
                {renderSendingItems()}
                
                {/* Render incoming files */}
                {incomingFiles.map(file => (
                  <Card key={file.id} style={styles.transferCard}>
                    <Card.Content>
                      <View style={styles.fileHeader}>
                        <MaterialCommunityIcons 
                          name={getFileIcon(file.fileName)} 
                          size={24} 
                          color="#0066cc" 
                        />
                        <Text style={styles.fileName} numberOfLines={1}>{file.fileName}</Text>
                        <Text style={[
                          styles.statusBadge, 
                          file.status === 'complete' ? styles.completeBadge : styles.receivingBadge
                        ]}>
                          {file.status === 'complete' ? 'Complete' : 'Receiving'}
                        </Text>
                      </View>
                      
                      <Text style={styles.transferInfo}>
                        {file.status === 'receiving' 
                          ? `Receiving from ${file.source || 'unknown'}`
                          : `From ${file.source || 'unknown'}`
                        }
                      </Text>
                      
                      <View style={styles.progressContainer}>
                        <ProgressBar 
                          progress={file.progress} 
                          color={file.status === 'complete' ? '#4CAF50' : '#0066cc'} 
                          style={styles.progressBar}
                        />
                        <Text style={styles.progressText}>
                          {Math.round(file.progress * 100)}%
                        </Text>
                      </View>
                    </Card.Content>
                  </Card>
                ))}
              </View>
            )}
            
            {/* Downloaded files section */}
            <Text style={styles.sectionTitle}>Downloaded Files</Text>
            {downloadedFiles.length === 0 && (
              <View style={styles.emptyState}>
                <MaterialCommunityIcons name="file-outline" size={40} color="#ccc" />
                <Text style={styles.emptyText}>No files downloaded yet</Text>
              </View>
            )}
          </>
        )}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      />
      
      {/* FAB for sending files */}
      <FAB
        style={styles.fab}
        icon="send"
        label="Send File"
        onPress={() => setPickerVisible(true)}
      />
      
      {/* Peer selection modal */}
      <Modal
        visible={pickerVisible}
        transparent={true}
        animationType="slide"
        onRequestClose={cancelFilePicker}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Select recipient</Text>
            
            {peers.length > 0 ? (
              <FlatList
                data={peers}
                renderItem={renderPeerItem}
                keyExtractor={item => item.id}
                style={styles.peerList}
              />
            ) : (
              <View style={styles.emptyState}>
                <MaterialCommunityIcons name="account-off" size={40} color="#ccc" />
                <Text style={styles.emptyText}>No peers available</Text>
              </View>
            )}
            
            <View style={styles.modalButtons}>
              <Button onPress={cancelFilePicker}>Cancel</Button>
              {selectedPeer && (
                <Button 
                  mode="contained" 
                  onPress={selectAndSendFile}
                  loading={sending}
                  disabled={sending}
                >
                  Choose File
                </Button>
              )}
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
    marginTop: 8,
  },
  fileCard: {
    marginBottom: 12,
    elevation: 2,
  },
  transferCard: {
    marginBottom: 8,
    elevation: 1,
  },
  fileHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  fileName: {
    fontSize: 16,
    marginLeft: 8,
    flex: 1,
    color: '#333',
  },
  fileDetails: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  fileSize: {
    fontSize: 14,
    color: '#666',
  },
  statusBadge: {
    fontSize: 12,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    overflow: 'hidden',
  },
  receivingBadge: {
    backgroundColor: '#E3F2FD',
    color: '#0066cc',
  },
  completeBadge: {
    backgroundColor: '#E8F5E9',
    color: '#4CAF50',
  },
  transferInfo: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  progressContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  progressBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
  },
  progressText: {
    marginLeft: 8,
    fontSize: 12,
    color: '#666',
    width: 40,
    textAlign: 'right',
  },
  emptyState: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    backgroundColor: '#fff',
    borderRadius: 8,
    marginVertical: 8,
  },
  emptyText: {
    marginTop: 8,
    color: '#999',
    textAlign: 'center',
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
    backgroundColor: '#0066cc',
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
    maxHeight: '80%',
    padding: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 16,
    color: '#333',
  },
  peerList: {
    maxHeight: 300,
  },
  peerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  peerText: {
    fontSize: 16,
    color: '#333',
    flex: 1,
    marginLeft: 8,
  },
  modalButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
});

export default FilesScreen; 