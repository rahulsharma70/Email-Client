"""
Middleware for ANAGHA SOLUTION
JWT authentication and user context
"""

from functools import wraps
from flask import request, jsonify
from core.auth import AuthManager
from database.db_manager import DatabaseManager

def get_current_user():
    """Get current user from JWT token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    db = DatabaseManager()
    auth = AuthManager(db)
    return auth.verify_token(token)

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Add user_id to kwargs
        kwargs['user_id'] = user['user_id']
        return f(*args, **kwargs)
    return decorated_function

def optional_auth(f):
    """Decorator for optional authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user:
            kwargs['user_id'] = user['user_id']
        else:
            kwargs['user_id'] = None
        return f(*args, **kwargs)
    return decorated_function

