package com.example.hotspotmesh.ui;

import android.Manifest;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import com.example.hotspotmesh.R;
import com.example.hotspotmesh.core.MessageHandler;
import com.example.hotspotmesh.core.NetworkDiscovery;
import com.example.hotspotmesh.core.PeerDevice;
import com.example.hotspotmesh.utils.WifiManagerHelper;
import java.util.Map;

public class MainActivity extends AppCompatActivity {
    private static final String TAG = "MainActivity";
    private static final int PERMISSIONS_REQUEST_CODE = 1001;
    
    private NetworkDiscovery networkDiscovery;
    private MessageHandler messageHandler;
    private WifiManagerHelper wifiManagerHelper;
    private PeerListAdapter peerListAdapter;
    private RecyclerView peerListView;
    private Button startButton;
    private Button broadcastButton;
    private Handler handler;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        handler = new Handler();

        // Initialize UI components
        peerListView = findViewById(R.id.peer_list);
        startButton = findViewById(R.id.start_button);
        broadcastButton = findViewById(R.id.broadcast_button);
        
        // Setup RecyclerView
        peerListAdapter = new PeerListAdapter(peer -> {
            // Start chat activity
            Intent intent = new Intent(this, ChatActivity.class);
            intent.putExtra("peer", peer);
            startActivity(intent);
        });
        peerListView.setLayoutManager(new LinearLayoutManager(this));
        peerListView.setAdapter(peerListAdapter);

        // Initialize network components
        wifiManagerHelper = new WifiManagerHelper(this);
        networkDiscovery = new NetworkDiscovery(this, "Device-" + android.os.Build.MODEL);
        messageHandler = new MessageHandler(this, (senderIp, message) -> {
            runOnUiThread(() -> {
                Toast.makeText(this, 
                    "Broadcast from " + senderIp + ": " + message, 
                    Toast.LENGTH_LONG).show();
            });
        });
        
        // Set NetworkDiscovery in MessageHandler
        messageHandler.setNetworkDiscovery(networkDiscovery);

        // Setup start button
        startButton.setOnClickListener(v -> {
            if (checkAndRequestPermissions()) {
                startNetworkServices();
            }
        });

        // Setup broadcast button
        broadcastButton.setOnClickListener(v -> showBroadcastDialog());

        // Update peer list periodically
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                peerListAdapter.updatePeers(networkDiscovery.getDiscoveredPeers());
                handler.postDelayed(this, 1000); // Update every second
            }
        }, 1000);
    }

    private void showBroadcastDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        View dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_broadcast, null);
        builder.setView(dialogView);

        EditText messageInput = dialogView.findViewById(R.id.broadcast_message);
        Button sendButton = dialogView.findViewById(R.id.send_broadcast);

        AlertDialog dialog = builder.create();
        
        sendButton.setOnClickListener(v -> {
            String message = messageInput.getText().toString().trim();
            if (!message.isEmpty()) {
                messageHandler.broadcastMessage(message);
                Toast.makeText(this, "Broadcast sent", Toast.LENGTH_SHORT).show();
                dialog.dismiss();
            } else {
                Toast.makeText(this, "Please enter a message", Toast.LENGTH_SHORT).show();
            }
        });

        dialog.show();
    }

    private boolean checkAndRequestPermissions() {
        String[] permissions = {
            Manifest.permission.INTERNET,
            Manifest.permission.ACCESS_WIFI_STATE,
            Manifest.permission.CHANGE_WIFI_MULTICAST_STATE,
            Manifest.permission.ACCESS_NETWORK_STATE
        };

        boolean allGranted = true;
        for (String permission : permissions) {
            if (ContextCompat.checkSelfPermission(this, permission) 
                != PackageManager.PERMISSION_GRANTED) {
                allGranted = false;
                break;
            }
        }

        if (!allGranted) {
            ActivityCompat.requestPermissions(this, 
                permissions, PERMISSIONS_REQUEST_CODE);
            return false;
        }
        return true;
    }

    private void startNetworkServices() {
        if (!wifiManagerHelper.isWifiEnabled()) {
            wifiManagerHelper.enableWifi();
        }
        
        wifiManagerHelper.acquireMulticastLock();
        networkDiscovery.startDiscovery();
        messageHandler.startMessageServer();
        
        startButton.setEnabled(false);
        broadcastButton.setEnabled(true);
        Toast.makeText(this, "Network services started", Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        networkDiscovery.stopDiscovery();
        messageHandler.stopMessageServer();
        wifiManagerHelper.releaseMulticastLock();
        handler.removeCallbacksAndMessages(null);
    }
} 