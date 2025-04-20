package com.example.hotspotmesh.ui;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import com.example.hotspotmesh.R;
import com.example.hotspotmesh.core.PeerDevice;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class PeerListAdapter extends RecyclerView.Adapter<PeerListAdapter.PeerViewHolder> {
    private List<PeerDevice> peers = new ArrayList<>();
    private OnPeerClickListener listener;

    public interface OnPeerClickListener {
        void onPeerClick(PeerDevice peer);
    }

    public PeerListAdapter(OnPeerClickListener listener) {
        this.listener = listener;
    }

    @NonNull
    @Override
    public PeerViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
            .inflate(R.layout.item_peer, parent, false);
        return new PeerViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull PeerViewHolder holder, int position) {
        PeerDevice peer = peers.get(position);
        holder.peerName.setText(peer.getDeviceName());
        holder.peerIp.setText(peer.getIpAddress().getHostAddress());
        
        // Set online status indicator
        holder.statusIndicator.setImageResource(
            peer.isOnline() ? R.drawable.ic_online : R.drawable.ic_offline
        );

        holder.chatButton.setOnClickListener(v -> {
            if (listener != null) {
                listener.onPeerClick(peer);
            }
        });
    }

    @Override
    public int getItemCount() {
        return peers.size();
    }

    public void updatePeers(Map<String, PeerDevice> newPeers) {
        peers.clear();
        peers.addAll(newPeers.values());
        notifyDataSetChanged();
    }

    static class PeerViewHolder extends RecyclerView.ViewHolder {
        ImageView statusIndicator;
        TextView peerName;
        TextView peerIp;
        Button chatButton;

        PeerViewHolder(View itemView) {
            super(itemView);
            statusIndicator = itemView.findViewById(R.id.peer_status);
            peerName = itemView.findViewById(R.id.peer_name);
            peerIp = itemView.findViewById(R.id.peer_ip);
            chatButton = itemView.findViewById(R.id.chat_button);
        }
    }
} 