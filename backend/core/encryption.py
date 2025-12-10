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
                return base64.urlsafe_b64decode(key_str.encode())
            except:
                pass
        
        # Generate new key from master password
        master_password = os.getenv('MASTER_PASSWORD', 'anagha_solution_default_change_in_production')
        salt = os.getenv('ENCRYPTION_SALT', 'anagha_solution_salt').encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        
        # Save to .env for persistence
        try:
            from core.config import Config
            Config._update_env_file('ENCRYPTION_KEY', key.decode())
        except:
            pass
        
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


