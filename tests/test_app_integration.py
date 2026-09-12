import importlib
import os
import sqlite3
import tempfile
import unittest


class AppIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = os.path.join(cls.tmp.name, 'integration.db')
        os.environ['SECRET_KEY'] = 'integration-test-secret'
        os.environ['ERP_DATABASE'] = cls.db_path
        os.environ['BOOTSTRAP_ADMIN_PASSWORD'] = 'Strong-Test-Password-123!'
        os.environ['BOOTSTRAP_ADMIN_USERNAME'] = 'admin'
        os.environ['BOOTSTRAP_ADMIN_NAME'] = 'Administrador Teste'

        cls.module = importlib.import_module('app')
        cls.module.app.config.update(TESTING=True, DATABASE=cls.db_path)
        cls.module.bootstrap_database()
        cls.client = cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        for key in (
            'ERP_DATABASE', 'BOOTSTRAP_ADMIN_PASSWORD',
            'BOOTSTRAP_ADMIN_USERNAME', 'BOOTSTRAP_ADMIN_NAME',
        ):
            os.environ.pop(key, None)

    def setUp(self):
        self.client.get('/logout', follow_redirects=False)

    def login_admin(self):
        response = self.client.post(
            '/login',
            json={'username': 'admin', 'password': 'Strong-Test-Password-123!'},
            headers={'Accept': 'application/json'},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.get_json()['ok'])

    def test_health_and_auth_boundary(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        response = self.client.get('/api/me', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_admin_login_uses_bootstrap_account(self):
        self.login_admin()
        me = self.client.get('/api/me')
        self.assertEqual(me.status_code, 200)
        payload = me.get_json()
        self.assertEqual(payload['username'], 'admin')
        self.assertEqual(payload['role'], 'admin')

        with sqlite3.connect(self.db_path) as db:
            stored = db.execute(
                "SELECT password_hash FROM usuarios WHERE username='admin'"
            ).fetchone()[0]
        self.assertTrue(stored.startswith(('scrypt:', 'pbkdf2:')))

    def test_login_blocks_external_next_redirect(self):
        response = self.client.post(
            '/login?next=https://evil.example/phish',
            data={'username': 'admin', 'password': 'Strong-Test-Password-123!'},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/residentes')

    def test_resident_creation_and_pipeline_transition(self):
        self.login_admin()
        created = self.client.post('/api/residentes', json={
            'nome': 'Aluno Integracao',
            'especialidade': 'Cardiologia',
            'mes_ano': '2026-10',
            'tipo': 'Residente',
            'modalidade': 'Optativo',
            'status': 'Interessado',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        pipeline = self.client.get(f'/api/pipeline/residente/{rid}')
        self.assertEqual(pipeline.status_code, 200)
        rows = pipeline.get_json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['etapa'], 1)
        self.assertEqual(rows[0]['situacao'], 'pendente')

        step1 = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 1, 'resultado': 'revisado'},
        )
        self.assertEqual(step1.status_code, 200, step1.get_data(as_text=True))
        self.assertEqual(step1.get_json()['proxima_etapa'], 2)

        step2 = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 2, 'resultado': 'confirmou'},
        )
        self.assertEqual(step2.status_code, 200, step2.get_data(as_text=True))
        self.assertEqual(step2.get_json()['novo_status'], 'Em andamento')
        self.assertEqual(step2.get_json()['proxima_etapa'], 3)

        detail = self.client.get(f'/api/pipeline/residente/{rid}').get_json()
        pending = [row for row in detail if row['situacao'] == 'pendente']
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['etapa'], 3)

    def test_non_admin_cannot_mutate_sensitive_configuration(self):
        self.login_admin()
        created = self.client.post('/api/usuarios', json={
            'username': 'regular',
            'nome': 'Usuario Regular',
            'senha': 'Another-Strong-Password-123!',
            'role': 'user',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))

        self.client.get('/logout')
        login = self.client.post(
            '/login',
            json={'username': 'regular', 'password': 'Another-Strong-Password-123!'},
            headers={'Accept': 'application/json'},
        )
        self.assertEqual(login.status_code, 200)

        response = self.client.post('/api/area-medica', json={'especialidade': 'Teste'})
        self.assertEqual(response.status_code, 403)


if __name__ == '__main__':
    unittest.main()
