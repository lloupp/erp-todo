"""One financial process per student, with exact monetary amounts and audit."""
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import date
from decimal import Decimal, InvalidOperation
from flask import jsonify, request
from flask_login import current_user, login_required
from sge_common import auditar, data_iso, iniciar_escrita
from sge_storage import storage, read_upload

ESTADOS={'Aguardando financeiro','Link solicitado','Link enviado','Aguardando pagamento','Vencido','Pago','Isento','Reembolsado','Cancelado'}
PENDENTES={'Aguardando financeiro','Link solicitado','Link enviado','Aguardando pagamento','Vencido'}


def centavos(value):
    try:
        amount=Decimal(str(value))
        if not amount.is_finite() or amount<0 or amount>Decimal('100000000') or amount!=amount.quantize(Decimal('0.01')):
            raise ValueError('Valor monetario invalido; use no maximo duas casas decimais.')
        return int(amount*100)
    except (InvalidOperation,TypeError) as exc:
        raise ValueError('Valor monetario invalido.') from exc


def financeiro(db,rid):
    r=db.execute('SELECT * FROM residente_financeiro WHERE residente_id=?',(rid,)).fetchone()
    if r:
        f=dict(r)
    else:
        r=db.execute('SELECT valor,status_pagamento FROM residentes WHERE id=?',(rid,)).fetchone()
        if not r:
            return None
        raw=r['status_pagamento']
        status=raw if raw in ESTADOS else 'Aguardando financeiro'
        f={'residente_id':rid,'previsto_centavos':centavos(r['valor'] or 0),'desconto_centavos':centavos(r['valor'] or 0) if status=='Isento' else 0,
           'status':status,'vencimento':None,'data_pagamento':None,'reembolso_centavos':0,
           'comprovante_id':None,'observacao':None,'responsavel':None,'versao':0}
    f['final_centavos']=f['previsto_centavos']-f['desconto_centavos']
    f['status_efetivo']=('Vencido' if f['status'] in PENDENTES and f['vencimento'] and f['vencimento']<date.today().isoformat() else f['status'])
    f['comprovante_url']=f"/api/sge/arquivos/{f['comprovante_id']}" if f['comprovante_id'] else None
    return f


def persistir(db,f):
    db.execute('''INSERT INTO residente_financeiro(residente_id,previsto_centavos,desconto_centavos,status,vencimento,data_pagamento,reembolso_centavos,comprovante_id,observacao,responsavel,versao)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(residente_id) DO UPDATE SET
                  previsto_centavos=excluded.previsto_centavos,desconto_centavos=excluded.desconto_centavos,
                  status=excluded.status,vencimento=excluded.vencimento,data_pagamento=excluded.data_pagamento,
                  reembolso_centavos=excluded.reembolso_centavos,comprovante_id=excluded.comprovante_id,
                  observacao=excluded.observacao,responsavel=excluded.responsavel,versao=excluded.versao,updated_at=CURRENT_TIMESTAMP''',
               tuple(f.get(k) for k in ('residente_id','previsto_centavos','desconto_centavos','status','vencimento','data_pagamento','reembolso_centavos','comprovante_id','observacao','responsavel','versao')))
    # Compatibility cache for existing reports. Gates read the process above.
    db.execute('UPDATE residentes SET valor=?,status_pagamento=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
               ((f['previsto_centavos']-f['desconto_centavos'])/100,f['status'],f['residente_id']))


def sincronizar_pipeline(db,rid,etapa,resultado):
    target={(5,'solicitado'):'Link solicitado',(6,'enviado'):'Link enviado'}.get((etapa,resultado))
    if not target:
        return
    f=financeiro(db,rid)
    if f['status'] not in PENDENTES:
        return
    anterior=f['status']
    f.update(status=target,responsavel=current_user.nome,versao=f['versao']+1)
    persistir(db,f)
    auditar(db,'residente_financeiro',rid,'pipeline',{'antes':anterior,'depois':target})


def register_financeiro(app,get_db):
    @app.route('/api/residentes/<int:rid>/financeiro',methods=['GET','PUT'])
    @login_required
    def api_financeiro(rid):
        db=get_db()
        if request.method=='GET':
            f=financeiro(db,rid)
            return jsonify(f) if f else (jsonify({'erro':'Aluno nao encontrado'}),404)
        if current_user.role not in {'admin','financeiro'}:
            return jsonify({'erro':'Alteracao financeira exige financeiro ou administrador.'}),403
        d=request.get_json() or {}
        try:
            iniciar_escrita(db)
            f=financeiro(db,rid)
            if not f:
                db.rollback()
                return jsonify({'erro':'Aluno nao encontrado'}),404
            if d.get('versao')!=f['versao']:
                db.rollback()
                return jsonify({'erro':'Financeiro mudou. Atualize antes de salvar.'}),409
            anterior=dict(f)
            for campo,key in [('valor_previsto','previsto_centavos'),('desconto','desconto_centavos'),('reembolso','reembolso_centavos')]:
                if campo in d:
                    f[key]=centavos(d[campo])
            if f['desconto_centavos']>f['previsto_centavos']:
                raise ValueError('Desconto nao pode exceder valor previsto.')
            status=d.get('status',f['status'])
            if status not in ESTADOS:
                raise ValueError('Estado financeiro invalido.')
            if f['status'] in {'Reembolsado','Cancelado'} and status!=f['status']:
                raise ValueError('Processo encerrado. Reabertura exige revisao administrativa separada.')
            if f['status']=='Pago' and status not in {'Pago','Reembolsado'}:
                raise ValueError('Pagamento confirmado so pode permanecer Pago ou ser Reembolsado.')
            if f['status']=='Isento' and status not in {'Isento','Cancelado'}:
                raise ValueError('Isencao encerrada so permite cancelamento.')
            for campo in ('vencimento','data_pagamento'):
                if campo in d:
                    f[campo]=data_iso(d[campo],campo) if d[campo] else None
            if f['data_pagamento'] and f['data_pagamento']>date.today().isoformat():
                raise ValueError('Data de pagamento nao pode ser futura.')
            if status=='Vencido' and (not f['vencimento'] or f['vencimento']>=date.today().isoformat()):
                raise ValueError('Vencido exige vencimento anterior a hoje.')
            if status=='Pago' and not f['data_pagamento']:
                raise ValueError('Informe a data do pagamento.')
            f['final_centavos']=f['previsto_centavos']-f['desconto_centavos']
            if f['status'] in {'Pago','Reembolsado','Cancelado','Isento'} and any(f[k]!=anterior[k] for k in ('previsto_centavos','desconto_centavos')):
                raise ValueError('Nao altere valores de pagamento confirmado; registre reembolso quando necessario.')
            if status=='Reembolsado':
                if f['status'] not in {'Pago','Reembolsado'} or not 0<f['reembolso_centavos']<=f['final_centavos']:
                    raise ValueError('Reembolso exige pagamento anterior e valor valido ate o total pago.')
            elif f['reembolso_centavos']:
                raise ValueError('Valor de reembolso exige estado Reembolsado.')
            if status in {'Isento','Cancelado','Reembolsado'} and not str(d.get('observacao') or f['observacao'] or '').strip():
                raise ValueError('Isencao, cancelamento e reembolso exigem justificativa.')
            if status=='Isento':
                f['desconto_centavos']=f['previsto_centavos']
            f.update(status=status,observacao=str(d.get('observacao',f['observacao']) or '').strip(),responsavel=current_user.nome,versao=f['versao']+1)
            persistir(db,f)
            auditar(db,'residente_financeiro',rid,'atualizar',
                    {'status_antes':anterior['status'],'status':status,'previsto_centavos':f['previsto_centavos'],
                     'desconto_centavos':f['desconto_centavos'],'reembolso_antes':anterior['reembolso_centavos'],'reembolso_centavos':f['reembolso_centavos'],'versao':f['versao']})
            db.commit()
            return jsonify(financeiro(db,rid))
        except ValueError as exc:
            db.rollback()
            return jsonify({'erro':str(exc)}),400

    @app.route('/api/residentes/<int:rid>/financeiro/comprovante',methods=['POST'])
    @login_required
    def api_comprovante_financeiro(rid):
        if current_user.role not in {'admin','financeiro'}:
            return jsonify({'erro':'Comprovante exige financeiro ou administrador.'}),403
        db=get_db(); store=storage(); key=None
        try:
            content,mime,name,digest=read_upload(request.files.get('arquivo'))
            iniciar_escrita(db)
            f=financeiro(db,rid)
            if not f:
                db.rollback()
                return jsonify({'erro':'Aluno nao encontrado'}),404
            key=store.put(content)
            cur=db.execute('INSERT INTO sge_arquivos(residente_id,storage_key,nome,mime,tamanho,sha256,enviado_por) VALUES (?,?,?,?,?,?,?)',
                           (rid,key,name,mime,len(content),digest,current_user.nome))
            f.update(comprovante_id=cur.lastrowid,versao=f['versao']+1,responsavel=current_user.nome)
            persistir(db,f)
            auditar(db,'residente_financeiro',rid,'anexar_comprovante',{'arquivo_id':cur.lastrowid,'sha256':digest})
            db.commit()
            return jsonify(financeiro(db,rid)),201
        except ValueError as exc:
            db.rollback()
            if key: store.remove_uncommitted(key)
            return jsonify({'erro':str(exc)}),400
        except RequestEntityTooLarge:
            db.rollback()
            if key:
                store.remove_uncommitted(key)
            raise
        except Exception:
            db.rollback()
            if key: store.remove_uncommitted(key)
            app.logger.error('Falha ao armazenar comprovante financeiro')
            return jsonify({'erro':'Nao foi possivel armazenar comprovante.'}),503

    @app.before_request
    def _legacy_finance_guard():
        if request.method not in {'POST','PUT'} or not current_user.is_authenticated:
            return None
        if request.endpoint=='api_create_residente':
            d=request.get_json(silent=True) or {}
            if not isinstance(d,dict):return None
            if d.get('status_pagamento','Pendente') not in {'Pendente','Aguardando financeiro'} and current_user.role!='admin':
                return jsonify({'erro':'Informe pagamento no modulo financeiro.'}),403
        if request.endpoint=='api_update_residente':
            d=request.get_json(silent=True) or {}
            row=get_db().execute('SELECT * FROM residentes WHERE id=?',(request.view_args['rid'],)).fetchone()
            if not row or not isinstance(d,dict):return None
            for key in ('valor','status_pagamento','comprovante_pagamento'):
                if key in d and d[key]!=row[key]:
                    return jsonify({'erro':'Altere valores e pagamentos pelo modulo financeiro.'}),409
