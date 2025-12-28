"""
Abuse Prevention Module for ANAGHA SOLUTION
Detects and prevents spam, bulk imports, scam keywords, and multi-account abuse
"""

import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
import hashlib

class AbusePrevention:
    """Prevents abuse and spam on the platform"""
    
    # Scam keywords to detect
    SCAM_KEYWORDS = [
        'urgent', 'act now', 'limited time', 'click here', 'free money',
        'winner', 'congratulations', 'claim your prize', 'verify account',
        'suspended', 'locked', 'expired', 'immediate action required',
        'nigerian prince', 'lottery', 'inheritance', 'wire transfer'
    ]
    
    # Limits
    MAX_EMAILS_PER_HOUR = 1000
    MAX_RECIPIENTS_PER_CAMPAIGN = 10000
    MAX_CAMPAIGNS_PER_DAY = 50
    MAX_ACCOUNTS_PER_IP = 3
    MAX_ACCOUNTS_PER_DOMAIN = 1
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def check_anti_spam_limits(self, user_id: int, email_count: int, recipient_count: int) -> Dict:
        """
        Check anti-spam limits
        
        Returns:
            Dictionary with allowed status
        """
        try:
            # Check emails per hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('email_queue').select(
                    'id', count='exact'
                ).eq('user_id', user_id).eq('status', 'sent').gte('sent_at', one_hour_ago.isoformat()).execute()
                emails_last_hour = result.count if result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM email_queue
                    WHERE user_id = ? AND status = 'sent' AND sent_at >= ?
                """, (user_id, one_hour_ago))
                emails_last_hour = cursor.fetchone()[0] or 0
            
            if emails_last_hour + email_count > self.MAX_EMAILS_PER_HOUR:
                return {
                    'allowed': False,
                    'reason': f'Email limit per hour ({self.MAX_EMAILS_PER_HOUR}) exceeded. Sent in last hour: {emails_last_hour}',
                    'limit': self.MAX_EMAILS_PER_HOUR,
                    'sent': emails_last_hour
                }
            
            # Check recipients per campaign
            if recipient_count > self.MAX_RECIPIENTS_PER_CAMPAIGN:
                return {
                    'allowed': False,
                    'reason': f'Recipient limit per campaign ({self.MAX_RECIPIENTS_PER_CAMPAIGN}) exceeded. Requested: {recipient_count}',
                    'limit': self.MAX_RECIPIENTS_PER_CAMPAIGN
                }
            
            # Check campaigns per day
            today = datetime.now().date()
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('campaigns').select(
                    'id', count='exact'
                ).eq('user_id', user_id).gte('created_at', today.isoformat()).execute()
                campaigns_today = result.count if result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM campaigns
                    WHERE user_id = ? AND DATE(created_at) = ?
                """, (user_id, today))
                campaigns_today = cursor.fetchone()[0] or 0
            
            if campaigns_today >= self.MAX_CAMPAIGNS_PER_DAY:
                return {
                    'allowed': False,
                    'reason': f'Campaign limit per day ({self.MAX_CAMPAIGNS_PER_DAY}) exceeded. Created today: {campaigns_today}',
                    'limit': self.MAX_CAMPAIGNS_PER_DAY
                }
            
            return {'allowed': True}
            
        except Exception as e:
            print(f"Error checking anti-spam limits: {e}")
            return {'allowed': True}  # Allow on error
    
    def check_banned_domains(self, domain: str) -> Dict:
        """
        Check if domain is banned
        
        Returns:
            Dictionary with banned status
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Check banned_domains table
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('banned_domains').select('*').eq('domain', domain.lower()).execute()
                if result.data and len(result.data) > 0:
                    return {
                        'banned': True,
                        'reason': result.data[0].get('reason', 'Domain is banned'),
                        'domain': domain
                    }
            else:
                cursor.execute("SELECT * FROM banned_domains WHERE domain = ?", (domain.lower(),))
                row = cursor.fetchone()
                if row:
                    return {
                        'banned': True,
                        'reason': row[1] if len(row) > 1 else 'Domain is banned',
                        'domain': domain
                    }
            
            return {'banned': False}
            
        except Exception as e:
            print(f"Error checking banned domains: {e}")
            return {'banned': False}
    
    def detect_bulk_import(self, user_id: int, lead_count: int, time_window_minutes: int = 60) -> Dict:
        """
        Detect bulk import of bad leads
        
        Returns:
            Dictionary with detection status
        """
        try:
            time_window = datetime.now() - timedelta(minutes=time_window_minutes)
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('leads').select(
                    'id', count='exact'
                ).eq('user_id', user_id).gte('created_at', time_window.isoformat()).execute()
                leads_recent = result.count if result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM leads
                    WHERE user_id = ? AND created_at >= ?
                """, (user_id, time_window))
                leads_recent = cursor.fetchone()[0] or 0
            
            # Threshold: more than 1000 leads in 1 hour
            threshold = 1000
            total_leads = leads_recent + lead_count
            
            if total_leads > threshold:
                return {
                    'detected': True,
                    'reason': f'Bulk import detected: {total_leads} leads imported in last {time_window_minutes} minutes',
                    'leads_recent': leads_recent,
                    'threshold': threshold,
                    'action': 'require_manual_approval'
                }
            
            return {'detected': False}
            
        except Exception as e:
            print(f"Error detecting bulk import: {e}")
            return {'detected': False}
    
    def detect_scam_keywords(self, content: str) -> Dict:
        """
        Detect scam keywords in email content
        
        Returns:
            Dictionary with detection status
        """
        try:
            content_lower = content.lower()
            detected_keywords = []
            
            for keyword in self.SCAM_KEYWORDS:
                if keyword in content_lower:
                    detected_keywords.append(keyword)
            
            if detected_keywords:
                return {
                    'detected': True,
                    'keywords': detected_keywords,
                    'action': 'flag_for_review',
                    'severity': 'high' if len(detected_keywords) >= 3 else 'medium'
                }
            
            return {'detected': False}
            
        except Exception as e:
            print(f"Error detecting scam keywords: {e}")
            return {'detected': False}
    
    def check_account_creation_rate(self, ip_address: str, email_domain: str) -> Dict:
        """
        Check rate limit on account creation
        
        Returns:
            Dictionary with allowed status
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Check accounts per IP (last 24 hours)
            one_day_ago = datetime.now() - timedelta(days=1)
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                # Count accounts created from this IP
                # Note: We'd need to store IP addresses in user_fingerprints table
                result = self.db.supabase.client.table('user_fingerprints').select(
                    'user_id', count='exact'
                ).eq('ip_address', ip_address).gte('created_at', one_day_ago.isoformat()).execute()
                accounts_from_ip = result.count if result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) FROM user_fingerprints
                    WHERE ip_address = ? AND created_at >= ?
                """, (ip_address, one_day_ago))
                accounts_from_ip = cursor.fetchone()[0] or 0
            
            if accounts_from_ip >= self.MAX_ACCOUNTS_PER_IP:
                return {
                    'allowed': False,
                    'reason': f'Account creation limit per IP ({self.MAX_ACCOUNTS_PER_IP}) exceeded',
                    'limit': self.MAX_ACCOUNTS_PER_IP,
                    'count': accounts_from_ip
                }
            
            # Check accounts per email domain (last 24 hours)
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('users').select(
                    'id', count='exact'
                ).like('email', f'%@{email_domain}').gte('created_at', one_day_ago.isoformat()).execute()
                accounts_from_domain = result.count if result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM users
                    WHERE email LIKE ? AND created_at >= ?
                """, (f'%@{email_domain}', one_day_ago))
                accounts_from_domain = cursor.fetchone()[0] or 0
            
            if accounts_from_domain >= self.MAX_ACCOUNTS_PER_DOMAIN:
                return {
                    'allowed': False,
                    'reason': f'Account creation limit per domain ({self.MAX_ACCOUNTS_PER_DOMAIN}) exceeded',
                    'limit': self.MAX_ACCOUNTS_PER_DOMAIN,
                    'count': accounts_from_domain
                }
            
            return {'allowed': True}
            
        except Exception as e:
            print(f"Error checking account creation rate: {e}")
            return {'allowed': True}  # Allow on error to prevent blocking legitimate users
    
    def fingerprint_user(self, user_id: int, ip_address: str, user_agent: str) -> Dict:
        """
        Create fingerprint for user to detect multi-account abuse
        
        Returns:
            Dictionary with fingerprint info
        """
        try:
            # Create browser fingerprint hash
            fingerprint_data = f"{ip_address}:{user_agent}"
            fingerprint_hash = hashlib.md5(fingerprint_data.encode()).hexdigest()
            
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Store fingerprint
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                self.db.supabase.client.table('user_fingerprints').insert({
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'browser_fingerprint': fingerprint_hash
                }).execute()
            else:
                cursor.execute("""
                    INSERT INTO user_fingerprints (user_id, ip_address, user_agent, browser_fingerprint)
                    VALUES (?, ?, ?, ?)
                """, (user_id, ip_address, user_agent, fingerprint_hash))
                conn.commit()
            
            # Check for duplicate fingerprints (multi-account detection)
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('user_fingerprints').select(
                    'user_id', count='exact'
                ).eq('browser_fingerprint', fingerprint_hash).execute()
                duplicate_count = result.count if result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) FROM user_fingerprints
                    WHERE browser_fingerprint = ?
                """, (fingerprint_hash,))
                duplicate_count = cursor.fetchone()[0] or 0
            
            if duplicate_count > 3:  # More than 3 accounts with same fingerprint
                return {
                    'fingerprint': fingerprint_hash,
                    'suspicious': True,
                    'reason': f'Multiple accounts ({duplicate_count}) detected with same fingerprint',
                    'action': 'flag_for_review'
                }
            
            return {
                'fingerprint': fingerprint_hash,
                'suspicious': False
            }
            
        except Exception as e:
            print(f"Error fingerprinting user: {e}")
            return {'fingerprint': None, 'error': str(e)}
    
    def create_banned_domain(self, domain: str, reason: str) -> Dict:
        """Add domain to banned list"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Create banned_domains table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS banned_domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL UNIQUE,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                self.db.supabase.client.table('banned_domains').insert({
                    'domain': domain.lower(),
                    'reason': reason
                }).execute()
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO banned_domains (domain, reason)
                    VALUES (?, ?)
                """, (domain.lower(), reason))
                conn.commit()
            
            return {'success': True}
            
        except Exception as e:
            print(f"Error creating banned domain: {e}")
            return {'success': False, 'error': str(e)}
