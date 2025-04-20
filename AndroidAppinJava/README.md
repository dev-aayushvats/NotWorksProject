# Mobile Hotspot Mesh Application

An Android-based mesh networking application that enables peer-to-peer communication through mobile hotspots. This application allows devices to discover each other, establish connections, and communicate without traditional internet infrastructure.

## Features

- Mobile hotspot management and control
- Automatic device discovery
- Real-time chat functionality
- Secure communication
- Network state monitoring
- Multicast support for device discovery

## Prerequisites

Before setting up the project, ensure you have the following installed:

1. **Java Development Kit (JDK)**
   - Download and install JDK 11 or later from [Oracle's website](https://www.oracle.com/java/technologies/downloads/)
   - Set JAVA_HOME environment variable

2. **Android Studio**
   - Download and install the latest version from [developer.android.com](https://developer.android.com/studio)
   - During installation, ensure you select:
     - Android SDK
     - Android SDK Platform
     - Android Virtual Device
     - Performance (Intel HAXM)

3. **Android SDK**
   - Minimum SDK version: 21 (Android 5.0)
   - Target SDK version: 33 (Android 13)
   - Required SDK components:
     - Android SDK Build-Tools
     - Android SDK Platform-Tools
     - Android SDK Tools
     - Android Emulator
     - Android SDK Platform

## Project Setup

1. **Open the Repository Folder**


2. **Open in Android Studio**
   - Launch Android Studio
   - Select "Open an existing project"
   - Navigate to and select the project directory

3. **Sync Project**
   - Wait for the project to sync with Gradle
   - If prompted, install any missing SDK components
   - Ensure all dependencies are downloaded

4. **Configure Project Settings**
   - Open `app/build.gradle` and verify:
     ```gradle
     android {
         compileSdkVersion 33
         defaultConfig {
             minSdkVersion 21
             targetSdkVersion 33
             // ... other config
         }
     }
     ```
   - Check `local.properties` has correct SDK path:
     ```properties
     sdk.dir=C\:\\Users\\YourUsername\\AppData\\Local\\Android\\Sdk
     ```

## Building the APK

### Method 1: Using Android Studio

1. **Build APK**
   - Click `Build` → `Build Bundle/APK`
   - Select `APK`
   - It will take some time to generate, a pop up will appear in the bottom left part of the screen where you can click on locate and basically get the app-debug.apk file which is our app


## Installing on Mobile Device

### Method 1: Direct Installation

1. **Enable Developer Options**
   - Go to Settings → About Phone
   - Tap "Build Number" 7 times
   - Return to Settings → Developer Options
   - Enable "USB Debugging"


2. **Install APK**
   - Copy APK to device
   - Open file manager on device
   - Navigate to APK location
   - Tap to install
   - Allow installation from unknown sources if prompted

## Running the Application

1. **First Launch**
   - Open the app
   - Grant required permissions:
     - Internet access
     - Wi-Fi state access
     - Network state access
     - Location access (if required)

2. **Setup Hotspot**
   - Go to Settings → Hotspot
   - Configure hotspot settings:
     - Network name (SSID)
     - Password
     - Security type (WPA2 recommended)

3. **Start Hotspot**
   - Enable hotspot from app
   - Wait for other devices to connect
   - Begin mesh networking