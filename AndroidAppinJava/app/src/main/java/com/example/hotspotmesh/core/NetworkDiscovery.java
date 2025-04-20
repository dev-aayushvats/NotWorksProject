package com.example.hotspotmesh.core;

import android.content.Context;
import android.util.Log;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.SocketException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class NetworkDiscovery {
    private static final String TAG = "NetworkDiscovery";
    private static final int DISCOVERY_PORT = 50000;
    private static final int BROADCAST_INTERVAL = 3000; // 3 seconds
    
    private Context context;
    private DatagramSocket discoverySocket;
    private Thread discoveryThread;
    private Thread broadcastThread;
    private Map<String, PeerDevice> discoveredPeers;
    private boolean isRunning;
    private String deviceName;

    public NetworkDiscovery(Context context, String deviceName) {
        this.context = context;
        this.deviceName = deviceName;
        this.discoveredPeers = new ConcurrentHashMap<>();
    }

    public void startDiscovery() {
        if (isRunning) return;
        
        try {
            discoverySocket = new DatagramSocket(DISCOVERY_PORT);
            discoverySocket.setBroadcast(true);
            isRunning = true;

            // Start listening for broadcasts
            discoveryThread = new Thread(() -> {
                byte[] buffer = new byte[1024];
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);

                while (isRunning) {
                    try {
                        discoverySocket.receive(packet);
                        String message = new String(packet.getData(), 0, packet.getLength());
                        handleDiscoveryMessage(message, packet.getAddress());
                    } catch (Exception e) {
                        Log.e(TAG, "Error receiving discovery packet", e);
                    }
                }
            });
            discoveryThread.start();

            // Start broadcasting presence
            broadcastThread = new Thread(() -> {
                while (isRunning) {
                    try {
                        broadcastPresence();
                        Thread.sleep(BROADCAST_INTERVAL);
                    } catch (Exception e) {
                        Log.e(TAG, "Error broadcasting presence", e);
                    }
                }
            });
            broadcastThread.start();

        } catch (SocketException e) {
            Log.e(TAG, "Error creating discovery socket", e);
        }
    }

    private void broadcastPresence() {
        try {
            String message = deviceName + "|" + DISCOVERY_PORT;
            byte[] data = message.getBytes();
            DatagramPacket packet = new DatagramPacket(
                data, 
                data.length,
                InetAddress.getByName("255.255.255.255"),
                DISCOVERY_PORT
            );
            discoverySocket.send(packet);
        } catch (Exception e) {
            Log.e(TAG, "Error broadcasting presence", e);
        }
    }

    private void handleDiscoveryMessage(String message, InetAddress senderAddress) {
        try {
            String[] parts = message.split("\\|");
            if (parts.length == 2) {
                String peerName = parts[0];
                int peerPort = Integer.parseInt(parts[1]);
                
                String peerKey = senderAddress.getHostAddress() + ":" + peerPort;
                PeerDevice peer = discoveredPeers.get(peerKey);
                
                if (peer == null) {
                    peer = new PeerDevice(peerName, senderAddress, peerPort);
                    discoveredPeers.put(peerKey, peer);
                    Log.d(TAG, "New peer discovered: " + peerName);
                } else {
                    peer.updateLastSeen();
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error handling discovery message", e);
        }
    }

    public void stopDiscovery() {
        isRunning = false;
        if (discoveryThread != null) {
            discoveryThread.interrupt();
        }
        if (broadcastThread != null) {
            broadcastThread.interrupt();
        }
        if (discoverySocket != null) {
            discoverySocket.close();
        }
    }

    public Map<String, PeerDevice> getDiscoveredPeers() {
        return discoveredPeers;
    }
}
