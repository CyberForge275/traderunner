"""
Basic HTTP Authentication for Dash
"""
import dash
from functools import wraps
from flask import request, Response

from .config import AUTH_USERNAME, AUTH_PASSWORD


def check_auth(username: str, password: str) -> bool:
    """Check if username/password combination is valid."""
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


def authenticate():
    """Send a 401 response that enables basic auth."""
    return Response(
        'Authentication required.\n',
        401,
        {'WWW-Authenticate': 'Basic realm="Trading Dashboard"'}
    )


def requires_auth(f):
    """Decorator for routes that require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def add_auth_to_app(app: dash.Dash):
    """Add authentication to all routes of a Dash app."""

    @app.server.before_request
    def before_request():
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()

    return app
