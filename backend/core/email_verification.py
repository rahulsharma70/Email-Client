"""
Email Verification Module for User Signup
Handles OTP/magic link generation and sending
"""

import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Optional
from database.db_manager import DatabaseManager
from core.config import Config
import os
import urllib.parse

class EmailVerificationManager:
    """Manages email verification for user signup"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.token_expiry = timedelta(hours=24)  # Token valid for 24 hours
    
    def generate_verification_token(self) -> str:
        """Generate a secure random token for email verification"""
        return secrets.token_urlsafe(32)
    
    def send_verification_email(self, email: str, token: str, user_id: int) -> Dict:
        """
        Send verification email with magic link
        
        Args:
            email: User's email address
            token: Verification token
            user_id: User ID
            
        Returns:
            Dictionary with success status
        """
        try:
            # Get app URL from config or environment
            app_url = Config.get('APP_URL', 'http://localhost:5001')
            verification_url = f"{app_url}/verify-email?token={token}"
            
            # Get email settings
            email_from = Config.get('EMAIL_FROM_ADDRESS', 'noreply@anaghasolution.com')
            email_from_name = Config.get('EMAIL_FROM_NAME', 'ANAGHA SOLUTION')
            
            # Create email content
            subject = "Verify Your Email Address"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #635bff; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .button {{ display: inline-block; padding: 12px 24px; background-color: #635bff; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Verify Your Email</h1>
                    </div>
                    <div class="content">
                        <p>Thank you for signing up! Please verify your email address by clicking the button below:</p>
                        <p style="text-align: center;">
                            <a href="{verification_url}" class="button">Verify Email Address</a>
                        </p>
                        <p>Or copy and paste this link into your browser:</p>
                        <p style="word-break: break-all; color: #635bff;">{verification_url}</p>
                        <p>This link will expire in 24 hours.</p>
                        <p>If you didn't create an account, you can safely ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2024 ANAGHA SOLUTION. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            Verify Your Email Address
            
            Thank you for signing up! Please verify your email address by visiting:
            
            {verification_url}
            
            This link will expire in 24 hours.
            
            If you didn't create an account, you can safely ignore this email.
            """
            
            # Try to send via SMTP if configured
            smtp_host = Config.get('SMTP_HOST')
            smtp_port = Config.get('SMTP_PORT', '587')
            smtp_user = Config.get('SMTP_USER')
            smtp_password = Config.get('SMTP_PASSWORD')
            
            if smtp_host and smtp_user and smtp_password:
                # Send via SMTP
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = f"{email_from_name} <{email_from}>"
                msg['To'] = email
                
                msg.attach(MIMEText(text_content, 'plain'))
                msg.attach(MIMEText(html_content, 'html'))
                
                try:
                    server = smtplib.SMTP(smtp_host, int(smtp_port))
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)
                    server.quit()
                    return {'success': True, 'message': 'Verification email sent'}
                except Exception as e:
                    print(f"Error sending verification email via SMTP: {e}")
                    # Fall through to log-only mode
            
            # If SMTP not configured, log the email (for development)
            print(f"\n{'='*60}")
            print(f"VERIFICATION EMAIL (SMTP not configured):")
            print(f"To: {email}")
            print(f"Subject: {subject}")
            print(f"Verification URL: {verification_url}")
            print(f"{'='*60}\n")
            
            return {'success': True, 'message': 'Verification email logged (SMTP not configured)'}
            
        except Exception as e:
            print(f"Error in send_verification_email: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def verify_email_token(self, token: str) -> Dict:
        """
        Verify email using token
        
        Args:
            token: Verification token
            
        Returns:
            Dictionary with success status and user_id
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Check if using Supabase
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                # Query Supabase
                result = self.db.supabase.client.table('users').select(
                    'id, email, email_verification_token, email_verification_sent_at, email_verified'
                ).eq('email_verification_token', token).execute()
                
                if not result.data or len(result.data) == 0:
                    return {'success': False, 'error': 'Invalid verification token'}
                
                user = result.data[0]
                
                # Check if already verified
                if user.get('email_verified'):
                    return {'success': False, 'error': 'Email already verified'}
                
                # Check token expiry
                sent_at = user.get('email_verification_sent_at')
                if sent_at:
                    if isinstance(sent_at, str):
                        sent_at = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                    if datetime.now() - sent_at.replace(tzinfo=None) > self.token_expiry:
                        return {'success': False, 'error': 'Verification token expired'}
                
                # Mark email as verified
                self.db.supabase.client.table('users').update({
                    'email_verified': 1,
                    'email_verification_token': None,
                    'email_verification_sent_at': None
                }).eq('id', user['id']).execute()
                
                return {
                    'success': True,
                    'user_id': user['id'],
                    'email': user['email']
                }
            else:
                # SQLite
                cursor.execute("""
                    SELECT id, email, email_verification_token, email_verification_sent_at, email_verified
                    FROM users
                    WHERE email_verification_token = ?
                """, (token,))
                
                row = cursor.fetchone()
                if not row:
                    return {'success': False, 'error': 'Invalid verification token'}
                
                user_id, email, stored_token, sent_at, email_verified = row
                
                # Check if already verified
                if email_verified:
                    return {'success': False, 'error': 'Email already verified'}
                
                # Check token expiry
                if sent_at:
                    if isinstance(sent_at, str):
                        sent_at = datetime.fromisoformat(sent_at)
                    if datetime.now() - sent_at > self.token_expiry:
                        return {'success': False, 'error': 'Verification token expired'}
                
                # Mark email as verified
                cursor.execute("""
                    UPDATE users
                    SET email_verified = 1,
                        email_verification_token = NULL,
                        email_verification_sent_at = NULL
                    WHERE id = ?
                """, (user_id,))
                conn.commit()
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'email': email
                }
                
        except Exception as e:
            print(f"Error in verify_email_token: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def resend_verification_email(self, email: str) -> Dict:
        """
        Resend verification email
        
        Args:
            email: User's email address
            
        Returns:
            Dictionary with success status
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Check if using Supabase
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('users').select(
                    'id, email_verified'
                ).eq('email', email.lower().strip()).execute()
                
                if not result.data or len(result.data) == 0:
                    return {'success': False, 'error': 'User not found'}
                
                user = result.data[0]
                
                if user.get('email_verified'):
                    return {'success': False, 'error': 'Email already verified'}
                
                user_id = user['id']
            else:
                # SQLite
                cursor.execute("""
                    SELECT id, email_verified FROM users WHERE email = ?
                """, (email.lower().strip(),))
                
                row = cursor.fetchone()
                if not row:
                    return {'success': False, 'error': 'User not found'}
                
                user_id, email_verified = row
                
                if email_verified:
                    return {'success': False, 'error': 'Email already verified'}
            
            # Generate new token
            token = self.generate_verification_token()
            sent_at = datetime.now()
            
            # Update database
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                self.db.supabase.client.table('users').update({
                    'email_verification_token': token,
                    'email_verification_sent_at': sent_at.isoformat()
                }).eq('id', user_id).execute()
            else:
                cursor.execute("""
                    UPDATE users
                    SET email_verification_token = ?,
                        email_verification_sent_at = ?
                    WHERE id = ?
                """, (token, sent_at, user_id))
                conn.commit()
            
            # Send email
            result = self.send_verification_email(email, token, user_id)
            return result
            
        except Exception as e:
            print(f"Error in resend_verification_email: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
