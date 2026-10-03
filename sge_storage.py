"""Private object-store interface. Keys are opaque and never returned by APIs."""
import hashlib
import os
from pathlib import Path
import re
import tempfile
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

MAX_BYTES = 8*1024*1024


class LocalStorage:
    def __init__(self, root):
        self.root=Path(root).resolve()

    def put(self, content):
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        key=uuid.uuid4().hex
        fd, name=tempfile.mkstemp(prefix='.upload-',dir=self.root)
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name,self.path(key))
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return key

    def path(self,key):
        if not re.fullmatch(r'[0-9a-f]{32}',str(key)):
            raise ValueError('Chave de arquivo invalida.')
        return self.root/key

    def remove_uncommitted(self,key):
        self.path(key).unlink(missing_ok=True)


def storage():
    # Deployments can inject an adapter with the same methods; credentials remain outside the DB.
    adapter=current_app.config.get('SGE_STORAGE_ADAPTER')
    if adapter is not None:
        return adapter
    root=os.environ.get('ERP_FILES_DIR') or str(Path(current_app.config['DATABASE']).resolve().parent/'private_sge_files')
    return LocalStorage(root)


def read_upload(file):
    if not file:
        raise ValueError('Selecione um arquivo PDF, PNG ou JPEG.')
    data=file.read(MAX_BYTES+1)
    if not data or len(data)>MAX_BYTES:
        raise ValueError('Arquivo vazio ou maior que 8 MB.')
    if data.startswith(b'%PDF-'):
        mime,extension='application/pdf','.pdf'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        mime,extension='image/png','.png'
    elif data.startswith(b'\xff\xd8\xff'):
        mime,extension='image/jpeg','.jpg'
    else:
        raise ValueError('Conteudo de arquivo nao permitido. Use PDF, PNG ou JPEG.')
    name=secure_filename(file.filename or '') or ('documento'+extension)
    if not name.lower().endswith(('.pdf','.png','.jpg','.jpeg')):
        name='documento'+extension
    return data,mime,name,hashlib.sha256(data).hexdigest()
