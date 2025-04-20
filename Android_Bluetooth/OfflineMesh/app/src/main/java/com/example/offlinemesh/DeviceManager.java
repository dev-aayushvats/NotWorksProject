package com.example.offlinemesh;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public class DeviceManager {
    private static final String TAG = "DeviceManager";
    private static final String PREFS_NAME = "DevicePrefs";
    private static final String KEY_DEVICE_ID = "device_id";
    private static final String KEY_MAC_TO_ID = "mac_to_id";

    private static DeviceManager instance;
    private final SharedPreferences prefs;
    private final String deviceId;
    private final Map<String, String> macToIdMap;

    private DeviceManager(Context context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        
        // Get or create device ID
        String storedId = prefs.getString(KEY_DEVICE_ID, null);
        if (storedId == null) {
            String newId = UUID.randomUUID().toString();
            prefs.edit().putString(KEY_DEVICE_ID, newId).apply();
            deviceId = newId;
        } else {
            deviceId = storedId;
        }
        
        // Load MAC to ID mapping
        macToIdMap = new HashMap<>();
        String macToIdString = prefs.getString(KEY_MAC_TO_ID, "");
        if (!macToIdString.isEmpty()) {
            String[] entries = macToIdString.split(",");
            for (String entry : entries) {
                String[] parts = entry.split(":");
                if (parts.length == 2) {
                    macToIdMap.put(parts[0], parts[1]);
                }
            }
        }
        
        Log.d(TAG, "Device ID: " + deviceId);
        Log.d(TAG, "MAC to ID map: " + macToIdMap);
    }

    public static synchronized DeviceManager getInstance(Context context) {
        if (instance == null) {
            instance = new DeviceManager(context);
        }
        return instance;
    }

    public String getDeviceId() {
        return deviceId;
    }

    public void addDeviceMapping(String macAddress, String deviceId) {
        macToIdMap.put(macAddress, deviceId);
        saveMacToIdMap();
    }

    public String getDeviceIdForMac(String macAddress) {
        return macToIdMap.get(macAddress);
    }

    private void saveMacToIdMap() {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, String> entry : macToIdMap.entrySet()) {
            sb.append(entry.getKey()).append(":").append(entry.getValue()).append(",");
        }
        prefs.edit().putString(KEY_MAC_TO_ID, sb.toString()).apply();
    }
} 