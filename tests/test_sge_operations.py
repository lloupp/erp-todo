import io
import os
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch
import test_app_integration as integration


class SgeOperationsTests(unittest.TestCase):
    setUpClass = classmethod(integration.AppIntegrationTests.setUpClass.__func__)
    tearDownClass = classmethod(integration.AppIntegrationTests.tearDownClass.__func__)
    setUp = integration.AppIntegrationTests.setUp
    login_admin = integration.AppIntegrationTests.login_admin

    def create(self, **extra):
        response = self.client.post('/api/residentes', json={
            'nome': 'Teste operacional', 'especialidade': 'Cardiologia',
            'mes_ano': '2026-10', **extra})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()['id']

    def test_invalid_hours_and_status_bypass(self):
        self.login_admin()
        rid = self.create()
        r = self.client.put(f'/api/residentes/{rid}/academico', json={
            'carga_horaria_prevista': 10, 'carga_horaria_realizada': float('inf')})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f'/api/residentes/{rid}/avancar', json={'status': 'Concluído'})
        self.assertEqual(r.status_code, 409)
        r = self.client.put(f'/api/residentes/{rid}', json={'status': 'Concluído'})
        self.assertEqual(r.status_code, 409)
        r = self.client.post('/api/residentes', json={'nome':'Futuro', 'especialidade':'Cardiologia',
            'mes_ano':'2026-10', 'status':'Concluído', 'termino':(date.today()+timedelta(days=10)).isoformat()})
        self.assertEqual(r.status_code, 409)
        r = self.client.post(f'/api/residentes/{rid}/acao', json={'etapa':1,'resultado':'revisado'},
            headers={'Origin':'https://evil.example'})
        self.assertEqual(r.status_code, 403)

    def test_outlook_error_does_not_disclose_secrets(self):
        self.login_admin()
        with patch('microsoft_integrations._send_graph_mail', side_effect=RuntimeError('test-secret token-private')):
            response = self.client.post('/api/integracoes/outlook/enviar', json={
                'destinatario':'test@example.org','assunto':'Teste','mensagem':'Texto'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('test-secret', response.get_data(as_text=True))
        with sqlite3.connect(self.db_path) as db:
            error = db.execute("SELECT erro FROM integracao_eventos WHERE status='error' ORDER BY id DESC").fetchone()[0]
            self.assertNotIn('token-private', error)

    def test_pipeline_pending_unique(self):
        self.login_admin()
        rid = self.create()
        with sqlite3.connect(self.db_path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO pipeline_acoes(residente_id,etapa,acao_tipo,situacao) VALUES (?,1,'triagem','pendente')",(rid,))
