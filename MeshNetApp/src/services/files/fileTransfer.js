import RNFS from 'react-native-fs';
import FileViewer from 'react-native-file-viewer';
import { DOWNLOAD_FOLDER } from '../../config/constants';
import { fileCache } from '../routing/cache';
import { Platform } from 'react-native';

// Set up download directory
const setupDownloadDirectory = async () => {
  try {
    const downloadPath = getDownloadPath();
    const exists = await RNFS.exists(downloadPath);
    
    if (!exists) {
      await RNFS.mkdir(downloadPath);
      console.log(`Created download directory: ${downloadPath}`);
    }
    
    return downloadPath;
  } catch (error) {
    console.error('Error setting up download directory:', error);
    return null;
  }
};

// Get download path based on platform
const getDownloadPath = () => {
  if (Platform.OS === 'android') {
    return `${RNFS.ExternalDirectoryPath}/${DOWNLOAD_FOLDER}`;
  } else {
    return `${RNFS.DocumentDirectoryPath}/${DOWNLOAD_FOLDER}`;
  }
};

/**
 * Save a received file from chunks
 * @param {string} fileId - ID of the file to save
 * @returns {Promise<string|null>} - Path to saved file or null if failed
 */
export const saveReceivedFile = async (fileId) => {
  try {
    // Get file metadata
    const metadata = fileCache.getFileMetadata(fileId);
    if (!metadata) {
      console.error(`No metadata found for file ${fileId}`);
      return null;
    }
    
    // Check if all chunks are present
    if (!fileCache.isFileComplete(fileId)) {
      console.error(`File ${fileId} is not complete`);
      return null;
    }
    
    // Set up download directory
    const downloadPath = await setupDownloadDirectory();
    if (!downloadPath) {
      console.error('Failed to set up download directory');
      return null;
    }
    
    // Create file path
    const filePath = `${downloadPath}/${metadata.fileName}`;
    
    // Create empty file
    await RNFS.writeFile(filePath, '', 'utf8');
    
    // Append each chunk
    for (let i = 0; i < metadata.totalChunks; i++) {
      const chunk = fileCache.getChunk(fileId, i);
      if (chunk) {
        // Convert base64 to binary and append to file
        await RNFS.appendFile(filePath, chunk, 'base64');
      } else {
        console.error(`Missing chunk ${i} for file ${fileId}`);
        return null;
      }
    }
    
    console.log(`File saved to ${filePath}`);
    
    return filePath;
  } catch (error) {
    console.error('Error saving file:', error);
    return null;
  }
};

/**
 * Open a file with the default viewer
 * @param {string} filePath - Path to the file
 * @returns {Promise<boolean>} - True if file opened successfully
 */
export const openFile = async (filePath) => {
  try {
    await FileViewer.open(filePath);
    return true;
  } catch (error) {
    console.error('Error opening file:', error);
    return false;
  }
};

/**
 * Get all downloaded files
 * @returns {Promise<string[]>} - Array of file paths
 */
export const getDownloadedFiles = async () => {
  try {
    const downloadPath = getDownloadPath();
    const exists = await RNFS.exists(downloadPath);
    
    if (!exists) {
      await setupDownloadDirectory();
      return [];
    }
    
    // Get files in download directory
    const files = await RNFS.readDir(downloadPath);
    
    // Return file paths
    return files.map(file => file.path);
  } catch (error) {
    console.error('Error getting downloaded files:', error);
    return [];
  }
};

/**
 * Delete a file
 * @param {string} filePath - Path to the file
 * @returns {Promise<boolean>} - True if file deleted successfully
 */
export const deleteFile = async (filePath) => {
  try {
    const exists = await RNFS.exists(filePath);
    
    if (exists) {
      await RNFS.unlink(filePath);
      console.log(`Deleted file: ${filePath}`);
      return true;
    }
    
    return false;
  } catch (error) {
    console.error('Error deleting file:', error);
    return false;
  }
};

// Initialize download directory on module load
setupDownloadDirectory()
  .then(path => console.log(`Download directory: ${path}`))
  .catch(error => console.error('Failed to initialize download directory:', error));