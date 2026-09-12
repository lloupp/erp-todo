"""Password hashing helpers with backward compatibility for legacy ERP hashes."""

from __future__ import annotations

import hashlib
import hmac

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError('A senha nao pode ser vazia')
    # Werkzeug 3.x defaults to scrypt, a memory-hard password KDF.
    return generate_password_hash(password)


def _verify_legacy_sha256(password: str, stored: str) -> bool:
    if stored.count(':') != 1:
        return False
    salt, expected = stored.split(':', 1)
    if len(salt) != 32 or len(expected) != 64:
        return False
    try:
        int(salt, 16)
        int(expected, 16)
    except ValueError:
        return False
    actual = hashlib.sha256((salt + password).encode()).hexdigest()
    return hmac.compare_digest(actual, expected)


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if stored.startswith(('scrypt:', 'pbkdf2:')):
        try:
            return check_password_hash(stored, password)
        except (ValueError, TypeError):
            return False
    return _verify_legacy_sha256(password, stored)


def needs_rehash(stored: str) -> bool:
    """Legacy hashes should be replaced after a successful password change/login flow."""
    return not stored.startswith(('scrypt:', 'pbkdf2:'))
