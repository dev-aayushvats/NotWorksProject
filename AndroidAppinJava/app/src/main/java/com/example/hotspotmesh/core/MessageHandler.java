package com.example.hotspotmesh.core;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.text.format.Formatter;
import android.util.Log;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MessageHandler {
    private static final String TAG = "MessageHandler";
    private static final int MESSAGE_PORT = 50001;
    private static final int MAX_CONNECTIONS = 10;
    
    private ServerSocket messageServer;
    private ExecutorService executorService;
    private MessageListener messageListener;
    private boolean isRunning;
    private Context context;
    private NetworkDiscovery networkDiscovery;

    public interface MessageListener {
        void onMessageReceived(String senderIp, String message);
    }

    public MessageHandler(Context context, MessageListener listener) {
        this.context = context;
        this.messageListener = listener;
        this.executorService = Executors.newFixedThreadPool(MAX_CONNECTIONS);
    }

    public void setNetworkDiscovery(NetworkDiscovery networkDiscovery) {
        this.networkDiscovery = networkDiscovery;
    }

    public void startMessageServer() {
        if (isRunning) return;
        
        try {
            messageServer = new ServerSocket(MESSAGE_PORT);
            isRunning = true;
            
            new Thread(() -> {
                while (isRunning) {
                    try {
                        Socket clientSocket = messageServer.accept();
                        executorService.execute(() -> handleClientConnection(clientSocket));
                    } catch (IOException e) {
                        if (isRunning) {
                            Log.e(TAG, "Error accepting connection", e);
                        }
                    }
                }
            }).start();
            
        } catch (IOException e) {
            Log.e(TAG, "Error starting message server", e);
        }
    }

    private void handleClientConnection(Socket clientSocket) {
        try {
            BufferedReader reader = new BufferedReader(
                new InputStreamReader(clientSocket.getInputStream())
            );
            
            String message = reader.readLine();
            if (message != null && messageListener != null) {
                messageListener.onMessageReceived(
                    clientSocket.getInetAddress().getHostAddress(),
                    message
                );
            }
            
            clientSocket.close();
        } catch (IOException e) {
            Log.e(TAG, "Error handling client connection", e);
        }
    }

    public void sendMessage(String peerIp, String message) {
        executorService.execute(() -> {
            try {
                Socket socket = new Socket(peerIp, MESSAGE_PORT);
                OutputStream out = socket.getOutputStream();
                out.write((message + "\n").getBytes());
                out.flush();
                socket.close();
                Log.d(TAG, "Message sent to " + peerIp);
            } catch (IOException e) {
                Log.e(TAG, "Error sending message to " + peerIp, e);
            }
        });
    }

    public void broadcastMessage(String message) {
        if (networkDiscovery == null) {
            Log.e(TAG, "NetworkDiscovery not set");
            return;
        }

        Map<String, PeerDevice> peers = networkDiscovery.getDiscoveredPeers();
        String localIp = getLocalIpAddress();
        
        for (PeerDevice peer : peers.values()) {
            String peerIp = peer.getIpAddress().getHostAddress();
            if (!peerIp.equals(localIp)) {
                Log.d(TAG, "Broadcasting to " + peerIp);
                sendMessage(peerIp, message);
            }
        }
    }

    private String getLocalIpAddress() {
        WifiManager wifiManager = (WifiManager) context.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        return Formatter.formatIpAddress(wifiManager.getConnectionInfo().getIpAddress());
    }

    public void stopMessageServer() {
        isRunning = false;
        if (messageServer != null) {
            try {
                messageServer.close();
            } catch (IOException e) {
                Log.e(TAG, "Error closing message server", e);
            }
        }
        executorService.shutdown();
    }
}
