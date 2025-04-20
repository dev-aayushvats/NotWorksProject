import tkinter as tk
from client.sender import send_to_peer
from config import KNOWN_PEERS
from routing.router import get_next_hops

def run_app():
    def send():
        msg = entry.get()
        for peer in KNOWN_PEERS:
            send_to_peer(peer, msg)
        entry.delete(0, tk.END)

    def update_peer_list():
        peer_list.delete(0, tk.END)
        for peer in KNOWN_PEERS:
            peer_list.insert(tk.END, peer)

    root = tk.Tk()
    root.title("Offline Mesh Chat")

    tk.Label(root, text="Enter message:").pack()
    entry = tk.Entry(root, width=50)
    entry.pack()

    tk.Button(root, text="Send", command=send).pack()

    tk.Label(root, text="Active Peers:").pack()
    peer_list = tk.Listbox(root, height=10)
    peer_list.pack()

    update_peer_list()  # Initial population of peer list

    root.after(5000, update_peer_list)  # Update peer list every 5 seconds
    root.mainloop()
