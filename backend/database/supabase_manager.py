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
        # Auto-create tables if they don't exist
        self.initialize_database()
    
    def connect(self):
        """Get Supabase client (for compatibility)"""
        return self.supabase.client
    
    def initialize_database(self):
        """Initialize database schema (run migrations)"""
        try:
            from database.supabase_schema import SupabaseSchema
            schema = SupabaseSchema(self.supabase)
            
            # Try to create tables
            print("Initializing Supabase database schema...")
            result = schema.create_all_tables()
            
            if result:
                print("✓ Supabase schema initialized")
            else:
                print("⚠️  Supabase tables may need to be created manually")
                print("   Run supabase_migration.sql in Supabase SQL Editor")
                # Still return True to allow app to continue
                return True
        except Exception as e:
            print(f"⚠️  Warning: Could not auto-create tables: {e}")
            import traceback
            traceback.print_exc()
            print("   Please run supabase_migration.sql in Supabase SQL Editor")
            # Return True to allow app to continue
            return True
    
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
        result = self.supabase.client.table('campaigns').insert(data).execute()
        return result.data[0]['id'] if result.data and len(result.data) > 0 else None
    
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
            self.supabase.client.table('leads').update({
                'name': name,
                'company_name': company_name,
                'domain': domain,
                'title': title,
                'follow_up_count': follow_up_count
            }).eq('id', lead['id']).execute()
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
        result = self.supabase.client.table('leads').insert(data).execute()
        return result.data[0]['id'] if result.data and len(result.data) > 0 else None
    
    def get_leads(self, verified_only: bool = False, company_name: str = None,
                 user_id: int = None) -> List[Dict]:
        """Get leads from database"""
        try:
            # Use Supabase client directly - CORRECT PATTERN: select() first, then eq()
            query = self.supabase.client.table('leads').select('*')
            
            # Apply filters using .eq() after .select()
        if user_id:
                query = query.eq('user_id', user_id)
        if verified_only:
                query = query.eq('is_verified', 1)
            
            # Order by created_at desc
            query = query.order('created_at', desc=True)
            
            # Execute query
            result = query.execute()
            leads = result.data if result.data else []
            
            # Filter by company_name in Python if needed
        if company_name:
                leads = [l for l in leads if company_name.lower() in (l.get('company_name') or '').lower()]
            
            return leads
        except Exception as e:
            print(f"Error getting leads from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_lead_by_id(self, lead_id: int) -> Optional[Dict]:
        """Get a lead by ID"""
        try:
            result = self.supabase.client.table('leads').select('*').eq('id', lead_id).execute()
            return result.data[0] if result.data and len(result.data) > 0 else None
        except Exception as e:
            print(f"Error getting lead by ID from Supabase: {e}")
            return None
            import traceback
            traceback.print_exc()
            raise Exception(f"Supabase query error: {e}")
    
    def update_lead_status(self, lead_id: int, is_verified: int, status: str):
        """Update lead verification status"""
        self.supabase.client.table('leads').update({
            'is_verified': is_verified,
            'verification_status': status,
            'verification_date': datetime.now().isoformat()
        }).eq('id', lead_id).execute()
    
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
                result = self.supabase.client.table('recipients').insert(data).execute()   
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
                       provider_type: str = 'smtp', incoming_protocol: str = 'imap',
                       imap_host: str = None, imap_port: int = 993,
                       pop3_host: str = None, pop3_port: int = 995,
                       pop3_ssl: bool = True, pop3_leave_on_server: bool = True,
                       save_to_sent: bool = True, **kwargs) -> int:
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
            'incoming_protocol': incoming_protocol,
            'imap_host': imap_host,
            'imap_port': imap_port,
            'pop3_host': pop3_host,
            'pop3_port': pop3_port,
            'pop3_ssl': 1 if pop3_ssl else 0,
            'pop3_leave_on_server': 1 if pop3_leave_on_server else 0,
            'save_to_sent': 1 if save_to_sent else 0,
            'is_active': 1,
            'is_default': 0,
            'daily_sent_count': 0,
            'warmup_stage': 0,
            'warmup_emails_sent': 0
        }
        data.update(kwargs)
        result = self.supabase.client.table('smtp_servers').insert(data).execute()
        return result.data[0]['id'] if result.data and len(result.data) > 0 else None
    
    def get_smtp_servers(self, active_only: bool = True, user_id: int = None) -> List[Dict]:
        """Get SMTP servers"""
        try:
            query = self.supabase.client.table('smtp_servers').select('*')
        if user_id:
                query = query.eq('user_id', user_id)
        if active_only:
                query = query.eq('is_active', 1)
            query = query.order('is_default', desc=True).order('created_at', desc=False)
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting SMTP servers from Supabase: {e}")
            return []
    
    def get_default_smtp_server(self) -> Optional[Dict]:
        """Get default SMTP server"""
        try:
            # Get default active server
            result = self.supabase.client.table('smtp_servers').select('*').eq('is_default', 1).eq('is_active', 1).limit(1).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                # Ensure password is properly decoded
                if 'password' in server and server['password']:
                    password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
                return server
            # Fallback to first active server
            result = self.supabase.client.table('smtp_servers').select('*').eq('is_active', 1).limit(1).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                # Ensure password is properly decoded
                if 'password' in server and server['password']:
                    password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
                return server
            return None
        except Exception as e:
            print(f"Error getting default SMTP server from Supabase: {e}")
            return None
    
    def update_smtp_server(self, server_id: int, data: Dict):
        """Update SMTP server"""
        self.supabase.client.table('smtp_servers').update(data).eq('id', server_id).execute()
    
    # Email queue methods
    def add_to_queue(self, campaign_id: int, recipient_id: int, smtp_server_id: int):
        """Add email to queue"""
        data = {
            'campaign_id': campaign_id,
            'recipient_id': recipient_id,
            'smtp_server_id': smtp_server_id,
            'status': 'pending'
        }
        result = self.supabase.client.table('email_queue').insert(data).execute()   
    
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
        self.supabase.client.table('email_queue').update(data).eq('id', queue_id).execute()
    
    # Template methods
    def get_templates(self, category: str = None) -> List[Dict]:
        """Get templates"""
        try:
            query = self.supabase.client.table('templates').select('*')
            if category:
                query = query.eq('category', category)
            query = query.order('created_at', desc=True)
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting templates from Supabase: {e}")
            return []
    
    def save_template(self, name: str, category: str, html_content: str) -> int:
        """Save template"""
        try:
            result = self.supabase.client.table('templates').insert({
                'name': name,
                'category': category,
                'html_content': html_content
            }).execute()
            return result.data[0]['id'] if result.data and len(result.data) > 0 else None
        except Exception as e:
            print(f"Error saving template to Supabase: {e}")
            return None
    
    # Lead scraping jobs methods
    def create_scraping_job(self, icp_description: str, user_id: int = None) -> int:
        """Create a new scraping job"""
        data = {
            'icp_description': icp_description,
            'status': 'running',
            'user_id': user_id,
            'current_step': 'Starting...',
            'progress_percent': 0
        }
        result = self.supabase.client.table('lead_scraping_jobs').insert(data).execute()
        return result.data[0]['id'] if result.data and len(result.data) > 0 else None
    
    def update_scraping_job(self, job_id: int, **kwargs) -> bool:
        """Update scraping job"""
        try:
            # Convert datetime to string if needed
            data = {}
            for key, value in kwargs.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                elif isinstance(value, date):
                    data[key] = value.isoformat()
                else:
                    data[key] = value
            
            self.supabase.client.table('lead_scraping_jobs').update(data).eq('id', job_id).execute()
            return True
        except Exception as e:
            print(f"Error updating scraping job: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_scraping_job(self, job_id: int) -> Dict:
        """Get scraping job by ID"""
        result = self.supabase.client.table('lead_scraping_jobs').select('*').eq('id', job_id).execute()
        return result.data[0] if result.data and len(result.data) > 0 else None
    
    def get_scraping_job_user_id(self, job_id: int) -> int:
        """Get user_id from scraping job"""
        result = self.supabase.client.table('lead_scraping_jobs').select('user_id').eq('id', job_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0].get('user_id')
        return None
    
    def get_recent_leads_by_source(self, source: str, limit: int = 100) -> List[Dict]:
        """Get recent leads by source"""
        result = self.supabase.client.table('leads').select('id').eq('source', source).order('id', desc=True).limit(limit).execute()
        return result.data if result.data else []
    
    def get_scraping_jobs(self, user_id: int = None) -> List[Dict]:
        """Get all scraping jobs"""
        try:
            query = self.supabase.client.table('lead_scraping_jobs').select('*')
            if user_id:
                query = query.eq('user_id', user_id)
            query = query.order('created_at', desc=True)
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting scraping jobs from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_email_responses(self, hot_leads_only: bool = False) -> List[Dict]:
        """Get email responses"""
        try:
            query = self.supabase.client.table('email_responses').select('*')
            if hot_leads_only:
                query = query.eq('is_hot_lead', 1)
            query = query.order('created_at', desc=True)
            result = query.execute()
            responses = result.data if result.data else []
            
            # Enrich with sent_email data
            for response in responses:
                if response.get('sent_email_id'):
                    sent_email = self.supabase.client.table('sent_emails').select('subject,sent_at').eq('id', response['sent_email_id']).execute()
                    if sent_email.data and len(sent_email.data) > 0:
                        response['original_subject'] = sent_email.data[0].get('subject')
                        response['sent_at'] = sent_email.data[0].get('sent_at')
            
            return responses
        except Exception as e:
            print(f"Error getting email responses from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_follow_ups_needed(self) -> List[Dict]:
        """Get emails that need follow-ups"""
        try:
            from datetime import datetime
            # Get responses that need follow-ups
            query = self.supabase.client.table('email_responses').select('*').eq('follow_up_needed', 1)
            result = query.execute()
            responses = result.data if result.data else []
            
            # Filter by follow_up_date and enrich with sent_email and recipient data
            follow_ups = []
            now = datetime.now()
            
            for response in responses:
                follow_up_date = response.get('follow_up_date')
                if not follow_up_date or (isinstance(follow_up_date, str) and datetime.fromisoformat(follow_up_date.replace('Z', '+00:00')) <= now):
                    # Get sent_email data
                    if response.get('sent_email_id'):
                        sent_email = self.supabase.client.table('sent_emails').select('recipient_email,subject,sent_at').eq('id', response['sent_email_id']).execute()
                        if sent_email.data and len(sent_email.data) > 0:
                            response['recipient_email'] = sent_email.data[0].get('recipient_email')
                            response['subject'] = sent_email.data[0].get('subject')
                            response['sent_at'] = sent_email.data[0].get('sent_at')
                            
                            # Get recipient data
                            recipient_email = response.get('recipient_email')
                            if recipient_email:
                                recipient = self.supabase.client.table('recipients').select('first_name,last_name,company').eq('email', recipient_email).limit(1).execute()
                                if recipient.data and len(recipient.data) > 0:
                                    rec = recipient.data[0]
                                    response['name'] = f"{rec.get('first_name', '')} {rec.get('last_name', '')}".strip()
                                    response['company'] = rec.get('company')
                            
                            follow_ups.append(response)
            
            # Sort by follow_up_date
            follow_ups.sort(key=lambda x: x.get('follow_up_date') or '')
            return follow_ups
        except Exception as e:
            print(f"Error getting follow-ups needed from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
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

