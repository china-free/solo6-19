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


DEFAULT_SENSITIVE_PATTERNS = [
    "password", "secret", "token", "key", "private",
    "credential", "auth", "passwd", "pwd"
]


def is_sensitive_key(key: str, sensitive_keys: list = None) -> bool:
    key_lower = key.lower()
    patterns = [p.lower() for p in (sensitive_keys or DEFAULT_SENSITIVE_PATTERNS)]
    return any(s in key_lower for s in patterns)


def mask_value(value: str, mode: str = "partial", mask_char: str = "*") -> str:
    if not isinstance(value, str) or not value:
        return value

    if mode == "full":
        return mask_char * 8

    if mode == "none":
        return value

    length = len(value)

    if length <= 4:
        return mask_char * length

    if length <= 8:
        return value[0] + mask_char * (length - 2) + value[-1]

    if mode == "last4":
        visible = 4
        return mask_char * (length - visible) + value[-visible:]

    if mode == "first4_last4":
        return value[:4] + mask_char * (length - 8) + value[-4:]

    return value[:2] + mask_char * (length - 4) + value[-2:]


def mask_dict(
    data: dict,
    mask_mode: str = "partial",
    mask_encrypted: bool = True,
    sensitive_keys: list = None,
) -> dict:
    def _is_sensitive_path(path: str) -> bool:
        return is_sensitive_key(path.split(".")[-1], sensitive_keys)

    def _mask_recursive(obj, path: str = ""):
        if isinstance(obj, dict):
            return {k: _mask_recursive(v, f"{path}.{k}" if path else k) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_mask_recursive(item, f"{path}[{i}]") for i, item in enumerate(obj)]
        elif isinstance(obj, str):
            if is_encrypted(obj):
                if mask_encrypted:
                    return mask_value(obj, mask_mode)
                return obj
            if _is_sensitive_path(path):
                return mask_value(obj, mask_mode)
            return obj
        else:
            return obj

    return _mask_recursive(data)


def collect_sensitive_fields(
    data: dict,
    sensitive_keys: list = None,
) -> list:
    fields = []

    def _collect(obj, path: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                child_path = f"{path}.{k}" if path else k
                _collect(v, child_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _collect(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            if is_encrypted(obj) or is_sensitive_key(path.split(".")[-1], sensitive_keys):
                fields.append(path)

    _collect(data)
    return fields


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
