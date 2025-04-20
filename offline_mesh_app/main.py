import threading
import time
import os
import sys
from threading import Thread

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import application components
from server.listener import start_server
from client.broadcast import broadcast_routing, periodic_discovery
from gui.app import run_app
from utils.logger import network_logger, routing_logger

def main():
    """Main entry point for the mesh network application"""
    try:
        network_logger.info("Starting Offline Mesh Network Application")
        
        # Create logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        # Start background TCP server
        network_logger.info("Starting TCP server...")
        server_thread = Thread(target=start_server, daemon=True)
        server_thread.start()

        # Start HSLS routing broadcast thread
        routing_logger.info("Starting routing protocol...")
        routing_thread = Thread(target=broadcast_routing, daemon=True)
        routing_thread.start()

        # Start periodic peer discovery
        network_logger.info("Starting peer discovery...")
        discovery_thread = Thread(target=periodic_discovery, daemon=True)
        discovery_thread.start()
        
        # Give time for the network services to initialize
        time.sleep(1)
        
        # Run the GUI application (runs in main thread)
        network_logger.info("Starting GUI application...")
        run_app()
        
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
