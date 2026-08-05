import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet(secret_key):
    digest = hashlib.sha256(f"sprachplattform-ki:{secret_key}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value):
    return _fernet(settings.SECRET_KEY).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value):
    keys = (settings.SECRET_KEY, *getattr(settings, "SECRET_KEY_FALLBACKS", ()))
    for secret_key in keys:
        try:
            return _fernet(secret_key).decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken:
            continue
    raise ValueError("Der gespeicherte API-Schlüssel kann nicht entschlüsselt werden.")
