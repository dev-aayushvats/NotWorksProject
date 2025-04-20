# chat.py
import socket
import threading
from discovery import start_discovery, get_peers
from utils import get_local_ip, get_device_name

LISTEN_PORT = 50001  # Can make this configurable

def handle_client(conn, addr):
    data = conn.recv(4096)
    if data:
        print(f"\n📩 Message from {addr}: {data.decode()}\n> ", end='')
    conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', LISTEN_PORT))
    server.listen(5)
    print(f"🖥️ Listening for messages on port {LISTEN_PORT}...")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

def send_message(ip, port, message):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, port))
        s.send(message.encode())
        s.close()
    except Exception as e:
        print(f"❌ Failed to send message: {e}")

def main():
    start_discovery(LISTEN_PORT)
    threading.Thread(target=start_server, daemon=True).start()

    while True:
        print("\n🌐 Discovered Peers:")
        peers = get_peers()
        for idx, ((ip, port), name) in enumerate(peers.items()):
            print(f"[{idx}] {name} ({ip}:{port})")

        choice = input("\nEnter peer number to send message (or 'r' to refresh): ")
        if choice == 'r':
            continue
        try:
            idx = int(choice)
            target = list(peers.items())[idx]
            message = input("Enter message: ")
            send_message(target[0][0], target[0][1], message)
        except Exception as e:
            print(f"Invalid choice: {e}")

if __name__ == "__main__":
    main()
