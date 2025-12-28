"""
Rate Limiting Module for ANAGHA SOLUTION
Handles rate limits per email provider
"""

from typing import Dict, Optional
from database.db_manager import DatabaseManager
from datetime import datetime, date, timedelta

class RateLimiter:
    """Rate limiter for email providers"""
    
    # Provider-specific limits
    PROVIDER_LIMITS = {
        'gmail': {
            'daily': 90,
            'hourly': 10,
            'per_minute': 2
        },
        'outlook': {
            'daily': 250,
            'hourly': 30,
            'per_minute': 5
        },
        'yahoo': {
            'daily': 100,
            'hourly': 15,
            'per_minute': 3
        },
        'smtp': {
            'daily': 200,
            'hourly': 50,
            'per_minute': 10
        },
        'custom': {
            'daily': 200,
            'hourly': 50,
            'per_minute': 10
        }
    }
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def detect_provider(self, email: str) -> str:
        """Detect email provider from email address"""
        email_lower = email.lower()
        if 'gmail.com' in email_lower:
            return 'gmail'
        elif 'outlook.com' in email_lower or 'hotmail.com' in email_lower or 'live.com' in email_lower:
            return 'outlook'
        elif 'yahoo.com' in email_lower or 'ymail.com' in email_lower:
            return 'yahoo'
        else:
            return 'smtp'
    
    def get_provider_limits(self, provider: str) -> Dict:
        """Get rate limits for a provider"""
        return self.PROVIDER_LIMITS.get(provider, self.PROVIDER_LIMITS['smtp'])
    
    def check_rate_limit(self, smtp_server_id: int, provider_type: str = None) -> Dict:
        """
        Check if SMTP server can send more emails
        
        Returns:
            Dictionary with can_send, remaining, reset_time
        """
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        
        if use_supabase:
            # Get SMTP server info from Supabase
            result = self.db.supabase.client.table('smtp_servers').select(
                'id, username, provider_type, daily_sent_count, last_sent_date, max_per_hour'
            ).eq('id', smtp_server_id).execute()
            
            if not result.data or len(result.data) == 0:
                return {
                    'can_send': False,
                    'reason': 'SMTP server not found',
                    'remaining': 0
                }
            
            server = result.data[0]
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, username, provider_type, daily_sent_count, last_sent_date, max_per_hour
                FROM smtp_servers WHERE id = ?
            """, (smtp_server_id,))
            row = cursor.fetchone()
            
            if not row:
                return {
                    'can_send': False,
                    'reason': 'SMTP server not found',
                    'remaining': 0
                }
            
            server = dict(row)
        
        provider = provider_type or server.get('provider_type', 'smtp')
        if provider == 'smtp':
            # Detect from username
            provider = self.detect_provider(server.get('username', ''))
        
        limits = self.get_provider_limits(provider)
        daily_limit = limits['daily']
        hourly_limit = limits['hourly']
        
        # Check daily limit
        today = date.today()
        last_sent_date = server.get('last_sent_date')
        daily_sent = server.get('daily_sent_count', 0) or 0
        
        if last_sent_date:
            if isinstance(last_sent_date, str):
                try:
                    last_sent_date = datetime.fromisoformat(last_sent_date.replace('Z', '+00:00')).date()
                except:
                    last_sent_date = None
            elif isinstance(last_sent_date, date):
                pass
            else:
                last_sent_date = None
        
        # Reset daily count if new day
        if not last_sent_date or last_sent_date < today:
            daily_sent = 0
            if use_supabase:
                self.db.supabase.client.table('smtp_servers').update({
                    'daily_sent_count': 0,
                    'last_sent_date': today.isoformat()
                }).eq('id', smtp_server_id).execute()
            else:
                cursor.execute("""
                    UPDATE smtp_servers 
                    SET daily_sent_count = 0, last_sent_date = ?
                    WHERE id = ?
                """, (today, smtp_server_id))
                conn.commit()
        
        # Check if daily limit reached
        if daily_sent >= daily_limit:
            return {
                'can_send': False,
                'reason': f'Daily limit reached ({daily_limit} emails/day)',
                'remaining': 0,
                'limit_type': 'daily',
                'reset_time': datetime.combine(today + timedelta(days=1), datetime.min.time())
            }
        
        # Check hourly limit (simplified - in production, track per hour)
        # For now, use max_per_hour from server config
        max_per_hour = server.get('max_per_hour', hourly_limit)
        
        return {
            'can_send': True,
            'remaining': daily_limit - daily_sent,
            'daily_limit': daily_limit,
            'hourly_limit': max_per_hour,
            'provider': provider
        }
    
    def increment_sent_count(self, smtp_server_id: int):
        """Increment sent count for SMTP server"""
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        today = date.today()
        
        if use_supabase:
            # Get current count
            result = self.db.supabase.client.table('smtp_servers').select('daily_sent_count').eq('id', smtp_server_id).execute()
            current_count = 0
            if result.data and len(result.data) > 0:
                current_count = result.data[0].get('daily_sent_count', 0) or 0
            
            # Update
            self.db.supabase.client.table('smtp_servers').update({
                'daily_sent_count': current_count + 1,
                'last_sent_date': today.isoformat()
            }).eq('id', smtp_server_id).execute()
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE smtp_servers 
                SET daily_sent_count = daily_sent_count + 1,
                    last_sent_date = ?
                WHERE id = ?
            """, (today, smtp_server_id))
            conn.commit()
    
    def reset_daily_counts(self):
        """Reset daily counts for all servers (called daily)"""
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        today = date.today()
        
        if use_supabase:
            # Get all servers with old dates
            result = self.db.supabase.client.table('smtp_servers').select('id, last_sent_date').execute()
            if result.data:
                for server in result.data:
                    last_date = server.get('last_sent_date')
                    should_reset = False
                    if not last_date:
                        should_reset = True
                    elif isinstance(last_date, str):
                        try:
                            last_date_obj = datetime.fromisoformat(last_date.replace('Z', '+00:00')).date()
                            if last_date_obj < today:
                                should_reset = True
                        except:
                            should_reset = True
                    
                    if should_reset:
                        self.db.supabase.client.table('smtp_servers').update({
                            'daily_sent_count': 0,
                            'last_sent_date': today.isoformat()
                        }).eq('id', server['id']).execute()
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE smtp_servers 
                SET daily_sent_count = 0, last_sent_date = ?
                WHERE last_sent_date < ? OR last_sent_date IS NULL
            """, (today, today))
            conn.commit()

