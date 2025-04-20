package com.example.hotspotmesh.utils;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.util.Log;

public class WifiManagerHelper {
    private static final String TAG = "WifiManagerHelper";
    private WifiManager wifiManager;
    private WifiManager.MulticastLock multicastLock;

    public WifiManagerHelper(Context context) {
        wifiManager = (WifiManager) context.getApplicationContext()
            .getSystemService(Context.WIFI_SERVICE);
    }

    public void acquireMulticastLock() {
        if (wifiManager != null) {
            multicastLock = wifiManager.createMulticastLock("MeshNetworkLock");
            multicastLock.setReferenceCounted(true);
            multicastLock.acquire();
            Log.d(TAG, "Multicast lock acquired");
        }
    }

    public void releaseMulticastLock() {
        if (multicastLock != null && multicastLock.isHeld()) {
            multicastLock.release();
            Log.d(TAG, "Multicast lock released");
        }
    }

    public boolean isWifiEnabled() {
        return wifiManager != null && wifiManager.isWifiEnabled();
    }

    public void enableWifi() {
        if (wifiManager != null) {
            wifiManager.setWifiEnabled(true);
        }
    }
} 