"""
Encryption Module for ANAGHA SOLUTION
Encrypts sensitive data at rest (credentials, tokens)
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from core.config import Config

class EncryptionManager:
    """Manages encryption/decryption of sensitive data"""
    
    def __init__(self):
        """Initialize encryption manager"""
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _get_or_create_key(self) -> bytes:
        """Get encryption key from env or generate new one"""
        # Try to get from environment
        key_str = os.getenv('ENCRYPTION_KEY')
        
        if key_str:
            try:
                # If it's already a valid Fernet key (base64 URL-safe string), use it directly
                # Fernet key must be 32 bytes when decoded
                decoded = base64.urlsafe_b64decode(key_str.encode())
                if len(decoded) == 32:
                    # Valid key, encode it back to base64 URL-safe for Fernet
                    return base64.urlsafe_b64encode(decoded)
                else:
                    # Invalid length, generate new
                    print(f"⚠️ Invalid ENCRYPTION_KEY length ({len(decoded)} bytes, expected 32). Generating new key.")
            except Exception as e:
                print(f"⚠️ Error decoding ENCRYPTION_KEY: {e}. Generating new key.")
        
        # Generate new key using Fernet's key generation
        key = Fernet.generate_key()
        
        # Save to .env for persistence
        try:
            from core.config import Config
            Config._update_env_file('ENCRYPTION_KEY', key.decode())
            print(f"✓ Generated and saved new encryption key")
        except Exception as e:
            print(f"⚠️ Could not save encryption key to .env: {e}")
        
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string"""
        if not plaintext:
            return ''
        try:
            encrypted = self.cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return plaintext  # Fallback to plaintext if encryption fails
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string"""
        if not ciphertext:
            return ''
        try:
            # Check if already decrypted (not base64)
            try:
                decoded = base64.urlsafe_b64decode(ciphertext.encode())
                decrypted = self.cipher.decrypt(decoded)
                return decrypted.decode()
            except:
                # If decryption fails, assume it's already plaintext
                return ciphertext
        except Exception as e:
            print(f"Decryption error: {e}")
            return ciphertext  # Fallback to ciphertext if decryption fails
    
    def encrypt_dict(self, data: dict, keys_to_encrypt: list) -> dict:
        """Encrypt specific keys in a dictionary"""
        encrypted = data.copy()
        for key in keys_to_encrypt:
            if key in encrypted and encrypted[key]:
                encrypted[key] = self.encrypt(str(encrypted[key]))
        return encrypted
    
    def decrypt_dict(self, data: dict, keys_to_decrypt: list) -> dict:
        """Decrypt specific keys in a dictionary"""
        decrypted = data.copy()
        for key in keys_to_decrypt:
            if key in decrypted and decrypted[key]:
                decrypted[key] = self.decrypt(str(decrypted[key]))
        return decrypted

# Global encryption manager instance
_encryption_manager = None

def get_encryption_manager() -> EncryptionManager:
    """Get global encryption manager instance"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager


