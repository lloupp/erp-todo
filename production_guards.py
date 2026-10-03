"""Centralized production-only HTTP hardening.

Route-level authorization remains the preferred defense, but these guards provide
an additional deny-by-default layer for configuration mutations and consistent
security headers at the production entry point.
"""

from __future__ import annotations

from flask import jsonify, request
from urllib.parse import urlsplit
from flask_login import current_user


ADMIN_MUTATION_PREFIXES = (
    '/api/area-medica',
    '/api/mensagens-modelo',
    '/api/usuarios',
    '/api/limites',
)
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def install_production_guards(app) -> None:
    if app.extensions.get('production_guards_installed'):
        return
    app.extensions['production_guards_installed'] = True

    @app.before_request
    def _enforce_sensitive_admin_mutations():
        if request.method not in UNSAFE_METHODS:
            return None
        if current_user.is_authenticated:
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify({'erro': 'Origem da requisicao nao permitida'}), 403
            origin = request.headers.get('Origin')
            if origin and urlsplit(origin).netloc != request.host:
                return jsonify({'erro': 'Origem da requisicao nao permitida'}), 403
            role=current_user.role
            if request.path.startswith('/api/') and role not in {'admin','user','atendimento','coordenacao','financeiro','somente_leitura'}:
                return jsonify({'erro':'Perfil sem permissao operacional.'}),403
            if role == 'financeiro' and request.path.startswith('/api/') and '/financeiro' not in request.path:
                return jsonify({'erro':'Perfil financeiro restrito ao modulo financeiro.'}),403
            if '/pago' in request.path and role not in {'admin','financeiro'}:
                return jsonify({'erro':'Pagamento exige financeiro ou administrador.'}),403
            if current_user.role == 'somente_leitura' and request.path.startswith('/api/'):
                return jsonify({'erro': 'Perfil somente leitura'}), 403
        if not request.path.startswith(ADMIN_MUTATION_PREFIXES):
            return None
        if not current_user.is_authenticated:
            return jsonify({'erro': 'Autenticacao obrigatoria'}), 401
        if getattr(current_user, 'role', None) != 'admin':
            return jsonify({'erro': 'Acesso negado'}), 403
        return None

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response
