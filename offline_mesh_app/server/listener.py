import socket
from server.handler import handle_packet
from config import PORT, BUFFER_SIZE

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', PORT))
    s.listen(5)
    print(f"[LISTENING] on port {PORT}")
    while True:
        conn, addr = s.accept()
        data = conn.recv(BUFFER_SIZE)
        handle_packet(data, addr)
        conn.close()
