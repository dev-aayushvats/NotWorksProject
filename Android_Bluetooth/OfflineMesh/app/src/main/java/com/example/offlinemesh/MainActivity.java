package com.example.offlinemesh;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

public class MainActivity extends AppCompatActivity {

    private static final int REQUEST_ENABLE_BT = 1;
    private static final int REQUEST_PERMISSION = 1002;
    private static final int REQUEST_DEVICE_CONNECT = 2001;
    private static final int REQUEST_BLUETOOTH_PERMISSIONS = 1;

    private BluetoothAdapter bluetoothAdapter;
    private BluetoothChatService chatService;
    private String currentDeviceAddress; // Add this field

    private final Handler handler = new Handler(msg -> {
        switch (msg.what) {
            case BluetoothChatService.MESSAGE_CONNECTED:
                runOnUiThread(() -> {
                    String deviceAddress = (String) msg.obj;
                    if (deviceAddress == null) {
                        Toast.makeText(MainActivity.this, "Connection failed: No device address", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    
                    chatService.setHandler(null); // detach handler
                    ChatActivity.setChatService(chatService);
                    Intent chatIntent = new Intent(MainActivity.this, ChatActivity.class);
                    chatIntent.putExtra("isServer", false);
                    chatIntent.putExtra("device_address", deviceAddress);
                    startActivity(chatIntent);
                });
                break;

            case BluetoothChatService.MESSAGE_CONNECTION_FAILED:
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Connection Failed", Toast.LENGTH_SHORT).show());
                break;
        }
        return true;
    });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        setupBluetooth();

        Button findBtn = findViewById(R.id.find_devices_btn);
        findBtn.setOnClickListener(v -> {
            Intent intent = new Intent(MainActivity.this, DeviceListActivity.class);
            startActivityForResult(intent, REQUEST_DEVICE_CONNECT);
        });
    }

    private void setupBluetooth() {
        bluetoothAdapter = BluetoothAdapter.getDefaultAdapter();
        if (bluetoothAdapter == null) {
            Toast.makeText(this, "Bluetooth is not available", Toast.LENGTH_LONG).show();
            finish();
            return;
        }

        if (!bluetoothAdapter.isEnabled()) {
            Intent enableBtIntent = new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE);
            startActivityForResult(enableBtIntent, REQUEST_ENABLE_BT);
        } else {
            startBluetoothService();
        }
    }

    private void startBluetoothService() {
        if (chatService == null) {
            chatService = new BluetoothChatService(this, handler);
            ChatActivity.setChatService(chatService);
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_ENABLE_BT) {
            if (resultCode == RESULT_OK) {
                startBluetoothService();
            } else {
                Toast.makeText(this, "Bluetooth must be enabled to use this app", Toast.LENGTH_LONG).show();
                finish();
            }
        }

        if (requestCode == REQUEST_DEVICE_CONNECT && resultCode == RESULT_OK) {
            try {
                String deviceAddress = data.getStringExtra("device_address");
                if (deviceAddress == null) {
                    Toast.makeText(this, "No device selected", Toast.LENGTH_SHORT).show();
                    return;
                }
                
                Toast.makeText(this, "Selected: " + deviceAddress, Toast.LENGTH_SHORT).show();

                if (chatService == null) {
                    chatService = new BluetoothChatService(this, handler);
                }

                BluetoothDevice device = bluetoothAdapter.getRemoteDevice(deviceAddress);
                chatService.connect(device);

            } catch (Exception e) {
                e.printStackTrace();
                Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_BLUETOOTH_PERMISSIONS) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }
            if (!allGranted) {
                Toast.makeText(this, "Bluetooth permissions are required for this app", Toast.LENGTH_LONG).show();
                finish();
            }
        }
    }

    private void checkBluetoothPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            String[] permissions = {
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT
            };
            
            boolean allPermissionsGranted = true;
            for (String permission : permissions) {
                if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                    allPermissionsGranted = false;
                    break;
                }
            }
            
            if (!allPermissionsGranted) {
                requestPermissions(permissions, REQUEST_BLUETOOTH_PERMISSIONS);
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (chatService != null) {
            chatService.stop();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (chatService != null) {
            // Save state if needed
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (chatService != null) {
            // Restore state if needed
            checkBluetoothPermissions();
        }
    }
}