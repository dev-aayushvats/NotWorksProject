import socket
import threading
from server.handler import handle_packet
from config import PORT, BUFFER_SIZE, MY_IP
from utils.logger import network_logger

def handle_connection(conn, addr):
    """Handle a single client connection"""
    try:
        # Log the incoming connection for debugging
        network_logger.info(f"Received connection from {addr[0]}:{addr[1]}")
        
        # Set a timeout to avoid hanging
        conn.settimeout(5)
        
        # Collect all data (may be in multiple parts)
        data = b''
        while True:
            try:
                chunk = conn.recv(BUFFER_SIZE)
                if not chunk:
                    break
                data += chunk
                
                # If size is less than buffer, we likely have all the data
                if len(chunk) < BUFFER_SIZE:
                    break
            except socket.timeout:
                # Timeout reached, process what we have
                network_logger.debug(f"Connection timeout from {addr[0]}, processing available data")
                break
        
        if data:
            network_logger.debug(f"Received {len(data)} bytes from {addr[0]}")
            # Process the packet in a separate thread to avoid blocking
            threading.Thread(
                target=handle_packet, 
                args=(data, addr, conn), 
                daemon=True
            ).start()
        else:
            network_logger.warning(f"Empty data received from {addr[0]}")
    except Exception as e:
        network_logger.error(f"Error handling connection from {addr}: {e}")
    finally:
        conn.close()

def start_server():
    """Start the TCP server to listen for incoming packets"""
    try:
        # Create socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Allow address reuse
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Bind to all interfaces
        s.bind(('', PORT))
        
        # Start listening
        s.listen(10)  # Allow up to 10 pending connections
        
        network_logger.info(f"Server listening on port {PORT} with IP {MY_IP}")
        network_logger.info(f"Ready to accept connections from other peers")
        
        # Accept connections in a loop
        while True:
            try:
                conn, addr = s.accept()
                network_logger.info(f"New connection established from {addr[0]}:{addr[1]}")
                # Handle each connection in a separate thread
                threading.Thread(
                    target=handle_connection,
                    args=(conn, addr),
                    daemon=True
                ).start()
            except Exception as e:
                network_logger.error(f"Error accepting connection: {e}")
    except Exception as e:
        network_logger.error(f"Server error: {e}")
    finally:
        if 's' in locals():
            s.close()
