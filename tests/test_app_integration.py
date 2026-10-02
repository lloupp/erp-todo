import importlib
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch


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
        os.environ['FORMS_WEBHOOK_ENABLED'] = 'true'
        os.environ['FORMS_WEBHOOK_SECRET'] = 'integration-forms-secret'
        os.environ['OUTLOOK_GRAPH_ENABLED'] = 'true'
        os.environ['MICROSOFT_TENANT_ID'] = 'test-tenant'
        os.environ['MICROSOFT_CLIENT_ID'] = 'test-client'
        os.environ['MICROSOFT_CLIENT_SECRET'] = 'test-secret'
        os.environ['OUTLOOK_SENDER'] = 'ensino@example.org'

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
            'FORMS_WEBHOOK_ENABLED', 'FORMS_WEBHOOK_SECRET',
            'OUTLOOK_GRAPH_ENABLED', 'MICROSOFT_TENANT_ID',
            'MICROSOFT_CLIENT_ID', 'MICROSOFT_CLIENT_SECRET',
            'OUTLOOK_SENDER',
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


    def test_microsoft_forms_webhook_is_idempotent_and_enters_triage(self):
        payload = {
            'form_id': 'estagio-optativo',
            'response_id': 'resp-1001',
            'nome': 'Aluno Forms Integracao',
            'email': 'aluno.forms@example.org',
            'telefone': '(51) 99999-1234',
            'tipo': 'Residente',
            'modalidade': 'Optativo',
            'especialidade': 'Cardiologia',
            'instituicao_origem': 'Universidade Teste',
            'mes_desejado': 'novembro 2026',
            'periodo_desejado': '01/11/2026 a 30/11/2026',
        }
        headers = {'X-Forms-Webhook-Secret': 'integration-forms-secret'}

        created = self.client.post(
            '/api/integracoes/forms/inscricao', json=payload, headers=headers
        )
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        repeated = self.client.post(
            '/api/integracoes/forms/inscricao', json=payload, headers=headers
        )
        self.assertEqual(repeated.status_code, 200, repeated.get_data(as_text=True))
        self.assertTrue(repeated.get_json()['duplicado'])
        self.assertEqual(repeated.get_json()['id'], rid)

        rejected = self.client.post(
            '/api/integracoes/forms/inscricao',
            json={**payload, 'response_id': 'resp-invalid-secret'},
            headers={'X-Forms-Webhook-Secret': 'wrong-secret'},
        )
        self.assertEqual(rejected.status_code, 401)

        with sqlite3.connect(self.db_path) as db:
            resident = db.execute(
                """SELECT nome, mes_ano, status, origem, origem_ref
                   FROM residentes WHERE id=?""",
                (rid,),
            ).fetchone()
            self.assertEqual(resident[0], 'Aluno Forms Integracao')
            self.assertEqual(resident[1], '2026-11')
            self.assertEqual(resident[2], 'Interessado')
            self.assertEqual(resident[3], 'microsoft_forms')
            self.assertEqual(resident[4], 'estagio-optativo:resp-1001')

            pipeline = db.execute(
                """SELECT etapa, situacao FROM pipeline_acoes
                   WHERE residente_id=? ORDER BY id""",
                (rid,),
            ).fetchall()
            self.assertEqual(pipeline, [(1, 'pendente')])

            audit = db.execute(
                """SELECT provider, event_type, status, payload_json
                   FROM integracao_eventos
                   WHERE residente_id=? ORDER BY id DESC LIMIT 1""",
                (rid,),
            ).fetchone()
            self.assertEqual(audit[0:3], ('microsoft_forms', 'new_response', 'success'))
            self.assertNotIn('aluno.forms@example.org', audit[3])

        self.login_admin()
        deleted = self.client.delete(f'/api/residentes/{rid}')
        self.assertEqual(deleted.status_code, 200)

    def test_outlook_pipeline_send_uses_graph_and_is_audited(self):
        self.login_admin()
        created = self.client.post('/api/residentes', json={
            'nome': 'Aluno Outlook Integracao',
            'email': 'aluno.outlook@example.org',
            'especialidade': 'Cardiologia',
            'mes_ano': '2026-11',
            'tipo': 'Residente',
            'modalidade': 'Optativo',
            'status': 'Interessado',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        with patch('microsoft_integrations._send_graph_mail') as mocked_send:
            response = self.client.post('/api/integracoes/outlook/enviar', json={
                'residente_id': rid,
                'etapa': 2,
                'destinatario': 'aluno.outlook@example.org',
                'assunto': 'Confirmação do estágio',
                'mensagem': 'Mensagem de teste do pipeline.',
            })

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.get_json()['enviado'])
        mocked_send.assert_called_once()
        call = mocked_send.call_args.kwargs
        self.assertEqual(call['to'], 'aluno.outlook@example.org')
        self.assertEqual(call['subject'], 'Confirmação do estágio')
        self.assertEqual(call['body'], 'Mensagem de teste do pipeline.')

        with sqlite3.connect(self.db_path) as db:
            event = db.execute(
                """SELECT provider, event_type, direction, status, responsavel, payload_json
                   FROM integracao_eventos
                   WHERE residente_id=? AND provider='outlook'
                   ORDER BY id DESC LIMIT 1""",
                (rid,),
            ).fetchone()
            self.assertEqual(event[0:4], ('outlook', 'send_mail', 'outbound', 'success'))
            self.assertEqual(event[4], 'Administrador Teste')
            self.assertNotIn('Mensagem de teste do pipeline.', event[5])

        status = self.client.get('/api/integracoes/status')
        self.assertEqual(status.status_code, 200)
        integrations = status.get_json()
        self.assertTrue(integrations['microsoft_forms']['configured'])
        self.assertTrue(integrations['outlook']['configured'])
        self.assertNotIn('test-secret', status.get_data(as_text=True))

        deleted = self.client.delete(f'/api/residentes/{rid}')
        self.assertEqual(deleted.status_code, 200)


    def test_pipeline_task_management_priority_owner_and_block(self):
        self.login_admin()
        created = self.client.post('/api/residentes', json={
            'nome': 'Aluno Fila Pipeline',
            'especialidade': 'Cardiologia',
            'mes_ano': '2026-10',
            'tipo': 'Residente',
            'modalidade': 'Optativo',
            'status': 'Interessado',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        fila = self.client.get('/api/pipeline/fila').get_json()
        item = next(x for x in fila if x['residente_id'] == rid)
        self.assertEqual(item['etapa'], 1)
        self.assertTrue(item['prazo_em'])

        managed = self.client.put(
            f"/api/pipeline/acoes/{item['acao_id']}",
            json={
                'prioridade': 2,
                'bloqueado': True,
                'bloqueio_motivo': 'Aguardando documento externo',
                'assumir': True,
            },
        )
        self.assertEqual(managed.status_code, 200, managed.get_data(as_text=True))
        payload = managed.get_json()
        self.assertEqual(payload['prioridade'], 2)
        self.assertEqual(payload['bloqueado'], 1)
        self.assertEqual(payload['atribuido_a'], 'Administrador Teste')

        blocked = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 1, 'resultado': 'revisado'},
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('bloqueada', blocked.get_json()['erro'].lower())

        legacy = self.client.post(
            f'/api/residentes/{rid}/avancar',
            json={'status': 'Em andamento'},
        )
        self.assertEqual(legacy.status_code, 409)

        dashboard = self.client.get('/api/pipeline/dashboard').get_json()
        self.assertGreaterEqual(dashboard['bloqueados'], 1)
        self.assertGreaterEqual(dashboard['criticos'], 1)

        unblocked = self.client.put(
            f"/api/pipeline/acoes/{item['acao_id']}",
            json={
                'prioridade': 1,
                'bloqueado': False,
                'bloqueio_motivo': '',
            },
        )
        self.assertEqual(unblocked.status_code, 200, unblocked.get_data(as_text=True))

        advanced = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 1, 'resultado': 'revisado'},
        )
        self.assertEqual(advanced.status_code, 200, advanced.get_data(as_text=True))
        self.assertEqual(advanced.get_json()['proxima_etapa'], 2)

        deleted = self.client.delete(f'/api/residentes/{rid}')
        self.assertEqual(deleted.status_code, 200)

    def test_pipeline_orientation_does_not_finish_internship(self):
        self.login_admin()
        inicio = (date.today() + timedelta(days=3)).isoformat()
        termino_futuro = (date.today() + timedelta(days=10)).isoformat()

        created = self.client.post('/api/residentes', json={
            'nome': 'Aluno Conclusao Real',
            'especialidade': 'Cardiologia',
            'mes_ano': inicio[:7],
            'tipo': 'Residente',
            'modalidade': 'Optativo',
            'status': 'Interessado',
            'inicio': inicio,
            'termino': termino_futuro,
            'status_pagamento': 'Pendente',
        })
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        rid = created.get_json()['id']

        sequence = [
            (1, 'revisado'),
            (2, 'confirmou'),
            (3, 'enviado'),
            (4, 'defere'),
            (5, 'solicitado'),
            (6, 'enviado'),
        ]
        for etapa, resultado in sequence:
            response = self.client.post(
                f'/api/residentes/{rid}/acao',
                json={'etapa': etapa, 'resultado': resultado},
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        unpaid = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 7, 'resultado': 'comprovante_ok'},
        )
        self.assertEqual(unpaid.status_code, 400)
        self.assertIn('pagamento', unpaid.get_json()['erro'].lower())

        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE residentes SET status_pagamento='Pago' WHERE id=?",
                (rid,),
            )
            db.commit()

        confirmed = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 7, 'resultado': 'comprovante_ok'},
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.get_data(as_text=True))
        self.assertEqual(confirmed.get_json()['novo_status'], 'Confirmado')
        self.assertEqual(confirmed.get_json()['proxima_etapa'], 8)

        orientations = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 8, 'resultado': 'enviado'},
        )
        self.assertEqual(orientations.status_code, 200, orientations.get_data(as_text=True))
        self.assertIsNone(orientations.get_json()['novo_status'])
        self.assertEqual(orientations.get_json()['proxima_etapa'], 9)

        with sqlite3.connect(self.db_path) as db:
            status = db.execute(
                "SELECT status FROM residentes WHERE id=?", (rid,)
            ).fetchone()[0]
            self.assertEqual(status, 'Confirmado')
            stage9 = db.execute(
                """SELECT etapa, prazo_em FROM pipeline_acoes
                   WHERE residente_id=? AND situacao='pendente'""",
                (rid,),
            ).fetchone()
            self.assertEqual(stage9[0], 9)
            self.assertEqual(stage9[1], termino_futuro)

        too_early = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 9, 'resultado': 'concluido'},
        )
        self.assertEqual(too_early.status_code, 400)
        self.assertIn('ainda nao pode', too_early.get_json()['erro'].lower())

        termino_passado = (date.today() - timedelta(days=1)).isoformat()
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE residentes SET termino=? WHERE id=?",
                (termino_passado, rid),
            )
            db.commit()

        finished = self.client.post(
            f'/api/residentes/{rid}/acao',
            json={'etapa': 9, 'resultado': 'concluido'},
        )
        self.assertEqual(finished.status_code, 200, finished.get_data(as_text=True))
        self.assertEqual(finished.get_json()['novo_status'], 'Concluído')

        deleted = self.client.delete(f'/api/residentes/{rid}')
        self.assertEqual(deleted.status_code, 200)


if __name__ == '__main__':
    unittest.main()
