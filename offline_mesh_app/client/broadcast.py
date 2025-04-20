import json
import threading
import time
from client.sender import send_to_peer
from config import KNOWN_PEERS, MY_ID
from routing.router import get_next_hops
import socket
from config import KNOWN_PEERS
from client.sender import send_to_peer

sequence_number = 0

def discover_peers():
    for peer in KNOWN_PEERS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((peer, PORT))
            s.close()
            print(f"[INFO] Peer {peer} is online.")
        except socket.error:
            print(f"[INFO] Peer {peer} is offline.")

def periodic_discovery():
    while True:
        discover_peers()
        time.sleep(30)  # Check every 30 seconds

def broadcast_routing():
    global sequence_number
    while True:
        sequence_number += 1
        packet = {
            "type": "routing",
            "src": MY_ID,
            "neighbors": KNOWN_PEERS,
            "seq": sequence_number
        }
        data = json.dumps(packet)

        # Perform scoped flooding
        for peer in get_next_hops(MY_ID, KNOWN_PEERS):
            send_to_peer(peer, data)

        time.sleep(10)
