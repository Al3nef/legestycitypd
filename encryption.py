"""تشفير AES-256-CBC - لصفحة الأدوات فقط"""

import os
import base64
import hashlib

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False
    print("⚠️  ثبّت cryptography: pip install cryptography")

DEFAULT_SECRET = "lspd-super-secret-key-2024"


def _get_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode('utf-8')).digest()


def encrypt_text(plain: str, secret: str = DEFAULT_SECRET) -> str:
    if not CRYPTO_OK:
        return plain
    key = _get_key(secret)
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plain.encode('utf-8')) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    ct = enc.update(padded) + enc.finalize()
    return base64.b64encode(iv + ct).decode('utf-8')


def decrypt_text(token: str, secret: str = DEFAULT_SECRET) -> str:
    if not CRYPTO_OK:
        return token
    try:
        key = _get_key(secret)
        raw = base64.b64decode(token.encode('utf-8'))
        iv, ct = raw[:16], raw[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        dec = cipher.decryptor()
        padded = dec.update(ct) + dec.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return (unpadder.update(padded) + unpadder.finalize()).decode('utf-8')
    except Exception as e:
        return f"[تعذّر فك التشفير: {e}]"