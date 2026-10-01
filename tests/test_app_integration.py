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

    def test_reports_page_and_aggregates_follow_current_residents(self):
        self.login_admin()
        before = self.client.get('/api/dashboard').get_json()
        pipeline_before = self.client.get('/api/pipeline/dashboard').get_json()
        stage1_before = int((pipeline_before.get('pendentes_por_etapa') or {}).get('1', 0))

        created = self.client.post('/api/residentes', json={
            'nome': 'Relatorio Integracao',
            'especialidade': 'Cardiologia',
            'mes_ano': '2026-12',
            'tipo': 'Residente',
            'modalidade': 'Optativo',
            'status': 'Interessado',
            'status_pagamento': 'Pendente',
            'valor': 1250,
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        after = self.client.get('/api/dashboard').get_json()
        self.assertEqual(after['total'], before['total'] + 1)
        self.assertEqual(after['kpis']['novos'], before['kpis']['novos'] + 1)
        self.assertAlmostEqual(
            float(after['financeiro']['pendente']),
            float(before['financeiro']['pendente']) + 1250,
            places=2,
        )

        pipeline_after = self.client.get('/api/pipeline/dashboard').get_json()
        self.assertEqual(
            int((pipeline_after.get('pendentes_por_etapa') or {}).get('1', 0)),
            stage1_before + 1,
        )

        page = self.client.get('/relatorios')
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn('Visão gerencial', html)
        self.assertIn('id="export-current-reports"', html)
        self.assertIn('relatorios_dashboard.js', html)

        deleted = self.client.delete(f'/api/residentes/{rid}')
        self.assertEqual(deleted.status_code, 200)

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


    def test_academic_tracking_and_certificate_gate(self):
        self.login_admin()
        created = self.client.post('/api/residentes', json={
            'nome': 'Aluno Academico',
            'especialidade': 'Cardiologia',
            'mes_ano': '2026-11',
            'tipo': 'Doutorando',
            'modalidade': 'Optativo',
            'status': 'Concluído',
            'status_pagamento': 'Pago',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        initial = self.client.get(f'/api/residentes/{rid}/academico')
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.get_json()['certificado']['apto'])

        hours = self.client.put(f'/api/residentes/{rid}/academico', json={
            'carga_horaria_prevista': 80,
            'carga_horaria_realizada': 80,
        })
        self.assertEqual(hours.status_code, 200, hours.get_data(as_text=True))
        self.assertFalse(hours.get_json()['certificado']['apto'])

        document = self.client.post(f'/api/residentes/{rid}/documentos', json={
            'nome': 'Documento de identificacao',
            'obrigatorio': True,
            'status': 'Recebido',
        })
        self.assertEqual(document.status_code, 200, document.get_data(as_text=True))
        doc_id = document.get_json()['id']

        blocked = self.client.post(f'/api/residentes/{rid}/certificado', json={'acao': 'emitir'})
        self.assertEqual(blocked.status_code, 409)

        approved = self.client.post(f'/api/residentes/{rid}/documentos', json={
            'id': doc_id,
            'nome': 'Documento de identificacao',
            'obrigatorio': True,
            'status': 'Aprovado',
            'observacao': 'Conferido',
        })
        self.assertEqual(approved.status_code, 200, approved.get_data(as_text=True))

        academic = self.client.get(f'/api/residentes/{rid}/academico').get_json()
        self.assertTrue(academic['certificado']['apto'])
        self.assertEqual(academic['certificado']['progresso_horas'], 100)

        issued = self.client.post(f'/api/residentes/{rid}/certificado', json={'acao': 'emitir'})
        self.assertEqual(issued.status_code, 200, issued.get_data(as_text=True))
        self.assertIsNotNone(issued.get_json()['certificado']['certificado_emitido_em'])

        sent = self.client.post(f'/api/residentes/{rid}/certificado', json={'acao': 'enviar'})
        self.assertEqual(sent.status_code, 200, sent.get_data(as_text=True))
        self.assertIsNotNone(sent.get_json()['certificado']['certificado_enviado_em'])

        deleted = self.client.delete(f'/api/residentes/{rid}')
        self.assertEqual(deleted.status_code, 200)


if __name__ == '__main__':
    unittest.main()
