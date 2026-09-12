import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from db_migrations import ensure_database


MESSAGE_SEED = [
    ('example', 'Example', 'Hello {{nome}}', 'nome'),
]
PIPELINE_ETAPAS = {
    1: 'triagem',
    2: 'confirmar_aluno',
    3: 'acionar_chefe',
    4: 'deferimento',
    5: 'solicitar_link_financeiro',
    6: 'enviar_link_docs',
    7: 'analisar_comprovante',
    8: 'orientacoes_1o_dia',
}


def fake_hash(password):
    return f'hash:{password}'


class SafeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, 'erp.db')

    def tearDown(self):
        self.tmp.cleanup()

    def ensure(self):
        ensure_database(
            self.db_path,
            hash_password=fake_hash,
            message_seed=MESSAGE_SEED,
            pipeline_etapas=PIPELINE_ETAPAS,
            data_dir=None,
        )

    def test_fresh_database_requires_explicit_admin_password(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'BOOTSTRAP_ADMIN_PASSWORD'):
                self.ensure()

    def test_fresh_database_creates_only_explicit_admin_and_no_demo_records(self):
        env = {
            'BOOTSTRAP_ADMIN_PASSWORD': 'strong-secret',
            'BOOTSTRAP_ADMIN_USERNAME': 'gestor',
            'BOOTSTRAP_ADMIN_NAME': 'Gestor ERP',
        }
        with patch.dict(os.environ, env, clear=True):
            self.ensure()

        db = sqlite3.connect(self.db_path)
        try:
            users = db.execute(
                'SELECT username, password_hash, nome, role FROM usuarios ORDER BY id'
            ).fetchall()
            self.assertEqual(users, [('gestor', 'hash:strong-secret', 'Gestor ERP', 'admin')])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM estagios').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM residentes').fetchone()[0], 0)
        finally:
            db.close()

    def test_second_start_is_idempotent_and_preserves_stage_seven(self):
        with patch.dict(os.environ, {'BOOTSTRAP_ADMIN_PASSWORD': 'first-secret'}, clear=True):
            self.ensure()

        db = sqlite3.connect(self.db_path)
        try:
            db.execute(
                '''INSERT INTO estagios
                   (tipo_id, mes_ano, semana, nome, especialidade, etapa)
                   VALUES (1, '2026-09', 1, 'Caso Real', 'Cardiologia', 7)'''
            )
            db.execute(
                '''INSERT INTO residentes
                   (nome, especialidade, mes_ano, status)
                   VALUES ('Pessoa Real', 'Cardiologia', '2026-09', 'Deferido')'''
            )
            db.commit()
        finally:
            db.close()

        with patch.dict(os.environ, {}, clear=True):
            self.ensure()
            self.ensure()

        db = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                db.execute("SELECT etapa FROM estagios WHERE nome='Caso Real'").fetchone()[0],
                7,
            )
            self.assertEqual(db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0], 1)
            pipeline = db.execute(
                '''SELECT etapa, situacao FROM pipeline_acoes pa
                   JOIN residentes r ON r.id = pa.residente_id
                   WHERE r.nome='Pessoa Real' '''
            ).fetchall()
            self.assertEqual(pipeline, [(5, 'pendente')])
        finally:
            db.close()

    def test_additive_migration_preserves_existing_rows(self):
        db = sqlite3.connect(self.db_path)
        try:
            db.executescript('''
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                );
                INSERT INTO usuarios (username, password_hash, nome, role)
                VALUES ('existing', 'legacy-hash', 'Existing User', 'admin');

                CREATE TABLE estagios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo_id INTEGER NOT NULL,
                    mes_ano TEXT NOT NULL,
                    semana INTEGER NOT NULL,
                    nome TEXT NOT NULL,
                    especialidade TEXT NOT NULL,
                    etapa INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO estagios (tipo_id, mes_ano, semana, nome, especialidade, etapa)
                VALUES (1, '2026-09', 2, 'Persistente', 'Pediatria', 7);
            ''')
            db.commit()
        finally:
            db.close()

        with patch.dict(os.environ, {}, clear=True):
            self.ensure()

        db = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                db.execute('SELECT username, password_hash FROM usuarios').fetchall(),
                [('existing', 'legacy-hash')],
            )
            self.assertEqual(
                db.execute("SELECT nome, etapa FROM estagios WHERE nome='Persistente'").fetchone(),
                ('Persistente', 7),
            )
            columns = {row[1] for row in db.execute('PRAGMA table_info(estagios)')}
            self.assertIn('carga_horaria', columns)
            self.assertIn('comprovante_estagio', columns)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
