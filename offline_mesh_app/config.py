import socket
import uuid
import os
import json

# Network settings
PORT = 5000
BUFFER_SIZE = 4096
BROADCAST_INTERVAL = 10  # seconds
DISCOVERY_INTERVAL = 30  # seconds

# Gateway node settings
IS_HOTSPOT_HOST = False  # Set to True if this device is hosting a hotspot
GATEWAY_BROADCAST_INTERVAL = 20  # seconds

# Node identification
MY_ID = str(uuid.uuid4())[:8]  # Generate a unique ID for this node

# Get the most reliable IP address
def get_best_ip():
    """Attempt to get the most appropriate IP address"""
    try:
        # First try to get the IP used for external connections
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))  # Google's DNS
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            # Fall back to hostname-based approach
            return socket.gethostbyname(socket.gethostname())
        except:
            # Last resort fallback
            return "127.0.0.1"

MY_IP = get_best_ip()

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
        "KNOWN_PEERS": KNOWN_PEERS,
        "IS_HOTSPOT_HOST": IS_HOTSPOT_HOST
    }
    with open("mesh_config.json", "w") as f:
        json.dump(config_data, f)

# Load configuration
def load_config():
    global MY_ID, KNOWN_PEERS, IS_HOTSPOT_HOST
    try:
        if os.path.exists("mesh_config.json"):
            with open("mesh_config.json", "r") as f:
                config_data = json.load(f)
                MY_ID = config_data.get("MY_ID", MY_ID)
                KNOWN_PEERS = config_data.get("KNOWN_PEERS", KNOWN_PEERS)
                IS_HOTSPOT_HOST = config_data.get("IS_HOTSPOT_HOST", IS_HOTSPOT_HOST)
    except Exception as e:
        print(f"Error loading config: {e}")

# Try to load existing configuration
load_config()
