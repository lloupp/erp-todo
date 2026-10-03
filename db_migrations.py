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
    sla = {1: 1, 2: 3, 3: 7, 4: 7, 5: 2, 6: 2, 7: 7}
    for residente_id, status, inicio in rows:
        etapa = PIPELINE_STAGE_BY_STATUS.get(status)
        if not etapa or etapa not in pipeline_etapas:
            continue
        reagendado_para = None
        prazo_em = None
        if etapa == 8 and inicio:
            try:
                target = datetime.strptime(str(inicio)[:10], '%Y-%m-%d') - timedelta(days=7)
                reagendado_para = target.strftime('%Y-%m-%d')
                prazo_em = reagendado_para
            except ValueError:
                pass
        elif etapa in sla:
            prazo_em = (datetime.now() + timedelta(days=sla[etapa])).strftime('%Y-%m-%d')
        db.execute(
            '''INSERT INTO pipeline_acoes
               (residente_id, etapa, acao_tipo, situacao, reagendado_para, prazo_em)
               VALUES (?, ?, ?, 'pendente', ?, ?)''',
            (residente_id, etapa, pipeline_etapas[etapa], reagendado_para, prazo_em),
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

            CREATE TABLE IF NOT EXISTS residente_frequencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                residente_id INTEGER NOT NULL REFERENCES residentes(id) ON DELETE RESTRICT,
                data DATE,
                horas REAL NOT NULL CHECK(horas>=0),
                presenca TEXT NOT NULL CHECK(presenca IN ('Presente','Ausente','Ausência justificada','Saldo legado')),
                observacao TEXT,
                responsavel TEXT NOT NULL,
                versao INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(residente_id,data),
                CHECK((presenca='Saldo legado' AND data IS NULL) OR (presenca!='Saldo legado' AND data IS NOT NULL)),
                CHECK(presenca IN ('Presente','Saldo legado') OR horas=0)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_frequencia_saldo_legado
                ON residente_frequencias(residente_id) WHERE data IS NULL;

            CREATE TABLE IF NOT EXISTS vagas_periodos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                especialidade TEXT NOT NULL,
                especialidade_chave TEXT NOT NULL,
                modalidade TEXT NOT NULL,
                modalidade_chave TEXT NOT NULL,
                inicio DATE NOT NULL,
                termino DATE NOT NULL,
                capacidade INTEGER NOT NULL CHECK(capacidade>=0),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CHECK(termino>=inicio)
            );
            CREATE INDEX IF NOT EXISTS idx_vagas_periodos_consulta
                ON vagas_periodos(especialidade_chave,modalidade_chave,inicio,termino);

            CREATE TABLE IF NOT EXISTS sge_auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entidade TEXT NOT NULL,
                entidade_id INTEGER,
                acao TEXT NOT NULL,
                responsavel TEXT NOT NULL,
                detalhes TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
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
                origem TEXT,
                origem_ref TEXT,
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
                prazo_em DATE,
                prioridade INTEGER NOT NULL DEFAULT 0,
                bloqueado INTEGER NOT NULL DEFAULT 0,
                bloqueio_motivo TEXT,
                atribuido_a TEXT,
                atualizado_em DATETIME,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
                concluido_em DATETIME
            );

            CREATE INDEX IF NOT EXISTS idx_pipeline_acoes_residente
                ON pipeline_acoes(residente_id);
            CREATE INDEX IF NOT EXISTS idx_pipeline_acoes_situacao
                ON pipeline_acoes(situacao, etapa);

            CREATE TABLE IF NOT EXISTS residente_documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                residente_id INTEGER NOT NULL REFERENCES residentes(id) ON DELETE CASCADE,
                nome TEXT NOT NULL,
                obrigatorio INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'Pendente',
                observacao TEXT,
                atualizado_por TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_residente_documentos_nome
                ON residente_documentos(residente_id, nome COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_residente_documentos_status
                ON residente_documentos(residente_id, obrigatorio, status);

            CREATE TABLE IF NOT EXISTS integracao_eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                event_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                status TEXT NOT NULL,
                residente_id INTEGER REFERENCES residentes(id) ON DELETE SET NULL,
                external_id TEXT,
                payload_json TEXT,
                erro TEXT,
                responsavel TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_integracao_eventos_provider
                ON integracao_eventos(provider, created_at);
            CREATE INDEX IF NOT EXISTS idx_integracao_eventos_residente
                ON integracao_eventos(residente_id, created_at);
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
            ('carga_horaria_prevista', 'REAL'),
            ('carga_horaria_realizada', 'REAL'),
            ('certificado_emitido_em', 'DATETIME'),
            ('certificado_enviado_em', 'DATETIME'),
            ('origem', 'TEXT'),
            ('origem_ref', 'TEXT'),
        ])

        if not db.execute("SELECT 1 FROM schema_migrations WHERE name='sge_frequencia_v1'").fetchone():
            import math
            for rid, total in db.execute('SELECT id,carga_horaria_realizada FROM residentes WHERE carga_horaria_realizada IS NOT NULL'):
                if not math.isfinite(float(total)) or float(total)<0:
                    raise RuntimeError(f'Carga horaria legada invalida no residente {rid}; revise sem apagar registros.')
                if float(total)>0:
                    db.execute("INSERT INTO residente_frequencias(residente_id,data,horas,presenca,responsavel,observacao) VALUES (?,NULL,?,'Saldo legado','Migracao','Total anterior preservado; sem inferir datas de presenca.')",(rid,total))
            db.execute("INSERT INTO schema_migrations(name) VALUES ('sge_frequencia_v1')")

        _add_missing_columns(db, 'pipeline_acoes', [
            ('prazo_em', 'DATE'),
            ('prioridade', 'INTEGER NOT NULL DEFAULT 0'),
            ('bloqueado', 'INTEGER NOT NULL DEFAULT 0'),
            ('bloqueio_motivo', 'TEXT'),
            ('atribuido_a', 'TEXT'),
            ('atualizado_em', 'DATETIME'),
        ])

        db.execute(
            """CREATE INDEX IF NOT EXISTS idx_pipeline_acoes_prazo
               ON pipeline_acoes(situacao, prazo_em, prioridade)"""
        )

        # Backfill de prazo apenas para a acao pendente atual. Nao altera
        # historico concluido e respeita datas operacionais das etapas 8/9.
        db.execute("""
            UPDATE pipeline_acoes
            SET prazo_em = CASE
                WHEN etapa = 8 THEN COALESCE(
                    reagendado_para,
                    (SELECT date(r.inicio, '-7 days') FROM residentes r
                     WHERE r.id = pipeline_acoes.residente_id)
                )
                WHEN etapa = 9 THEN (
                    SELECT date(r.termino) FROM residentes r
                    WHERE r.id = pipeline_acoes.residente_id
                )
                WHEN etapa = 1 THEN date(criado_em, '+1 day')
                WHEN etapa = 2 THEN date(criado_em, '+3 days')
                WHEN etapa IN (3,4,7) THEN date(criado_em, '+7 days')
                WHEN etapa IN (5,6) THEN date(criado_em, '+2 days')
                ELSE NULL
            END
            WHERE situacao = 'pendente' AND prazo_em IS NULL
        """)

        db.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_residentes_origem_ref
               ON residentes(origem, origem_ref)
               WHERE origem_ref IS NOT NULL"""
        )
        duplicates = db.execute("SELECT residente_id FROM pipeline_acoes WHERE situacao='pendente' GROUP BY residente_id HAVING COUNT(*)>1").fetchall()
        if duplicates:
            raise RuntimeError('Pipeline possui acoes pendentes duplicadas; revise os registros sem apagar historico.')
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_unica_pendente ON pipeline_acoes(residente_id) WHERE situacao='pendente'")
        db.execute("INSERT OR IGNORE INTO schema_migrations(name) VALUES ('sge_operational_guards_v1')")
        db.execute("INSERT OR IGNORE INTO schema_migrations(name) VALUES ('sge_vagas_periodos_v1')")
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
