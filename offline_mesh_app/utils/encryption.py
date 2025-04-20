# AES encryption utils
# from Crypto.Cipher import AES
# from Crypto.Random import get_random_bytes

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
from config import AES_KEY, USE_ENCRYPTION

def encrypt_data(data):
    """Encrypt data using AES encryption"""
    if not USE_ENCRYPTION:
        return data
    
    try:
        # Convert data to bytes if it's a string
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Generate a random initialization vector
        iv = get_random_bytes(16)
        
        # Create the cipher
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        
        # Pad the data to be a multiple of 16 bytes
        padded_data = pad(data, AES.block_size)
        
        # Encrypt the data
        ciphertext = cipher.encrypt(padded_data)
        
        # Combine IV and ciphertext
        encrypted_data = iv + ciphertext
        
        # Encode as base64 for easy transmission
        return base64.b64encode(encrypted_data)
    except Exception as e:
        print(f"Encryption error: {e}")
        return data

def decrypt_data(encrypted_data):
    """Decrypt data using AES encryption"""
    if not USE_ENCRYPTION:
        return encrypted_data
    
    try:
        # Decode from base64
        raw_data = base64.b64decode(encrypted_data)
        
        # Extract IV (first 16 bytes)
        iv = raw_data[:16]
        ciphertext = raw_data[16:]
        
        # Create the cipher
        cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
        
        # Decrypt and unpad the data
        padded_data = cipher.decrypt(ciphertext)
        data = unpad(padded_data, AES.block_size)
        
        # Return as string if it was originally a string
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data
    except Exception as e:
        print(f"Decryption error: {e}")
        return encrypted_data
