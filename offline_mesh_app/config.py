import socket
import uuid
import os
import json

# Network settings
PORT = 5000
BUFFER_SIZE = 4096
BROADCAST_INTERVAL = 10  # seconds
DISCOVERY_INTERVAL = 30  # seconds

# Node identification
MY_ID = str(uuid.uuid4())[:8]  # Generate a unique ID for this node
MY_IP = socket.gethostbyname(socket.gethostname())

# Network peers
KNOWN_PEERS = []  # Will be populated through discovery

# File transfer settings
CHUNK_SIZE = 8192
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "MeshDownloads")
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Routing settings
MAX_TTL = 3  # Maximum number of hops for a message
ROUTING_TIMEOUT = 60  # Seconds before route is considered stale

# Encryption settings
USE_ENCRYPTION = True
AES_KEY = b'ThisIsA16ByteKey'  # 16-byte key for AES
AES_MODE = 'CBC'

# Cache settings
MESSAGE_CACHE_SIZE = 100
FILE_CACHE_SIZE = 5  # Number of files to cache

# Save configuration
def save_config():
    config_data = {
        "MY_ID": MY_ID,
        "KNOWN_PEERS": KNOWN_PEERS
    }
    with open("mesh_config.json", "w") as f:
        json.dump(config_data, f)

# Load configuration
def load_config():
    global MY_ID, KNOWN_PEERS
    try:
        if os.path.exists("mesh_config.json"):
            with open("mesh_config.json", "r") as f:
                config_data = json.load(f)
                MY_ID = config_data.get("MY_ID", MY_ID)
                KNOWN_PEERS = config_data.get("KNOWN_PEERS", KNOWN_PEERS)
    except Exception as e:
        print(f"Error loading config: {e}")

# Try to load existing configuration
load_config()
