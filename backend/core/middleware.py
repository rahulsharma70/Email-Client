"""
Middleware for ANAGHA SOLUTION
JWT authentication and user context
"""

from functools import wraps
from flask import request, jsonify
from core.auth import AuthManager
from database.db_manager import DatabaseManager
import os

# Global auth manager instance - will be set by web_app.py
_auth_manager = None

def set_auth_manager(auth_manager_instance):
    """Set the auth manager instance to use (called from web_app.py)"""
    global _auth_manager
    _auth_manager = auth_manager_instance

def get_current_user():
    """Get current user from JWT token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    try:
        token = auth_header.split(' ')[1]
        
        # Use the global auth manager if available, otherwise create one
        if _auth_manager:
            auth = _auth_manager
        else:
            # Fallback: create new instance with same secret key
            db = DatabaseManager()
            secret_key = os.getenv('JWT_SECRET_KEY') or 'anagha_solution_secret_key_change_in_production'
            auth = AuthManager(db, secret_key=secret_key)
        
        user_data = auth.verify_token(token)
        if user_data:
            return {'user_id': user_data.get('user_id') or user_data.get('sub'), 'email': user_data.get('email')}
        return None
    except Exception as e:
        print(f"Error verifying token: {e}")
        import traceback
        traceback.print_exc()
        return None

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

