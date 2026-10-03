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
    approve_document = integration.AppIntegrationTests.approve_document

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
        for rid in ids:
            self.approve_document(rid)
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

    def test_attendance_totals_corrections_and_certificate_source(self):
        self.login_admin()
        start=(date.today()-timedelta(days=10)).isoformat()
        end=(date.today()-timedelta(days=1)).isoformat()
        rid=self.create(inicio=start,termino=end)
        r=self.client.put(f'/api/residentes/{rid}/academico',json={'carga_horaria_prevista':10})
        self.assertEqual(r.status_code,200)
        day=(date.today()-timedelta(days=2)).isoformat()
        data={'data':day,'horas':8,'presenca':'Presente'}
        r=self.client.post(f'/api/residentes/{rid}/frequencia',json=data)
        self.assertEqual(r.status_code,201,r.get_data(as_text=True))
        self.assertEqual((r.get_json()['realizadas'],r.get_json()['faltantes'],r.get_json()['percentual']),(8,2,80))
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/frequencia',json=data).status_code,409)
        data.update(versao=1,horas=6)
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/frequencia',json=data).get_json()['realizadas'],6)
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/frequencia',json=data).status_code,409)
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/frequencia',json={'data':end,'horas':1,'presenca':'Ausente'}).status_code,400)
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/frequencia',json={'data':end,'horas':0,'presenca':'Ausência justificada'}).status_code,201)
        self.assertEqual(self.client.put(f'/api/residentes/{rid}/academico',json={'carga_horaria_prevista':10,'carga_horaria_realizada':10}).status_code,409)
        a=self.client.get(f'/api/residentes/{rid}/academico').get_json()
        self.assertEqual(a['certificado']['carga_horaria_realizada'],6)
        self.assertFalse(a['certificado']['apto'])
        self.assertEqual(self.client.delete(f'/api/residentes/{rid}').status_code,409)

    def test_legacy_hours_migration_preserves_total_once(self):
        import tempfile
        from pathlib import Path
        from db_migrations import ensure_database
        with tempfile.TemporaryDirectory() as tmp:
            path=str(Path(tmp)/'legacy.db')
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE usuarios(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password_hash TEXT,nome TEXT,role TEXT); INSERT INTO usuarios VALUES (1,'gestor','hash','Gestor','admin'); CREATE TABLE residentes(id INTEGER PRIMARY KEY,nome TEXT,especialidade TEXT,mes_ano TEXT,status TEXT,inicio TEXT,termino TEXT,created_at TEXT,updated_at TEXT,carga_horaria_realizada REAL); INSERT INTO residentes VALUES(1,'Aluno existente','Cardiologia','2026-09','Concluído','2026-09-01','2026-09-30',NULL,NULL,42);")
            for _ in range(3):
                ensure_database(path,hash_password=lambda p:p,message_seed=[],pipeline_etapas=self.module.PIPELINE_ETAPAS)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT SUM(horas),COUNT(*) FROM residente_frequencias WHERE residente_id=1').fetchone(),(42,1))
                self.assertEqual(db.execute('SELECT carga_horaria_realizada FROM residentes WHERE id=1').fetchone()[0],42)

    def test_documents_files_expiration_and_private_download(self):
        self.login_admin()
        rid=self.create()
        doc=self.client.post(f'/api/residentes/{rid}/documentos',json={'nome':'Identificacao','obrigatorio':True})
        did=doc.get_json()['id']
        payload={'id':did,'nome':'Identificacao','obrigatorio':True,'status':'Aprovado'}
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/documentos',json=payload).status_code,409)
        upload=self.client.post(f'/api/residentes/{rid}/documentos/{did}/arquivo',data={'arquivo':(io.BytesIO(b'%PDF-1.4\nPrivate test'),'../../arquivo.pdf')})
        self.assertEqual(upload.status_code,201,upload.get_data(as_text=True))
        aid=upload.get_json()['id']
        self.assertNotIn('storage_key',upload.get_data(as_text=True))
        payload['arquivo_id']=aid
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/documentos',json=payload).status_code,200)
        download=self.client.get(f'/api/sge/arquivos/{aid}')
        self.assertEqual(download.status_code,200)
        self.assertIn('attachment',download.headers['Content-Disposition'])
        self.assertEqual(download.headers['Cache-Control'],'private, no-store')
        download.close()
        self.client.get('/logout')
        self.assertEqual(self.client.get(f'/api/sge/arquivos/{aid}').status_code,302)
        self.login_admin()
        with sqlite3.connect(self.db_path) as db:
            db.execute('UPDATE residente_documentos SET validade=? WHERE id=?',((date.today()-timedelta(days=1)).isoformat(),did))
        docs=self.client.get(f'/api/residentes/{rid}/academico').get_json()
        self.assertEqual(docs['documentos'][0]['status'],'Expirado')
        self.assertFalse(docs['certificado']['apto'])
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/documentos/{did}/arquivo',data={'arquivo':(io.BytesIO(b'<script>bad</script>'),'arquivo.pdf')}).status_code,400)
        # Replacing a file resets approval; approval of the stale version is rejected.
        replacement=self.client.post(f'/api/residentes/{rid}/documentos/{did}/arquivo',data={'arquivo':(io.BytesIO(b'%PDF-1.4\nNew'),'arquivo.pdf')})
        self.assertEqual(replacement.status_code,201)
        payload['validade']=None
        self.assertEqual(self.client.post(f'/api/residentes/{rid}/documentos',json=payload).status_code,409)
        previous=self.client.get(f'/api/sge/arquivos/{aid}')
        self.assertEqual(previous.status_code,200)
        previous.close()
        self.assertEqual(self.client.delete(f'/api/residentes/{rid}/documentos/{did}',json={'motivo':'Requisito substituido'}).status_code,200)
        self.assertEqual(self.client.delete(f'/api/residentes/{rid}').status_code,409)

    def test_financial_values_lifecycle_receipts_and_no_pipeline_advance(self):
        self.login_admin(); rid=self.create(valor=1000)
        f=self.client.get(f'/api/residentes/{rid}/financeiro').get_json()
        data={'versao':f['versao'],'valor_previsto':'1000.00','desconto':'100.00','status':'Aguardando pagamento','vencimento':(date.today()-timedelta(days=1)).isoformat()}
        result=self.client.put(f'/api/residentes/{rid}/financeiro',json=data)
        self.assertEqual(result.status_code,200,result.get_data(as_text=True)); f=result.get_json()
        self.assertEqual((f['final_centavos'],f['status_efetivo']),(90000,'Vencido'))
        self.assertEqual(self.client.put(f'/api/residentes/{rid}/financeiro',json=data).status_code,409)
        self.assertEqual(self.client.put(f'/api/residentes/{rid}/financeiro',json={'versao':f['versao'],'desconto':1001}).status_code,400)
        self.assertEqual(self.client.put(f'/api/residentes/{rid}/financeiro',json={'versao':f['versao'],'status':'Pago'}).status_code,400)
        result=self.client.put(f'/api/residentes/{rid}/financeiro',json={'versao':f['versao'],'status':'Pago','data_pagamento':date.today().isoformat()})
        self.assertEqual(result.status_code,200); f=result.get_json()
        pipeline=self.client.get(f'/api/pipeline/residente/{rid}').get_json()
        self.assertEqual([p['etapa'] for p in pipeline if p['situacao']=='pendente'],[1])
        upload=self.client.post(f'/api/residentes/{rid}/financeiro/comprovante',data={'arquivo':(io.BytesIO(b'%PDF-1.4\nReceipt'),'comprovante.pdf')})
        self.assertEqual(upload.status_code,201); f=upload.get_json()
        self.assertEqual(self.client.put(f'/api/residentes/{rid}/financeiro',json={'versao':f['versao'],'status':'Reembolsado','reembolso':1000,'observacao':'Solicitacao'}).status_code,400)
        result=self.client.put(f'/api/residentes/{rid}/financeiro',json={'versao':f['versao'],'status':'Reembolsado','reembolso':'900.00','observacao':'Solicitacao do aluno'})
        self.assertEqual(result.status_code,200,result.get_data(as_text=True))
        self.assertEqual(result.get_json()['reembolso_centavos'],90000)
        self.assertFalse(self.client.get(f'/api/residentes/{rid}/academico').get_json()['certificado']['apto'])

    def test_role_boundaries_finance_and_read_only(self):
        self.login_admin(); rid=self.create()
        for role in ['atendimento','financeiro','somente_leitura','coordenacao']:
            response=self.client.post('/api/usuarios',json={'username':role,'nome':role,'senha':'Role-Test-Password-123!','role':role})
            self.assertEqual(response.status_code,201)
        for role in ['atendimento','financeiro','somente_leitura','coordenacao']:
            self.client.get('/logout')
            self.client.post('/login',json={'username':role,'password':'Role-Test-Password-123!'},headers={'Accept':'application/json'})
            self.assertEqual(self.client.get(f'/api/residentes/{rid}/financeiro').status_code,200)
            f=self.client.get(f'/api/residentes/{rid}/financeiro').get_json()
            r=self.client.put(f'/api/residentes/{rid}/financeiro',json={'versao':f['versao'],'valor_previsto':10})
            self.assertEqual(r.status_code,200 if role=='financeiro' else 403)
            if role in ['financeiro','somente_leitura']:
                self.assertEqual(self.client.post(f'/api/residentes/{rid}/acao',json={'etapa':1,'resultado':'revisado'}).status_code,403)
            if role=='somente_leitura':
                self.assertEqual(self.client.post('/api/integracoes/outlook/enviar',json={'destinatario':'aluno@example.org','assunto':'Teste','mensagem':'Texto'}).status_code,403)
