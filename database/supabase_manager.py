"""
Supabase Database Manager for ANAGHA SOLUTION
PostgreSQL-based database using Supabase
"""

from typing import List, Dict, Optional
from core.supabase_client import SupabaseClient
from datetime import datetime, date
import json

class SupabaseDatabaseManager:
    """Database manager using Supabase PostgreSQL"""
    
    def __init__(self, supabase_url: str = None, supabase_key: str = None):
        """Initialize Supabase database manager"""
        self.supabase = SupabaseClient(supabase_url, supabase_key)
        self.use_supabase = True
    
    def connect(self):
        """Get Supabase client (for compatibility)"""
        return self.supabase.client
    
    def initialize_database(self):
        """Initialize database schema (run migrations)"""
        # Supabase schema should be created via migrations
        # This is a placeholder - migrations should be run separately
        pass
    
    # User methods
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        result = self.supabase.select('users', {'id': user_id}, limit=1)
        return result[0] if result else None
    
    # Campaign methods
    def create_campaign(self, name: str, subject: str, sender_name: str,
                       sender_email: str, reply_to: str = None, html_content: str = "",
                       template_id: int = None, use_personalization: bool = False,
                       user_id: int = None) -> int:
        """Create a new email campaign"""
        data = {
            'name': name,
            'subject': subject,
            'sender_name': sender_name,
            'sender_email': sender_email,
            'reply_to': reply_to,
            'html_content': html_content,
            'template_id': template_id,
            'use_personalization': 1 if use_personalization else 0,
            'user_id': user_id,
            'status': 'draft'
        }
        result = self.supabase.insert('campaigns', data)
        return result.get('id')
    
    def get_campaigns(self, user_id: int = None) -> List[Dict]:
        """Get all campaigns"""
        filters = {'user_id': user_id} if user_id else None
        return self.supabase.select('campaigns', filters=filters, order_by='created_at.desc')
    
    # Lead methods
    def add_lead(self, name: str, company_name: str, domain: str, email: str,
                 title: str = None, source: str = 'manual', user_id: int = None) -> int:
        """Add a single lead with deduplication"""
        email_lower = email.lower().strip()
        
        # Check if lead exists
        filters = {'email': email_lower}
        if user_id:
            filters['user_id'] = user_id
        
        existing = self.supabase.select('leads', filters=filters, limit=1)
        
        if existing:
            # Update existing lead
            lead = existing[0]
            follow_up_count = (lead.get('follow_up_count') or 0) + 1
            self.supabase.update('leads', {'id': lead['id']}, {
                'name': name,
                'company_name': company_name,
                'domain': domain,
                'title': title,
                'follow_up_count': follow_up_count
            })
            return lead['id']
        
        # Insert new lead
        data = {
            'name': name,
            'company_name': company_name,
            'domain': domain,
            'email': email_lower,
            'title': title,
            'source': source,
            'user_id': user_id,
            'follow_up_count': 0,
            'is_verified': 0,
            'verification_status': 'pending'
        }
        result = self.supabase.insert('leads', data)
        return result.get('id')
    
    def get_leads(self, verified_only: bool = False, company_name: str = None,
                 user_id: int = None) -> List[Dict]:
        """Get leads from database"""
        filters = {}
        if user_id:
            filters['user_id'] = user_id
        if verified_only:
            filters['is_verified'] = 1
        if company_name:
            # Supabase doesn't support LIKE directly, use ilike
            # For now, filter in Python
            leads = self.supabase.select('leads', filters=filters, order_by='created_at.desc')
            return [l for l in leads if company_name.lower() in (l.get('company_name') or '').lower()]
        
        return self.supabase.select('leads', filters=filters, order_by='created_at.desc')
    
    def update_lead_status(self, lead_id: int, is_verified: int, status: str):
        """Update lead verification status"""
        self.supabase.update('leads', {'id': lead_id}, {
            'is_verified': is_verified,
            'verification_status': status,
            'verification_date': datetime.now().isoformat()
        })
    
    # Recipient methods
    def add_recipients(self, recipients: List[Dict], user_id: int = None) -> int:
        """Add recipients"""
        count = 0
        for recipient in recipients:
            try:
                email = recipient.get('email', '').lower().strip()
                data = {
                    'email': email,
                    'first_name': recipient.get('first_name', ''),
                    'last_name': recipient.get('last_name', ''),
                    'company': recipient.get('company', ''),
                    'city': recipient.get('city', ''),
                    'phone': recipient.get('phone', ''),
                    'list_name': recipient.get('list_name', 'default'),
                    'user_id': user_id,
                    'is_verified': 0,
                    'is_unsubscribed': 0
                }
                self.supabase.insert('recipients', data)
                count += 1
            except Exception as e:
                # Duplicate or error, skip
                continue
        return count
    
    def get_recipients(self, list_name: str = None, unsubscribed_only: bool = False,
                      user_id: int = None) -> List[Dict]:
        """Get recipients"""
        filters = {}
        if user_id:
            filters['user_id'] = user_id
        if list_name:
            filters['list_name'] = list_name
        if not unsubscribed_only:
            filters['is_unsubscribed'] = 0
        
        return self.supabase.select('recipients', filters=filters, order_by='created_at.desc')
    
    # SMTP methods
    def add_smtp_server(self, name: str, host: str, port: int, username: str,
                       password: str, use_tls: bool = True, use_ssl: bool = False,
                       max_per_hour: int = 100, user_id: int = None,
                       provider_type: str = 'smtp', **kwargs) -> int:
        """Add SMTP server"""
        data = {
            'name': name,
            'host': host,
            'port': port,
            'username': username,
            'password': password,  # Should be encrypted in production
            'use_tls': 1 if use_tls else 0,
            'use_ssl': 1 if use_ssl else 0,
            'max_per_hour': max_per_hour,
            'user_id': user_id,
            'provider_type': provider_type,
            'is_active': 1,
            'is_default': 0,
            'daily_sent_count': 0,
            'warmup_stage': 0,
            'warmup_emails_sent': 0
        }
        data.update(kwargs)
        result = self.supabase.insert('smtp_servers', data)
        return result.get('id')
    
    def get_smtp_servers(self, active_only: bool = True, user_id: int = None) -> List[Dict]:
        """Get SMTP servers"""
        filters = {}
        if user_id:
            filters['user_id'] = user_id
        if active_only:
            filters['is_active'] = 1
        
        return self.supabase.select('smtp_servers', filters=filters, order_by='is_default.desc')
    
    def update_smtp_server(self, server_id: int, data: Dict):
        """Update SMTP server"""
        self.supabase.update('smtp_servers', {'id': server_id}, data)
    
    # Email queue methods
    def add_to_queue(self, campaign_id: int, recipient_id: int, smtp_server_id: int):
        """Add email to queue"""
        data = {
            'campaign_id': campaign_id,
            'recipient_id': recipient_id,
            'smtp_server_id': smtp_server_id,
            'status': 'pending'
        }
        self.supabase.insert('email_queue', data)
    
    def get_next_queue_item(self) -> Optional[Dict]:
        """Get next item from queue"""
        result = self.supabase.select('email_queue', 
                                     {'status': 'pending'}, 
                                     limit=1,
                                     order_by='created_at.asc')
        return result[0] if result else None
    
    def update_queue_status(self, queue_id: int, status: str, error: str = None):
        """Update queue item status"""
        data = {'status': status}
        if status == 'sent':
            data['sent_at'] = datetime.now().isoformat()
        if error:
            data['error_message'] = error
        self.supabase.update('email_queue', {'id': queue_id}, data)
    
    # Compatibility methods for existing code
    def execute(self, query: str, params: tuple = None):
        """Execute query (compatibility method)"""
        # This is a simplified compatibility layer
        # For complex queries, use direct Supabase methods
        raise NotImplementedError("Use Supabase table methods directly")
    
    def commit(self):
        """Commit (no-op for Supabase, auto-commits)"""
        pass
    
    def cursor(self):
        """Get cursor (compatibility)"""
        return self

