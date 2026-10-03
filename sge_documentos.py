"""Document files, effective expiration and private authenticated downloads."""
from datetime import date
from flask import jsonify, request, send_file
from flask_login import current_user, login_required
from sge_common import auditar, iniciar_escrita
from sge_storage import storage, read_upload


def status_documento(doc):
    if doc['validade'] and doc['validade']<date.today().isoformat():
        return 'Expirado'
    return doc['status']


def documentos_publicos(db,rid):
    rows=db.execute('SELECT * FROM residente_documentos WHERE residente_id=? AND arquivado_em IS NULL ORDER BY obrigatorio DESC,nome',(rid,)).fetchall()
    result=[]
    for row in rows:
        doc=dict(row)
        doc['status']=status_documento(doc)
        doc['arquivo_url']=f"/api/sge/arquivos/{doc['arquivo_id']}" if doc['arquivo_id'] else None
        result.append(doc)
    return result


def register_documentos(app,get_db):
    app.config.setdefault('MAX_CONTENT_LENGTH',12*1024*1024)

    @app.route('/api/residentes/<int:rid>/documentos/<int:did>/arquivo',methods=['POST'])
    @login_required
    def api_documento_arquivo(rid,did):
        db=get_db()
        key=None
        store=storage()
        try:
            data,mime,name,digest=read_upload(request.files.get('arquivo'))
            iniciar_escrita(db)
            doc=db.execute('SELECT * FROM residente_documentos WHERE id=? AND residente_id=? AND arquivado_em IS NULL',(did,rid)).fetchone()
            if not doc:
                db.rollback()
                return jsonify({'erro':'Documento nao encontrado.'}),404
            key=store.put(data)
            cur=db.execute('INSERT INTO sge_arquivos(residente_id,documento_id,storage_key,nome,mime,tamanho,sha256,enviado_por) VALUES (?,?,?,?,?,?,?,?)',
                           (rid,did,key,name,mime,len(data),digest,current_user.nome))
            aid=cur.lastrowid
            db.execute("UPDATE residente_documentos SET arquivo_id=?,status='Recebido',enviado_em=CURRENT_TIMESTAMP,aprovado_em=NULL,aprovado_por=NULL,atualizado_por=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (aid,current_user.nome,did))
            auditar(db,'residente_documentos',did,'anexar',{'arquivo_id':aid,'sha256':digest,'arquivo_anterior':doc['arquivo_id']})
            db.commit()
            return jsonify({'id':aid,'nome':name,'sha256':digest,'url':f'/api/sge/arquivos/{aid}'}),201
        except ValueError as exc:
            db.rollback()
            if key:
                store.remove_uncommitted(key)
            return jsonify({'erro':str(exc)}),400
        except Exception:
            db.rollback()
            if key:
                store.remove_uncommitted(key)
            app.logger.error('Falha no armazenamento privado do documento')
            return jsonify({'erro':'Nao foi possivel armazenar o arquivo.'}),503

    @app.route('/api/sge/arquivos/<int:aid>',methods=['GET'])
    @login_required
    def api_arquivo_privado(aid):
        row=get_db().execute('SELECT * FROM sge_arquivos WHERE id=?',(aid,)).fetchone()
        if not row:
            return jsonify({'erro':'Arquivo nao encontrado.'}),404
        if row['documento_id'] is None and current_user.role not in {'admin','financeiro'}:
            return jsonify({'erro':'Acesso restrito ao financeiro.'}),403
        try:
            response=send_file(storage().path(row['storage_key']),as_attachment=True,download_name=row['nome'],mimetype=row['mime'],conditional=True)
            response.headers['Cache-Control']='private, no-store'
            return response
        except (FileNotFoundError,ValueError):
            return jsonify({'erro':'Arquivo indisponivel. Solicite verificacao ao administrador.'}),404
