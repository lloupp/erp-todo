import sqlite3
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g, Response

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'estagios.db')

app = Flask(__name__)
app.config['DATABASE'] = DB_PATH


TIPO_ESTAGIO = {1: 'Observership', 2: 'Obrigatorio', 3: 'Optativo'}

ETAPAS_OBS = {
    1: 'Venda realizada',
    2: 'Pagamento confirmado',
    3: 'Docs enviados',
    4: 'Docs validados',
    5: 'Vaga confirmada',
    6: 'Orientacoes enviadas',
    7: 'Concluido',
}

ETAPAS_OBR_OPT = {
    0: 'Verificacao de vaga',
    1: 'Venda realizada',
    2: 'Pagamento confirmado',
    3: 'Docs enviados',
    4: 'Docs validados',
    5: 'Vaga confirmada',
    6: 'Orientacoes enviadas',
    7: 'Concluido',
}

ETAPA_COLORS = {
    0: '#6b7280',
    1: '#f59e0b',
    2: '#3b82f6',
    3: '#8b5cf6',
    4: '#06b6d4',
    5: '#10b981',
    6: '#6366f1',
    7: '#22c55e',
}


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA foreign_keys = OFF')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS tipo_estagio (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS estagios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_id INTEGER NOT NULL REFERENCES tipo_estagio(id),
            mes_ano TEXT NOT NULL,
            semana INTEGER NOT NULL,
            nome TEXT NOT NULL,
            especialidade TEXT NOT NULL,
            cracha TEXT,
            valor REAL,
            termino DATE,
            email TEXT,
            telefone TEXT,
            observacao TEXT,
            documentos TEXT,
            envio_certificado DATE,
            etapa INTEGER NOT NULL DEFAULT 0,
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

        DELETE FROM historico_etapas;
        DELETE FROM estagios;
        DELETE FROM tipo_estagio;
        INSERT INTO tipo_estagio (id, nome) VALUES (1, 'Observership');
        INSERT INTO tipo_estagio (id, nome) VALUES (2, 'Obrigatorio');
        INSERT INTO tipo_estagio (id, nome) VALUES (3, 'Optativo');
    ''')
    db.commit()

    count = db.execute('SELECT COUNT(*) FROM estagios').fetchone()[0]
    if count == 0:
        db.executescript('''
            INSERT INTO estagios (tipo_id, mes_ano, semana, nome, especialidade, cracha, valor, termino, email, telefone, observacao, documentos, envio_certificado, etapa)
            VALUES
                (1, '2025-06', 1, 'Ana Silva', 'Cardiologia', 'OBS-001', 1500.00, '2025-07-15', 'ana@email.com', '(51) 99999-0001', 'Aluna do programa de observership', 'CRM;Termo', '2025-06-10', 2),
                (2, '2025-06', 2, 'Bruno Costa', 'Cirurgia Geral', 'OBR-002', 0, '2025-12-31', 'bruno@email.com', '(51) 99999-0002', 'Estagio obrigatorio 6o periodo', 'CRM;Vacina', NULL, 0),
                (3, '2025-06', 2, 'Carla Souza', 'Pediatria', 'OPT-003', 800.00, '2025-08-30', 'carla@email.com', '(51) 99999-0003', 'Estagio optativo de pediatria', 'CRM', NULL, 1);

            INSERT INTO historico_etapas (estagio_id, etapa, observacao, responsavel)
            VALUES
                (1, 1, 'Venda registrada', 'Sistema'),
                (1, 2, 'Pagamento via PIX confirmado', 'Sistema'),
                (2, 0, 'Solicitacao de vaga enviada a Cirurgia', 'Sistema'),
                (3, 0, 'Vaga confirmada pela Pediatria', 'Sistema'),
                (3, 1, 'Venda registrada', 'Sistema');
        ''')
        db.commit()

    db.execute('PRAGMA foreign_keys = ON')
    db.close()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/estagios', methods=['GET'])
def api_get_estagios():
    db = get_db()
    query = '''
        SELECT e.*, t.nome as tipo_nome
        FROM estagios e
        JOIN tipo_estagio t ON e.tipo_id = t.id
        WHERE 1=1
    '''
    params = []

    tipo_id = request.args.get('tipo_id')
    if tipo_id:
        query += ' AND e.tipo_id = ?'
        params.append(tipo_id)

    especialidade = request.args.get('especialidade')
    if especialidade:
        query += ' AND e.especialidade = ?'
        params.append(especialidade)

    etapa = request.args.get('etapa')
    if etapa is not None and etapa != '':
        query += ' AND e.etapa = ?'
        params.append(etapa)

    mes_ano = request.args.get('mes_ano')
    if mes_ano:
        query += ' AND e.mes_ano = ?'
        params.append(mes_ano)

    busca = request.args.get('busca')
    if busca:
        query += ' AND (e.nome LIKE ? OR e.email LIKE ? OR e.cracha LIKE ?)'
        params.extend([f'%{busca}%', f'%{busca}%', f'%{busca}%'])

    query += ' ORDER BY e.mes_ano DESC, e.semana, e.nome'

    rows = db.execute(query, params).fetchall()
    result = []
    for r in rows:
        result.append({
            'id': r['id'],
            'tipo_id': r['tipo_id'],
            'tipo_nome': r['tipo_nome'],
            'mes_ano': r['mes_ano'],
            'semana': r['semana'],
            'nome': r['nome'],
            'especialidade': r['especialidade'],
            'cracha': r['cracha'],
            'valor': r['valor'],
            'termino': r['termino'],
            'email': r['email'],
            'telefone': r['telefone'],
            'observacao': r['observacao'],
            'documentos': r['documentos'],
            'envio_certificado': r['envio_certificado'],
            'etapa': r['etapa'],
            'created_at': r['created_at'],
            'updated_at': r['updated_at'],
        })
    return jsonify(result)


@app.route('/api/estagios', methods=['POST'])
def api_create_estagio():
    db = get_db()
    data = request.get_json()
    tipo_id = data.get('tipo_id')
    if tipo_id in (2, 3):
        etapa_inicial = 0
    else:
        etapa_inicial = 1

    cursor = db.execute('''
        INSERT INTO estagios (tipo_id, mes_ano, semana, nome, especialidade, cracha, valor, termino, email, telefone, observacao, documentos, envio_certificado, etapa)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        tipo_id, data.get('mes_ano'), data.get('semana'), data.get('nome'),
        data.get('especialidade'), data.get('cracha'), data.get('valor'),
        data.get('termino'), data.get('email'), data.get('telefone'),
        data.get('observacao'), data.get('documentos'), data.get('envio_certificado'),
        etapa_inicial,
    ))
    estagio_id = cursor.lastrowid
    db.execute('''
        INSERT INTO historico_etapas (estagio_id, etapa, observacao, responsavel)
        VALUES (?, ?, ?, ?)
    ''', (estagio_id, etapa_inicial, 'Registro criado', 'Sistema'))
    db.commit()
    return jsonify({'id': estagio_id, 'etapa': etapa_inicial}), 201


@app.route('/api/estagios/<int:estagio_id>', methods=['PUT'])
def api_update_estagio(estagio_id):
    db = get_db()
    data = request.get_json()
    db.execute('''
        UPDATE estagios SET
            tipo_id=?, mes_ano=?, semana=?, nome=?, especialidade=?,
            cracha=?, valor=?, termino=?, email=?, telefone=?,
            observacao=?, documentos=?, envio_certificado=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    ''', (
        data.get('tipo_id'), data.get('mes_ano'), data.get('semana'),
        data.get('nome'), data.get('especialidade'), data.get('cracha'),
        data.get('valor'), data.get('termino'), data.get('email'),
        data.get('telefone'), data.get('observacao'), data.get('documentos'),
        data.get('envio_certificado'), estagio_id,
    ))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/estagios/<int:estagio_id>', methods=['DELETE'])
def api_delete_estagio(estagio_id):
    db = get_db()
    db.execute('DELETE FROM historico_etapas WHERE estagio_id=?', (estagio_id,))
    db.execute('DELETE FROM estagios WHERE id=?', (estagio_id,))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/estagios/<int:estagio_id>/avancar', methods=['POST'])
def api_avancar_etapa(estagio_id):
    db = get_db()
    row = db.execute('SELECT e.*, t.nome as tipo_nome FROM estagios e JOIN tipo_estagio t ON e.tipo_id = t.id WHERE e.id=?', (estagio_id,)).fetchone()
    if not row:
        return jsonify({'erro': 'Estagio nao encontrado'}), 404

    etapa_atual = row['etapa']
    tipo_id = row['tipo_id']
    max_etapa = 7
    if tipo_id == 1:
        min_etapa = 1
    else:
        min_etapa = 0

    if etapa_atual >= max_etapa:
        return jsonify({'erro': 'Estagio ja concluido'}), 400

    nova_etapa = etapa_atual + 1
    data = request.get_json() or {}
    db.execute('UPDATE estagios SET etapa=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (nova_etapa, estagio_id))
    db.execute('''
        INSERT INTO historico_etapas (estagio_id, etapa, observacao, responsavel)
        VALUES (?, ?, ?, ?)
    ''', (estagio_id, nova_etapa, data.get('observacao', ''), data.get('responsavel', 'Sistema')))
    db.commit()
    return jsonify({'etapa': nova_etapa})


@app.route('/api/estagios/<int:estagio_id>/historico', methods=['GET'])
def api_historico(estagio_id):
    db = get_db()
    rows = db.execute('SELECT * FROM historico_etapas WHERE estagio_id=? ORDER BY ts', (estagio_id,)).fetchall()
    result = []
    for r in rows:
        result.append({
            'id': r['id'],
            'estagio_id': r['estagio_id'],
            'etapa': r['etapa'],
            'observacao': r['observacao'],
            'responsavel': r['responsavel'],
            'ts': r['ts'],
        })
    return jsonify(result)


@app.route('/api/tipos', methods=['GET'])
def api_tipos():
    db = get_db()
    rows = db.execute('SELECT * FROM tipo_estagio ORDER BY id').fetchall()
    return jsonify([{'id': r['id'], 'nome': r['nome']} for r in rows])


@app.route('/api/especialidades', methods=['GET'])
def api_especialidades():
    db = get_db()
    rows = db.execute('SELECT DISTINCT especialidade FROM estagios ORDER BY especialidade').fetchall()
    return jsonify([r['especialidade'] for r in rows])


@app.route('/api/meses', methods=['GET'])
def api_meses():
    db = get_db()
    rows = db.execute('SELECT DISTINCT mes_ano FROM estagios ORDER BY mes_ano DESC').fetchall()
    return jsonify([r['mes_ano'] for r in rows])


@app.route('/api/exportar-csv', methods=['GET'])
def api_exportar_csv():
    db = get_db()
    query = '''
        SELECT e.*, t.nome as tipo_nome
        FROM estagios e
        JOIN tipo_estagio t ON e.tipo_id = t.id
        WHERE 1=1
    '''
    params = []

    tipo_id = request.args.get('tipo_id')
    if tipo_id:
        query += ' AND e.tipo_id = ?'
        params.append(tipo_id)

    especialidade = request.args.get('especialidade')
    if especialidade:
        query += ' AND e.especialidade = ?'
        params.append(especialidade)

    etapa = request.args.get('etapa')
    if etapa is not None and etapa != '':
        query += ' AND e.etapa = ?'
        params.append(etapa)

    mes_ano = request.args.get('mes_ano')
    if mes_ano:
        query += ' AND e.mes_ano = ?'
        params.append(mes_ano)

    busca = request.args.get('busca')
    if busca:
        query += ' AND (e.nome LIKE ? OR e.email LIKE ? OR e.cracha LIKE ?)'
        params.extend([f'%{busca}%', f'%{busca}%', f'%{busca}%'])

    query += ' ORDER BY e.mes_ano DESC, e.semana, e.nome'

    rows = db.execute(query, params).fetchall()

    def get_etapa_nome(tipo_id, etapa):
        if tipo_id == 1:
            return ETAPAS_OBS.get(etapa, '')
        return ETAPAS_OBR_OPT.get(etapa, '')

    lines = [
        'ID;Tipo;Mes/Ano;Semana;Nome;Especialidade;Cracha;Valor;Termino;Email;Telefone;Documentos;Observacao;Envio Certificado;Etapa'
    ]
    for r in rows:
        etapa_nome = get_etapa_nome(r['tipo_id'], r['etapa'])
        lines.append(';'.join(str(v) if v is not None else '' for v in [
            r['id'], r['tipo_nome'], r['mes_ano'], r['semana'],
            r['nome'], r['especialidade'], r['cracha'], r['valor'],
            r['termino'], r['email'], r['telefone'], r['documentos'],
            r['observacao'], r['envio_certificado'], f"{r['etapa']} - {etapa_nome}"
        ]))

    csv_content = '\n'.join(lines)
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=estagios.csv'}
    )


if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
