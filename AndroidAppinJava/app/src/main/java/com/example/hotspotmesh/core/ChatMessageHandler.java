package com.example.hotspotmesh.core;

import android.content.Context;
import android.util.Log;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ChatMessageHandler {
    private static final String TAG = "ChatMessageHandler";
    private static final int CHAT_PORT = 50002; // Different port from broadcast
    
    private ServerSocket chatServer;
    private ExecutorService executorService;
    private MessageListener messageListener;
    private boolean isRunning;
    private Context context;

    public interface MessageListener {
        void onMessageReceived(String senderIp, String message);
    }

    public ChatMessageHandler(Context context, MessageListener listener) {
        this.context = context;
        this.messageListener = listener;
        this.executorService = Executors.newFixedThreadPool(1); // Only need one connection for chat
    }

    public void startChatServer() {
        if (isRunning) return;
        
        try {
            chatServer = new ServerSocket(CHAT_PORT);
            isRunning = true;
            
            new Thread(() -> {
                while (isRunning) {
                    try {
                        Socket clientSocket = chatServer.accept();
                        executorService.execute(() -> handleClientConnection(clientSocket));
                    } catch (IOException e) {
                        if (isRunning) {
                            Log.e(TAG, "Error accepting chat connection", e);
                        }
                    }
                }
            }).start();
            
        } catch (IOException e) {
            Log.e(TAG, "Error starting chat server", e);
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
            Log.e(TAG, "Error handling chat connection", e);
        }
    }

    public void sendMessage(String peerIp, String message) {
        executorService.execute(() -> {
            try {
                Socket socket = new Socket(peerIp, CHAT_PORT);
                OutputStream out = socket.getOutputStream();
                out.write((message + "\n").getBytes());
                out.flush();
                socket.close();
                Log.d(TAG, "Chat message sent to " + peerIp);
            } catch (IOException e) {
                Log.e(TAG, "Error sending chat message to " + peerIp, e);
            }
        });
    }

    public void stopChatServer() {
        isRunning = false;
        if (chatServer != null) {
            try {
                chatServer.close();
            } catch (IOException e) {
                Log.e(TAG, "Error closing chat server", e);
            }
        }
        executorService.shutdown();
    }
} 