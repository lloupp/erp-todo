from pathlib import Path
import unittest


class StartupSafetyTests(unittest.TestCase):
    def test_supported_app_entrypoint_has_no_destructive_bootstrap(self):
        source = Path('app.py').read_text(encoding='utf-8')

        forbidden = (
            'def init_db(',
            'DELETE FROM estagios',
            'UPDATE estagios SET etapa=8 WHERE etapa=7',
            "hash_password('admin')",
            "hash_password('user')",
        )
        for pattern in forbidden:
            self.assertNotIn(pattern, source)

        self.assertIn('from password_security import hash_password, verify_password', source)
        self.assertIn('install_production_guards(app)', source)
        self.assertIn('ensure_database(', source)

    def test_production_entrypoint_uses_safe_facade(self):
        source = Path('wsgi.py').read_text(encoding='utf-8')
        self.assertIn('import app as app_module', source)
        self.assertIn('ensure_database(', source)


if __name__ == '__main__':
    unittest.main()
