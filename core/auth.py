"""
Authentication Module for ANAGHA SOLUTION
Handles user registration, login, JWT tokens
"""

try:
    import jwt
except ImportError:
    # PyJWT package provides jwt module
    try:
        from jwt import PyJWT as jwt
    except:
        raise ImportError("Please install PyJWT: pip install PyJWT")
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
from database.db_manager import DatabaseManager
import os

class AuthManager:
    def __init__(self, db_manager: DatabaseManager, secret_key: str = None):
        """
        Initialize authentication manager
        
        Args:
            db_manager: Database manager instance
            secret_key: JWT secret key (defaults to env var or generates)
        """
        self.db = db_manager
        # Require JWT_SECRET_KEY environment variable - no insecure fallback
        self.secret_key = secret_key or os.getenv('JWT_SECRET_KEY')
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY environment variable must be set. Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'")
        self.algorithm = 'HS256'
        self.token_expiry = timedelta(days=7)  # 7 days
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except:
            return False
    
    def register_user(self, email: str, password: str, first_name: str = '', 
                     last_name: str = '', company_name: str = '') -> Dict:
        """
        Register a new user
        
        Returns:
            Dictionary with user_id and token
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),))
        if cursor.fetchone():
            return {
                'success': False,
                'error': 'User with this email already exists'
            }
        
        # Hash password
        password_hash = self.hash_password(password)
        
        # Create user
        cursor.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, company_name, subscription_plan)
            VALUES (?, ?, ?, ?, ?, 'free')
        """, (email.lower().strip(), password_hash, first_name, last_name, company_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Generate token
        token = self.generate_token(user_id, email)
        
        return {
            'success': True,
            'user_id': user_id,
            'email': email,
            'token': token
        }
    
    def login_user(self, email: str, password: str) -> Dict:
        """
        Login user and return JWT token
        
        Returns:
            Dictionary with user info and token
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, email, password_hash, first_name, last_name, company_name, 
                   subscription_plan, is_active, is_admin
            FROM users WHERE email = ?
        """, (email.lower().strip(),))
        
        row = cursor.fetchone()
        if not row:
            return {
                'success': False,
                'error': 'Invalid email or password'
            }
        
        user = dict(row)
        
        # Check if account is active
        if not user.get('is_active', 1):
            return {
                'success': False,
                'error': 'Account is deactivated'
            }
        
        # Verify password
        if not self.verify_password(password, user['password_hash']):
            return {
                'success': False,
                'error': 'Invalid email or password'
            }
        
        # Generate token
        token = self.generate_token(user['id'], user['email'])
        
        return {
            'success': True,
            'user_id': user['id'],
            'email': user['email'],
            'first_name': user.get('first_name', ''),
            'last_name': user.get('last_name', ''),
            'company_name': user.get('company_name', ''),
            'subscription_plan': user.get('subscription_plan', 'free'),
            'is_admin': bool(user.get('is_admin', 0)),
            'token': token
        }
    
    def generate_token(self, user_id: int, email: str) -> str:
        """Generate JWT token"""
        payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.utcnow() + self.token_expiry,
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify JWT token and return user info
        
        Returns:
            Dictionary with user_id and email, or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return {
                'user_id': payload.get('user_id'),
                'email': payload.get('email')
            }
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email, first_name, last_name, company_name, 
                   subscription_plan, subscription_status, is_active, is_admin,
                   stripe_customer_id, created_at
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """Update user information"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        allowed_fields = ['first_name', 'last_name', 'company_name', 'email']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if not updates:
            return False
        
        params.append(user_id)
        cursor.execute(f"""
            UPDATE users 
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, params)
        conn.commit()
        return cursor.rowcount > 0
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict:
        """Change user password"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return {'success': False, 'error': 'User not found'}
        
        if not self.verify_password(old_password, row[0]):
            return {'success': False, 'error': 'Current password is incorrect'}
        
        new_hash = self.hash_password(new_password)
        cursor.execute("""
            UPDATE users 
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_hash, user_id))
        conn.commit()
        
        return {'success': True}
    
    def reset_password_request(self, email: str) -> Dict:
        """Request password reset (sends reset token)"""
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),))
        row = cursor.fetchone()
        
        if not row:
            # Don't reveal if user exists
            return {'success': True, 'message': 'If email exists, reset link will be sent'}
        
        # Generate reset token
        reset_token = jwt.encode(
            {'user_id': row[0], 'type': 'password_reset', 'exp': datetime.utcnow() + timedelta(hours=1)},
            self.secret_key,
            algorithm=self.algorithm
        )
        
        # In production, send email with reset link
        # For now, return token (should be sent via email)
        return {
            'success': True,
            'reset_token': reset_token,  # In production, send via email
            'message': 'Password reset link generated'
        }
    
    def reset_password(self, reset_token: str, new_password: str) -> Dict:
        """Reset password using reset token"""
        try:
            payload = jwt.decode(reset_token, self.secret_key, algorithms=[self.algorithm])
            if payload.get('type') != 'password_reset':
                return {'success': False, 'error': 'Invalid reset token'}
            
            user_id = payload.get('user_id')
            new_hash = self.hash_password(new_password)
            
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_hash, user_id))
            conn.commit()
            
            return {'success': True}
        except jwt.ExpiredSignatureError:
            return {'success': False, 'error': 'Reset token expired'}
        except jwt.InvalidTokenError:
            return {'success': False, 'error': 'Invalid reset token'}

