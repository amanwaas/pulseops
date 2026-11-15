import base64
import os
import binascii
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


class EncryptionService:
    """
    AES-256-GCM Authenticated Encryption Service.
    Protects Webhook secrets and alert destination URLs stored at rest in PostgreSQL.
    """

    def __init__(self, key_str: str = settings.ENCRYPTION_KEY):
        self._key = self._derive_key_bytes(key_str)
        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def _derive_key_bytes(key_str: str) -> bytes:
        # Check if key is 64 hex characters (32 bytes)
        try:
            if len(key_str) == 64:
                return bytes.fromhex(key_str)
        except ValueError:
            pass

        # Check if base64 encoded
        try:
            decoded = base64.b64decode(key_str)
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass

        # Fallback: pad or truncate utf-8 bytes to exactly 32 bytes
        raw = key_str.encode("utf-8")
        if len(raw) < 32:
            return raw.ljust(32, b"0")
        return raw[:32]

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypts a string using AES-256-GCM.
        Generates a 12-byte cryptographically secure random nonce.
        Returns base64-encoded string containing (nonce + ciphertext + 16-byte tag).
        """
        if not plaintext:
            return ""
        nonce = os.urandom(12)  # 96-bit standard GCM nonce
        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext_with_tag = self._aesgcm.encrypt(nonce, plaintext_bytes, None)
        payload = nonce + ciphertext_with_tag
        return base64.b64encode(payload).decode("utf-8")

    def decrypt(self, encrypted_b64: str) -> str:
        """
        Decrypts a base64-encoded AES-256-GCM payload.
        Verifies Galois authentication tag.
        """
        if not encrypted_b64:
            return ""
        try:
            payload = base64.b64decode(encrypted_b64.encode("utf-8"))
            if len(payload) < 28:  # 12-byte nonce + 16-byte minimum tag
                raise ValueError("Ciphertext payload is too short.")
            nonce = payload[:12]
            ciphertext_with_tag = payload[12:]
            decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")


encryption_service = EncryptionService()
