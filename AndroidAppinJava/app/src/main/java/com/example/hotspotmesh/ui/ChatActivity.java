package com.example.hotspotmesh.ui;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.example.hotspotmesh.R;
import com.example.hotspotmesh.core.ChatMessage;
import com.example.hotspotmesh.core.ChatMessageHandler;
import com.example.hotspotmesh.core.PeerDevice;
import java.util.ArrayList;
import java.util.List;

public class ChatActivity extends AppCompatActivity {
    private PeerDevice peer;
    private ChatMessageHandler chatHandler;
    private RecyclerView messageList;
    private EditText messageInput;
    private Button sendButton;
    private List<ChatMessage> messages = new ArrayList<>();
    private ChatAdapter chatAdapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_chat);

        // Get peer from intent
        peer = (PeerDevice) getIntent().getSerializableExtra("peer");
        
        // Initialize UI
        TextView chatTitle = findViewById(R.id.chat_title);
        chatTitle.setText("Chat with " + peer.getDeviceName());

        messageList = findViewById(R.id.message_list);
        messageInput = findViewById(R.id.message_input);
        sendButton = findViewById(R.id.send_button);

        // Setup RecyclerView
        chatAdapter = new ChatAdapter(messages);
        messageList.setLayoutManager(new LinearLayoutManager(this));
        messageList.setAdapter(chatAdapter);

        // Initialize chat handler
        chatHandler = new ChatMessageHandler(this, (senderIp, message) -> {
            runOnUiThread(() -> {
                messages.add(new ChatMessage(message, senderIp, ChatMessage.MessageType.RECEIVED));
                chatAdapter.notifyDataSetChanged();
                messageList.scrollToPosition(messages.size() - 1);
            });
        });

        // Start the chat server
        chatHandler.startChatServer();

        // Setup send button
        sendButton.setOnClickListener(v -> {
            String message = messageInput.getText().toString().trim();
            if (!message.isEmpty()) {
                chatHandler.sendMessage(peer.getIpAddress().getHostAddress(), message);
                messages.add(new ChatMessage(message, "You", ChatMessage.MessageType.SENT));
                chatAdapter.notifyDataSetChanged();
                messageList.scrollToPosition(messages.size() - 1);
                messageInput.setText("");
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        chatHandler.stopChatServer();
    }
} 