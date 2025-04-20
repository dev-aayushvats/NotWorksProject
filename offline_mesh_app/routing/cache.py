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
                    "timestamp": time.time(),
                    "received_chunks": 0,
                    "last_chunk_time": time.time()
                }
                # Update the files shorthand reference
                self.files[file_id] = self.cache[file_id]
                self.cache.move_to_end(file_id)
                
                # Remove oldest if exceeding max size
                if len(self.cache) > self.max_size:
                    oldest_id, _ = self.cache.popitem(last=False)
                    # Also clean up the file if it exists
                    self._cleanup_file(oldest_id)
                    # Remove from files shorthand
                    if oldest_id in self.files:
                        del self.files[oldest_id]
                
                log_routing(file_id, "FILE_CREATED", f"Created entry for {filename} with {total_chunks} chunks")
            
            # Update the timestamp and last chunk time
            self.cache[file_id]["timestamp"] = time.time()
            self.cache[file_id]["last_chunk_time"] = time.time()
            self.cache.move_to_end(file_id)
            
            # Validate chunk index
            if chunk_index < 0 or chunk_index >= self.cache[file_id]["total_chunks"]:
                log_routing(file_id, "INVALID_CHUNK", f"Received invalid chunk index {chunk_index}, max is {self.cache[file_id]['total_chunks']-1}")
                return False
            
            # Skip if we already have this chunk
            if chunk_index in self.cache[file_id]["chunks"]:
                log_routing(file_id, "DUPLICATE_CHUNK", f"Received duplicate chunk {chunk_index}")
                # Check if file is complete despite receiving a duplicate
                return self.is_file_complete(file_id)
            
            # Validate the chunk data
            if not chunk_data:
                log_routing(file_id, "EMPTY_CHUNK", f"Received empty chunk {chunk_index}")
                return False
            
            # Add the chunk
            try:
                self.cache[file_id]["chunks"][chunk_index] = chunk_data
                self.cache[file_id]["received_chunks"] = len(self.cache[file_id]["chunks"])
                
                # Update files shorthand
                self.files[file_id] = self.cache[file_id]
                
                # Calculate progress percentage
                progress = (self.cache[file_id]["received_chunks"] / self.cache[file_id]["total_chunks"]) * 100
                
                # Log progress at regular intervals
                if (self.cache[file_id]["received_chunks"] % 5 == 0 or 
                    self.cache[file_id]["received_chunks"] == self.cache[file_id]["total_chunks"] or
                    self.cache[file_id]["received_chunks"] == 1):
                    log_routing(file_id, "FILE_PROGRESS", 
                              f"Received {self.cache[file_id]['received_chunks']}/{self.cache[file_id]['total_chunks']} chunks ({progress:.1f}%)")
            except Exception as e:
                log_routing(file_id, "CHUNK_ERROR", f"Error adding chunk {chunk_index}: {e}")
                return False
            
            # Check if file is complete
            is_complete = self.is_file_complete(file_id)
            if is_complete:
                log_routing(file_id, "FILE_COMPLETE", 
                          f"All {self.cache[file_id]['total_chunks']} chunks received for {filename}")
            
            return is_complete
    
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
            if file_id not in self.cache:
                log_routing(file_id, "FILE_SAVE_ERROR", "File not found in cache")
                return None
            
            if not self.is_file_complete(file_id):
                missing = self.get_missing_chunks(file_id)
                missing_count = len(missing)
                log_routing(file_id, "FILE_INCOMPLETE", 
                          f"Cannot save incomplete file. Missing {missing_count} chunks. First few missing: {missing[:5]}...")
                return None
            
            file_data = self.cache[file_id]
            filename = file_data["filename"]
            total_chunks = file_data["total_chunks"]
            
            # Create a safe filename (avoid path traversal)
            safe_filename = os.path.basename(filename)
            
            # Add a timestamp to avoid overwriting existing files
            import time
            timestamp = int(time.time())
            name_parts = os.path.splitext(safe_filename)
            new_filename = f"{name_parts[0]}_{timestamp}{name_parts[1]}"
            
            # Ensure download directory exists
            if not os.path.exists(DOWNLOAD_DIR):
                try:
                    os.makedirs(DOWNLOAD_DIR)
                except Exception as e:
                    log_routing(file_id, "DIR_CREATE_ERROR", f"Failed to create download directory: {e}")
                    return None
                
            # Create a temporary file first, then move to final location
            temp_dir = os.path.join(DOWNLOAD_DIR, "temp")
            if not os.path.exists(temp_dir):
                try:
                    os.makedirs(temp_dir)
                except Exception as e:
                    log_routing(file_id, "DIR_CREATE_ERROR", f"Failed to create temp directory: {e}")
                    return None
                
            temp_path = os.path.join(temp_dir, f"temp_{file_id}_{timestamp}")
            output_path = os.path.join(DOWNLOAD_DIR, new_filename)
            
            try:
                # Combine chunks in order, writing to temporary file first
                log_routing(file_id, "FILE_SAVING", f"Saving {total_chunks} chunks to {new_filename}")
                
                with open(temp_path, "wb") as f:
                    for i in range(total_chunks):
                        if i not in file_data["chunks"]:
                            raise ValueError(f"Missing chunk {i} when saving file {filename}")
                        
                        chunk = file_data["chunks"][i]
                        # If chunk is base64 encoded string, decode it
                        if isinstance(chunk, str):
                            try:
                                chunk = base64.b64decode(chunk)
                            except Exception as e:
                                # If decoding fails, try using it as-is
                                log_routing(file_id, "CHUNK_DECODE_ERROR", f"Error decoding chunk {i}: {e}")
                                chunk = chunk.encode() if isinstance(chunk, str) else chunk
                        
                        # Write chunk to file
                        try:
                            f.write(chunk)
                        except Exception as e:
                            raise IOError(f"Error writing chunk {i} to file: {e}")
                
                # Move from temp location to final location
                import shutil
                try:
                    shutil.move(temp_path, output_path)
                except Exception as e:
                    log_routing(file_id, "FILE_MOVE_ERROR", f"Error moving file from temp location: {e}")
                    # Try to copy instead of move if move fails
                    try:
                        shutil.copy2(temp_path, output_path)
                        os.remove(temp_path)
                    except Exception as e2:
                        log_routing(file_id, "FILE_COPY_ERROR", f"Error copying file: {e2}")
                        return None
                
                # Log success
                log_routing(file_id, "FILE_SAVED", f"Saved to {output_path}")
                
                # Remove from cache (no longer needed)
                del self.cache[file_id]
                if file_id in self.files:
                    del self.files[file_id]
                
                return output_path
                
            except ValueError as e:
                log_routing(file_id, "FILE_SAVE_ERROR", f"Error saving file - missing chunks: {e}")
                return None
            except IOError as e:
                log_routing(file_id, "FILE_SAVE_ERROR", f"Error writing to file: {e}")
                return None
            except Exception as e:
                log_routing(file_id, "FILE_SAVE_ERROR", f"Error saving file: {e}")
                # Try to clean up temp file if it exists
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass
                return None
    
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

    def has_file(self, file_id):
        """Check if a file exists in the cache"""
        with self.lock:
            return file_id in self.cache

    def initialize_file(self, file_id, filename, total_chunks):
        """Initialize a file entry in the cache"""
        with self.lock:
            if file_id not in self.cache:
                self.cache[file_id] = {
                    "chunks": {},
                    "total_chunks": total_chunks,
                    "filename": filename,
                    "timestamp": time.time(),
                    "received_chunks": 0
                }
                # Update the files shorthand reference
                self.files[file_id] = self.cache[file_id]
                self.cache.move_to_end(file_id)
                
                log_routing(file_id, "FILE_INITIALIZED", f"File {filename} with {total_chunks} chunks")
                return True
            return False


# Create global instances
message_cache = MessageCache()
file_cache = FileCache()
