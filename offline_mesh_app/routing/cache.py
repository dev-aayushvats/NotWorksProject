import os
import time
import json
import threading
import base64
from collections import OrderedDict
from config import MESSAGE_CACHE_SIZE, FILE_CACHE_SIZE, DOWNLOAD_DIR
from utils.logger import log_routing

class MessageCache:
    def __init__(self, max_size=MESSAGE_CACHE_SIZE):
        self.cache = OrderedDict()  # {message_id: {"data": data, "timestamp": time}}
        self.max_size = max_size
        self.lock = threading.RLock()
    
    def add_message(self, message_id, data):
        """Add a message to the cache"""
        with self.lock:
            # If message already exists, just update its position (most recently used)
            if message_id in self.cache:
                self.cache.move_to_end(message_id)
                return False
            
            # Add new message
            self.cache[message_id] = {
                "data": data,
                "timestamp": time.time()
            }
            self.cache.move_to_end(message_id)
            
            # Remove oldest if exceeding max size
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
            
            return True
    
    def get_message(self, message_id):
        """Get a message from the cache"""
        with self.lock:
            if message_id in self.cache:
                self.cache.move_to_end(message_id)  # Mark as recently used
                return self.cache[message_id]["data"]
            return None
    
    def has_message(self, message_id):
        """Check if a message exists in the cache"""
        with self.lock:
            return message_id in self.cache
    
    def remove_old_messages(self, max_age_seconds=3600):
        """Remove messages older than the specified age"""
        with self.lock:
            current_time = time.time()
            to_remove = []
            
            for message_id, message_data in self.cache.items():
                if current_time - message_data["timestamp"] > max_age_seconds:
                    to_remove.append(message_id)
            
            for message_id in to_remove:
                del self.cache[message_id]
            
            return len(to_remove)


class FileCache:
    def __init__(self, max_size=FILE_CACHE_SIZE):
        self.cache = OrderedDict()  # {file_id: {"chunks": {chunk_index: data}, "total_chunks": total, "filename": name, "timestamp": time}}
        self.max_size = max_size
        self.lock = threading.RLock()
        
        # Create cache directory if it doesn't exist
        self.cache_dir = os.path.join(DOWNLOAD_DIR, "cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def add_file_chunk(self, file_id, chunk_index, chunk_data, total_chunks, filename):
        """Add a file chunk to the cache"""
        with self.lock:
            # If this is a new file, initialize its entry
            if file_id not in self.cache:
                self.cache[file_id] = {
                    "chunks": {},
                    "total_chunks": total_chunks,
                    "filename": filename,
                    "timestamp": time.time()
                }
                self.cache.move_to_end(file_id)
                
                # Remove oldest if exceeding max size
                if len(self.cache) > self.max_size:
                    oldest = self.cache.popitem(last=False)
                    # Also clean up the file if it exists
                    self._cleanup_file(oldest[0])
            
            # Update the timestamp
            self.cache[file_id]["timestamp"] = time.time()
            self.cache.move_to_end(file_id)
            
            # Add the chunk
            self.cache[file_id]["chunks"][chunk_index] = chunk_data
            
            # Check if file is complete
            return self.is_file_complete(file_id)
    
    def get_file_chunk(self, file_id, chunk_index):
        """Get a file chunk from the cache"""
        with self.lock:
            if file_id in self.cache and chunk_index in self.cache[file_id]["chunks"]:
                self.cache.move_to_end(file_id)  # Mark as recently used
                return self.cache[file_id]["chunks"][chunk_index]
            return None
    
    def is_file_complete(self, file_id):
        """Check if all chunks of a file have been received"""
        with self.lock:
            if file_id not in self.cache:
                return False
            
            file_data = self.cache[file_id]
            return len(file_data["chunks"]) == file_data["total_chunks"]
    
    def save_complete_file(self, file_id):
        """Save a complete file to disk"""
        with self.lock:
            if not self.is_file_complete(file_id):
                return None
            
            file_data = self.cache[file_id]
            filename = file_data["filename"]
            output_path = os.path.join(DOWNLOAD_DIR, filename)
            
            # Combine chunks in order
            with open(output_path, "wb") as f:
                for i in range(file_data["total_chunks"]):
                    chunk = file_data["chunks"][i]
                    # If chunk is base64 encoded, decode it
                    if isinstance(chunk, str):
                        try:
                            chunk = base64.b64decode(chunk)
                        except:
                            pass
                    f.write(chunk)
            
            # Remove from cache (no longer needed)
            del self.cache[file_id]
            
            return output_path
    
    def _cleanup_file(self, file_id):
        """Clean up any temporary files for a file ID"""
        temp_path = os.path.join(self.cache_dir, file_id)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                log_routing(file_id, "CACHE_CLEANUP_ERROR", str(e))
    
    def get_pending_files(self):
        """Get list of files in progress and their completion status"""
        with self.lock:
            pending = {}
            for file_id, file_data in self.cache.items():
                pending[file_id] = {
                    "filename": file_data["filename"],
                    "progress": len(file_data["chunks"]) / file_data["total_chunks"],
                    "total_chunks": file_data["total_chunks"]
                }
            return pending
    
    def remove_old_files(self, max_age_seconds=3600):
        """Remove files older than the specified age"""
        with self.lock:
            current_time = time.time()
            to_remove = []
            
            for file_id, file_data in self.cache.items():
                if current_time - file_data["timestamp"] > max_age_seconds:
                    to_remove.append(file_id)
            
            for file_id in to_remove:
                self._cleanup_file(file_id)
                del self.cache[file_id]
            
            return len(to_remove)


# Create global instances
message_cache = MessageCache()
file_cache = FileCache()
