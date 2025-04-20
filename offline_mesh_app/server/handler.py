import json
from routing.router import update_link_state
from config import MY_ID
import os

def handle_file_transfer(conn, addr):
    with open(f"received_file_{addr[1]}.dat", "wb") as f:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            f.write(data)
    print(f"[INFO] File received from {addr}")

def handle_packet(data, addr, conn=None):
    try:
        packet = json.loads(data.decode())
        if packet['type'] == "message":
            print(f"[MESSAGE] {packet['src']} -> {packet['dst']}: {packet['data']}")
        elif packet['type'] == "routing":
            update_link_state(packet['src'], packet['neighbors'], packet['seq'])
            print(f"[ROUTING UPDATE] from {packet['src']}")
        elif packet['type'] == "file":
            handle_file_transfer(conn, addr)
    except Exception as e:
        print(f"[ERROR] Invalid packet: {e}")

