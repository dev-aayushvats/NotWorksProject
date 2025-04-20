package com.example.hotspotmesh.core;

import java.net.InetAddress;
import java.io.Serializable;

public class PeerDevice implements Serializable {
    private String deviceName;
    private InetAddress ipAddress;
    private int port;
    private long lastSeen;
    private boolean isOnline;

    public PeerDevice(String deviceName, InetAddress ipAddress, int port) {
        this.deviceName = deviceName;
        this.ipAddress = ipAddress;
        this.port = port;
        this.lastSeen = System.currentTimeMillis();
        this.isOnline = true;
    }

    public String getDeviceName() { return deviceName; }
    public InetAddress getIpAddress() { return ipAddress; }
    public int getPort() { return port; }
    public long getLastSeen() { return lastSeen; }
    public boolean isOnline() { return isOnline; }

    public void updateLastSeen() {
        this.lastSeen = System.currentTimeMillis();
        this.isOnline = true;
    }

    public void setOffline() {
        this.isOnline = false;
    }
}
