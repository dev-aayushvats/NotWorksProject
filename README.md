# Offline Mesh Network Communication Project

This repository contains a collection of projects focused on enabling offline communication through mesh networking. Each project implements different approaches to create resilient peer-to-peer networks without relying on traditional internet infrastructure.

## Projects Overview

### 1. Offline Mesh Network Application (Python)

**Directory:** `offline_mesh_app/`

A desktop-based peer-to-peer mesh network application for communication without internet. This Python application uses Wi-Fi connections between laptops/computers and enables multi-hop routing, store-and-forward message delivery, and end-to-end encryption.

**Key Features:**
- Peer discovery on local networks
- HSLS routing protocol for multi-hop communication
- Secure text messaging and file sharing
- End-to-end encryption with AES
- Store-and-forward messaging
- Self-healing network topology

**How to Run:**
```bash
cd offline_mesh_app
pip install -r requirements.txt
python main.py
```

<!-- ### 2. React Native Mesh Network App (Android)

**Directory:** `MeshNetApp/`

A mobile implementation of a peer-to-peer mesh network application for Android. This React Native app uses Wi-Fi connections for communication between mobile devices and implements similar features to the desktop version.

**Key Features:**
- Automatic peer discovery
- Multi-hop message routing
- Secure text messaging
- File sharing with chunking and reassembly
- End-to-end encryption
- Mobile-optimized interface

**How to Run:**
```bash
cd MeshNetApp
npm install --force
npx react-native run-android
```

**Building APK:**
```bash
cd MeshNetApp
npm install --force
cd android
./gradlew assembleRelease
```
The APK will be at: `android/app/build/outputs/apk/release/app-release.apk` -->

### 2. Bluetooth Mesh Network (Android Java)

**Directory:** `Android_Bluetooth/`

An Android application that implements mesh networking over Bluetooth, allowing devices to discover and communicate with each other without internet connectivity.

**Key Features:**
- Bluetooth device discovery
- Direct device-to-device communication
- Chat functionality
- Message forwarding through intermediary devices

**How to Run:**
```bash
# Open in Android Studio
# Build and run on a device with Bluetooth capabilities
```

### 3. Mobile Hotspot Mesh Application (Android Java)

**Directory:** `AndroidAppinJava/`

An Android application that enables mesh networking through mobile hotspots, allowing devices to create, connect to, and communicate through Wi-Fi hotspots.

**Key Features:**
- Mobile hotspot management
- Automatic device discovery
- Real-time chat functionality
- Network state monitoring
- Multicast support

**How to Run:**
```bash
# Open in Android Studio
# Build and run on a device with hotspot capabilities
```

**Building APK:**
```bash
# In Android Studio:
# Build → Build Bundle/APK → APK
```

## Pre-built APKs

For convenience, pre-built APKs are available in the repository root:

- `OfflineBluetooth.apk`: Pre-built version of the Bluetooth Mesh Network app
- `hotspot_implementation.apk`: Pre-built version of the Mobile Hotspot Mesh Application

## Network Setup Instructions

### For Desktop Application
1. **Same Network Connection**:
   - Ensure all devices are connected to the same Wi-Fi network
   - Or create a computer-to-computer network using Wi-Fi hotspot functionality

2. **Firewall Configuration**:
   - Allow incoming connections on port 5000 (TCP)

### For Mobile Applications
1. **Mobile Hotspot Method (Recommended)**:
   - On one device, enable Wi-Fi hotspot
   - Have other devices connect to this hotspot
   - Run the respective app on all devices

2. **Common Wi-Fi Network Method**:
   - Connect all devices to the same Wi-Fi network
   - Note that some public networks may block device-to-device communication

### For Bluetooth Application
1. **Enable Bluetooth**:
   - Enable Bluetooth on all devices
   - Ensure devices are within Bluetooth range (typically ~10 meters)
   - Grant necessary permissions to the app