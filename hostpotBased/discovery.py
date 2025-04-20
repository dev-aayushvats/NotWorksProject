# discovery.py
import socket
import threading
import time
from utils import get_local_ip, get_device_name

BROADCAST_PORT = 50000
BROADCAST_INTERVAL = 3  # seconds
PEERS = {}  # { (ip, port): name }

def broadcast_presence(listen_port):
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = f"{get_device_name()}|{listen_port}"
    while True:
        udp.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
        time.sleep(BROADCAST_INTERVAL)

def listen_for_peers():
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(('', BROADCAST_PORT))
    while True:
        data, addr = udp.recvfrom(1024)
        try:
            name, port = data.decode().split('|')
            ip = addr[0]
            PEERS[(ip, int(port))] = name
        except Exception as e:
            print(f"Failed to decode peer message: {e}")

def start_discovery(listen_port):
    threading.Thread(target=broadcast_presence, args=(listen_port,), daemon=True).start()
    threading.Thread(target=listen_for_peers, daemon=True).start()

def get_peers():
    return PEERS
