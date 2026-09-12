import unittest

from flask import Flask, jsonify
from flask_login import LoginManager, UserMixin, login_user

from production_guards import install_production_guards


class User(UserMixin):
    def __init__(self, user_id, role):
        self.id = user_id
        self.role = role


class ProductionGuardsTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'test-secret'
        app.config.update(TESTING=True)
        login_manager = LoginManager(app)

        @login_manager.user_loader
        def load_user(user_id):
            return User(user_id, 'admin' if user_id == '1' else 'user')

        @app.post('/login/<user_id>')
        def login(user_id):
            login_user(load_user(user_id))
            return jsonify({'ok': True})

        @app.post('/api/area-medica')
        def area_medica_write():
            return jsonify({'ok': True})

        @app.put('/api/mensagens-modelo/teste')
        def message_write():
            return jsonify({'ok': True})

        @app.post('/api/residentes')
        def normal_write():
            return jsonify({'ok': True})

        install_production_guards(app)
        self.app = app
        self.client = app.test_client()

    def test_anonymous_sensitive_mutation_is_denied(self):
        response = self.client.post('/api/area-medica', json={})
        self.assertEqual(response.status_code, 401)

    def test_regular_user_sensitive_mutation_is_denied(self):
        self.client.post('/login/2')
        response = self.client.put('/api/mensagens-modelo/teste', json={})
        self.assertEqual(response.status_code, 403)

    def test_admin_sensitive_mutation_is_allowed(self):
        self.client.post('/login/1')
        response = self.client.post('/api/area-medica', json={})
        self.assertEqual(response.status_code, 200)

    def test_non_configuration_mutation_is_not_blocked(self):
        response = self.client.post('/api/residentes', json={})
        self.assertEqual(response.status_code, 200)

    def test_security_headers_are_added(self):
        response = self.client.post('/api/residentes', json={})
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertIn('geolocation=()', response.headers['Permissions-Policy'])


if __name__ == '__main__':
    unittest.main()
