"""Capacity pools by specialty, modality and date window; no legacy rewrites."""
from flask import jsonify, request, render_template, g
from flask_login import current_user, login_required
from sge_common import normalizar, data_iso, numero, auditar, iniciar_escrita


OCUPANTES = {'Confirmado', 'Concluído'}


def _ocupantes(db, periodo, excluir=None):
    for table in ('residentes','estagios'):
        filtro = "status IN ('Confirmado','Concluído')" if table=='residentes' else 'etapa>=5'
        for row in db.execute(f'SELECT * FROM {table} WHERE {filtro}'):
            if excluir==(table,row['id']):
                continue
            modalidade = row['modalidade'] if table=='residentes' else {1:'Observership',2:'Obrigatorio',3:'Optativo'}.get(row['tipo_id'])
            if normalizar(row['especialidade'])!=periodo['especialidade_chave'] or normalizar(modalidade)!=periodo['modalidade_chave']:
                continue
            try:
                inicio,termino=data_iso(row['inicio'],'inicio'),data_iso(row['termino'],'termino')
                if termino<inicio:
                    raise ValueError()
            except ValueError:
                # Undated active records conservatively occupy every matching window.
                # Completed records with no dates remain historical, never guessed into a future window.
                concluido = row['status']=='Concluído' if table=='residentes' else row['etapa']==8
                if not concluido:
                    yield True
                continue
            if inicio<=periodo['termino'] and termino>=periodo['inicio']:
                yield False


def ocupacao(db,periodo,excluir=None):
    return sum(1 for _ in _ocupantes(db,periodo,excluir))


def resumo(db, row):
    p = dict(row)
    ocupantes=list(_ocupantes(db,p))
    p['ocupadas']=len(ocupantes)
    p['ocupadas_sem_datas']=sum(ocupantes)
    p['disponiveis'] = max(0, p['capacidade'] - p['ocupadas'])
    p['excedentes'] = max(0, p['ocupadas'] - p['capacidade'])
    p['situacao'] = ('Lotado' if p['disponiveis'] == 0 else
                     'Últimas vagas' if p['disponiveis'] <= max(1, p['capacidade']//5) else 'Disponível')
    return p


def validar_vaga(db, aluno, table, override=False, motivo=None):
    inicio = data_iso(aluno.get('inicio'), 'inicio')
    termino = data_iso(aluno.get('termino'), 'termino')
    if termino < inicio:
        raise ValueError('Termino deve ser igual ou posterior ao inicio.')
    modalidade = aluno.get('modalidade') if table == 'residentes' else {1:'Observership',2:'Obrigatorio',3:'Optativo'}.get(aluno.get('tipo_id'))
    pools = db.execute('SELECT * FROM vagas_periodos WHERE especialidade_chave=? AND modalidade_chave=? AND inicio<=? AND termino>=?',
                      (normalizar(aluno.get('especialidade')), normalizar(modalidade), termino, inicio)).fetchall()
    if not pools:
        raise ValueError('Cadastre capacidade para a especialidade, modalidade e todo o periodo antes de confirmar.')
    # Validate all intersecting windows, including an internship spanning several pools.
    for pool in pools:
        ocupadas = ocupacao(db, pool, (table, aluno.get('id')))
        if ocupadas >= pool['capacidade']:
            if not (override is True and current_user.role == 'admin' and str(motivo or '').strip()):
                raise ValueError(f"Periodo lotado: {ocupadas}/{pool['capacidade']}. Override exige administrador e justificativa.")
            audit_id = auditar(db, 'vagas_periodos', pool['id'], 'override_capacidade',
                    {'aluno_id':aluno.get('id'), 'tabela':table, 'ocupadas':ocupadas,
                     'capacidade':pool['capacidade'], 'motivo':str(motivo).strip()})
            g.sge_capacity_overrides = getattr(g,'sge_capacity_overrides',[]) + [audit_id]
    # No gaps allowed: contiguous pools may cover a longer internship.
    cursor = inicio
    from datetime import date, timedelta
    for pool in sorted(pools, key=lambda p:p['inicio']):
        if pool['inicio'] > cursor:
            raise ValueError('Periodo do estagio possui datas sem capacidade cadastrada.')
        if pool['termino'] >= termino:
            return
        cursor = max(cursor, (date.fromisoformat(pool['termino']) + timedelta(days=1)).isoformat())
    raise ValueError('Periodo do estagio possui datas sem capacidade cadastrada.')


def register_vagas(app, get_db):
    @app.route('/sge/vagas')
    @login_required
    def pagina_capacidade():
        return render_template('sge_vagas.html')

    @app.route('/api/sge/vagas', methods=['GET', 'POST'])
    @login_required
    def api_capacidade():
        db = get_db()
        if request.method == 'GET':
            return jsonify([resumo(db,r) for r in db.execute('SELECT * FROM vagas_periodos ORDER BY inicio,especialidade')])
        if current_user.role != 'admin':
            return jsonify({'erro':'Somente administrador pode configurar capacidade.'}), 403
        d = request.get_json() or {}
        try:
            inicio, termino = data_iso(d.get('inicio'),'inicio'), data_iso(d.get('termino'),'termino')
            capacidade = numero(d.get('capacidade'),'capacidade', 100000)
            if capacidade != int(capacidade) or termino < inicio:
                raise ValueError('Capacidade inteira e periodo valido sao obrigatorios.')
            especialidade = str(d.get('especialidade') or '').strip()
            modalidade = str(d.get('modalidade') or '').strip()
            if not especialidade or not modalidade:
                raise ValueError('Especialidade e modalidade obrigatorias.')
            iniciar_escrita(db)
            conflicts = db.execute('SELECT id FROM vagas_periodos WHERE especialidade_chave=? AND modalidade_chave=? AND inicio<=? AND termino>=?',
                                  (normalizar(especialidade),normalizar(modalidade),termino,inicio)).fetchone()
            if conflicts:
                raise ValueError('Existe periodo sobreposto nesta especialidade/modalidade.')
            cur = db.execute('INSERT INTO vagas_periodos(especialidade,especialidade_chave,modalidade,modalidade_chave,inicio,termino,capacidade) VALUES (?,?,?,?,?,?,?)',
                             (especialidade,normalizar(especialidade),modalidade,normalizar(modalidade),inicio,termino,int(capacidade)))
            auditar(db,'vagas_periodos',cur.lastrowid,'criar',{'capacidade':int(capacidade)})
            db.commit()
            return jsonify(resumo(db,db.execute('SELECT * FROM vagas_periodos WHERE id=?',(cur.lastrowid,)).fetchone())), 201
        except ValueError as exc:
            db.rollback()
            return jsonify({'erro':str(exc)}), 409

    @app.route('/api/sge/vagas/<int:pid>', methods=['PUT'])
    @login_required
    def api_capacidade_editar(pid):
        if current_user.role != 'admin':
            return jsonify({'erro':'Somente administrador.'}), 403
        db = get_db()
        d = request.get_json() or {}
        try:
            capacidade = numero(d.get('capacidade'),'capacidade',100000)
            if int(capacidade) != capacidade:
                raise ValueError('Capacidade deve ser inteira.')
            iniciar_escrita(db)
            pool = db.execute('SELECT * FROM vagas_periodos WHERE id=?',(pid,)).fetchone()
            if not pool:
                db.rollback()
                return jsonify({'erro':'Periodo nao encontrado.'}),404
            ocupadas = ocupacao(db,pool)
            if capacidade < ocupadas:
                if not (d.get('override_capacidade') is True and str(d.get('motivo') or '').strip()):
                    raise ValueError('Reducao abaixo da ocupacao exige override e justificativa.')
                auditar(db,'vagas_periodos',pid,'override_reducao',{'ocupadas':ocupadas,'motivo':d['motivo']})
            db.execute('UPDATE vagas_periodos SET capacidade=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(int(capacidade),pid))
            auditar(db,'vagas_periodos',pid,'alterar_capacidade',{'antes':pool['capacidade'],'depois':int(capacidade)})
            db.commit()
            return jsonify(resumo(db,db.execute('SELECT * FROM vagas_periodos WHERE id=?',(pid,)).fetchone()))
        except ValueError as exc:
            db.rollback()
            return jsonify({'erro':str(exc)}),409

    @app.before_request
    def _capacity_guard():
        endpoint = request.endpoint
        if request.method not in {'POST','PUT'} or not current_user.is_authenticated:
            return None
        endpoints = {'api_create_residente','api_update_residente','api_avancar_residente','api_residente_acao',
                     'api_create_estagio','api_update_estagio','api_avancar_etapa'}
        if endpoint not in endpoints:
            return None
        db = get_db()
        d = request.get_json(silent=True) or {}
        if not isinstance(d, dict):
            return jsonify({'erro':'Envie um objeto JSON.'}),400
        table = 'estagios' if endpoint in {'api_create_estagio','api_update_estagio','api_avancar_etapa'} else 'residentes'
        rid = (request.view_args or {}).get('rid') or (request.view_args or {}).get('estagio_id')
        iniciar_escrita(db)
        row = db.execute(f'SELECT * FROM {table} WHERE id=?',(rid,)).fetchone() if rid else None
        if rid and not row:
            db.rollback()
            return None
        aluno = dict(row) if row else {}
        aluno.update(d)
        if rid:
            aluno['id'] = rid
        aluno.setdefault('modalidade','Optativo')
        if endpoint == 'api_residente_acao':
            confirmar = d.get('etapa') in (7,'7') and d.get('resultado') == 'comprovante_ok'
            aluno = dict(row) if row else {}
        elif table == 'residentes':
            confirmar = aluno.get('status') in OCUPANTES
        else:
            etapa = (int(row['etapa']) + 1) if endpoint == 'api_avancar_etapa' and row else aluno.get('etapa',0)
            try:
                confirmar = int(etapa) >= 5
            except (TypeError, ValueError):
                db.rollback()
                return jsonify({'erro':'Etapa invalida.'}),400
        # Existing active records keep their status when unrelated contact fields are edited.
        existing = bool(row and (row['status'] in OCUPANTES if table == 'residentes' else row['etapa']>=5))
        changed = bool(row and any(aluno.get(k) != row[k] for k in ('inicio','termino','especialidade', *(['modalidade'] if table == 'residentes' else ['tipo_id']))))
        if confirmar and (not existing or changed):
            try:
                validar_vaga(db,aluno,table,d.get('override_capacidade'),d.get('motivo_capacidade'))
            except ValueError as exc:
                db.rollback()
                return jsonify({'erro':str(exc)}),409
        return None
