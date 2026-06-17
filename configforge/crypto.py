import os
import base64
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


SALT_SIZE = 16
ITERATIONS = 100_000
ENCRYPTED_PREFIX = "ENC:"


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def generate_master_key() -> str:
    return Fernet.generate_key().decode()


def get_master_key(master_key_env: str = "CONFIGFORGE_MASTER_KEY") -> str:
    key = os.environ.get(master_key_env)
    if not key:
        raise ValueError(
            f"Master key not found. Please set the {master_key_env} environment variable "
            f"or generate one with 'configforge crypto gen-key'."
        )
    return key


def _get_fernet(master_key: str) -> Fernet:
    return Fernet(master_key.encode())


def encrypt_value(value: str, master_key: str) -> str:
    fernet = _get_fernet(master_key)
    encrypted = fernet.encrypt(value.encode())
    return f"{ENCRYPTED_PREFIX}{encrypted.decode()}"


def decrypt_value(encrypted_value: str, master_key: str) -> str:
    if not encrypted_value.startswith(ENCRYPTED_PREFIX):
        return encrypted_value
    raw = encrypted_value[len(ENCRYPTED_PREFIX):]
    fernet = _get_fernet(master_key)
    return fernet.decrypt(raw.encode()).decode()


def encrypt_dict(data: dict, master_key: str, sensitive_keys: list = None) -> dict:
    result = {}
    sensitive_keys = [k.lower() for k in (sensitive_keys or [])]
    
    def _is_sensitive(key: str) -> bool:
        key_lower = key.lower()
        if not sensitive_keys:
            return any(s in key_lower for s in [
                "password", "secret", "token", "key", "private",
                "credential", "auth", "passwd", "pwd"
            ])
        return any(s in key_lower for s in sensitive_keys)
    
    def _encrypt_recursive(obj, path: str = ""):
        if isinstance(obj, dict):
            return {k: _encrypt_recursive(v, f"{path}.{k}" if path else k) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_encrypt_recursive(item, f"{path}[{i}]") for i, item in enumerate(obj)]
        elif isinstance(obj, str) and _is_sensitive(path.split(".")[-1]) and not obj.startswith(ENCRYPTED_PREFIX):
            return encrypt_value(obj, master_key)
        else:
            return obj
    
    return _encrypt_recursive(data)


def decrypt_dict(data: dict, master_key: str) -> dict:
    def _decrypt_recursive(obj):
        if isinstance(obj, dict):
            return {k: _decrypt_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_decrypt_recursive(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith(ENCRYPTED_PREFIX):
            return decrypt_value(obj, master_key)
        else:
            return obj
    
    return _decrypt_recursive(data)


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)
