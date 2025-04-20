from threading import Thread
from server.listener import start_server
from client.broadcast import broadcast_routing
from gui.app import run_app

if __name__ == "__main__":
    # Start background TCP server
    server_thread = Thread(target=start_server, daemon=True)
    server_thread.start()

    # Start HSLS routing broadcast thread
    routing_thread = Thread(target=broadcast_routing, daemon=True)
    routing_thread.start()

    # Start periodic peer discovery
    discovery_thread = Thread(target=periodic_discovery, daemon=True)
    discovery_thread.start()

    # Start GUI app (runs in main thread)
    run_app()
