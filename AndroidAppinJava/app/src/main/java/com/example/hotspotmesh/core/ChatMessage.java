package com.example.hotspotmesh.core;

public class ChatMessage {
    public enum MessageType {
        SENT,
        RECEIVED,
        BROADCAST
    }

    private String content;
    private String sender;
    private MessageType type;
    private long timestamp;

    public ChatMessage(String content, String sender, MessageType type) {
        this.content = content;
        this.sender = sender;
        this.type = type;
        this.timestamp = System.currentTimeMillis();
    }

    public String getContent() { return content; }
    public String getSender() { return sender; }
    public MessageType getType() { return type; }
    public long getTimestamp() { return timestamp; }
} 