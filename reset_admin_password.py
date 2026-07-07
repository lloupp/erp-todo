"""
Reseta a senha do usuário 'admin' diretamente no banco.
A senha é digitada de forma oculta (getpass) e nunca fica visível na tela
nem é passada como argumento — só existe na memória deste processo.

Uso:
    python reset_admin_password.py
"""
import os
import sqlite3
import hashlib
import getpass

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'estagios.db')


def hash_password(password):
    """Mesmo esquema usado em app.py: salt:sha256(salt+senha)."""
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f'{salt}:{h}'


def main():
    username = input("Usuário a resetar [admin]: ").strip() or 'admin'

    db = sqlite3.connect(DB)
    row = db.execute('SELECT id FROM usuarios WHERE username = ?', (username,)).fetchone()
    if not row:
        print(f'Usuário "{username}" não encontrado.')
        db.close()
        return

    pw1 = getpass.getpass('Nova senha: ')
    pw2 = getpass.getpass('Confirme a nova senha: ')
    if not pw1:
        print('Senha vazia. Cancelado.')
        db.close()
        return
    if pw1 != pw2:
        print('As senhas não coincidem. Cancelado.')
        db.close()
        return

    novo_hash = hash_password(pw1)
    db.execute('UPDATE usuarios SET password_hash = ? WHERE username = ?', (novo_hash, username))
    db.commit()
    db.close()
    print(f'Senha do usuário "{username}" atualizada com sucesso.')
    print('IMPORTANTE: se o servidor de produção estiver rodando, não é necessário reiniciar '
          '(a alteração é direto no banco), mas faça login novamente para validar.')


if __name__ == '__main__':
    main()
