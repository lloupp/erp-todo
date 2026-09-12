"""Centralized production-only HTTP hardening.

Route-level authorization remains the preferred defense, but these guards provide
an additional deny-by-default layer for configuration mutations and consistent
security headers at the production entry point.
"""

from __future__ import annotations

from flask import jsonify, request
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
