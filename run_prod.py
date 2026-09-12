import os

from dotenv import load_dotenv
from waitress import serve

load_dotenv()

import app as app_module
from db_migrations import ensure_database
from password_security import hash_password, verify_password
from production_guards import install_production_guards

# Troca os helpers legados do modulo principal por KDF adaptativa mantendo
# compatibilidade de leitura com hashes antigos. As rotas olham os globals do
# modulo em runtime, entao novas senhas e validacoes passam por estes helpers.
app_module.hash_password = hash_password
app_module.verify_password = verify_password
app = app_module.app


if __name__ == '__main__':
    secret = os.environ.get('SECRET_KEY')
    if not secret or secret == 'chave-super-secreta-mude-em-producao':
        raise SystemExit(
            'ERRO: defina a variavel de ambiente SECRET_KEY antes de iniciar em producao.\n'
            '  Windows: set SECRET_KEY=sua-chave-aqui\n'
            '  Linux:   export SECRET_KEY=sua-chave-aqui'
        )

    ensure_database(
        app.config['DATABASE'],
        hash_password=hash_password,
        message_seed=app_module.MENSAGENS_MODELO_SEED,
        pipeline_etapas=app_module.PIPELINE_ETAPAS,
        data_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'),
    )
    install_production_guards(app)

    app.secret_key = secret
    port = int(os.environ.get('PORT', 5000))
    threads = int(os.environ.get('WAITRESS_THREADS', 16))
    print(f'Servidor de producao rodando em http://0.0.0.0:{port} (threads={threads})')
    serve(app, host='0.0.0.0', port=port, threads=threads)
