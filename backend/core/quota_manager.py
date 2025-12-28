"""
Quota Manager for ANAGHA SOLUTION
Enforces per-tenant quotas at enqueue time
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from database.db_manager import DatabaseManager
from core.billing import BillingManager

class QuotaManager:
    """Manages per-tenant quotas and limits"""
    
    # Plan limits
    PLAN_LIMITS = {
        'start': {
            'emails_per_month': 10000,
            'leads_per_month': 1000,
            'campaigns_per_month': 10,
            'llm_tokens_per_month': 100000,
            'domains_per_account': 1
        },
        'growth': {
            'emails_per_month': 50000,
            'leads_per_month': 5000,
            'campaigns_per_month': 50,
            'llm_tokens_per_month': 500000,
            'domains_per_account': 3
        },
        'pro': {
            'emails_per_month': 200000,
            'leads_per_month': 20000,
            'campaigns_per_month': 200,
            'llm_tokens_per_month': 2000000,
            'domains_per_account': 10
        },
        'agency': {
            'emails_per_month': 1000000,
            'leads_per_month': 100000,
            'campaigns_per_month': 1000,
            'llm_tokens_per_month': 10000000,
            'domains_per_account': 50
        }
    }
    
    # Per-domain daily limits
    DOMAIN_DAILY_LIMITS = {
        'gmail': 90,
        'outlook': 250,
        'yahoo': 200,
        'smtp': 500  # Generic SMTP
    }
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize quota manager"""
        self.db = db_manager
        self.billing = BillingManager(db_manager)
    
    def get_user_plan(self, user_id: int) -> str:
        """Get user's subscription plan"""
        try:
            subscription = self.billing.get_subscription_info(user_id)
            if subscription and subscription.get('plan'):
                return subscription['plan'].lower()
        except:
            pass
        return 'start'  # Default to start plan
    
    def check_email_quota(self, user_id: int, count: int = 1) -> Dict:
        """
        Check if user can send N emails
        
        Returns:
            {'allowed': bool, 'reason': str, 'remaining': int}
        """
        plan = self.get_user_plan(user_id)
        limit = self.PLAN_LIMITS[plan]['emails_per_month']
        
        # Get current month usage
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Count emails sent this month
        cursor.execute("""
            SELECT COUNT(*) FROM email_queue
            WHERE user_id = ? AND sent_at >= ? AND status = 'sent'
        """, (user_id, month_start))
        
        sent_count = cursor.fetchone()[0]
        
        remaining = limit - sent_count
        
        if sent_count + count > limit:
            return {
                'allowed': False,
                'reason': f'Monthly email limit ({limit}) exceeded. Sent: {sent_count}, Requested: {count}',
                'remaining': max(0, remaining),
                'limit': limit,
                'used': sent_count
            }
        
        return {
            'allowed': True,
            'remaining': remaining - count,
            'limit': limit,
            'used': sent_count
        }
    
    def check_domain_daily_limit(self, domain: str, provider: str, count: int = 1) -> Dict:
        """
        Check per-domain daily sending limit
        
        Returns:
            {'allowed': bool, 'reason': str, 'remaining': int}
        """
        limit = self.DOMAIN_DAILY_LIMITS.get(provider.lower(), 500)
        
        # Get today's usage for this domain
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Count emails sent today from this domain
        cursor.execute("""
            SELECT COUNT(*) FROM email_queue eq
            JOIN smtp_servers ss ON eq.smtp_server_id = ss.id
            WHERE ss.username LIKE ? AND eq.sent_at >= ? AND eq.status = 'sent'
        """, (f'%@{domain}', today))
        
        sent_count = cursor.fetchone()[0]
        
        remaining = limit - sent_count
        
        if sent_count + count > limit:
            return {
                'allowed': False,
                'reason': f'Daily limit for {domain} ({limit}) exceeded. Sent: {sent_count}, Requested: {count}',
                'remaining': max(0, remaining),
                'limit': limit,
                'used': sent_count
            }
        
        return {
            'allowed': True,
            'remaining': remaining - count,
            'limit': limit,
            'used': sent_count
        }
    
    def check_lead_quota(self, user_id: int, count: int = 1) -> Dict:
        """Check if user can scrape N leads"""
        plan = self.get_user_plan(user_id)
        limit = self.PLAN_LIMITS[plan]['leads_per_month']
        
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM leads
            WHERE user_id = ? AND created_at >= ?
        """, (user_id, month_start))
        
        lead_count = cursor.fetchone()[0]
        
        remaining = limit - lead_count
        
        if lead_count + count > limit:
            return {
                'allowed': False,
                'reason': f'Monthly lead limit ({limit}) exceeded. Scraped: {lead_count}, Requested: {count}',
                'remaining': max(0, remaining),
                'limit': limit,
                'used': lead_count
            }
        
        return {
            'allowed': True,
            'remaining': remaining - count,
            'limit': limit,
            'used': lead_count
        }
    
    def check_llm_quota(self, user_id: int, tokens: int) -> Dict:
        """Check if user can use N LLM tokens"""
        plan = self.get_user_plan(user_id)
        limit = self.PLAN_LIMITS[plan]['llm_tokens_per_month']
        
        # Use SettingsManager to get LLM usage (works with both SQLite and Supabase)
        from database.settings_manager import SettingsManager
        settings = SettingsManager(self.db)
        
        # Get LLM usage this month
        tokens_used_str = settings.get_setting('llm_tokens_used_this_month', user_id=user_id, default='0')
        try:
            tokens_used = int(tokens_used_str)
        except (ValueError, TypeError):
            tokens_used = 0
        
        remaining = limit - tokens_used
        
        if tokens_used + tokens > limit:
            return {
                'allowed': False,
                'reason': f'Monthly LLM token limit ({limit}) exceeded. Used: {tokens_used}, Requested: {tokens}',
                'remaining': max(0, remaining),
                'limit': limit,
                'used': tokens_used
            }
        
        return {
            'allowed': True,
            'remaining': remaining - tokens,
            'limit': limit,
            'used': tokens_used
        }
    
    def record_llm_usage(self, user_id: int, tokens: int):
        """Record LLM token usage and cost"""
        from database.settings_manager import SettingsManager
        settings = SettingsManager(self.db)
        
        # Get current usage
        current_str = settings.get_setting('llm_tokens_used_this_month', user_id=user_id, default='0')
        try:
            current = int(current_str)
        except (ValueError, TypeError):
            current = 0
        
        # Calculate cost (approximate: $0.002 per 1K tokens)
        cost_per_1k_tokens = 0.002
        cost = (tokens / 1000) * cost_per_1k_tokens
        
        # Get current cost
        current_cost_str = settings.get_setting('llm_cost_this_month', user_id=user_id, default='0.0')
        try:
            current_cost = float(current_cost_str)
        except (ValueError, TypeError):
            current_cost = 0.0
        
        # Update usage and cost
        settings.set_setting('llm_tokens_used_this_month', str(current + tokens), user_id=user_id)
        settings.set_setting('llm_cost_this_month', str(current_cost + cost), user_id=user_id)
    
    def check_llm_cost_quota(self, user_id: int, estimated_tokens: int = 0) -> Dict:
        """
        Check LLM cost quota per plan
        
        Returns:
            Dictionary with allowed status and cost info
        """
        try:
            plan = self.get_user_plan(user_id)
            
            # Cost limits per plan (in USD per month)
            COST_LIMITS = {
                'free': 0.0,
                'start': 0.20,      # $0.20/month (100K tokens)
                'growth': 1.00,     # $1.00/month (500K tokens)
                'pro': 4.00,        # $4.00/month (2M tokens)
                'agency': 20.00     # $20.00/month (10M tokens)
            }
            
            cost_limit = COST_LIMITS.get(plan, COST_LIMITS['start'])
            
            # Get current cost using SettingsManager (works with both SQLite and Supabase)
            from database.settings_manager import SettingsManager
            settings = SettingsManager(self.db)
            current_cost_str = settings.get_setting('llm_cost_this_month', user_id=user_id, default='0.0')
            try:
                current_cost = float(current_cost_str)
            except (ValueError, TypeError):
                current_cost = 0.0
            
            # Estimate cost for this request
            cost_per_1k_tokens = 0.002
            estimated_cost = (estimated_tokens / 1000) * cost_per_1k_tokens
            total_cost = current_cost + estimated_cost
            
            if total_cost > cost_limit:
                return {
                    'allowed': False,
                    'reason': f'LLM cost limit ({cost_limit:.2f}) exceeded. Current: ${current_cost:.2f}, Estimated: ${estimated_cost:.2f}',
                    'limit': cost_limit,
                    'current': current_cost,
                    'estimated': estimated_cost
                }
            
            return {
                'allowed': True,
                'limit': cost_limit,
                'current': current_cost,
                'remaining': cost_limit - current_cost,
                'estimated': estimated_cost
            }
            
        except Exception as e:
            print(f"Error checking LLM cost quota: {e}")
            return {'allowed': True}  # Allow on error
    
    def enforce_quota_at_enqueue(self, user_id: int, email_count: int, 
                                 domain: str = None, provider: str = None) -> Dict:
        """
        Enforce all quotas before enqueueing emails
        
        Returns:
            {'allowed': bool, 'reason': str, 'quotas': dict}
        """
        # Check monthly email quota
        email_check = self.check_email_quota(user_id, email_count)
        if not email_check['allowed']:
            return {
                'allowed': False,
                'reason': email_check['reason'],
                'quotas': {'email': email_check}
            }
        
        # Check domain daily limit if provided
        if domain and provider:
            domain_check = self.check_domain_daily_limit(domain, provider, email_count)
            if not domain_check['allowed']:
                return {
                    'allowed': False,
                    'reason': domain_check['reason'],
                    'quotas': {'domain': domain_check}
                }
        
        return {
            'allowed': True,
            'quotas': {
                'email': email_check,
                'domain': domain_check if domain and provider else None
            }
        }


