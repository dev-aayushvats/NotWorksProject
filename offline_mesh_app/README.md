# Offline Mesh Network Application

A resilient peer-to-peer mesh network application for communication without traditional infrastructure. This application uses Wi-Fi connections for communication between laptops/computers and enables multi-hop routing, store-and-forward message delivery, and end-to-end encryption.

## Features

- **Peer Discovery**: Automatically finds other nodes on the local network
- **HSLS Routing Protocol**: Implements Hazy-Sighted Link State routing for multi-hop communication
- **Messaging**: Secure text messaging between nodes
- **File Sharing**: Transfer files between nodes with chunking and reassembly
- **End-to-End Encryption**: AES encryption for secure communication
- **Store-and-Forward**: Caches messages until delivery is possible
- **Self-Healing**: Dynamic reconfiguration when nodes join or leave

## Requirements

- Python 3.7 or later
- Dependencies listed in `requirements.txt`
- Computers connected to the same network (Wi-Fi/LAN)

## Installation

1. Clone the repository:
   ```
   git clone <repository_url>
   cd offline_mesh_app
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the application:
   ```
   python main.py
   ```

2. The GUI will open with four tabs:
   - **Messages**: Send and receive text messages
   - **Routing**: View and manage routing information
   - **Files**: Send and receive files
   - **Settings**: Configure node settings and manually add peers

3. **Network Setup**:
   - The application will automatically discover other nodes on the same network
   - You can manually add peers by their IP address in the Settings tab
   - For best results, ensure computers can communicate directly over the network

## Network Setup Instructions

For optimal mesh networking, follow these steps:

1. **Same Network Connection**:
   - Ensure all devices are connected to the same Wi-Fi network
   - Or create a computer-to-computer network using Wi-Fi hotspot functionality

2. **Using Wi-Fi Hotspot** (for offline mesh):
   - On Windows 10/11: Use the Mobile Hotspot feature
   - On macOS: Use Internet Sharing to create a Wi-Fi hotspot
   - On Linux: Use NetworkManager to create a hotspot

3. **Chained Hotspot Configuration**:
   - For devices that create hotspots:
     - Go to the Settings tab in the application
     - Enable the "Hotspot Host Mode" option
     - Restart the application when prompted
   - This marks the device as a gateway that will share peer information
   - Gateway nodes will automatically exchange their peer lists
   - Other nodes can connect through these gateway nodes to reach all parts of the network
   
4. **Multi-Network Mesh**:
   - With gateway nodes enabled, messages can route through multiple network segments
   - For example: NodeA ↔ Hotspot1 ↔ Hotspot2 ↔ NodeB
   - Each hotspot acts as a bridge between different network segments

5. **Firewall Configuration**:
   - Allow incoming connections on port 5000 (TCP)
   - If using Windows, you may need to create an exception in Windows Defender Firewall

## Architecture

- **Routing Protocol**: Hazy-Sighted Link State (HSLS) routing
- **Transport**: TCP for reliable communication
- **Data Security**: AES-256 encryption
- **Node Identification**: UUID-based node IDs
- **File Transfer**: Chunked file transfer with reassembly

## Troubleshooting

- **Peer Discovery Issues**:
  - Ensure you're on the same network
  - Check firewall settings
  - Manually add peers using their IP address

- **Connection Problems**:
  - Verify that port 5000 is not blocked
  - Check network/VPN settings that might interfere with direct connections

## License

[MIT License](LICENSE)

## Contributors

This project was developed as part of a computer networks project. 