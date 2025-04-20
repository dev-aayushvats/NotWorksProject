import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import time
import os
from datetime import datetime

from client.sender import send_message, send_file, broadcast_message
from config import MY_ID, MY_IP, KNOWN_PEERS, save_config, IS_HOTSPOT_HOST
from routing.router import router
from routing.cache import file_cache
from utils.logger import get_message_history, gui_logger
from client.gateway_discovery import start_gateway_service

class MeshNetworkApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Mesh Network - Node {MY_ID}")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)
        
        # Create the main notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.messages_tab = ttk.Frame(self.notebook)
        self.routing_tab = ttk.Frame(self.notebook)
        self.files_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.messages_tab, text="Messages")
        self.notebook.add(self.routing_tab, text="Routing")
        self.notebook.add(self.files_tab, text="Files")
        self.notebook.add(self.settings_tab, text="Settings")
        
        # Set up each tab
        self.setup_messages_tab()
        self.setup_routing_tab()
        self.setup_files_tab()
        self.setup_settings_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set(f"Node ID: {MY_ID} | IP: {MY_IP} | Connected peers: {len(router.neighbors)}")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Start the update threads
        self.setup_periodic_updates()

    def setup_messages_tab(self):
        """Set up the messages tab with chat and peer list"""
        # Create frames
        left_frame = ttk.Frame(self.messages_tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        right_frame = ttk.Frame(self.messages_tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        # Message display area (left frame)
        message_frame = ttk.LabelFrame(left_frame, text="Messages")
        message_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.message_display = scrolledtext.ScrolledText(message_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.message_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Message entry area (left frame bottom)
        entry_frame = ttk.Frame(left_frame)
        entry_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(entry_frame, text="Message:").pack(side=tk.LEFT, padx=5)
        self.message_entry = ttk.Entry(entry_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.message_entry.bind("<Return>", self.send_message)
        
        # Create a frame for the buttons
        button_frame = ttk.Frame(entry_frame)
        button_frame.pack(side=tk.LEFT, padx=5)
        
        # Destination selector
        ttk.Label(button_frame, text="To:").pack(side=tk.LEFT, padx=2)
        self.dest_var = tk.StringVar()
        self.dest_combobox = ttk.Combobox(button_frame, textvariable=self.dest_var, width=10)
        self.dest_combobox.pack(side=tk.LEFT, padx=2)
        self.dest_combobox['values'] = ['ALL']
        self.dest_var.set('ALL')
        
        # Send button
        ttk.Button(button_frame, text="Send", command=self.send_message).pack(side=tk.LEFT, padx=2)
        
        # Peer list (right frame)
        peer_frame = ttk.LabelFrame(right_frame, text="Active Peers")
        peer_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.peer_listbox = tk.Listbox(peer_frame, width=20)
        self.peer_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.peer_listbox.bind('<<ListboxSelect>>', self.on_peer_select)
        
        # Refresh button
        ttk.Button(right_frame, text="Refresh Peers", command=self.refresh_peers).pack(padx=5, pady=5)

    def setup_routing_tab(self):
        """Set up the routing information tab"""
        # Top frame for routing table
        top_frame = ttk.LabelFrame(self.routing_tab, text="Routing Table")
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create Treeview widget
        columns = ("node_id", "next_hop", "ttl", "age", "node_type")
        self.routing_tree = ttk.Treeview(top_frame, columns=columns, show="headings")
        
        # Define headings
        self.routing_tree.heading("node_id", text="Node ID")
        self.routing_tree.heading("next_hop", text="Next Hop")
        self.routing_tree.heading("ttl", text="TTL")
        self.routing_tree.heading("age", text="Age (s)")
        self.routing_tree.heading("node_type", text="Node Type")
        
        # Define columns
        self.routing_tree.column("node_id", width=150)
        self.routing_tree.column("next_hop", width=150)
        self.routing_tree.column("ttl", width=50)
        self.routing_tree.column("age", width=70)
        self.routing_tree.column("node_type", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(top_frame, orient=tk.VERTICAL, command=self.routing_tree.yview)
        self.routing_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.routing_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bottom frame for logs
        bottom_frame = ttk.LabelFrame(self.routing_tab, text="Routing Logs")
        bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.routing_log = scrolledtext.ScrolledText(bottom_frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        self.routing_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(self.routing_tab)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(button_frame, text="Force Update", command=self.force_routing_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Log", command=self.clear_routing_log).pack(side=tk.LEFT, padx=5)

    def setup_files_tab(self):
        """Set up the file transfer tab"""
        # Left frame for sending files
        left_frame = ttk.LabelFrame(self.files_tab, text="Send File")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # File selection
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(file_frame, text="File:").pack(side=tk.LEFT, padx=5)
        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT, padx=5)
        
        # Destination selection
        dest_frame = ttk.Frame(left_frame)
        dest_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(dest_frame, text="Destination:").pack(side=tk.LEFT, padx=5)
        self.file_dest_var = tk.StringVar()
        self.file_dest_combobox = ttk.Combobox(dest_frame, textvariable=self.file_dest_var, width=20)
        self.file_dest_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Send button
        ttk.Button(left_frame, text="Send File", command=self.send_file).pack(padx=5, pady=10)
        
        # Progress frame
        progress_frame = ttk.Frame(left_frame)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(progress_frame, text="Progress:").pack(side=tk.LEFT, padx=5)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, length=200, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Right frame for received files
        right_frame = ttk.LabelFrame(self.files_tab, text="File Transfers")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Transfers list
        columns = ("filename", "status", "progress", "size")
        self.transfers_tree = ttk.Treeview(right_frame, columns=columns, show="headings")
        
        # Define headings
        self.transfers_tree.heading("filename", text="Filename")
        self.transfers_tree.heading("status", text="Status")
        self.transfers_tree.heading("progress", text="Progress")
        self.transfers_tree.heading("size", text="Size")
        
        # Define columns
        self.transfers_tree.column("filename", width=150)
        self.transfers_tree.column("status", width=80)
        self.transfers_tree.column("progress", width=100)
        self.transfers_tree.column("size", width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.transfers_tree.yview)
        self.transfers_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.transfers_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Open downloads folder button
        ttk.Button(right_frame, text="Open Downloads Folder", command=self.open_downloads).pack(padx=5, pady=5)

    def setup_settings_tab(self):
        """Set up the settings tab"""
        # Node information
        info_frame = ttk.LabelFrame(self.settings_tab, text="Node Information")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Node ID: {MY_ID}").pack(anchor=tk.W, padx=10, pady=2)
        ttk.Label(info_frame, text=f"IP Address: {MY_IP}").pack(anchor=tk.W, padx=10, pady=2)
        
        # Hotspot host mode
        hotspot_frame = ttk.LabelFrame(self.settings_tab, text="Hotspot Host Mode")
        hotspot_frame.pack(fill=tk.X, padx=10, pady=5)
        
        description = """Enable this option if this device is hosting a WiFi hotspot.
This will mark this node as a gateway that connects different network segments.
Gateway nodes share information about all connected peers to enable multi-network mesh routing.
Restart the application for changes to take effect."""
        
        ttk.Label(hotspot_frame, text=description, wraplength=600).pack(anchor=tk.W, padx=10, pady=5)
        
        # Hotspot toggle
        toggle_frame = ttk.Frame(hotspot_frame)
        toggle_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.hotspot_var = tk.BooleanVar(value=IS_HOTSPOT_HOST)
        ttk.Checkbutton(toggle_frame, text="Enable Hotspot Host Mode", variable=self.hotspot_var, 
                        command=self.toggle_hotspot_mode).pack(side=tk.LEFT, padx=5)
        
        self.hotspot_status = ttk.Label(toggle_frame, 
                                       text=f"Status: {'ENABLED' if IS_HOTSPOT_HOST else 'DISABLED'}")
        self.hotspot_status.pack(side=tk.LEFT, padx=20)
        
        # Manual peer addition
        peer_frame = ttk.LabelFrame(self.settings_tab, text="Add Peer Manually")
        peer_frame.pack(fill=tk.X, padx=10, pady=5)
        
        peer_entry_frame = ttk.Frame(peer_frame)
        peer_entry_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(peer_entry_frame, text="Peer IP:").pack(side=tk.LEFT, padx=5)
        self.peer_ip_var = tk.StringVar()
        ttk.Entry(peer_entry_frame, textvariable=self.peer_ip_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(peer_entry_frame, text="Add Peer", command=self.add_peer).pack(side=tk.LEFT, padx=5)
        
        # Network discovery
        discovery_frame = ttk.LabelFrame(self.settings_tab, text="Network Discovery")
        discovery_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(discovery_frame, text="Run Network Discovery", command=self.run_discovery).pack(padx=10, pady=10)
        
        # Export/import configuration
        config_frame = ttk.LabelFrame(self.settings_tab, text="Configuration")
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        button_frame = ttk.Frame(config_frame)
        button_frame.pack(padx=10, pady=10)
        
        ttk.Button(button_frame, text="Save Configuration", command=self.save_config).pack(side=tk.LEFT, padx=5)

    def setup_periodic_updates(self):
        """Set up periodic updates for the UI"""
        # Start a thread to update the UI
        self.update_thread = threading.Thread(target=self.update_ui_periodically, daemon=True)
        self.update_thread.start()

    def update_ui_periodically(self):
        """Periodically update the UI with new data"""
        while True:
            try:
                # Update the UI components
                self.update_message_display()
                self.update_peer_list()
                self.update_routing_table()
                self.update_file_transfers()
                self.update_status_bar()
            except Exception as e:
                gui_logger.error(f"Error updating UI: {e}")
            
            # Sleep to avoid consuming too much CPU
            time.sleep(1)

    def update_message_display(self):
        """Update the message display with latest messages"""
        messages = get_message_history()
        
        if not messages:
            return
        
        # Clear and update the message display
        self.message_display.config(state=tk.NORMAL)
        self.message_display.delete(1.0, tk.END)
        
        for msg in messages:
            timestamp = msg.get("timestamp", "")
            source = msg.get("source", "Unknown")
            destination = msg.get("destination", "Unknown")
            content = msg.get("content", "")
            msg_type = msg.get("type", "TEXT")
            
            # Format the message
            if destination == "ALL":
                header = f"[{timestamp}] {source} (BROADCAST): "
            else:
                if source == MY_ID:
                    header = f"[{timestamp}] You → {destination}: "
                else:
                    header = f"[{timestamp}] {source} → {destination}: "
            
            # Add message with formatting
            self.message_display.insert(tk.END, header)
            self.message_display.insert(tk.END, f"{content}\n\n")
        
        self.message_display.see(tk.END)  # Scroll to bottom
        self.message_display.config(state=tk.DISABLED)

    def update_peer_list(self):
        """Update the peer list with active peers"""
        # Get active peers from router
        active_peers = list(router.neighbors)
        
        # Update the peer listbox
        self.peer_listbox.delete(0, tk.END)
        
        # Add all peers
        self.peer_listbox.insert(tk.END, f"ALL (Broadcast)")
        
        for peer_id, route in router.get_all_routes().items():
            self.peer_listbox.insert(tk.END, f"{peer_id} ({route['next_hop']})")
        
        # Update destination comboboxes
        peer_ids = ['ALL'] + list(router.get_all_routes().keys())
        self.dest_combobox['values'] = peer_ids
        self.file_dest_combobox['values'] = peer_ids
        
        if not self.dest_var.get() in peer_ids:
            self.dest_var.set('ALL')
        
        if not self.file_dest_var.get() in peer_ids:
            self.file_dest_var.set(peer_ids[0] if peer_ids else '')

    def update_routing_table(self):
        """Update the routing table display"""
        # Clear the routing tree
        for item in self.routing_tree.get_children():
            self.routing_tree.delete(item)
        
        # Get all active routes
        routes = router.get_all_routes()
        
        # Add routes to the tree
        for node_id, route in routes.items():
            node_type = []
            if route.get("is_gateway", False):
                node_type.append("Gateway")
            if route.get("via_bridge", False):
                node_type.append("Bridge")
            if not node_type:
                node_type.append("Regular")
                
            # Join the node types with commas
            node_type_str = ", ".join(node_type)
            
            self.routing_tree.insert("", tk.END, values=(
                node_id,
                route["next_hop"],
                route["ttl"],
                route["age"],
                node_type_str
            ))

    def update_file_transfers(self):
        """Update the file transfers display"""
        # Clear existing items
        for item in self.transfers_tree.get_children():
            self.transfers_tree.delete(item)
        
        # Get pending file transfers
        pending_files = file_cache.get_pending_files()
        
        # Add file transfers to the table
        for file_id, file_info in pending_files.items():
            filename = file_info['filename']
            progress = f"{int(file_info['progress'] * 100)}%"
            total_chunks = file_info['total_chunks']
            
            self.transfers_tree.insert('', tk.END, values=(
                filename,
                "Receiving",
                progress,
                f"{total_chunks} chunks"
            ))

    def update_status_bar(self):
        """Update the status bar with current information"""
        gateway_status = "Gateway: ✓" if IS_HOTSPOT_HOST else ""
        self.status_var.set(f"Node ID: {MY_ID} | IP: {MY_IP} | Connected peers: {len(router.neighbors)} | {gateway_status}")

    def send_message(self, event=None):
        """Send a message to the selected destination"""
        message = self.message_entry.get().strip()
        destination = self.dest_var.get()
        
        if not message:
            return
        
        try:
            if destination == 'ALL':
                # Broadcast message
                broadcast_message(message)
            else:
                # Send to specific destination
                send_message(destination, message)
            
            # Clear entry
            self.message_entry.delete(0, tk.END)
            
        except Exception as e:
            gui_logger.error(f"Error sending message: {e}")
            self.show_error(f"Failed to send message: {e}")

    def browse_file(self):
        """Open file browser to select a file"""
        file_path = filedialog.askopenfilename()
        if file_path:
            self.file_path_var.set(file_path)

    def send_file(self):
        """Send a file to the selected destination"""
        file_path = self.file_path_var.get()
        destination = self.file_dest_var.get()
        
        if not file_path or not os.path.exists(file_path):
            self.show_error("Please select a valid file")
            return
        
        if not destination or destination == 'ALL':
            self.show_error("Please select a specific destination (not broadcast)")
            return
        
        # Start a thread for sending the file
        threading.Thread(
            target=self.send_file_task,
            args=(file_path, destination),
            daemon=True
        ).start()

    def send_file_task(self, file_path, destination):
        """Background task for sending files"""
        try:
            # Update progress bar
            self.progress_var.set(0)
            
            # Send the file
            result = send_file(destination, file_path)
            
            # Update UI based on result
            if result:
                self.progress_var.set(100)
                self.show_info(f"File sent successfully to {destination}")
            else:
                self.progress_var.set(0)
                self.show_error(f"Failed to send file to {destination}")
                
        except Exception as e:
            gui_logger.error(f"Error in file transfer: {e}")
            self.show_error(f"File transfer error: {e}")
            self.progress_var.set(0)

    def open_downloads(self):
        """Open the downloads folder"""
        try:
            # Open the folder using the default file explorer
            from config import DOWNLOAD_DIR
            if os.path.exists(DOWNLOAD_DIR):
                # Use appropriate command for windows
                os.startfile(DOWNLOAD_DIR)
        except Exception as e:
            gui_logger.error(f"Error opening downloads folder: {e}")
            self.show_error(f"Could not open downloads folder: {e}")

    def on_peer_select(self, event):
        """Handle peer selection in the peer list"""
        selection = self.peer_listbox.curselection()
        if selection:
            peer = self.peer_listbox.get(selection[0])
            # Extract just the peer ID from the display string
            peer_id = peer.split(' ')[0]
            self.dest_var.set(peer_id)

    def refresh_peers(self):
        """Manually refresh the peer list"""
        from client.broadcast import discover_peers
        threading.Thread(target=discover_peers, daemon=True).start()
        self.show_info("Peer discovery started")

    def force_routing_update(self):
        """Force a routing update"""
        from client.broadcast import broadcast_routing_update
        threading.Thread(target=broadcast_routing_update, daemon=True).start()
        self.add_routing_log("Forced routing update sent")

    def clear_routing_log(self):
        """Clear the routing log display"""
        self.routing_log.config(state=tk.NORMAL)
        self.routing_log.delete(1.0, tk.END)
        self.routing_log.config(state=tk.DISABLED)

    def add_routing_log(self, message):
        """Add an entry to the routing log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.routing_log.config(state=tk.NORMAL)
        self.routing_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.routing_log.see(tk.END)
        self.routing_log.config(state=tk.DISABLED)

    def add_peer(self):
        """Manually add a peer to the known peers list"""
        from config import KNOWN_PEERS, save_config
        
        peer_ip = self.peer_ip_var.get().strip()
        if not peer_ip:
            return
        
        if peer_ip not in KNOWN_PEERS:
            KNOWN_PEERS.append(peer_ip)
            save_config()
            self.show_info(f"Added peer {peer_ip}")
            self.peer_ip_var.set("")
            
            # Trigger a routing update
            from client.broadcast import broadcast_routing_update
            threading.Thread(target=broadcast_routing_update, daemon=True).start()
        else:
            self.show_info(f"Peer {peer_ip} already in list")

    def run_discovery(self):
        """Run network discovery"""
        from client.broadcast import discover_peers
        
        # Start discovery in a thread
        def discovery_task():
            self.show_info("Network discovery started")
            new_peers = discover_peers()
            if new_peers:
                self.show_info(f"Found {len(new_peers)} new peers")
            else:
                self.show_info("No new peers found")
        
        threading.Thread(target=discovery_task, daemon=True).start()

    def save_config(self):
        """Save current configuration"""
        save_config()
        self.show_info("Configuration saved")

    def show_info(self, message):
        """Show an info message"""
        messagebox.showinfo("Information", message)

    def show_error(self, message):
        """Show an error message"""
        messagebox.showerror("Error", message)

    def toggle_hotspot_mode(self):
        """Toggle hotspot host mode"""
        try:
            from config import IS_HOTSPOT_HOST
            import json
            
            # Get the new setting
            new_setting = self.hotspot_var.get()
            
            # Update config file
            config_file = "mesh_config.json"
            
            # Load current config
            if os.path.exists(config_file):
                try:
                    with open(config_file, "r") as f:
                        config = json.load(f)
                except json.JSONDecodeError:
                    config = {}
            else:
                config = {}
            
            # Update config
            config["IS_HOTSPOT_HOST"] = new_setting
            
            # Save updated config
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            
            # Update UI
            self.hotspot_status.config(text=f"Status: {'ENABLED' if new_setting else 'DISABLED'}")
            
            # Show message to user
            if new_setting:
                messagebox.showinfo("Hotspot Host Mode", 
                                   "Hotspot host mode has been ENABLED. This device will act as a gateway between networks.\n\nPlease restart the application for changes to take effect.")
            else:
                messagebox.showinfo("Hotspot Host Mode", 
                                   "Hotspot host mode has been DISABLED.\n\nPlease restart the application for changes to take effect.")
                
        except Exception as e:
            self.show_error(f"Error toggling hotspot mode: {e}")

def run_app():
    """Run the mesh network application"""
    root = tk.Tk()
    app = MeshNetworkApp(root)
    root.mainloop() 