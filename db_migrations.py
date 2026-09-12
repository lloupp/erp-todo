"""Production-safe SQLite schema bootstrap and additive migrations.

This module intentionally never deletes operational data and never performs
ambiguous data rewrites during normal process startup. Schema changes here must
be idempotent because every supported entry point may call ``ensure_database``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta


LIMITES_SEED = [
    ('Anestesiologia', 4), ('Cardiologia', 4), ('Cirurgia cardiovascular', 2),
    ('Cirurgia de aparelho digestivo', 3), ('Cirurgia de cabeca e pescoco', 3),
    ('Cirurgia geral', 8), ('Cirurgia oncologica', 3), ('Cirurgia pediatrica', 4),
    ('Cirurgia plastica', 3), ('Cirurgia toracica', 2), ('Clinica medica', 8),
    ('Emergencia adulta', 8), ('Emergencia cardiologica', 3), ('Gastroenterologia', 2),
    ('Geriatria', 3), ('Mastologia', 3), ('Neurologia pediatrica', 2),
    ('Neurocirurgia', 4), ('Oncologia clinica', 4), ('Otorrino', 2),
    ('Terapia intensiva', 2),
]

PIPELINE_STAGE_BY_STATUS = {
    'Interessado': 1,
    'Em andamento': 3,
    'Trocado': 3,
    'Deferido': 5,
    'Confirmado': 8,
}


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f'PRAGMA table_info({table})').fetchall()}


def _add_missing_columns(db: sqlite3.Connection, table: str, columns: list[tuple[str, str]]) -> None:
    existing = _columns(db, table)
    for name, definition in columns:
        if name not in existing:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
            existing.add(name)


def _seed_area_medica(db: sqlite3.Connection, data_dir: str | None) -> None:
    if db.execute('SELECT COUNT(*) FROM area_medica').fetchone()[0] != 0 or not data_dir:
        return
    path = os.path.join(data_dir, 'area_medica.json')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as handle:
        contatos = json.load(handle)
    db.executemany(
        '''INSERT INTO area_medica
           (especialidade, nome, celular, email, obs_internato, obs_residencia)
           VALUES (?,?,?,?,?,?)''',
        [
            (
                item.get('especialidade'), item.get('nome'), item.get('celular'),
                item.get('email'), item.get('obs_internato'), item.get('obs_residencia'),
            )
            for item in contatos
            if item.get('especialidade')
        ],
    )


def _backfill_pipeline(db: sqlite3.Connection, pipeline_etapas: dict[int, str]) -> None:
    rows = db.execute('''
        SELECT r.id, r.status, r.inicio
        FROM residentes r
        WHERE NOT EXISTS (
            SELECT 1 FROM pipeline_acoes pa WHERE pa.residente_id = r.id
        )
    ''').fetchall()
    for residente_id, status, inicio in rows:
        etapa = PIPELINE_STAGE_BY_STATUS.get(status)
        if not etapa or etapa not in pipeline_etapas:
            continue
        reagendado_para = None
        if etapa == 8 and inicio:
            try:
                target = datetime.strptime(str(inicio)[:10], '%Y-%m-%d') - timedelta(days=7)
                reagendado_para = target.strftime('%Y-%m-%d')
            except ValueError:
                pass
        db.execute(
            '''INSERT INTO pipeline_acoes
               (residente_id, etapa, acao_tipo, situacao, reagendado_para)
               VALUES (?, ?, ?, 'pendente', ?)''',
            (residente_id, etapa, pipeline_etapas[etapa], reagendado_para),
        )


def ensure_database(
    db_path: str,
    *,
    hash_password,
    message_seed,
    pipeline_etapas: dict[int, str],
    data_dir: str | None = None,
) -> None:
    """Create/update the database without deleting user data.

    A fresh installation must provide ``BOOTSTRAP_ADMIN_PASSWORD``. Existing
    installations are left untouched. This removes the historical admin/admin
    and user/user production defaults.
    """
    db = sqlite3.connect(db_path, timeout=10)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('PRAGMA busy_timeout = 5000')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tipo_estagio (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                last_login DATETIME
            );

            CREATE TABLE IF NOT EXISTS estagios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_id INTEGER NOT NULL REFERENCES tipo_estagio(id),
                mes_ano TEXT NOT NULL,
                semana INTEGER NOT NULL,
                nome TEXT NOT NULL,
                cpf TEXT,
                especialidade TEXT NOT NULL,
                cracha TEXT,
                valor REAL,
                forma_pagamento TEXT,
                status_pagamento TEXT DEFAULT 'Pendente',
                comprovante_pagamento TEXT,
                inicio DATE,
                termino DATE,
                email TEXT,
                telefone TEXT,
                observacao TEXT,
                documentos TEXT,
                envio_certificado DATE,
                etapa INTEGER NOT NULL DEFAULT 0,
                carga_horaria INTEGER,
                comprovante_estagio INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS historico_etapas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estagio_id INTEGER NOT NULL REFERENCES estagios(id),
                etapa INTEGER NOT NULL,
                observacao TEXT,
                responsavel TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notificacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estagio_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                mensagem TEXT NOT NULL,
                email_destino TEXT,
                enviado INTEGER DEFAULT 0,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS limite_especialidade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                especialidade TEXT UNIQUE NOT NULL COLLATE NOCASE,
                limite_semanal INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS residentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT,
                telefone TEXT,
                cpf TEXT,
                tipo TEXT NOT NULL DEFAULT 'Residente',
                modalidade TEXT NOT NULL DEFAULT 'Optativo',
                especialidade TEXT NOT NULL,
                subespecialidade TEXT,
                instituicao_origem TEXT,
                programa_ano TEXT,
                mes_ano TEXT NOT NULL,
                inicio DATE,
                termino DATE,
                status TEXT NOT NULL DEFAULT 'Interessado',
                valor REAL,
                forma_pagamento TEXT,
                status_pagamento TEXT DEFAULT 'Pendente',
                comprovante_pagamento TEXT,
                observacao TEXT,
                data_inscricao TEXT,
                periodo_desejado TEXT,
                mes_desejado TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS historico_residentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                residente_id INTEGER NOT NULL REFERENCES residentes(id),
                status TEXT NOT NULL,
                observacao TEXT,
                responsavel TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS area_medica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                especialidade TEXT NOT NULL,
                nome TEXT,
                celular TEXT,
                email TEXT,
                obs_internato TEXT,
                obs_residencia TEXT
            );

            CREATE TABLE IF NOT EXISTS mensagens_modelo (
                chave TEXT PRIMARY KEY,
                titulo TEXT NOT NULL,
                texto TEXT NOT NULL,
                placeholders TEXT
            );

            CREATE TABLE IF NOT EXISTS pipeline_acoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                residente_id INTEGER NOT NULL REFERENCES residentes(id),
                etapa INTEGER NOT NULL,
                acao_tipo TEXT NOT NULL,
                situacao TEXT NOT NULL DEFAULT 'pendente',
                responsavel TEXT,
                observacao TEXT,
                reagendado_para DATE,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                concluido_em DATETIME
            );

            CREATE INDEX IF NOT EXISTS idx_pipeline_acoes_residente
                ON pipeline_acoes(residente_id);
            CREATE INDEX IF NOT EXISTS idx_pipeline_acoes_situacao
                ON pipeline_acoes(situacao, etapa);
        ''')

        _add_missing_columns(db, 'estagios', [
            ('cpf', 'TEXT'), ('forma_pagamento', 'TEXT'),
            ('status_pagamento', "TEXT DEFAULT 'Pendente'"),
            ('comprovante_pagamento', 'TEXT'), ('inicio', 'DATE'),
            ('comprovante_estagio', 'INTEGER DEFAULT 0'), ('carga_horaria', 'INTEGER'),
        ])
        _add_missing_columns(db, 'usuarios', [('last_login', 'DATETIME')])
        _add_missing_columns(db, 'residentes', [
            ('subespecialidade', 'TEXT'), ('programa_ano', 'TEXT'),
            ('instituicao_origem', 'TEXT'), ('cpf', 'TEXT'), ('valor', 'REAL'),
            ('forma_pagamento', 'TEXT'), ('status_pagamento', "TEXT DEFAULT 'Pendente'"),
            ('comprovante_pagamento', 'TEXT'), ('data_inscricao', 'TEXT'),
            ('periodo_desejado', 'TEXT'), ('mes_desejado', 'TEXT'),
        ])

        db.execute('DROP INDEX IF EXISTS idx_estagios_cracha')
        db.executemany(
            'INSERT OR IGNORE INTO tipo_estagio (id, nome) VALUES (?, ?)',
            [(1, 'Observership'), (2, 'Obrigatorio'), (3, 'Optativo')],
        )
        db.executemany(
            'INSERT OR IGNORE INTO limite_especialidade (especialidade, limite_semanal) VALUES (?,?)',
            LIMITES_SEED,
        )
        db.executemany(
            'INSERT OR IGNORE INTO mensagens_modelo (chave, titulo, texto, placeholders) VALUES (?,?,?,?)',
            message_seed,
        )
        _seed_area_medica(db, data_dir)
        _backfill_pipeline(db, pipeline_etapas)

        # The old application used to rewrite stage 7 -> 8 on every startup.
        # We deliberately mark the new baseline without replaying that ambiguous
        # data migration, preserving current operational stage values.
        db.execute(
            "INSERT OR IGNORE INTO schema_migrations (name) VALUES ('gauntlet_safe_bootstrap_v1')"
        )

        user_count = db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]
        if user_count == 0:
            password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '')
            if not password:
                raise RuntimeError(
                    'Banco sem usuarios. Defina BOOTSTRAP_ADMIN_PASSWORD para criar o primeiro administrador.'
                )
            username = os.environ.get('BOOTSTRAP_ADMIN_USERNAME', 'admin').strip() or 'admin'
            name = os.environ.get('BOOTSTRAP_ADMIN_NAME', 'Administrador').strip() or 'Administrador'
            db.execute(
                'INSERT INTO usuarios (username, password_hash, nome, role) VALUES (?,?,?,?)',
                (username, hash_password(password), name, 'admin'),
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
