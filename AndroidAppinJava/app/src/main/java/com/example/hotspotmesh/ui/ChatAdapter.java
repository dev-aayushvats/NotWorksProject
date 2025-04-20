package com.example.hotspotmesh.ui;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import com.example.hotspotmesh.R;
import com.example.hotspotmesh.core.ChatMessage;
import java.text.SimpleDateFormat;
import java.util.List;
import java.util.Locale;

public class ChatAdapter extends RecyclerView.Adapter<ChatAdapter.MessageViewHolder> {
    private List<ChatMessage> messages;
    private SimpleDateFormat timeFormat = new SimpleDateFormat("HH:mm", Locale.getDefault());

    public ChatAdapter(List<ChatMessage> messages) {
        this.messages = messages;
    }

    @NonNull
    @Override
    public MessageViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_message, parent, false);
        return new MessageViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull MessageViewHolder holder, int position) {
        ChatMessage message = messages.get(position);
        holder.messageText.setText(message.getContent());
        holder.timeText.setText(timeFormat.format(message.getTimestamp()));

        switch (message.getType()) {
            case SENT:
                holder.messageText.setBackgroundResource(R.drawable.bubble_sent);
                holder.senderText.setText("You");
                break;
            case RECEIVED:
                holder.messageText.setBackgroundResource(R.drawable.bubble_received);
                holder.senderText.setText(message.getSender());
                break;
            case BROADCAST:
                holder.messageText.setBackgroundResource(R.drawable.bubble_broadcast);
                holder.senderText.setText(message.getSender() + " (Broadcast)");
                break;
        }
    }

    @Override
    public int getItemCount() {
        return messages.size();
    }

    static class MessageViewHolder extends RecyclerView.ViewHolder {
        TextView messageText;
        TextView senderText;
        TextView timeText;

        MessageViewHolder(View itemView) {
            super(itemView);
            messageText = itemView.findViewById(R.id.message_text);
            senderText = itemView.findViewById(R.id.sender_text);
            timeText = itemView.findViewById(R.id.time_text);
        }
    }
} 