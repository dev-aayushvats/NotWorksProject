import socket
from config import PORT
import os


def chunk_file(file_path, chunk_size=1024):
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk

def send_file_to_peer(ip, file_path):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, PORT))

        for chunk in chunk_file(file_path):
            s.sendall(chunk)
        
        s.close()
        print(f"[INFO] File sent to {ip}")
    except Exception as e:
        print(f"[ERROR] Could not send file to {ip}: {e}")


def send_to_peer(ip, data):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((ip, PORT))
        s.sendall(data.encode())
        s.close()
    except Exception as e:
        print(f"[ERROR] Could not send to {ip}: {e}")
