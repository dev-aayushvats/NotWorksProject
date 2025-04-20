import threading
import time
import os
import sys
import socket
from threading import Thread

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import application components
from server.listener import start_server
from client.broadcast import broadcast_routing, periodic_discovery
from client.gateway_discovery import start_gateway_service
from gui.app import run_app
from utils.logger import network_logger, routing_logger
from config import MY_ID, MY_IP, PORT, IS_HOTSPOT_HOST

def check_network_status():
    """Check and print network status information"""
    try:
        # Get hostname and IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Try to get a more accurate IP if the above returns a loopback address
        if local_ip.startswith("127."):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # This doesn't actually establish a connection
            s.connect(("8.8.8.8", 53))
            local_ip = s.getsockname()[0]
            s.close()
        
        # Print network information
        print("\n===== NETWORK INFORMATION =====")
        print(f"Hostname: {hostname}")
        print(f"IP Address: {local_ip}")
        print(f"Node ID: {MY_ID}")
        print(f"Configured IP: {MY_IP}")
        print(f"Listening on port: {PORT}")
        print(f"Is Hotspot Host: {IS_HOTSPOT_HOST}")
        print("================================")
        print("\nIf your IP address doesn't match the Configured IP, there might be networking issues.")
        print("Other computers should connect to your actual IP address (shown above).")
        print("\nIf firewall problems persist, try manually adding peers using the Settings tab.")
        print("================================\n")
        
        # Check if the port is already in use
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind(('', PORT))
            test_socket.close()
            print(f"✅ Port {PORT} is available and ready to use.")
        except socket.error:
            print(f"⚠️ WARNING: Port {PORT} may already be in use! The application might not work correctly.")
            
        # Check firewall status (basic check for Windows)
        if sys.platform.startswith('win'):
            try:
                import subprocess
                result = subprocess.run(['netsh', 'advfirewall', 'show', 'currentprofile'], 
                                      capture_output=True, text=True)
                if "State                                 ON" in result.stdout:
                    print("⚠️ Windows Firewall is ON - you may need to allow Python/this app through the firewall.")
                else:
                    print("✅ Windows Firewall appears to be OFF.")
            except Exception:
                print("ℹ️ Could not determine Windows firewall status.")
                
    except Exception as e:
        print(f"Error checking network status: {e}")

def main():
    """Main entry point for the mesh network application"""
    try:
        print("\n===== OFFLINE MESH NETWORK APPLICATION =====")
        network_logger.info("Starting Offline Mesh Network Application")
        
        # Show network status
        check_network_status()
        
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
        
        # Start gateway service if this is a hotspot host
        if IS_HOTSPOT_HOST:
            network_logger.info("Starting gateway service for hotspot hosts...")
            start_gateway_service()
            
        # Give time for the network services to initialize
        time.sleep(1)
        
        # Run the GUI application (runs in main thread)
        network_logger.info("Starting GUI application...")
        print("Application started successfully! The GUI should appear shortly.")
        run_app()
        
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
