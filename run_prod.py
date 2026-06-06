import os
from waitress import serve
from app import app

if __name__ == '__main__':
    secret = os.environ.get('SECRET_KEY')
    if not secret or secret == 'chave-super-secreta-mude-em-producao':
        raise SystemExit(
            'ERRO: defina a variavel de ambiente SECRET_KEY antes de iniciar em producao.\n'
            '  Windows: set SECRET_KEY=sua-chave-aqui\n'
            '  Linux:   export SECRET_KEY=sua-chave-aqui'
        )
    app.secret_key = secret
    port = int(os.environ.get('PORT', 5000))
    print(f'Servidor de producao rodando em http://0.0.0.0:{port}')
    serve(app, host='0.0.0.0', port=port, threads=8)
