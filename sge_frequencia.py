"""Daily attendance is the only source of completed hours."""
from datetime import date
from flask import jsonify, request, render_template
from flask_login import login_required, current_user
from sge_common import numero, data_iso, auditar, iniciar_escrita

PRESENCAS = {'Presente','Ausente','Ausência justificada'}


def horas_realizadas(db, rid):
    return db.execute('SELECT COALESCE(SUM(horas),0) FROM residente_frequencias WHERE residente_id=?',(rid,)).fetchone()[0]


def resumo_frequencia(db, rid):
    residente = db.execute('SELECT carga_horaria_prevista FROM residentes WHERE id=?',(rid,)).fetchone()
    if not residente:
        return None
    prevista = residente['carga_horaria_prevista'] or 0
    realizada = horas_realizadas(db,rid)
    return {'previstas':prevista,'realizadas':realizada,'faltantes':max(0,prevista-realizada),
            'percentual':min(100,round(100*realizada/prevista,1)) if prevista>0 else 0,
            'registros':[dict(r) for r in db.execute('SELECT * FROM residente_frequencias WHERE residente_id=? ORDER BY data DESC,id DESC',(rid,))]}


def register_frequencia(app,get_db):
    @app.route('/sge/residentes/<int:rid>')
    @login_required
    def pagina_operacional_aluno(rid):
        aluno=get_db().execute('SELECT id,nome FROM residentes WHERE id=?',(rid,)).fetchone()
        if not aluno:
            return 'Aluno nao encontrado',404
        return render_template('sge_aluno.html',aluno=aluno)

    @app.route('/api/residentes/<int:rid>/frequencia',methods=['GET','POST'])
    @login_required
    def api_frequencia(rid):
        db=get_db()
        if request.method=='GET':
            resumo=resumo_frequencia(db,rid)
            return (jsonify(resumo),200) if resumo else (jsonify({'erro':'Aluno nao encontrado'}),404)
        d=request.get_json() or {}
        try:
            data=data_iso(d.get('data'),'data')
            if data>date.today().isoformat():
                raise ValueError('Nao registre frequencia futura.')
            horas=numero(d.get('horas',0),'horas',24)
            presenca=d.get('presenca')
            if presenca not in PRESENCAS:
                raise ValueError('Presenca invalida.')
            if (presenca!='Presente' and horas!=0) or (presenca=='Presente' and horas<=0):
                raise ValueError('Ausencia exige zero horas; presenca exige horas realizadas.')
            iniciar_escrita(db)
            aluno=db.execute('SELECT inicio,termino FROM residentes WHERE id=?',(rid,)).fetchone()
            if not aluno:
                db.rollback()
                return jsonify({'erro':'Aluno nao encontrado'}),404
            if not aluno['inicio'] or not aluno['termino'] or not aluno['inicio']<=data<=aluno['termino']:
                raise ValueError('Frequencia deve estar dentro das datas do estagio.')
            atual=db.execute('SELECT * FROM residente_frequencias WHERE residente_id=? AND data=?',(rid,data)).fetchone()
            if atual:
                if d.get('versao')!=atual['versao']:
                    db.rollback()
                    return jsonify({'erro':'Frequencia ja existe ou foi alterada. Atualize antes de corrigir.'}),409
                db.execute('UPDATE residente_frequencias SET horas=?,presenca=?,observacao=?,responsavel=?,versao=versao+1,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                           (horas,presenca,str(d.get('observacao') or '').strip(),current_user.nome,atual['id']))
                fid=atual['id']
            else:
                cur=db.execute('INSERT INTO residente_frequencias(residente_id,data,horas,presenca,observacao,responsavel) VALUES (?,?,?,?,?,?)',
                               (rid,data,horas,presenca,str(d.get('observacao') or '').strip(),current_user.nome))
                fid=cur.lastrowid
            auditar(db,'residente_frequencias',fid,'corrigir' if atual else 'lancar',
                    {'residente_id':rid,'data':data,'horas_antes':atual['horas'] if atual else None,'horas':horas,'presenca':presenca})
            db.commit()
            return jsonify(resumo_frequencia(db,rid)),200 if atual else 201
        except ValueError as exc:
            db.rollback()
            return jsonify({'erro':str(exc)}),400
