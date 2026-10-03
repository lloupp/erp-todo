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

    def test_capacity_counts_legacy_and_override(self):
        self.login_admin()
        tomorrow = (date.today()+timedelta(days=1)).isoformat()
        end = (date.today()+timedelta(days=20)).isoformat()
        p = self.client.post('/api/sge/vagas', json={'especialidade':'Neurologia','modalidade':'Optativo',
            'inicio':tomorrow,'termino':end,'capacidade':1})
        self.assertEqual(p.status_code,201,p.get_data(as_text=True))
        pid = p.get_json()['id']
        a = self.create(especialidade='Neurologia',inicio=tomorrow,termino=end,status='Confirmado')
        p = next(p for p in self.client.get('/api/sge/vagas').get_json() if p['id']==pid)
        self.assertEqual((p['ocupadas'],p['disponiveis'],p['situacao']),(1,0,'Lotado'))
        data={'nome':'Segundo','especialidade':'Neurologia','mes_ano':tomorrow[:7],
            'inicio':tomorrow,'termino':end,'status':'Confirmado'}
        self.assertEqual(self.client.post('/api/residentes',json=data).status_code,409)
        data.update(override_capacidade=True,motivo_capacidade='Autorizacao excepcional da coordenacao')
        self.assertEqual(self.client.post('/api/residentes',json=data).status_code,201)
        p = next(p for p in self.client.get('/api/sge/vagas').get_json() if p['id']==pid)
        self.assertEqual(p['excedentes'],1)
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sge_auditoria WHERE acao='override_capacidade'").fetchone()[0],1)
        self.assertEqual(self.client.put(f'/api/sge/vagas/{pid}',json={'capacidade':0}).status_code,409)
        # Date changes cannot silently move a confirmed record outside configured capacity.
        self.assertEqual(self.client.put(f'/api/residentes/{a}',json={'termino':'2050-01-01'}).status_code,409)
        self.module.bootstrap_database()
        self.module.bootstrap_database()
        p = next(p for p in self.client.get('/api/sge/vagas').get_json() if p['id']==pid)
        self.assertEqual(p['ocupadas'],2)

    def test_last_place_concurrent_pipeline_confirmations(self):
        from concurrent.futures import ThreadPoolExecutor
        self.login_admin()
        start, end = '2026-10-10', '2026-10-20'
        p=self.client.post('/api/sge/vagas',json={'especialidade':'Neurocirurgia','modalidade':'Optativo',
            'inicio':start,'termino':end,'capacidade':1})
        self.assertEqual(p.status_code,201)
        ids=[self.create(especialidade='Neurocirurgia',inicio=start,termino=end,status_pagamento='Pago') for _ in range(2)]
        with sqlite3.connect(self.db_path) as db:
            for rid in ids:
                db.execute("UPDATE pipeline_acoes SET etapa=7,acao_tipo='analisar_comprovante' WHERE residente_id=?",(rid,))
        def confirm(rid):
            client=self.module.app.test_client()
            client.post('/login',json={'username':'admin','password':'Strong-Test-Password-123!'},headers={'Accept':'application/json'})
            return client.post(f'/api/residentes/{rid}/acao',json={'etapa':7,'resultado':'comprovante_ok'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(confirm,ids))
        self.assertEqual(sorted(statuses),[200,409])
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM residentes WHERE especialidade='Neurocirurgia' AND status='Confirmado'").fetchone()[0],1)
