import hashlib
import unittest

from password_security import hash_password, needs_rehash, verify_password


class PasswordSecurityTests(unittest.TestCase):
    def test_new_hash_is_adaptive_and_round_trips(self):
        stored = hash_password('segredo-forte')
        self.assertTrue(stored.startswith(('scrypt:', 'pbkdf2:')))
        self.assertTrue(verify_password('segredo-forte', stored))
        self.assertFalse(verify_password('senha-errada', stored))
        self.assertFalse(needs_rehash(stored))

    def test_legacy_sha256_hash_remains_compatible(self):
        salt = '0123456789abcdef0123456789abcdef'
        expected = hashlib.sha256((salt + 'senha-antiga').encode()).hexdigest()
        legacy = f'{salt}:{expected}'

        self.assertTrue(verify_password('senha-antiga', legacy))
        self.assertFalse(verify_password('outra-senha', legacy))
        self.assertTrue(needs_rehash(legacy))

    def test_invalid_legacy_hash_is_rejected(self):
        self.assertFalse(verify_password('senha', 'salt-invalido:hash-invalido'))

    def test_empty_password_cannot_be_hashed(self):
        with self.assertRaises(ValueError):
            hash_password('')


if __name__ == '__main__':
    unittest.main()
