package com.example.offlinemesh;

import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.util.Log;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import java.util.Set;

import android.app.Activity;

public class ChatActivity extends AppCompatActivity {

    private static final String TAG = "ChatActivity";
    public static final String EXTRA_DEVICE_ID = "device_id";
    public static final String EXTRA_DEVICE_ADDRESS = "device_address";
    public static final String EXTRA_IS_SERVER = "is_server";

    private static BluetoothChatService chatService;
    private LinearLayout chatContainer;
    private ScrollView scrollView;
    private EditText inputField;
    private Button sendBtn;
    private String targetDeviceId;
    private String targetDeviceAddress;
    private boolean isServer;
    private Handler messageHandler;
    private TextView chatTitle;
    private EditText messageInput;
    private Button sendButton;
    private Button connectNewDeviceButton;

    public static void setChatService(BluetoothChatService service) {
        chatService = service;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_chat);

        // Initialize UI components
        chatTitle = findViewById(R.id.chat_title);
        messageInput = findViewById(R.id.message_input);
        sendButton = findViewById(R.id.send_btn);
        chatContainer = findViewById(R.id.chat_container);
        connectNewDeviceButton = findViewById(R.id.connect_new_device_button);

        // Get target device info from intent
        targetDeviceAddress = getIntent().getStringExtra("device_address");
        isServer = getIntent().getBooleanExtra("is_server", false);

        // Set up connect new device button
        connectNewDeviceButton.setOnClickListener(v -> {
            Intent intent = new Intent(this, DeviceListActivity.class);
            intent.putExtra("is_server", isServer);
            startActivity(intent);
        });

        // If target address is null and we're the server, try to get connected device
        if (targetDeviceAddress == null && isServer) {
            BluetoothChatService chatService = MeshManager.getInstance(this).getChatService(targetDeviceAddress);
            if (chatService != null) {
                Set<String> connectedDevices = chatService.getConnectedDevices();
                if (!connectedDevices.isEmpty()) {
                    targetDeviceAddress = connectedDevices.iterator().next();
                } else {
                    Toast.makeText(this, "No connected devices", Toast.LENGTH_SHORT).show();
                    finish();
                    return;
                }
            } else {
                Toast.makeText(this, "Chat service not available", Toast.LENGTH_SHORT).show();
                finish();
                return;
            }
        }

        if (targetDeviceAddress == null) {
            Toast.makeText(this, "Target device address is null", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // Get device ID from MeshManager
        targetDeviceId = MeshManager.getInstance(this).getDeviceId(targetDeviceAddress);
        if (targetDeviceId == null) {
            Toast.makeText(this, "Could not get device ID", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }

        // Set chat title
        chatTitle.setText("Chat with " + targetDeviceId);

        // Set up message handler
        messageHandler = new Handler(Looper.getMainLooper()) {
            @Override
            public void handleMessage(Message msg) {
                switch (msg.what) {
                    case BluetoothChatService.MESSAGE_READ:
                        byte[] readBuf = (byte[]) msg.obj;
                        String readMessage = new String(readBuf, 0, msg.arg1);
                        addMessage(readMessage, false);
                        break;
                    case BluetoothChatService.MESSAGE_WRITE:
                        byte[] writeBuf = (byte[]) msg.obj;
                        String writeMessage = new String(writeBuf);
                        addMessage(writeMessage, true);
                        break;
                    case BluetoothChatService.MESSAGE_TOAST:
                        Toast.makeText(ChatActivity.this, msg.getData().getString(BluetoothChatService.TOAST), Toast.LENGTH_SHORT).show();
                        break;
                }
            }
        };

        // Set handler for BluetoothChatService
        BluetoothChatService chatService = MeshManager.getInstance(this).getChatService(targetDeviceAddress);
        if (chatService != null) {
            chatService.setHandler(messageHandler);
        }

        // Set handler for MeshManager
        MeshManager.getInstance(this).setUIHandler(messageHandler);

        // Set up send button
        sendButton.setOnClickListener(v -> {
            String message = messageInput.getText().toString().trim();
            if (!message.isEmpty()) {
                MeshManager.getInstance(ChatActivity.this).sendMessage(targetDeviceId, message);
                messageInput.setText("");
            }
        });

        // Setup UI
        scrollView = findViewById(R.id.scroll_view);
        inputField = findViewById(R.id.message_input);
        sendBtn = findViewById(R.id.send_btn);

        // Register for broadcasts
        IntentFilter filter = new IntentFilter(BluetoothAdapter.ACTION_STATE_CHANGED);
        registerReceiver(mReceiver, filter);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (chatService != null) {
            chatService.setHandler(null);
        }
        MeshManager.getInstance(this).setUIHandler(null);
    }

    private void addMessage(String message, boolean isSent) {
        LayoutInflater inflater = LayoutInflater.from(this);
        View messageView = inflater.inflate(R.layout.message_bubble, chatContainer, false);
        
        TextView messageText = messageView.findViewById(R.id.message_text);
        messageText.setText(message);
        
        LinearLayout messageContainer = messageView.findViewById(R.id.message_container);
        LinearLayout.LayoutParams params = (LinearLayout.LayoutParams) messageContainer.getLayoutParams();
        
        if (isSent) {
            params.gravity = Gravity.END;
            messageContainer.setBackground(ContextCompat.getDrawable(this, R.drawable.sent_message_bg));
        } else {
            params.gravity = Gravity.START;
            messageContainer.setBackground(ContextCompat.getDrawable(this, R.drawable.received_message_bg));
        }
        
        messageContainer.setLayoutParams(params);
        chatContainer.addView(messageView);
        
        // Scroll to bottom
        scrollView.post(() -> scrollView.fullScroll(View.FOCUS_DOWN));
    }

    private BroadcastReceiver mReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (BluetoothAdapter.ACTION_STATE_CHANGED.equals(action)) {
                int state = intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.STATE_OFF);
                switch (state) {
                    case BluetoothAdapter.STATE_OFF:
                        setStatus("Bluetooth turned off");
                        break;
                    case BluetoothAdapter.STATE_TURNING_OFF:
                        setStatus("Bluetooth turning off");
                        break;
                    case BluetoothAdapter.STATE_ON:
                        setStatus("Bluetooth turned on");
                        break;
                    case BluetoothAdapter.STATE_TURNING_ON:
                        setStatus("Bluetooth turning on");
                        break;
                }
            }
        }
    };

    private void setStatus(String status) {
        // Implementation of setStatus method
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        
        if (resultCode == Activity.RESULT_OK) {
            String deviceAddress = data.getStringExtra(DeviceListActivity.EXTRA_DEVICE_ADDRESS);
            if (deviceAddress != null) {
                // Get the BluetoothDevice object
                BluetoothAdapter bluetoothAdapter = BluetoothAdapter.getDefaultAdapter();
                BluetoothDevice device = bluetoothAdapter.getRemoteDevice(deviceAddress);
                
                // Connect to the device
                BluetoothChatService chatService = MeshManager.getInstance(this).getChatService(deviceAddress);
                if (chatService != null) {
                    chatService.connect(device);
                }
            }
        }
    }
}
