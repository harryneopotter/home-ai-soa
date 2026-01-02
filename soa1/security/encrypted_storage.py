import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptedStorage:
    def __init__(self, key_path: str = None):
        if key_path is None:
            key_path = os.environ.get(
                "SOA1_KEY_PATH", "/home/ryzen/projects/soa1/security/.key"
            )

        self.key_path = Path(key_path)
        self.key = self._load_or_generate_key()
        self.aesgcm = AESGCM(self.key)

    def _load_or_generate_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()

        key = AESGCM.generate_key(bit_length=256)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key_path.write_bytes(key)
        os.chmod(self.key_path, 0o600)
        return key

    def encrypt(self, data: str) -> bytes:
        if not data:
            return b""
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, data.encode(), None)
        return nonce + ciphertext

    def decrypt(self, encrypted: bytes) -> str:
        if not encrypted:
            return ""
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return self.aesgcm.decrypt(nonce, ciphertext, None).decode()


if __name__ == "__main__":
    storage = EncryptedStorage()
    test_data = "Sensitive financial information"
    encrypted = storage.encrypt(test_data)
    decrypted = storage.decrypt(encrypted)
    print(f"Original: {test_data}")
    print(f"Encrypted: {encrypted.hex()[:20]}...")
    print(f"Decrypted: {decrypted}")
    assert test_data == decrypted
    print("Encryption/Decryption successful!")
