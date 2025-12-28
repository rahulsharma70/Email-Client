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
        self.secret_key = secret_key or os.getenv('JWT_SECRET_KEY') or 'anagha_solution_secret_key_change_in_production'
        self.algorithm = 'HS256'
        self.token_expiry = timedelta(days=7)  # 7 days
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash (supports bcrypt and werkzeug formats)"""
        if not password_hash:
            return False
        
        try:
            # Try bcrypt first (current method)
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            # Fallback to werkzeug.security if bcrypt fails
            try:
                from werkzeug.security import check_password_hash
                return check_password_hash(password_hash, password)
            except Exception as e2:
                print(f"[DEBUG] Password verification error: {e}, {e2}")
                return False
    
    def register_user(self, email: str, password: str, first_name: str = '', 
                     last_name: str = '', company_name: str = '') -> Dict:
        """
        Register a new user
        
        Returns:
            Dictionary with user_id and verification token (not JWT - email verification token)
        """
        from core.email_verification import EmailVerificationManager
        from datetime import datetime
        
        email_verification = EmailVerificationManager(self.db)
        verification_token = email_verification.generate_verification_token()
        sent_at = datetime.now()
        
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            # Use Supabase methods
            try:
                # Check if user already exists
                result = self.db.supabase.client.table('users').select('id').eq('email', email.lower().strip()).execute()
                if result.data and len(result.data) > 0:
                    return {
                        'success': False,
                        'error': 'User with this email already exists'
                    }
                
                # Hash password
                password_hash = self.hash_password(password)
                
                # Create user with email verification fields
                result = self.db.supabase.client.table('users').insert({
                    'email': email.lower().strip(),
                    'password_hash': password_hash,
                    'first_name': first_name,
                    'last_name': last_name,
                    'company_name': company_name,
                    'subscription_plan': 'free',
                    'is_active': 1,  # INTEGER in Supabase, not boolean
                    'is_admin': 0,    # INTEGER in Supabase, not boolean
                    'email_verified': 0,  # Not verified yet
                    'email_verification_token': verification_token,
                    'email_verification_sent_at': sent_at.isoformat()
                }).execute()
                
                if not result.data or len(result.data) == 0:
                    return {
                        'success': False,
                        'error': 'Failed to create user'
                    }
                
                user_id = result.data[0]['id']
                
                # Send verification email
                email_result = email_verification.send_verification_email(email, verification_token, user_id)
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'email': email,
                    'email_sent': email_result.get('success', False),
                    'message': 'Registration successful. Please check your email to verify your account.'
                }
            except Exception as e:
                print(f"Error in Supabase registration: {e}")
                import traceback
                traceback.print_exc()
                # Check if it's a duplicate email error
                if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                    return {
                        'success': False,
                        'error': 'User with this email already exists'
                    }
                return {
                    'success': False,
                    'error': 'Database error during registration'
                }
        else:
            # SQLite
            # Check if using Supabase FIRST
            use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
            if not use_supabase:
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
                
                # Create user with email verification fields
                cursor.execute("""
                    INSERT INTO users (email, password_hash, first_name, last_name, company_name, subscription_plan,
                                      email_verified, email_verification_token, email_verification_sent_at)
                    VALUES (?, ?, ?, ?, ?, 'free', 0, ?, ?)
                """, (email.lower().strip(), password_hash, first_name, last_name, company_name, 
                      verification_token, sent_at))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                # Send verification email
                email_result = email_verification.send_verification_email(email, verification_token, user_id)
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'email': email,
                    'email_sent': email_result.get('success', False),
                    'message': 'Registration successful. Please check your email to verify your account.'
                }
    
    def login_user(self, email: str, password: str) -> Dict:
        """
        Login user and return JWT token
        
        Returns:
            Dictionary with user info and token
        """
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            # Use Supabase methods
            try:
                email_lower = email.lower().strip()
                print(f"[DEBUG] Attempting login for email: {email_lower}")
                
                result = self.db.supabase.client.table('users').select(
                    'id, email, password_hash, first_name, last_name, company_name, subscription_plan, is_active, is_admin, email_verified'
                ).eq('email', email_lower).execute()
                
                print(f"[DEBUG] Supabase query result: {len(result.data) if result.data else 0} users found")
                
                if not result.data or len(result.data) == 0:
                    print(f"[DEBUG] No user found with email: {email_lower}")
                    return {
                        'success': False,
                        'error': 'Invalid email or password'
                    }
                
                user = result.data[0]
                print(f"[DEBUG] User found: ID={user.get('id')}, Email={user.get('email')}, Active={user.get('is_active')}")
                
                # Check if account is active (is_active is INTEGER: 1 = active, 0 = inactive)
                is_active = user.get('is_active')
                if isinstance(is_active, bool):
                    is_active = 1 if is_active else 0
                if not is_active:
                    print(f"[DEBUG] Account is deactivated")
                    return {
                        'success': False,
                        'error': 'Account is deactivated'
                    }
                
                # Get password hash
                password_hash = user.get('password_hash')
                if not password_hash:
                    print(f"[DEBUG] No password hash found for user")
                    return {
                        'success': False,
                        'error': 'Invalid email or password'
                    }
                
                print(f"[DEBUG] Verifying password... Hash length: {len(password_hash)}")
                
                # Verify password
                password_valid = self.verify_password(password, password_hash)
                print(f"[DEBUG] Password verification result: {password_valid}")
                
                if not password_valid:
                    print(f"[DEBUG] Password verification failed")
                    return {
                        'success': False,
                        'error': 'Invalid email or password'
                    }
                
                # Check if email is verified
                email_verified = user.get('email_verified', 0)
                if isinstance(email_verified, bool):
                    email_verified = 1 if email_verified else 0
                if not email_verified:
                    return {
                        'success': False,
                        'error': 'Email not verified. Please check your email and verify your account.',
                        'email_verified': False
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
                    'is_admin': bool(user.get('is_admin', 0)),  # Convert INTEGER to boolean
                    'token': token
                }
            except Exception as e:
                print(f"Error in Supabase login: {e}")
                import traceback
                traceback.print_exc()
                return {
                    'success': False,
                    'error': 'Database error during login'
                }
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, email, password_hash, first_name, last_name, company_name, 
                       subscription_plan, is_active, is_admin, email_verified
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
            
            # Check if email is verified
            email_verified = user.get('email_verified', 0)
            if not email_verified:
                return {
                    'success': False,
                    'error': 'Email not verified. Please check your email and verify your account.',
                    'email_verified': False
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
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            try:
                result = self.db.supabase.client.table('users').select(
                    'id, email, first_name, last_name, company_name, subscription_plan, subscription_status, is_active, is_admin, stripe_customer_id, created_at'
                ).eq('id', user_id).execute()
                
                if result.data and len(result.data) > 0:
                    return result.data[0]
                return None
            except Exception as e:
                # Handle network errors gracefully (retry logic)
                error_msg = str(e)
                error_type = str(type(e).__name__)
                if 'Resource temporarily unavailable' in error_msg or 'ReadError' in error_type or 'ConnectionError' in error_type or 'OSError' in error_type:
                    # Network error - retry once with delay
                    import time
                    try:
                        time.sleep(0.5)
                        result = self.db.supabase.client.table('users').select(
                            'id, email, first_name, last_name, company_name, subscription_plan, subscription_status, is_active, is_admin, stripe_customer_id, created_at'
                        ).eq('id', user_id).execute()
                        if result.data and len(result.data) > 0:
                            return result.data[0]
                    except Exception as retry_error:
                        print(f"Error getting user from Supabase (retry failed): {retry_error}")
                        return None
                else:
                    print(f"Error getting user from Supabase: {e}")
                    return None
        else:
            # SQLite
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
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            try:
                # Get user
                result = self.db.supabase.client.table('users').select('password_hash').eq('id', user_id).execute()
                if not result.data or len(result.data) == 0:
                    return {'success': False, 'error': 'User not found'}
                
                if not self.verify_password(old_password, result.data[0]['password_hash']):
                    return {'success': False, 'error': 'Current password is incorrect'}
                
                new_hash = self.hash_password(new_password)
                self.db.supabase.client.table('users').update({
                    'password_hash': new_hash
                }).eq('id', user_id).execute()
                
                return {'success': True}
            except Exception as e:
                print(f"Error changing password in Supabase: {e}")
                return {'success': False, 'error': 'Database error'}
        else:
            # SQLite
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
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            try:
                result = self.db.supabase.client.table('users').select('id').eq('email', email.lower().strip()).execute()
                if not result.data or len(result.data) == 0:
                    # Don't reveal if user exists
                    return {'success': True, 'message': 'If email exists, reset link will be sent'}
                
                user_id = result.data[0]['id']
            except Exception as e:
                # Don't reveal if user exists
                return {'success': True, 'message': 'If email exists, reset link will be sent'}
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),))
            row = cursor.fetchone()
            
            if not row:
                # Don't reveal if user exists
                return {'success': True, 'message': 'If email exists, reset link will be sent'}
            
            user_id = row[0]
        
        # Generate reset token
        reset_token = jwt.encode(
            {'user_id': user_id, 'type': 'password_reset', 'exp': datetime.utcnow() + timedelta(hours=1)},
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
            
            # Check if using Supabase
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                try:
                    self.db.supabase.client.table('users').update({
                        'password_hash': new_hash
                    }).eq('id', user_id).execute()
                    return {'success': True}
                except Exception as e:
                    print(f"Error resetting password in Supabase: {e}")
                    return {'success': False, 'error': 'Database error'}
            else:
                # SQLite
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

