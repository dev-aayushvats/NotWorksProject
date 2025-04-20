import socket
import threading
import time

# Global list of discovered devices
devices = {}

# Lock for thread safety
devices_lock = threading.Lock()

# UDP broadcast settings
UDP_PORT = 50000
TCP_PORT = 50001
BUFFER_SIZE = 1024

def get_my_ip():
    # Get your own IP address
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def listen_for_devices():
    # Listen for incoming broadcasts
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.bind(('', UDP_PORT))

    while True:
        try:
            data, addr = udp_sock.recvfrom(1024)
            device_name = data.decode()
            with devices_lock:
                devices[addr[0]] = device_name
        except Exception as e:
            print(f"Error receiving broadcast: {e}")

def broadcast_myself(name):
    # Periodically broadcast your name
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = name.encode()

    while True:
        try:
            udp_sock.sendto(message, ('<broadcast>', UDP_PORT))
        except Exception as e:
            print(f"Error broadcasting: {e}")
        time.sleep(2)  # Broadcast every 2 seconds

def send_message(ip, message):
    try:
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((ip, TCP_PORT))
        tcp_sock.sendall(message.encode())
        tcp_sock.close()
    except Exception as e:
        print(f"Error sending message: {e}")

def receive_messages():
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_server.bind(('', TCP_PORT))
    tcp_server.listen(5)

    while True:
        try:
            conn, addr = tcp_server.accept()
            data = conn.recv(BUFFER_SIZE)
            if data:
                print(f"\n📨 Message from {addr[0]} ({devices.get(addr[0], 'Unknown')}): {data.decode()}\n")
            conn.close()
        except Exception as e:
            print(f"Error receiving message: {e}")

def main():
    my_name = input("Enter your name: ")

    # Start discovery threads
    threading.Thread(target=listen_for_devices, daemon=True).start()
    threading.Thread(target=broadcast_myself, args=(my_name,), daemon=True).start()
    threading.Thread(target=receive_messages, daemon=True).start()

    time.sleep(2)  # Small wait for devices to populate

    while True:
        print("\n===== MENU =====")
        print("1. Show discovered devices")
        print("2. Send a message")
        print("3. Refresh devices list")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            with devices_lock:
                if devices:
                    for idx, (ip, name) in enumerate(devices.items(), start=1):
                        print(f"{idx}. {name} ({ip})")
                else:
                    print("No devices discovered yet.")
        elif choice == '2':
            with devices_lock:
                device_list = list(devices.items())
            if not device_list:
                print("No devices to message.")
                continue
            for idx, (ip, name) in enumerate(device_list, start=1):
                print(f"{idx}. {name} ({ip})")
            try:
                selected = int(input("Select device number: ")) - 1
                ip, name = device_list[selected]
                msg = input(f"Enter message to {name}: ")
                send_message(ip, msg)
            except (IndexError, ValueError):
                print("Invalid selection.")
        elif choice == '3':
            print("🔄 Refreshing device list...")
            # Actually, device list updates automatically. 
            # Just redisplay them to simulate "refresh".
            with devices_lock:
                if devices:
                    for idx, (ip, name) in enumerate(devices.items(), start=1):
                        print(f"{idx}. {name} ({ip})")
                else:
                    print("No devices discovered yet.")
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
