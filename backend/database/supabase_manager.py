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
        """Get database connection (for compatibility with SQLite code)"""
        # Return a compatibility wrapper that provides cursor-like interface
        return self
    
    def cursor(self):
        """Get cursor (for compatibility) - returns self for method chaining"""
        return self
    
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
    
    def _check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in Supabase"""
        try:
            # Try a simple select query - if table doesn't exist, it will raise an error
            self.supabase.client.table(table_name).select('id').limit(1).execute()
            return True
        except Exception as e:
            error_msg = str(e)
            if 'PGRST205' in error_msg or 'Could not find the table' in error_msg:
                return False
            # Other errors might mean table exists but has no data or permission issue
            return True
    
    def _ensure_table_exists(self, table_name: str, operation: str = "operation"):
        """Ensure table exists, raise helpful error if not"""
        if not self._check_table_exists(table_name):
            error_msg = f"""
❌ ERROR: Table '{table_name}' does not exist in Supabase!

To fix this:
1. Open your Supabase Dashboard
2. Go to SQL Editor
3. Copy and paste the contents of supabase_migration.sql
4. Run the migration script
5. Wait a few seconds for PostgREST to refresh its schema cache

The migration script will create all required tables including:
- campaigns
- email_queue
- recipients
- smtp_servers
- sent_emails
- And all other tables

After running the migration, try your {operation} again.
"""
            raise Exception(error_msg)
    
    # User methods
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        result = self.supabase.select('users', {'id': user_id}, limit=1)
        return result[0] if result else None
    
    # Campaign methods
    def create_campaign(self, name: str, subject: str, sender_name: str,
                       sender_email: str, reply_to: str = None, html_content: str = "",
                       template_id: int = None, use_personalization: bool = False,
                       user_id: int = None, personalization_prompt: str = None) -> int:
        """Create a new email campaign"""
        # Ensure campaigns table exists
        self._ensure_table_exists('campaigns', 'campaign creation')
        
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
            'status': 'draft',
            'personalization_prompt': personalization_prompt
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
        """Add a single lead with deduplication (removes duplicate unverified leads)"""
        email_lower = email.lower().strip()
        if not email_lower:
            return None
        
        # Check if lead exists
        existing_result = self.supabase.client.table('leads').select('*').eq('email', email_lower).eq('user_id', user_id).execute()
        existing_leads = existing_result.data if existing_result.data else []
        
        # Filter: Keep verified leads, remove duplicate unverified leads
        verified_leads = [l for l in existing_leads if l.get('is_verified', 0) == 1]
        unverified_leads = [l for l in existing_leads if l.get('is_verified', 0) == 0]
        
        if verified_leads:
            # If verified lead exists, update it (don't create duplicate)
            lead = verified_leads[0]
            self.supabase.client.table('leads').update({
                'name': name,
                'company_name': company_name,
                'domain': domain,
                'title': title
            }).eq('id', lead['id']).execute()
            return lead['id']
        
        if unverified_leads:
            # Remove duplicate unverified leads (keep only the first one)
            if len(unverified_leads) > 1:
                # Delete all but the first
                ids_to_delete = [l['id'] for l in unverified_leads[1:]]
                for lead_id in ids_to_delete:
                    try:
                        self.supabase.client.table('leads').delete().eq('id', lead_id).execute()
                    except:
                        pass
                print(f"Removed {len(ids_to_delete)} duplicate unverified leads for {email_lower}")
            
            # Update the remaining unverified lead
            lead = unverified_leads[0]
            follow_up_count = (lead.get('follow_up_count') or 0) + 1
            self.supabase.client.table('leads').update({
                'name': name,
                'company_name': company_name,
                'domain': domain,
                'title': title,
                'follow_up_count': follow_up_count
            }).eq('id', lead['id']).execute()
            return lead['id']
        
        # Insert new lead (no duplicates found)
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
            
            # Ensure leads is a list (handle None case)
            if leads is None:
                leads = []
            
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
        """Add recipients with proper deduplication - only fills NULL/empty values"""
        count = 0
        updated_count = 0
        skipped = 0
        
        for recipient in recipients:
            try:
                email = recipient.get('email', '').lower().strip()
                if not email:
                    continue
                
                # Check if recipient already exists (deduplication by email + user_id)
                existing_result = self.supabase.client.table('recipients').select('*').eq('email', email).eq('user_id', user_id).execute()
                
                if existing_result.data and len(existing_result.data) > 0:
                    # Update existing recipient - only fill NULL/empty values, don't overwrite existing
                    existing = existing_result.data[0]
                    existing_id = existing['id']
                    
                    # Build update dict - only include fields that are not NULL/empty in new data
                    # and the existing field is NULL/empty
                    update_data = {}
                    
                    new_first_name = recipient.get('first_name', '').strip() if recipient.get('first_name') else None
                    if new_first_name and (not existing.get('first_name') or existing.get('first_name') == ''):
                        update_data['first_name'] = new_first_name
                    
                    new_last_name = recipient.get('last_name', '').strip() if recipient.get('last_name') else None
                    if new_last_name and (not existing.get('last_name') or existing.get('last_name') == ''):
                        update_data['last_name'] = new_last_name
                    
                    new_company = (recipient.get('company', '') or recipient.get('company_name', '')).strip()
                    if new_company and (not existing.get('company') or existing.get('company') == ''):
                        update_data['company'] = new_company
                    
                    new_city = recipient.get('city', '').strip() if recipient.get('city') else None
                    if new_city and (not existing.get('city') or existing.get('city') == ''):
                        update_data['city'] = new_city
                    
                    new_phone = recipient.get('phone', '').strip() if recipient.get('phone') else None
                    if new_phone and (not existing.get('phone') or existing.get('phone') == ''):
                        update_data['phone'] = new_phone
                    
                    new_list_name = recipient.get('list_name', 'default').strip()
                    if new_list_name and new_list_name != 'default' and (not existing.get('list_name') or existing.get('list_name') == 'default'):
                        update_data['list_name'] = new_list_name
                    
                    # Only update if there are fields to update
                    if update_data:
                        self.supabase.client.table('recipients').update(update_data).eq('id', existing_id).execute()
                        updated_count += 1
                    else:
                        skipped += 1
                    continue
                
                # Insert new recipient
                data = {
                    'email': email,
                    'first_name': recipient.get('first_name', ''),
                    'last_name': recipient.get('last_name', ''),
                    'company': recipient.get('company', '') or recipient.get('company_name', ''),
                    'city': recipient.get('city', ''),
                    'phone': recipient.get('phone', ''),
                    'list_name': recipient.get('list_name', 'default'),
                    'user_id': user_id,
                    'is_verified': recipient.get('is_verified', 0),
                    'is_unsubscribed': 0
                }
                result = self.supabase.client.table('recipients').insert(data).execute()
                if result.data:
                    count += 1
            except Exception as e:
                # Duplicate or error, skip
                print(f"Error adding recipient {recipient.get('email', 'unknown')}: {e}")
                skipped += 1
                continue
        
        print(f"Added {count} new recipients, updated {updated_count} existing recipients, skipped {skipped} duplicates")
        return count + updated_count
    
    def get_recipients(self, list_name: str = None, unsubscribed_only: bool = False,
                      user_id: int = None) -> List[Dict]:
        """Get recipients"""
        try:
            query = self.supabase.client.table('recipients').select('*')
            
            if user_id:
                query = query.eq('user_id', user_id)
            if list_name:
                query = query.eq('list_name', list_name)
            if not unsubscribed_only:
                query = query.eq('is_unsubscribed', 0)
            
            query = query.order('created_at', desc=True)
            result = query.execute()
            
            # Ensure result is a list (handle None case)
            recipients = result.data if result.data else []
            if recipients is None:
                recipients = []
            
            return recipients
        except Exception as e:
            print(f"Error getting recipients from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    # SMTP methods
    def add_smtp_server(self, name: str, host: str, port: int, username: str,
                       password: str, use_tls: bool = True, use_ssl: bool = False,
                       max_per_hour: int = 100, user_id: int = None,
                       provider_type: str = 'smtp', incoming_protocol: str = 'imap',
                       imap_host: str = None, imap_port: int = 993,
                       pop3_host: str = None, pop3_port: int = 995,
                       pop3_ssl: bool = True, pop3_leave_on_server: bool = True,
                       save_to_sent: bool = True, **kwargs) -> int:
        """Add SMTP server with encrypted password"""
        from core.encryption import get_encryption_manager
        encryptor = get_encryption_manager()
        
        # Encrypt password
        encrypted_password = encryptor.encrypt(password) if password else ''
        
        # Encrypt OAuth tokens if provided
        oauth_token = kwargs.get('oauth_token')
        oauth_refresh_token = kwargs.get('oauth_refresh_token')
        encrypted_oauth = encryptor.encrypt(oauth_token) if oauth_token else None
        encrypted_refresh = encryptor.encrypt(oauth_refresh_token) if oauth_refresh_token else None
        
        data = {
            'name': name,
            'host': host,
            'port': port,
            'username': username,
            'password': encrypted_password,  # Encrypted
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
        
        # Add encrypted OAuth tokens if provided
        if encrypted_oauth:
            data['oauth_token'] = encrypted_oauth
        if encrypted_refresh:
            data['oauth_refresh_token'] = encrypted_refresh
        
        data.update({k: v for k, v in kwargs.items() if k not in ['oauth_token', 'oauth_refresh_token']})
        result = self.supabase.client.table('smtp_servers').insert(data).execute()
        return result.data[0]['id'] if result.data and len(result.data) > 0 else None
    
    def get_smtp_servers(self, active_only: bool = True, user_id: int = None) -> List[Dict]:
        """Get SMTP servers with decrypted passwords"""
        try:
            from core.encryption import get_encryption_manager
            encryptor = get_encryption_manager()
            
            query = self.supabase.client.table('smtp_servers').select('*')
            if user_id:
                query = query.eq('user_id', user_id)
            if active_only:
                query = query.eq('is_active', 1)
            query = query.order('is_default', desc=True).order('created_at', desc=False)
            result = query.execute()
            
            servers = result.data if result.data else []
            
            # Decrypt passwords
            for server in servers:
                if server.get('password'):
                    try:
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        pass  # If decryption fails, keep as-is (might be plaintext from old data)
                
                # Decrypt OAuth tokens if present
                if server.get('oauth_token'):
                    try:
                        server['oauth_token'] = encryptor.decrypt(server['oauth_token'])
                    except:
                        pass
                
                if server.get('oauth_refresh_token'):
                    try:
                        server['oauth_refresh_token'] = encryptor.decrypt(server['oauth_refresh_token'])
                    except:
                        pass
            
            return servers
        except Exception as e:
            print(f"Error getting SMTP servers from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_default_smtp_server(self) -> Optional[Dict]:
        """Get default SMTP server with decrypted password"""
        try:
            from core.encryption import get_encryption_manager
            encryptor = get_encryption_manager()
            
            # Get default active server
            result = self.supabase.client.table('smtp_servers').select('*').eq('is_default', 1).eq('is_active', 1).limit(1).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                # Decrypt password
                if server.get('password'):
                    try:
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        pass  # If decryption fails, keep as-is
                return server
            # Fallback to first active server
            result = self.supabase.client.table('smtp_servers').select('*').eq('is_active', 1).limit(1).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                # Decrypt password
                if server.get('password'):
                    try:
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        pass  # If decryption fails, keep as-is
                return server
            return None
        except Exception as e:
            print(f"Error getting default SMTP server from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def update_smtp_server(self, server_id: int, data: Dict):
        """Update SMTP server with encrypted password if provided"""
        from core.encryption import get_encryption_manager
        encryptor = get_encryption_manager()
        
        # Encrypt password if provided
        if 'password' in data and data['password']:
            data['password'] = encryptor.encrypt(data['password'])
        
        # Encrypt OAuth tokens if provided
        if 'oauth_token' in data and data['oauth_token']:
            data['oauth_token'] = encryptor.encrypt(data['oauth_token'])
        
        if 'oauth_refresh_token' in data and data['oauth_refresh_token']:
            data['oauth_refresh_token'] = encryptor.encrypt(data['oauth_refresh_token'])
        
        self.supabase.client.table('smtp_servers').update(data).eq('id', server_id).execute()
    
    # Email queue methods
    def add_to_queue(self, campaign_id: int, recipient_ids: List[int], smtp_server_id: int = None, 
                     emails_per_server: int = 20, selected_smtp_servers: List[int] = None) -> int:
        """
        Add emails to sending queue with round-robin SMTP distribution
        
        Args:
            campaign_id: Campaign ID
            recipient_ids: List of recipient IDs
            smtp_server_id: Optional single SMTP server ID (if None, uses round-robin)
            emails_per_server: Number of emails per SMTP server (default: 20)
            selected_smtp_servers: Optional list of selected SMTP server IDs (if provided, uses only these)
        
        Returns:
            Number of emails added to queue
        """
        added_count = 0
        
        # Get SMTP servers
        if smtp_server_id:
            smtp_servers = [smtp_server_id]
        elif selected_smtp_servers and len(selected_smtp_servers) > 0:
            # Get active servers from selection
            result = self.supabase.client.table('smtp_servers').select('id').in_('id', selected_smtp_servers).eq('is_active', 1).execute()
            smtp_servers = [s['id'] for s in (result.data or [])]
            if not smtp_servers:
                print("⚠ No active SMTP servers found from selection!")
                return 0
        else:
            # Get all active SMTP servers
            result = self.supabase.client.table('smtp_servers').select('id').eq('is_active', 1).execute()
            smtp_servers = [s['id'] for s in (result.data or [])]
            if not smtp_servers:
                print("⚠ No active SMTP servers found!")
                return 0
        
        # Calculate total emails to send
        total_emails_to_send = emails_per_server * len(smtp_servers)
        recipient_ids_to_process = recipient_ids[:total_emails_to_send]
        
        print(f"📧 Distributing {len(recipient_ids_to_process)} emails across {len(smtp_servers)} SMTP servers")
        
        # Get recipients to check unsubscribed status
        recipient_result = self.supabase.client.table('recipients').select('id, is_unsubscribed').in_('id', recipient_ids_to_process).execute()
        recipients_dict = {r['id']: r for r in (recipient_result.data or [])}
        
        # Distribute emails in round-robin fashion
        for index, recipient_id in enumerate(recipient_ids_to_process):
            try:
                # Check if recipient is unsubscribed
                recipient = recipients_dict.get(recipient_id)
                if recipient and recipient.get('is_unsubscribed'):
                    continue  # Skip unsubscribed
                
                # Check if already in queue
                existing = self.supabase.client.table('email_queue').select('id').eq('campaign_id', campaign_id).eq('recipient_id', recipient_id).in_('status', ['pending', 'processing']).execute()
                if existing.data and len(existing.data) > 0:
                    continue  # Already queued
                
                # Add to campaign_recipients (many-to-many)
                try:
                    self.supabase.client.table('campaign_recipients').insert({
                        'campaign_id': campaign_id,
                        'recipient_id': recipient_id,
                        'status': 'pending'
                    }).execute()
                except:
                    pass  # Already exists, continue
                
                # Calculate which SMTP server to use (round-robin)
                server_index = (index // emails_per_server) % len(smtp_servers)
                assigned_smtp_id = smtp_servers[server_index]
                
                # Add to queue
                self.supabase.client.table('email_queue').insert({
                    'campaign_id': campaign_id,
                    'recipient_id': recipient_id,
                    'smtp_server_id': assigned_smtp_id,
                    'status': 'pending'
                }).execute()
                
                added_count += 1
            except Exception as e:
                print(f"Error adding recipient {recipient_id} to queue: {e}")
                continue
        
        print(f"✅ Added {added_count} emails to queue for campaign {campaign_id}")
        return added_count   
    
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
    def create_scraping_job(self, icp_description: str, user_id: int = None, lead_type: str = 'B2B') -> int:
        """Create a new scraping job"""
        data = {
            'icp_description': icp_description,
            'lead_type': lead_type,
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
            # Select all columns, but handle case where is_hot_lead might not exist
            query = self.supabase.client.table('email_responses').select('*')
            
            # Only filter by is_hot_lead if the column exists and hot_leads_only is True
            if hot_leads_only:
                try:
                    # Try to filter by is_hot_lead
                    query = query.eq('is_hot_lead', 1)
                except Exception as filter_error:
                    # If column doesn't exist, log warning and return all responses
                    # The migration should add this column, but handle gracefully
                    print(f"⚠ Warning: is_hot_lead column may not exist. Filtering disabled: {filter_error}")
                    # Continue without filtering - will return all responses
            
            query = query.order('created_at', desc=True)
            result = query.execute()
            responses = result.data if result.data else []
            
            # If hot_leads_only was requested but column doesn't exist, filter in Python
            if hot_leads_only and responses:
                # Check if any response has is_hot_lead field
                has_hot_lead_column = any('is_hot_lead' in r for r in responses)
                if not has_hot_lead_column:
                    # Column doesn't exist - can't filter, return empty or all
                    print("⚠ Warning: is_hot_lead column not found in responses. Cannot filter hot leads.")
                    return []
                else:
                    # Filter in Python as fallback
                    responses = [r for r in responses if r.get('is_hot_lead', 0) == 1]
            
            # Enrich with sent_email data
            for response in responses:
                # Try sent_email_id first, then fallback to campaign_id/recipient_id
                sent_email_id = response.get('sent_email_id')
                if sent_email_id:
                    try:
                        sent_email = self.supabase.client.table('sent_emails').select('subject,sent_at,recipient_email').eq('id', sent_email_id).execute()
                        if sent_email.data and len(sent_email.data) > 0:
                            response['original_subject'] = sent_email.data[0].get('subject')
                            response['sent_at'] = sent_email.data[0].get('sent_at')
                            if not response.get('recipient_email'):
                                response['recipient_email'] = sent_email.data[0].get('recipient_email')
                    except Exception as enrich_error:
                        print(f"⚠ Could not enrich response with sent_email data: {enrich_error}")
                
                # Also try to get from campaign/recipient if sent_email_id not available
                if not response.get('original_subject') and response.get('campaign_id'):
                    try:
                        campaign = self.supabase.client.table('campaigns').select('subject').eq('id', response['campaign_id']).execute()
                        if campaign.data and len(campaign.data) > 0:
                            response['original_subject'] = campaign.data[0].get('subject')
                    except:
                        pass
                
                # Ensure response_content exists (might be stored as 'body' in old schema)
                if not response.get('response_content') and response.get('body'):
                    response['response_content'] = response.get('body')
            
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
    
    # Settings methods
    def get_setting(self, key: str, default: str = None) -> str:
        """Get a setting value (global setting, no user_id)"""
        try:
            # Get all settings with this key (both global and user-specific)
            result = self.supabase.client.table('app_settings').select('setting_value, user_id').eq('setting_key', key).execute()
            if result.data:
                # Filter for NULL user_id (global settings) in Python
                for setting in result.data:
                    if setting.get('user_id') is None or setting.get('user_id') == 'None':
                        return setting.get('setting_value', default)
            return default
        except Exception as e:
            print(f"Error getting setting from Supabase: {e}")
            return default
    
    def set_setting(self, key: str, value: str):
        """Set a setting value (global setting, no user_id)"""
        try:
            # Get all settings with this key and find the one with NULL user_id
            result = self.supabase.client.table('app_settings').select('id, user_id').eq('setting_key', key).execute()
            
            # Find setting with NULL user_id
            existing_id = None
            if result.data:
                for setting in result.data:
                    if setting.get('user_id') is None:
                        existing_id = setting['id']
                        break
            
            if existing_id:
                # Update existing
                self.supabase.client.table('app_settings').update({
                    'setting_value': str(value),
                    'updated_at': datetime.now().isoformat()
                }).eq('id', existing_id).execute()
            else:
                # Insert new (upsert with user_id = NULL)
                # Use upsert to handle unique constraint
                self.supabase.client.table('app_settings').upsert({
                    'setting_key': key,
                    'setting_value': str(value),
                    'user_id': None,
                    'updated_at': datetime.now().isoformat()
                }, on_conflict='setting_key,user_id').execute()
        except Exception as e:
            print(f"Error setting setting in Supabase: {e}")
            import traceback
            traceback.print_exc()
    
    def get_email_delay(self) -> int:
        """Get email delay setting in seconds"""
        delay = self.get_setting('email_delay', '30')
        try:
            return int(delay)
        except:
            return 30
    
    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        try:
            # Get pending emails count
            pending_result = self.supabase.client.table('email_queue').select('id', count='exact').eq('status', 'pending').execute()
            pending = pending_result.count if pending_result.count else 0
            
            # Get sent today count (IST date)
            from datetime import date, timedelta
            today = date.today().isoformat()
            tomorrow = (date.today() + timedelta(days=1)).isoformat()
            sent_result = self.supabase.client.table('email_queue').select('id', count='exact').eq('status', 'sent').gte('sent_at', today).lt('sent_at', tomorrow).execute()
            sent_today = sent_result.count if sent_result.count else 0
            
            return {
                'pending': pending,
                'sent_today': sent_today
            }
        except Exception as e:
            print(f"Error getting queue stats from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return {'pending': 0, 'sent_today': 0}
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Get daily statistics"""
        try:
            from datetime import date as date_class
            if not date:
                date = date_class.today().isoformat()
            
            # Get stats for the date
            result = self.supabase.client.table('daily_stats').select('*').eq('date', date).execute()
            
            if result.data and len(result.data) > 0:
                stats = result.data[0]
                return {
                    'emails_sent': stats.get('emails_sent', 0) or 0,
                    'emails_delivered': stats.get('emails_delivered', 0) or 0,
                    'emails_bounced': stats.get('emails_bounced', 0) or 0,
                    'emails_opened': stats.get('emails_opened', 0) or 0,
                    'emails_clicked': stats.get('emails_clicked', 0) or 0,
                    'spam_reports': stats.get('spam_reports', 0) or 0,
                    'unsubscribes': stats.get('emails_unsubscribed', 0) or 0
                }
            else:
                return {
                    'emails_sent': 0,
                    'emails_delivered': 0,
                    'emails_bounced': 0,
                    'emails_opened': 0,
                    'emails_clicked': 0,
                    'spam_reports': 0,
                    'unsubscribes': 0
                }
        except Exception as e:
            print(f"Error getting daily stats from Supabase: {e}")
            import traceback
            traceback.print_exc()
            return {
                'emails_sent': 0,
                'emails_delivered': 0,
                'emails_bounced': 0,
                'emails_opened': 0,
                'emails_clicked': 0,
                'spam_reports': 0,
                'unsubscribes': 0
            }
    
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

