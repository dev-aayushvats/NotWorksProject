import time
from config import MY_ID

routing_table = {}
sequence_numbers = {}

def update_link_state(sender_id, neighbors, seq_num):
    if sender_id not in sequence_numbers or seq_num > sequence_numbers[sender_id]:
        sequence_numbers[sender_id] = seq_num
        routing_table[sender_id] = {"neighbors": neighbors, "timestamp": time.time()}

def get_next_hops(destination, known_peers):
    if destination == MY_ID:
        return []
    if destination in routing_table:
        return routing_table[destination]["neighbors"]
    return known_peers  # fallback: scoped flooding

