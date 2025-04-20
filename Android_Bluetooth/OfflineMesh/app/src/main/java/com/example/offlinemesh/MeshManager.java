package com.example.offlinemesh;

import android.bluetooth.BluetoothAdapter;
import android.content.Context;
import android.os.Handler;
import android.util.Log;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public class MeshManager {
    private static final String TAG = "MeshManager";
    
    // Message types for mesh communication
    public static final int MESSAGE_TYPE_CHAT = 1;
    public static final int MESSAGE_TYPE_DEVICE_INFO = 2;
    public static final int MESSAGE_TYPE_ROUTE_UPDATE = 3;
    
    // Singleton instance
    private static MeshManager instance;
    
    // Map of device addresses to their chat services
    private final Map<String, BluetoothChatService> deviceConnections;
    
    // Set of known devices in the mesh
    private final Set<String> knownDevices;
    
    // Message routing table (target -> next hop)
    private final Map<String, String> routingTable;
    
    // Handler for UI updates
    private Handler uiHandler;
    
    // Device's own Bluetooth address
    private String ownAddress;

    private final Map<String, String> idToMacMap;  // Maps device IDs to MAC addresses
    private final Map<String, String> macToIdMap;  // Maps MAC addresses to device IDs
    private String ownId;
    private final Context context;

    private MeshManager(Context context) {
        this.context = context;
        deviceConnections = new HashMap<>();
        knownDevices = new HashSet<>();
        routingTable = new HashMap<>();
        idToMacMap = new HashMap<>();
        macToIdMap = new HashMap<>();
        ownId = DeviceManager.getInstance(context).getDeviceId();
    }

    public static synchronized MeshManager getInstance(Context context) {
        if (instance == null) {
            instance = new MeshManager(context);
        }
        return instance;
    }

    public void setUIHandler(Handler handler) {
        this.uiHandler = handler;
    }

    public void addDevice(String macAddress, BluetoothChatService chatService) {
        deviceConnections.put(macAddress, chatService);
        knownDevices.add(macAddress);
        
        // Exchange device IDs
        String helloMessage = String.format("HELLO|%s", ownId);
        chatService.write(macAddress, helloMessage.getBytes());
        
        updateRoutingTable();
        broadcastDeviceInfo();
    }

    public void removeDevice(String deviceAddress) {
        deviceConnections.remove(deviceAddress);
        knownDevices.remove(deviceAddress);
        routingTable.remove(deviceAddress);
        String deviceId = macToIdMap.remove(deviceAddress);
        if (deviceId != null) {
            idToMacMap.remove(deviceId);
        }
        updateRoutingTable();
    }

    private void updateRoutingTable() {
        routingTable.clear();
        
        // Step 1: Add direct routes
        for (String device : deviceConnections.keySet()) {
            routingTable.put(device, device);
        }
        
        // Step 2: Add indirect routes through connected devices
        for (String device : deviceConnections.keySet()) {
            BluetoothChatService service = deviceConnections.get(device);
            if (service != null) {
                for (String connectedDevice : service.getConnectedDevices()) {
                    if (!routingTable.containsKey(connectedDevice)) {
                        routingTable.put(connectedDevice, device);
                    }
                }
            }
        }
        
        Log.d(TAG, "Updated routing table: " + routingTable);
        broadcastRoutingUpdate();
    }

    private void broadcastDeviceInfo() {
        String deviceInfo = String.format("DEVICE_INFO|%s|%s", 
            ownId, 
            String.join(",", knownDevices)
        );
        Log.d(TAG, "Broadcasting device info: " + deviceInfo);
        broadcastToAllConnected(deviceInfo.getBytes());
    }

    private void broadcastRoutingUpdate() {
        StringBuilder routes = new StringBuilder();
        for (Map.Entry<String, String> route : routingTable.entrySet()) {
            routes.append(route.getKey()).append(">").append(route.getValue()).append(",");
        }
        String routeUpdate = String.format("ROUTE_UPDATE|%s|%s", 
            ownId, 
            routes.toString()
        );
        Log.d(TAG, "Broadcasting route update: " + routeUpdate);
        broadcastToAllConnected(routeUpdate.getBytes());
    }

    private void broadcastToAllConnected(byte[] message) {
        for (BluetoothChatService service : deviceConnections.values()) {
            service.writeToAll(message);
        }
    }

    public void sendMessage(String targetId, String message) {
        String targetMac = idToMacMap.get(targetId);
        if (targetMac == null) {
            Log.e(TAG, "No MAC address found for target ID: " + targetId);
            return;
        }
        
        String meshMessage = String.format("CHAT|%s|%s|%s", 
            ownId, targetId, message);
        Log.d(TAG, "Sending message: " + meshMessage);
        
        String nextHop = routingTable.get(targetMac);
        if (nextHop != null) {
            BluetoothChatService service = deviceConnections.get(nextHop);
            if (service != null) {
                service.write(nextHop, meshMessage.getBytes());
            } else {
                Log.e(TAG, "No service found for next hop: " + nextHop);
            }
        } else {
            Log.e(TAG, "No route found for target: " + targetMac);
        }
    }

    public void handleIncomingMessage(String sourceMac, byte[] messageBytes) {
        String message = new String(messageBytes);
        Log.d(TAG, "Received raw message: " + message);
        
        String[] parts = message.split("\\|");
        if (parts.length < 2) {
            Log.e(TAG, "Invalid message format: " + message);
            return;
        }
        
        String messageType = parts[0];
        String payload = parts[1];
        
        switch (messageType) {
            case "HELLO":
                String deviceId = payload;
                Log.d(TAG, "Received HELLO from " + sourceMac + " with ID " + deviceId);
                
                String existingMac = idToMacMap.get(deviceId);
                if (existingMac == null || !existingMac.equals(sourceMac)) {
                    idToMacMap.put(deviceId, sourceMac);
                    macToIdMap.put(sourceMac, deviceId);
                    Log.d(TAG, "Updated device mapping: " + deviceId + " -> " + sourceMac);
                    
                    if (existingMac == null) {
                        String ourHello = "HELLO|" + ownId;
                        BluetoothChatService service = deviceConnections.get(sourceMac);
                        if (service != null) {
                            service.write(sourceMac, ourHello.getBytes());
                            Log.d(TAG, "Sent HELLO response to " + sourceMac);
                        }
                    }
                }
                break;
                
            case "ROUTE_UPDATE":
                String[] routes = payload.split(",");
                for (String route : routes) {
                    String[] routeParts = route.split(">");
                    if (routeParts.length == 2) {
                        String dest = routeParts[0];
                        String nextHop = routeParts[1];
                        routingTable.put(dest, nextHop);
                    }
                }
                break;
                
            case "DEVICE_INFO":
                String infoId = payload;
                if (!infoId.equals("null")) {
                    DeviceManager.getInstance(context).addDeviceMapping(infoId, sourceMac);
                }
                break;
                
            case "CHAT":
                String[] chatParts = payload.split(">", 2);
                if (chatParts.length == 2) {
                    String targetId = chatParts[0];
                    String content = chatParts[1];
                    
                    if (targetId.equals(ownId)) {
                        // Message is for us
                        Log.d(TAG, "Received chat message: " + content);
                        if (uiHandler != null) {
                            uiHandler.obtainMessage(BluetoothChatService.MESSAGE_READ, content.length(), -1, content.getBytes()).sendToTarget();
                        }
                    } else {
                        // Forward message
                        String targetMac = idToMacMap.get(targetId);
                        if (targetMac != null) {
                            sendMessage(targetId, content);
                        } else {
                            Log.e(TAG, "No MAC address found for target ID: " + targetId);
                        }
                    }
                }
                break;
        }
    }

    private void deliverMessageToUI(String sourceAddress, String message) {
        if (uiHandler != null) {
            uiHandler.obtainMessage(
                BluetoothChatService.MESSAGE_READ,
                message.length(),
                -1,
                message.getBytes()
            ).sendToTarget();
        }
    }

    public Set<String> getConnectedDevices() {
        return new HashSet<>(deviceConnections.keySet());
    }

    public Set<String> getKnownDevices() {
        return new HashSet<>(knownDevices);
    }

    public BluetoothChatService getChatService(String deviceAddress) {
        return deviceConnections.get(deviceAddress);
    }

    public String getDeviceId(String deviceAddress) {
        return macToIdMap.get(deviceAddress);
    }

    public String getDeviceAddress(String deviceId) {
        return idToMacMap.get(deviceId);
    }
}
