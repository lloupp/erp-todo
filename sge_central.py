"""Actionable daily worklists, using the same sources as the operational gates."""
from datetime import date,timedelta
from flask import jsonify,render_template,request
from flask_login import login_required
from sge_financeiro import financeiro,PENDENTES
from sge_frequencia import horas_realizadas
from sge_documentos import documentos_publicos
from sge_academico import avaliar_certificado

CATEGORIAS=[
 ('atrasadas','Tarefas atrasadas'),('hoje','Vencendo hoje'),('urgentes','Tarefas urgentes'),
 ('bloqueadas','Ações bloqueadas'),('sem_responsavel','Sem responsável'),
 ('novas_inscricoes','Novas inscrições'),('aguardando_resposta','Aguardando resposta'),
 ('pagamentos','Pagamentos pendentes'),('documentos','Documentos faltantes ou expirados'),
 ('iniciando','Iniciando nos próximos 7 dias'),('terminando','Terminando estágio / conclusão pendente'),
 ('certificados_aptos','Certificados aptos para emissão'),('certificados_enviar','Certificados emitidos ainda não enviados')]
ENCERRADOS={'Concluído','Cancelado','Desistente','Indeferido','Nao veio'}


def central(db):
    hoje=date.today().isoformat()
    sete=(date.today()+timedelta(days=7)).isoformat()
    grupos={key:[] for key,_ in CATEGORIAS}
    alunos={r['id']:dict(r) for r in db.execute('SELECT * FROM residentes')}
    for acao in db.execute("SELECT * FROM pipeline_acoes WHERE situacao='pendente' ORDER BY prioridade DESC,prazo_em,id"):
        a=dict(acao); r=alunos.get(a['residente_id'])
        if not r or r['status'] in ENCERRADOS:
            continue
        item={'id':r['id'],'nome':r['nome'],'especialidade':r['especialidade'],
              'prazo':a['prazo_em'],'prioridade':a['prioridade'],'responsavel':a['atribuido_a'],
              'detalhe':f"Etapa {a['etapa']}: {a['acao_tipo']}"+(f" — {a['bloqueio_motivo']}" if a['bloqueado'] else ''),
              'url':f"/residentes?acao={a['id']}"}
        keys=[]
        if a['prazo_em'] and a['prazo_em']<hoje:keys.append('atrasadas')
        if a['prazo_em']==hoje:keys.append('hoje')
        if a['prioridade']==2:keys.append('urgentes')
        if a['bloqueado']:keys.append('bloqueadas')
        if not a['atribuido_a']:keys.append('sem_responsavel')
        if a['etapa']==1:keys.append('novas_inscricoes')
        if a['etapa'] in {2,4}:keys.append('aguardando_resposta')
        for key in keys:grupos[key].append(item)
    for rid,r in alunos.items():
        base={'id':rid,'nome':r['nome'],'especialidade':r['especialidade'],'prazo':None,
              'prioridade':0,'responsavel':None,'url':f'/sge/residentes/{rid}'}
        f=financeiro(db,rid)
        docs=documentos_publicos(db,rid)
        ativos=r['status'] not in ENCERRADOS
        if (ativos and f['status_efetivo'] in PENDENTES) or (r['status']=='Cancelado' and f['status_efetivo'] in PENDENTES|{'Pago'}):
            grupos['pagamentos'].append({**base,'prazo':f['vencimento'],'prioridade':2 if f['status_efetivo']=='Vencido' else 0,
                 'responsavel':f['responsavel'],'detalhe':('Estágio cancelado: revisar cancelamento financeiro/reembolso — ' if r['status']=='Cancelado' else '')+f"{f['status_efetivo']} — R$ {f['final_centavos']/100:.2f}",'url':base['url']+'#financeiro'})
        obrigatorios=[d for d in docs if d['obrigatorio']]
        faltantes=[d['nome'] for d in obrigatorios if d['status']!='Aprovado' or not d['arquivo_id']]
        if ativos and (not obrigatorios or faltantes):
            grupos['documentos'].append({**base,'detalhe':', '.join(faltantes) if obrigatorios else 'Configure o checklist obrigatório', 'url':base['url']+'#documentos'})
        if r['status']=='Confirmado' and r['inicio'] and hoje<=r['inicio']<=sete:
            grupos['iniciando'].append({**base,'prazo':r['inicio'],'detalhe':'Conferir início, documentos e orientações'})
        if r['status']=='Confirmado' and r['termino'] and r['termino']<=sete:
            grupos['terminando'].append({**base,'prazo':r['termino'],'prioridade':2 if r['termino']<hoje else 0,
                 'detalhe':'Conferir frequência e registrar conclusão real','url':f'/residentes?aluno={rid}'})
        if r['status']=='Concluído' or (r['certificado_emitido_em'] and not r['certificado_enviado_em']):
            r['carga_horaria_realizada']=horas_realizadas(db,rid)
            r['status_pagamento']=f['status_efetivo']
            gate=avaliar_certificado(r,docs)
            if r['status']=='Concluído' and gate['apto'] and not r['certificado_emitido_em']:
                grupos['certificados_aptos'].append({**base,'detalhe':'Gate acadêmico atendido; emissão exige ação humana','url':f'/residentes?academico={rid}'})
            if r['certificado_emitido_em'] and not r['certificado_enviado_em']:
                grupos['certificados_enviar'].append({**base,'detalhe':'Conferir envio' if gate['apto'] else 'Gate bloqueado: '+' '.join(gate['motivos']), 'url':f'/residentes?academico={rid}'})
    for items in grupos.values():
        items.sort(key=lambda i:(-i['prioridade'],i['prazo'] or '9999-12-31',i['nome'].casefold(),i['id']))
    return grupos


def register_central(app,get_db):
    @app.route('/sge/hoje')
    @login_required
    def pagina_central():
        return render_template('sge_central.html')

    @app.route('/api/sge/hoje')
    @login_required
    def api_central():
        try:
            offset=max(0,int(request.args.get('offset',0)))
            limit=max(1,min(200,int(request.args.get('limit',50))))
        except ValueError:
            return jsonify({'erro':'Paginacao invalida.'}),400
        categoria=request.args.get('categoria')
        if categoria and categoria not in dict(CATEGORIAS):
            return jsonify({'erro':'Categoria invalida.'}),400
        grupos=central(get_db())
        return jsonify({'data':date.today().isoformat(),'categorias':[
            {'id':key,'titulo':title,'total':len(grupos[key]),'offset':offset,'items':grupos[key][offset:offset+limit],
             'proximo_offset':offset+limit if offset+limit<len(grupos[key]) else None}
            for key,title in CATEGORIAS if not categoria or categoria==key]})
