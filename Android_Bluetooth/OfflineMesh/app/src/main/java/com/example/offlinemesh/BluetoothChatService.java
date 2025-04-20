package com.example.offlinemesh;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothServerSocket;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.os.Handler;
import android.util.Log;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public class BluetoothChatService {

    public static final int MESSAGE_READ = 0;
    public static final int MESSAGE_WRITE = 1;
    public static final int MESSAGE_TOAST = 2;
    public static final int MESSAGE_CONNECTED = 3;
    public static final int MESSAGE_CONNECTION_FAILED = 4;
    public static final int MESSAGE_STATE_CHANGE = 5;
    public static final int MESSAGE_DEVICE_NAME = 6;

    public static final int STATE_NONE = 0;
    public static final int STATE_LISTEN = 1;
    public static final int STATE_CONNECTING = 2;
    public static final int STATE_CONNECTED = 3;

    public static final String DEVICE_NAME = "device_name";
    public static final String TOAST = "toast";

    private static final String TAG = "BluetoothChatService";
    private static final String APP_NAME = "OfflineMesh";
    private static final UUID MY_UUID = UUID.fromString("fa87c0d0-afac-11de-8a39-0800200c9a66");

    private final BluetoothAdapter adapter;
    private Handler handler;
    private final Context context;

    private AcceptThread acceptThread;
    private ConnectThread connectThread;
    private final Map<String, ConnectedThread> connectedThreads = new HashMap<>();

    private String localDeviceAddress = null;

    public BluetoothChatService(Context context, Handler handler) {
        this.context = context;
        this.adapter = BluetoothAdapter.getDefaultAdapter();
        this.handler = handler;
        this.localDeviceAddress = adapter.getAddress();
        start();
    }

    public void setHandler(Handler handler) {
        this.handler = handler;
    }

    public synchronized void start() {
        if (connectThread != null) {
            connectThread.cancel();
            connectThread = null;
        }

        if (acceptThread == null) {
            acceptThread = new AcceptThread();
            acceptThread.start();
        }
    }

    public void stop() {
        if (connectThread != null) {
            connectThread.cancel();
            connectThread = null;
        }

        if (acceptThread != null) {
            acceptThread.cancel();
            acceptThread = null;
        }

        synchronized (connectedThreads) {
            for (ConnectedThread thread : connectedThreads.values()) {
                thread.cancel();
            }
            connectedThreads.clear();
        }
    }

    public void connect(BluetoothDevice device) {
        if (connectThread != null) {
            connectThread.cancel();
        }
        connectThread = new ConnectThread(device);
        connectThread.start();
    }

    public void write(String targetAddress, byte[] bytes) {
        ConnectedThread r;
        synchronized (connectedThreads) {
            r = connectedThreads.get(targetAddress);
        }
        
        if (r == null) {
            if (handler != null) {
                handler.obtainMessage(MESSAGE_TOAST, -1, -1, "Not connected to device: " + targetAddress).sendToTarget();
            }
            return;
        }
        
        try {
            r.write(bytes);
        } catch (SecurityException e) {
            Log.e(TAG, "Bluetooth permission denied", e);
            if (handler != null) {
                handler.obtainMessage(MESSAGE_TOAST, -1, -1, "Bluetooth permission denied").sendToTarget();
            }
        } catch (Exception e) {
            Log.e(TAG, "Error writing data", e);
            if (handler != null) {
                handler.obtainMessage(MESSAGE_TOAST, -1, -1, "Error sending message").sendToTarget();
            }
        }
    }

    public void writeToAll(byte[] bytes) {
        synchronized (connectedThreads) {
            for (ConnectedThread thread : connectedThreads.values()) {
                try {
                    thread.write(bytes);
                } catch (Exception e) {
                    Log.e(TAG, "Error broadcasting message", e);
                }
            }
        }
    }

    public Set<String> getConnectedDevices() {
        synchronized (connectedThreads) {
            return new HashSet<>(connectedThreads.keySet());
        }
    }

    public String getLocalDeviceAddress() {
        return localDeviceAddress;
    }

    private class AcceptThread extends Thread {
        private final BluetoothServerSocket serverSocket;

        public AcceptThread() {
            BluetoothServerSocket tmp = null;
            try {
                tmp = adapter.listenUsingRfcommWithServiceRecord(APP_NAME, MY_UUID);
            } catch (IOException e) {
                Log.e(TAG, "AcceptThread listen failed", e);
            }
            serverSocket = tmp;
        }

        public void run() {
            BluetoothSocket socket;
            while (true) {
                try {
                    socket = serverSocket.accept();
                } catch (IOException e) {
                    Log.e(TAG, "AcceptThread accept() failed", e);
                    handler.obtainMessage(MESSAGE_CONNECTION_FAILED).sendToTarget();
                    break;
                }

                if (socket != null) {
                    manageConnectedSocket(socket);
                    try {
                        serverSocket.close();
                    } catch (IOException e) {
                        Log.e(TAG, "Could not close server socket", e);
                    }
                    break;
                }
            }
        }

        public void cancel() {
            try {
                serverSocket.close();
            } catch (IOException e) {
                Log.e(TAG, "AcceptThread cancel failed", e);
            }
        }
    }

    private class ConnectThread extends Thread {
        private final BluetoothSocket socket;
        private final BluetoothDevice device;

        public ConnectThread(BluetoothDevice device) {
            BluetoothSocket tmp = null;
            this.device = device;

            try {
                tmp = device.createRfcommSocketToServiceRecord(MY_UUID);
            } catch (IOException e) {
                Log.e(TAG, "ConnectThread: Socket creation failed", e);
            }

            socket = tmp;
        }

        public void run() {
            adapter.cancelDiscovery();

            try {
                socket.connect();
                manageConnectedSocket(socket);
            } catch (IOException connectException) {
                Log.e(TAG, "ConnectThread: Unable to connect", connectException);
                handler.obtainMessage(MESSAGE_CONNECTION_FAILED).sendToTarget();
                try {
                    socket.close();
                } catch (IOException closeException) {
                    Log.e(TAG, "Could not close client socket", closeException);
                }
            }
        }

        public void cancel() {
            try {
                socket.close();
            } catch (IOException e) {
                Log.e(TAG, "ConnectThread cancel failed", e);
            }
        }
    }

    private void manageConnectedSocket(BluetoothSocket socket) {
        try {
            String deviceAddress = socket.getRemoteDevice().getAddress();
            Log.d(TAG, "Connected to device: " + deviceAddress);
            
            synchronized (connectedThreads) {
                ConnectedThread existingThread = connectedThreads.get(deviceAddress);
                if (existingThread != null) {
                    existingThread.cancel();
                }
                
                ConnectedThread connectedThread = new ConnectedThread(socket);
                connectedThreads.put(deviceAddress, connectedThread);
                connectedThread.start();
            }
            
            // Add the device to MeshManager
            MeshManager.getInstance(context).addDevice(deviceAddress, this);
            
            // Notify UI of successful connection
            if (handler != null) {
                handler.obtainMessage(MESSAGE_CONNECTED, -1, -1, deviceAddress).sendToTarget();
            }
        } catch (Exception e) {
            Log.e(TAG, "Error managing connected socket", e);
            if (handler != null) {
                handler.obtainMessage(MESSAGE_CONNECTION_FAILED).sendToTarget();
            }
        }
    }

    private class ConnectedThread extends Thread {
        private final BluetoothSocket socket;
        private final InputStream inStream;
        private final OutputStream outStream;
        private volatile boolean running = true;
        private final String deviceAddress;

        public ConnectedThread(BluetoothSocket socket) {
            this.socket = socket;
            this.deviceAddress = socket.getRemoteDevice().getAddress();
            InputStream tmpIn = null;
            OutputStream tmpOut = null;

            try {
                tmpIn = socket.getInputStream();
                tmpOut = socket.getOutputStream();
            } catch (IOException e) {
                Log.e(TAG, "Error getting streams", e);
            }

            inStream = tmpIn;
            outStream = tmpOut;
        }

        public void run() {
            byte[] buffer = new byte[1024];
            int bytes;

            while (running) {
                try {
                    bytes = inStream.read(buffer);
                    if (bytes > 0) {
                        byte[] messageBytes = Arrays.copyOf(buffer, bytes);
                        String message = new String(messageBytes);
                        Log.d(TAG, "Received message from " + deviceAddress + ": " + message);
                        
                        // Pass the message to MeshManager for processing
                        MeshManager.getInstance(context).handleIncomingMessage(
                            deviceAddress, 
                            messageBytes
                        );
                        
                        // Also notify the UI handler
                        if (handler != null) {
                            handler.obtainMessage(MESSAGE_READ, bytes, -1, messageBytes).sendToTarget();
                        }
                    }
                } catch (IOException e) {
                    Log.e(TAG, "Connection lost with " + deviceAddress, e);
                    running = false;
                    synchronized (connectedThreads) {
                        connectedThreads.remove(deviceAddress);
                    }
                    MeshManager.getInstance(context).removeDevice(deviceAddress);
                    if (handler != null) {
                        handler.obtainMessage(MESSAGE_CONNECTION_FAILED).sendToTarget();
                    }
                    break;
                }
            }
        }

        public void write(byte[] bytes) throws IOException {
            if (outStream != null) {
                outStream.write(bytes);
                outStream.flush();
                if (handler != null) {
                    handler.obtainMessage(MESSAGE_WRITE, -1, -1, bytes).sendToTarget();
                }
            } else {
                Log.e(TAG, "Output stream is null for " + deviceAddress);
            }
        }

        public void cancel() {
            running = false;
            try {
                if (socket != null) {
                    socket.close();
                }
            } catch (IOException e) {
                Log.e(TAG, "Socket close failed for " + deviceAddress, e);
            }
        }
    }

}
