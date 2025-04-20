# React Native Mesh Network App

A mobile implementation of a peer-to-peer mesh network application for Android that enables offline communication between devices. This app uses Wi-Fi connections for communication and implements multi-hop routing, store-and-forward message delivery, and end-to-end encryption.

## Features

- 🌐 **Peer Discovery**: Automatically finds other devices on the local network
- 🔄 **HSLS Routing Protocol**: Implements Hazy-Sighted Link State routing for multi-hop communication
- 💬 **Messaging**: Secure text messaging between nodes
- 📁 **File Sharing**: Transfer files between devices with chunking and reassembly
- 🔒 **End-to-End Encryption**: AES encryption for secure communication
- 🔄 **Store-and-Forward**: Caches messages until delivery is possible
- 🔁 **Self-Healing**: Dynamic reconfiguration when nodes join or leave

## Requirements

- Android device running Android 5.0 (API level 21) or higher
- React Native development environment
- Devices connected to the same network (Wi-Fi/Hotspot)

## Installation

1. Clone the repository:
   ```
   git clone <repository_url>
   cd MeshNetApp
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Run the app:
   ```
   npx react-native run-android
   ```

## Usage

The app includes four main tabs:

1. **Messages**: Send and receive text messages
   - Select a recipient from the drop-down or send to "EVERYONE" (broadcast)
   - Messages are automatically routed through the mesh network

2. **Routing**: View and manage network topology
   - See all known nodes and direct neighbors
   - Manually trigger discovery or routing broadcasts
   - View routing table with next-hop information

3. **Files**: Send and receive files
   - Send files to specific nodes
   - View download progress
   - Access downloaded files

4. **Settings**: Configure the app
   - View device information (IP, node ID)
   - Toggle server on/off
   - Manually add peers by IP address
   - Clear message and file caches

## Network Setup Instructions

For optimal mesh networking, follow these steps:

### Mobile Hotspot Method (Recommended)

1. **Create a Hotspot**:
   - On one Android device, go to Settings > Network & Internet > Hotspot & Tethering
   - Turn on "Wi-Fi hotspot"
   - Configure a hotspot name and password

2. **Connect Devices**:
   - Have other devices connect to this hotspot
   - Each device should run the Mesh Network App

### Common Wi-Fi Network Method

1. **Connect to the Same Wi-Fi**:
   - Ensure all devices are connected to the same Wi-Fi network
   - Note that some public networks may block device-to-device communication

2. **Run the App**:
   - Start the app on all devices
   - The app will automatically discover other peers on the network

## Android-Specific Considerations

- **Permissions**: The app requires the following permissions:
  - Location (for Wi-Fi scanning)
  - Storage (for file operations)
  - Wi-Fi state (for network operations)

- **Battery Optimization**: To ensure reliable message delivery, disable battery optimization for this app:
  - Settings > Apps > Mesh Network App > Battery > Don't optimize

- **Wi-Fi Behavior**: Some Android devices automatically switch to mobile data when Wi-Fi has no internet connection. Disable this feature:
  - Settings > Network & Internet > Wi-Fi > Wi-Fi preferences > Turn off "Switch to mobile data"

## Troubleshooting

- **Peer Discovery Issues**:
  - Ensure you're on the same network
  - Check that location services are enabled
  - Try adding peers manually in the Settings tab

- **Connection Problems**:
  - Verify that port 5000 is not blocked by a firewall
  - Try restarting the server from the Settings tab
  - Restart the app on all devices

- **File Transfer Failures**:
  - Try sending smaller files
  - Ensure you have sufficient storage space
  - Make sure all devices maintain network connectivity during transfer

## Architecture

This app is built with:

- **React Native**: Cross-platform mobile framework
- **TCP Sockets**: For reliable communication
- **HSLS Routing**: Hazy-Sighted Link State routing protocol
- **MMKV Storage**: For efficient local data caching
- **AES Encryption**: For secure messaging

## License

[MIT License](LICENSE)

## Acknowledgments

Based on the offline mesh networking project designed for computer networks educational purposes.
