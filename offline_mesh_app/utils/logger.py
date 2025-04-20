import logging
import os
import time
from datetime import datetime

# Create logs directory if it doesn't exist
if not os.path.exists("logs"):
    os.makedirs("logs")

# Configure logging
log_filename = f"logs/mesh_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

# Create loggers for different components
network_logger = logging.getLogger('network')
routing_logger = logging.getLogger('routing')
file_logger = logging.getLogger('file')
gui_logger = logging.getLogger('gui')
security_logger = logging.getLogger('security')

# Message history for GUI display
message_history = []

def log_message(source, destination, content, message_type="TEXT"):
    """Log a message for display in the GUI and in the logs"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    message_entry = {
        "timestamp": timestamp,
        "source": source,
        "destination": destination,
        "content": content,
        "type": message_type
    }
    message_history.append(message_entry)
    
    # Keep only the most recent messages
    if len(message_history) > 100:
        message_history.pop(0)
    
    # Also log to file
    network_logger.info(f"Message {message_type}: {source} -> {destination}: {content}")
    
    return message_entry

def log_routing(node_id, event_type, details=""):
    """Log routing events"""
    routing_logger.info(f"Routing {event_type} from {node_id}: {details}")

def log_file_transfer(filename, source, destination, status, details=""):
    """Log file transfer events"""
    file_logger.info(f"File {filename} from {source} to {destination}: {status} - {details}")

def get_message_history():
    """Get the message history for display"""
    return message_history
