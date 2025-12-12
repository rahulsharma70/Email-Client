"""
Email Sending Engine for ANAGHA SOLUTION
Handles multi-threaded email sending with rate limiting
"""

import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, format_datetime
from datetime import datetime, timezone, timedelta
import os
import re
import uuid
import imaplib

# Timezone support for IST (Kolkata)
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo('Asia/Kolkata')
except ImportError:
    # Fallback for Python < 3.9
    try:
        import pytz
        IST = pytz.timezone('Asia/Kolkata')
    except ImportError:
        # If neither is available, we'll use UTC offset (not ideal but works)
        IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Get current datetime in IST (Kolkata) timezone as naive datetime (for database storage)"""
    try:
        if hasattr(IST, 'localize'):
            # pytz timezone - get aware datetime then convert to naive
            ist_aware = datetime.now(IST)
            return ist_aware.replace(tzinfo=None)
        else:
            # zoneinfo timezone - get aware datetime then convert to naive
            ist_aware = datetime.now(IST)
            return ist_aware.replace(tzinfo=None)
    except:
        # Fallback: use UTC and add offset
        from datetime import timedelta
        utc_now = datetime.now(timezone.utc)
        ist_offset = timedelta(hours=5, minutes=30)
        return (utc_now + ist_offset).replace(tzinfo=None)

def get_ist_now_aware():
    """Get current datetime in IST (Kolkata) timezone as timezone-aware datetime"""
    try:
        if hasattr(IST, 'localize'):
            # pytz timezone
            return datetime.now(IST)
        else:
            # zoneinfo timezone
            return datetime.now(IST)
    except:
        # Fallback: use UTC and add offset
        from datetime import timedelta
        utc_now = datetime.now(timezone.utc)
        ist_offset = timedelta(hours=5, minutes=30)
        ist_aware = (utc_now + ist_offset)
        # Create a timezone object for the offset
        return ist_aware.replace(tzinfo=timezone(ist_offset))

class EmailSender:
    def __init__(self, db_manager, interval=30.0, max_threads=1):
        """
        Initialize email sender
        
        Args:
            db_manager: Database manager instance
            interval: Delay in seconds between sending each email (default: 30 seconds)
            max_threads: Number of worker threads (default: 1 for sequential sending)
        """
        self.db = db_manager
        self.interval = interval  # 30 seconds delay between emails
        self.max_threads = max_threads  # Single thread for controlled sending
        self.is_sending = False
        self.is_paused = False  # Pause state
        self.threads = []
        self.lock = threading.Lock()
        
    def start_sending(self):
        """Start sending emails from queue"""
        if self.is_sending:
            print("Email sender is already running")
            return
        
        self.is_sending = True
        print(f"Starting email sender with {self.max_threads} worker threads...")
        
        # Start worker threads
        for i in range(self.max_threads):
            thread = threading.Thread(target=self.worker_thread, daemon=True, name=f"EmailWorker-{i}")
            thread.start()
            self.threads.append(thread)
            print(f"Started worker thread {i+1}/{self.max_threads}")
        
        print("Email sender started successfully")
    
    def stop_sending(self):
        """Stop sending emails"""
        self.is_sending = False
        self.is_paused = False
        print("🛑 Email sending stopped")
    
    def pause_sending(self):
        """Pause sending emails (can be resumed)"""
        self.is_paused = True
        print("⏸️ Email sending paused")
    
    def resume_sending(self):
        """Resume sending emails after pause"""
        self.is_paused = False
        print("▶️ Email sending resumed")
    
    def get_status(self):
        """Get current sending status"""
        if not self.is_sending:
            return 'stopped'
        elif self.is_paused:
            return 'paused'
        else:
            return 'sending'
    
    def worker_thread(self):
        """Worker thread for sending emails"""
        thread_name = threading.current_thread().name
        print(f"Worker thread {thread_name} started")
        while self.is_sending:
            try:
                # Check if paused
                if self.is_paused:
                    print(f"[{thread_name}] Email sending is paused, waiting...")
                    time.sleep(2)
                    continue
                
                # Get next email from queue
                queue_item = self.get_next_queue_item()
                
                if queue_item:
                    print(f"[{thread_name}] Processing email for {queue_item.get('email', 'unknown')}")
                    
                    # Get campaign personalization setting (if not already in queue_item from JOIN)
                    if 'use_personalization' not in queue_item:
                        # Check if using Supabase FIRST before trying to use SQLite methods
                        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
                        
                        if use_supabase:
                            result = self.db.supabase.client.table('campaigns').select('use_personalization, personalization_prompt, user_id').eq('id', queue_item.get('campaign_id')).execute()
                            if result.data and len(result.data) > 0:
                                camp = result.data[0]
                                queue_item['use_personalization'] = bool(camp.get('use_personalization', 0))
                                queue_item['personalization_prompt'] = camp.get('personalization_prompt')
                                queue_item['campaign_user_id'] = camp.get('user_id')
                        else:
                            # SQLite
                            conn = self.db.connect()
                            cursor = conn.cursor()
                            cursor.execute("SELECT use_personalization, personalization_prompt, user_id FROM campaigns WHERE id = ?", (queue_item.get('campaign_id'),))
                            row = cursor.fetchone()
                            if row:
                                queue_item['use_personalization'] = bool(row[0] if row[0] else 0)
                                queue_item['personalization_prompt'] = row[1] if len(row) > 1 else None
                                queue_item['campaign_user_id'] = row[2] if len(row) > 2 else None
                    else:
                        # Convert use_personalization to boolean if it's an integer
                        if isinstance(queue_item.get('use_personalization'), int):
                            queue_item['use_personalization'] = bool(queue_item['use_personalization'])
                    
                    # Send the email
                    self.send_email(queue_item)
                    print(f"[{thread_name}] Waiting {self.interval} seconds before next email...")
                    time.sleep(self.interval)
                else:
                    # No items in queue, wait a bit
                    time.sleep(2)
                    
            except Exception as e:
                import traceback
                print(f"Error in worker thread {thread_name}: {e}")
                print(traceback.format_exc())
                time.sleep(2)
    
    def get_next_queue_item(self):
        """Get next item from email queue - with locking to prevent duplicates"""
        try:
            # Check if using Supabase FIRST before trying to use SQLite methods
            use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
            
            if use_supabase:
                # Supabase: Get pending queue items with joins
                # First, get pending queue items (will filter nulls and inactive SMTP in Python)
                queue_result = self.db.supabase.client.table('email_queue').select(
                    'id, campaign_id, recipient_id, smtp_server_id, status, priority, created_at'
                ).eq('status', 'pending').order('created_at', desc=False).limit(100).execute()
                
                # Filter for non-null smtp_server_id in Python
                pending_queues = []
                if queue_result.data:
                    pending_queues = [q for q in queue_result.data if q.get('smtp_server_id') is not None]
                
                if not pending_queues:
                    return None
                
                # Sort by smtp_server_id, priority desc, created_at
                pending_queues.sort(key=lambda x: (
                    x.get('smtp_server_id', 0),
                    -x.get('priority', 0),
                    x.get('created_at', '')
                ))
                
                # Try to process each queue item until one is successfully locked
                for queue_row in pending_queues:
                    queue_id = queue_row['id']
                    campaign_id = queue_row['campaign_id']
                    recipient_id = queue_row['recipient_id']
                    smtp_server_id = queue_row['smtp_server_id']
                    
                    # Try to mark as processing atomically (use update with filter to prevent race condition)
                    try:
                        update_result = self.db.supabase.client.table('email_queue').update({'status': 'processing'}).eq('id', queue_id).eq('status', 'pending').execute()
                        if not update_result.data or len(update_result.data) == 0:
                            # Another thread already picked this up, try next
                            continue
                    except:
                        # Race condition - another thread got it, try next
                        continue
                    
                    # Get campaign data
                    camp_result = self.db.supabase.client.table('campaigns').select(
                        'name, subject, sender_name, sender_email, reply_to, html_content, use_personalization, personalization_prompt, user_id'
                    ).eq('id', campaign_id).execute()
                    
                    if not camp_result.data or len(camp_result.data) == 0:
                        # Mark as failed and try next
                        self.db.supabase.client.table('email_queue').update({'status': 'failed', 'error_message': 'Campaign not found'}).eq('id', queue_id).execute()
                        continue
                    
                    campaign = camp_result.data[0]
                    
                    # Get recipient data
                    rec_result = self.db.supabase.client.table('recipients').select(
                        'email, first_name, last_name, company, city, is_unsubscribed'
                    ).eq('id', recipient_id).execute()
                    
                    if not rec_result.data or len(rec_result.data) == 0:
                        # Mark as failed and try next
                        self.db.supabase.client.table('email_queue').update({'status': 'failed', 'error_message': 'Recipient not found'}).eq('id', queue_id).execute()
                        continue
                    
                    recipient = rec_result.data[0]
                    
                    # Check if unsubscribed
                    if recipient.get('is_unsubscribed'):
                        self.db.supabase.client.table('email_queue').update({'status': 'skipped', 'error_message': 'Recipient unsubscribed'}).eq('id', queue_id).execute()
                        continue
                    
                    # Get SMTP server data (including IMAP settings for sent folder)
                    smtp_result = self.db.supabase.client.table('smtp_servers').select(
                        'host, port, username, password, use_tls, use_ssl, is_active, imap_host, imap_port, save_to_sent'
                    ).eq('id', smtp_server_id).eq('is_active', 1).execute()
                    
                    # Filter for non-null password in Python
                    smtp_servers_list = []
                    if smtp_result.data:
                        smtp_servers_list = [s for s in smtp_result.data if s.get('password') and s.get('password').strip()]
                    
                    if not smtp_servers_list:
                        # Mark as failed and try next
                        self.db.supabase.client.table('email_queue').update({'status': 'failed', 'error_message': 'SMTP server password missing or inactive'}).eq('id', queue_id).execute()
                        continue
                    
                    smtp_server = smtp_servers_list[0]
                    
                    # CRITICAL: Decrypt password before adding to queue_item
                    password = smtp_server.get('password', '')
                    if password:
                        try:
                            from core.encryption import get_encryption_manager
                            encryptor = get_encryption_manager()
                            try:
                                decrypted = encryptor.decrypt(password)
                                if decrypted:
                                    password = decrypted
                            except:
                                # Password might be plaintext, use as-is
                                pass
                        except Exception as decrypt_error:
                            # Encryption manager not available or password is plaintext
                            pass
                    
                    # Ensure password is a string
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    
                    # Build queue_item dict
                    queue_item = {
                        'queue_id': queue_id,
                        'campaign_id': campaign_id,
                        'recipient_id': recipient_id,
                        'smtp_server_id': smtp_server_id,
                        'campaign_name': campaign.get('name', ''),
                        'subject': campaign.get('subject', ''),
                        'sender_name': campaign.get('sender_name', ''),
                        'sender_email': campaign.get('sender_email', ''),
                        'reply_to': campaign.get('reply_to'),
                        'html_content': campaign.get('html_content', ''),
                        'use_personalization': campaign.get('use_personalization', False),
                        'personalization_prompt': campaign.get('personalization_prompt'),
                        'user_id': campaign.get('user_id'),
                        'email': recipient.get('email', ''),
                        'first_name': recipient.get('first_name', ''),
                        'last_name': recipient.get('last_name', ''),
                        'company': recipient.get('company', ''),
                        'city': recipient.get('city', ''),
                        'is_unsubscribed': recipient.get('is_unsubscribed', False),
                        'host': smtp_server.get('host', ''),
                        'port': smtp_server.get('port', 465),
                        'username': smtp_server.get('username', ''),
                        'password': password,  # Use decrypted password
                        'use_tls': smtp_server.get('use_tls', False),
                        'use_ssl': smtp_server.get('use_ssl', False),
                        'is_active': smtp_server.get('is_active', True),
                        'imap_host': smtp_server.get('imap_host'),  # For saving to sent folder
                        'imap_port': smtp_server.get('imap_port', 993),
                        'save_to_sent': smtp_server.get('save_to_sent', 1)
                    }
                    
                    smtp_username = queue_item.get('username', 'N/A')
                    print(f"[{threading.current_thread().name}] Locked queue item {queue_id} for processing")
                    print(f"   Using SMTP Server ID: {smtp_server_id}, Username: {smtp_username}")
                    
                    return queue_item
                
                # If we get here, none of the queue items could be processed
                return None
            else:
                # SQLite
                conn = self.db.connect()
                cursor = conn.cursor()
                
                # Use a transaction with row-level locking to prevent duplicate processing
                cursor.execute("""
                    SELECT eq.id as queue_id, eq.campaign_id, eq.recipient_id, eq.smtp_server_id,
                           c.name as campaign_name, c.subject, c.sender_name, c.sender_email, 
                           c.reply_to, c.html_content, c.use_personalization, c.personalization_prompt, c.user_id,
                           r.email, r.first_name, r.last_name, r.company, r.city, r.is_unsubscribed,
                           s.host, s.port, s.username, s.password, s.use_tls, s.use_ssl, s.is_active
                    FROM email_queue eq
                    JOIN campaigns c ON eq.campaign_id = c.id
                    JOIN recipients r ON eq.recipient_id = r.id
                    INNER JOIN smtp_servers s ON eq.smtp_server_id = s.id
                    WHERE eq.status = 'pending' 
                      AND r.is_unsubscribed = 0 
                      AND s.is_active = 1 
                      AND s.password IS NOT NULL 
                      AND s.password != ''
                      AND eq.smtp_server_id IS NOT NULL
                    ORDER BY eq.smtp_server_id ASC, eq.priority DESC, eq.created_at ASC
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    queue_item = dict(row)
                    queue_id = queue_item['queue_id']
                    
                    # CRITICAL: Immediately mark as 'processing' to prevent duplicate processing
                    cursor.execute("""
                        UPDATE email_queue 
                        SET status = 'processing' 
                        WHERE id = ? AND status = 'pending'
                    """, (queue_id,))
                    
                    if cursor.rowcount == 0:
                        # Another thread already picked this up, return None
                        conn.rollback()
                        return None
                    
                    conn.commit()
                    smtp_id = queue_item.get('smtp_server_id')
                    smtp_username = queue_item.get('username', 'N/A')
                    print(f"[{threading.current_thread().name}] Locked queue item {queue_id} for processing")
                    print(f"   Using SMTP Server ID: {smtp_id}, Username: {smtp_username}")
                    
                    return queue_item
                
                return None
        except Exception as e:
            import traceback
            print(f"Error getting queue item: {e}")
            print(traceback.format_exc())
            return None
    
    def send_email(self, queue_item):
        """Send a single email"""
        try:
            # Check if unsubscribed
            if queue_item.get('is_unsubscribed'):
                self.mark_skipped(queue_item['queue_id'], "Recipient unsubscribed")
                return
            
            # Check rate limits
            from core.rate_limiter import RateLimiter
            from core.warmup import WarmupManager
            rate_limiter = RateLimiter(self.db)
            warmup_manager = WarmupManager(self.db)
            
            smtp_server_id = queue_item.get('smtp_server_id')
            user_id = queue_item.get('user_id')
            
            if smtp_server_id and user_id:
                # Check policy enforcement
                from core.policy_enforcer import PolicyEnforcer
                policy_enforcer = PolicyEnforcer(self.db)
                
                # Extract domain from sender email
                sender_email = queue_item.get('sender_email', '')
                domain = sender_email.split('@')[1] if '@' in sender_email else None
                
                # Enforce all policies
                policy_check = policy_enforcer.enforce_all_policies(user_id, smtp_server_id, 1, domain)
                if not policy_check.get('allowed'):
                    self.mark_failed(queue_item['queue_id'], f"Policy violation: {policy_check.get('reason', 'Policy check failed')}")
                    return
                
                # Check rate limit
                rate_check = rate_limiter.check_rate_limit(smtp_server_id)
                if not rate_check.get('can_send'):
                    self.mark_failed(queue_item['queue_id'], f"Rate limit: {rate_check.get('reason')}")
                    return
                
                # Check warmup
                warmup_check = warmup_manager.can_send_email(smtp_server_id)
                if not warmup_check.get('can_send'):
                    self.mark_failed(queue_item['queue_id'], f"Warmup limit: {warmup_check.get('reason')}")
                    return
                
                # Use warmup delay if available
                warmup_delay = warmup_check.get('delay_seconds', self.interval)
                if warmup_delay > self.interval:
                    import time
                    time.sleep(warmup_delay - self.interval)
            
            # Get SMTP server config from queue_item
            # CRITICAL: Always use the SMTP server assigned in the queue item
            queue_smtp_id = queue_item.get('smtp_server_id')
            
            # First try to use SMTP config from the JOIN (most reliable)
            if queue_item.get('host') and queue_item.get('password') and queue_item.get('username'):
                # CRITICAL: Decrypt password if it's encrypted
                password = queue_item['password']
                if password:
                    try:
                        from core.encryption import get_encryption_manager
                        encryptor = get_encryption_manager()
                        # Try to decrypt - if it fails, it might be plaintext
                        try:
                            decrypted = encryptor.decrypt(password)
                            if decrypted:
                                password = decrypted
                        except:
                            # Password might be plaintext, use as-is
                            pass
                    except Exception as decrypt_error:
                        # Encryption manager not available or password is plaintext
                        pass
                
                # Ensure password is a string
                if isinstance(password, bytes):
                    password = password.decode('utf-8')
                
                smtp_config = {
                    'host': queue_item['host'],
                    'port': queue_item['port'],
                    'username': queue_item['username'],
                    'password': password,  # Use decrypted password
                    'use_ssl': queue_item.get('use_ssl', 0),
                    'use_tls': queue_item.get('use_tls', 0)
                }
                print(f"   Using SMTP config from queue JOIN: {queue_item.get('username')} @ {queue_item.get('host')}")
                print(f"   Password decrypted: {bool(password and len(password) > 0)}")
            elif queue_smtp_id:
                # Fallback: fetch SMTP config using the queue's smtp_server_id
                print(f"   Fetching SMTP config for server ID: {queue_smtp_id}")
                smtp_config = self.get_smtp_config(queue_smtp_id)
                if not smtp_config:
                    self.mark_failed(queue_item['queue_id'], f"SMTP server {queue_smtp_id} not found or not active")
                    return
                if not smtp_config.get('password'):
                    self.mark_failed(queue_item['queue_id'], f"SMTP server {queue_smtp_id} password is missing")
                    return
                print(f"   Using SMTP config: {smtp_config.get('username')} @ {smtp_config.get('host')}")
            else:
                self.mark_failed(queue_item['queue_id'], "No SMTP server ID in queue item")
                return
            
            # Validate password is not None or empty
            if not smtp_config.get('password') or smtp_config['password'].strip() == '':
                error_msg = "SMTP password is empty or missing"
                print(f"✗ {error_msg}")
                self.mark_failed(queue_item['queue_id'], error_msg)
                return
            
            # Ensure password is properly decoded (handle special characters like *)
            import urllib.parse
            password = smtp_config['password']
            if isinstance(password, bytes):
                password = password.decode('utf-8')
            # Try URL decode if needed (some forms might encode special chars)
            try:
                # Only decode if it looks URL-encoded (contains %)
                if '%' in password:
                    decoded = urllib.parse.unquote(password)
                    # Only use decoded if it's different and makes sense
                    if decoded != password and len(decoded) > 0:
                        password = decoded
            except:
                pass  # If decoding fails, use original
            smtp_config['password'] = password
            
            # Prepare campaign and recipient dicts
            campaign = {
                'subject': queue_item.get('subject', ''),
                'sender_name': queue_item.get('sender_name', ''),
                'sender_email': queue_item.get('sender_email', ''),
                'reply_to': queue_item.get('reply_to'),
                'html_content': queue_item.get('html_content', ''),
                'use_personalization': queue_item.get('use_personalization', False),
                'personalization_prompt': queue_item.get('personalization_prompt'),
                'user_id': queue_item.get('campaign_user_id') or queue_item.get('user_id')
            }
            
            # Store queue_item for personalization access
            self._current_queue_item = queue_item
            
            recipient = {
                'email': queue_item.get('email', ''),
                'first_name': queue_item.get('first_name', ''),
                'last_name': queue_item.get('last_name', ''),
                'company': queue_item.get('company', ''),
                'city': queue_item.get('city', '')
            }
            
            # Store user_id for personalization
            self._current_user_id = queue_item.get('campaign_user_id') or queue_item.get('user_id')
            
            # Prepare email
            msg = self.prepare_email(campaign, recipient, smtp_config, 
                                   queue_item['campaign_id'], queue_item['recipient_id'],
                                   personalization_prompt=queue_item.get('personalization_prompt'))
            
            # Connect to SMTP server
            try:
                smtp_username = smtp_config.get('username', '').strip()
                smtp_password = smtp_config.get('password', '').strip()
                smtp_host = smtp_config.get('host', '').strip()
                smtp_port = int(smtp_config.get('port', 465))
                
                # Validate credentials
                if not smtp_username or not smtp_password:
                    error_msg = "SMTP username or password is missing"
                    print(f"✗ {error_msg}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    return
                
                print(f"🔗 Connecting to SMTP: {smtp_host}:{smtp_port} as {smtp_username}")
                print(f"   Queue SMTP Server ID: {queue_item.get('smtp_server_id')}")
                print(f"   Using SMTP Config: {smtp_config.get('username')} @ {smtp_config.get('host')}")
                
                # Connect to SMTP server
                if smtp_config.get('use_ssl') or smtp_config.get('use_ssl') == 1:
                    server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
                    # For SSL connections, EHLO is called automatically, but we'll call it explicitly
                    try:
                        server.ehlo()
                    except:
                        server.helo()
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
                    # Send EHLO first
                    try:
                        server.ehlo()
                    except:
                        server.helo()
                    
                    if smtp_config.get('use_tls') or smtp_config.get('use_tls') == 1:
                        server.starttls()
                        # After STARTTLS, send EHLO again
                        try:
                            server.ehlo()
                        except:
                            server.helo()
                
                # Login with proper authentication - CRITICAL STEP
                print(f"Attempting authentication for {smtp_username}...")
                print(f"Password length: {len(smtp_password) if smtp_password else 0} characters")
                # Debug: Show first and last char (for verification, not security risk)
                if smtp_password:
                    print(f"Password starts with: {smtp_password[0] if len(smtp_password) > 0 else 'N/A'}")
                    print(f"Password ends with: {smtp_password[-1] if len(smtp_password) > 0 else 'N/A'}")
                    # Check for special characters
                    special_chars = [c for c in smtp_password if not c.isalnum()]
                    if special_chars:
                        print(f"Password contains special characters: {set(special_chars)}")
                
                # Check server capabilities for authentication methods
                auth_methods = []
                try:
                    if hasattr(server, 'esmtp_features'):
                        auth_methods = server.esmtp_features.get('auth', [])
                        print(f"Server supports auth methods: {auth_methods}")
                except:
                    pass
                
                # Try authentication - some servers are picky about the method
                auth_success = False
                auth_exception = None
                try:
                    # Standard login - this should work for most servers
                    # CRITICAL: Ensure password is a string, not bytes
                    if isinstance(smtp_password, bytes):
                        smtp_password = smtp_password.decode('utf-8')
                    
                    server.login(smtp_username, smtp_password)
                    auth_success = True
                    print(f"✓ Authenticated successfully as {smtp_username}")
                    
                    # Verify authentication by checking server state
                    try:
                        # Try a NOOP command to verify connection is still authenticated
                        server.noop()
                    except:
                        print("⚠ Warning: Connection may have been reset after login")
                        # Re-authenticate if needed
                        try:
                            server.login(smtp_username, smtp_password)
                            auth_success = True
                        except:
                            auth_success = False
                            
                except smtplib.SMTPAuthenticationError as auth_error:
                    auth_exception = auth_error
                    error_msg = f"Authentication failed: {str(auth_error)}"
                    print(f"✗ {error_msg}")
                    print(f"  Username: {smtp_username}")
                    print(f"  Password present: {bool(smtp_password)}")
                    print(f"  Error code: {getattr(auth_error, 'smtp_code', 'N/A')}")
                    print(f"  Error message: {getattr(auth_error, 'smtp_error', 'N/A')}")
                    
                    # Try alternative authentication methods
                    if not auth_success:
                        # Try AUTH PLAIN if available - use smtplib's auth() method for proper state management
                        if 'PLAIN' in auth_methods:
                            try:
                                print("  Trying AUTH PLAIN method...")
                                if isinstance(smtp_password, bytes):
                                    smtp_password = smtp_password.decode('utf-8')
                                
                                # Use smtplib's auth() method which properly sets internal state
                                # This ensures sendmail() recognizes we're authenticated
                                try:
                                    # For SMTP_SSL and SMTP, try auth() method first
                                    if hasattr(server, 'auth'):
                                        # Create auth mechanism
                                        import base64
                                        auth_string = base64.b64encode(f"\0{smtp_username}\0{smtp_password}".encode()).decode()
                                    # Use auth() method with PLAIN mechanism
                                    # The auth() method expects a callable that returns credentials
                                    def plain_auth():
                                        return (smtp_username, smtp_password)
                                    server.auth('PLAIN', plain_auth)
                                    auth_success = True
                                    print(f"✓ Authenticated successfully using AUTH PLAIN (via auth())")
                                except (AttributeError, Exception) as auth_method_error:
                                    # Fallback: use docmd() and manually set state
                                    print(f"  auth() method failed, trying docmd(): {auth_method_error}")
                                    import base64
                                    auth_string = base64.b64encode(f"\0{smtp_username}\0{smtp_password}".encode()).decode()
                                    response = server.docmd('AUTH', 'PLAIN ' + auth_string)
                                    if response and len(response) > 0 and response[0] == 235:
                                        auth_success = True
                                        print(f"✓ Authenticated successfully using AUTH PLAIN (via docmd)")
                                        # Manually set authenticated state for smtplib
                                        # This is critical - docmd doesn't update smtplib's internal state
                                        try:
                                            # Set internal authentication flags
                                            if hasattr(server, '_auth_object'):
                                                server._auth_object = True
                                            # Mark as authenticated in esmtp_features
                                            if hasattr(server, 'esmtp_features'):
                                                if 'auth' not in server.esmtp_features:
                                                    server.esmtp_features['auth'] = []
                                            # Set a flag that login was successful
                                            if hasattr(server, '_login'):
                                                server._login = True
                                            # For SMTP_SSL, we need to ensure it knows we're authenticated
                                            if hasattr(server, 'sock') and hasattr(server, '_auth_challenge'):
                                                server._auth_challenge = None
                                        except Exception as state_error:
                                            print(f"⚠ Could not set auth state: {state_error}")
                                            # Still continue - server accepted auth
                                    else:
                                        print(f"  AUTH PLAIN failed with response: {response}")
                                
                                if auth_success:
                                    # Verify authentication works
                                    try:
                                        noop_resp = server.noop()
                                        if noop_resp and len(noop_resp) > 0 and noop_resp[0] == 250:
                                            print(f"✓ Authentication verified (NOOP: {noop_resp[0]})")
                                        else:
                                            print(f"⚠ NOOP returned unexpected response: {noop_resp}")
                                    except Exception as verify_err:
                                        print(f"⚠ Could not verify authentication state: {verify_err}")
                            except Exception as plain_error:
                                print(f"  AUTH PLAIN also failed: {plain_error}")
                                import traceback
                                traceback.print_exc()
                        
                        # Try AUTH LOGIN if available
                        if not auth_success and 'LOGIN' in auth_methods:
                            try:
                                print("  Trying AUTH LOGIN method...")
                                if isinstance(smtp_password, bytes):
                                    smtp_password = smtp_password.decode('utf-8')
                                
                                # Try smtplib's auth() method first
                                try:
                                    server.auth('LOGIN', lambda: (smtp_username, smtp_password))
                                    auth_success = True
                                    print(f"✓ Authenticated successfully using AUTH LOGIN (via auth())")
                                except (AttributeError, Exception):
                                    # Fallback to docmd
                                    import base64
                                    response1 = server.docmd('AUTH', 'LOGIN')
                                    if response1 and len(response1) > 0 and response1[0] == 334:
                                        response2 = server.docmd(base64.b64encode(smtp_username.encode()).decode())
                                        if response2 and len(response2) > 0 and response2[0] == 334:
                                            response3 = server.docmd(base64.b64encode(smtp_password.encode()).decode())
                                            if response3 and len(response3) > 0 and response3[0] == 235:
                                                auth_success = True
                                                print(f"✓ Authenticated successfully using AUTH LOGIN (via docmd)")
                                                if hasattr(server, '_auth_object'):
                                                    server._auth_object = True
                            except Exception as login_error:
                                print(f"  AUTH LOGIN also failed: {login_error}")
                                import traceback
                                traceback.print_exc()
                    
                    if not auth_success:
                        # Final error with detailed info
                        final_error = f"SMTP Authentication failed. Server requires authentication. Check username and password. Error: {str(auth_exception) if auth_exception else 'Unknown error'}"
                        print(f"✗ {final_error}")
                        self.mark_failed(queue_item['queue_id'], final_error)
                        try:
                            server.quit()
                        except:
                            pass
                        return
                except smtplib.SMTPException as smtp_error:
                    error_msg = f"SMTP authentication error: {str(smtp_error)}"
                    print(f"✗ {error_msg}")
                    print(f"  Full error: {repr(smtp_error)}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    try:
                        server.quit()
                    except:
                        pass
                    return
                except Exception as login_error:
                    error_msg = f"Login error: {str(login_error)}"
                    print(f"✗ {error_msg}")
                    print(f"  Error type: {type(login_error).__name__}")
                    import traceback
                    print(traceback.format_exc())
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    try:
                        server.quit()
                    except:
                        pass
                    return
                
                if not auth_success:
                    error_msg = "Authentication failed - no method succeeded"
                    print(f"✗ {error_msg}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    try:
                        server.quit()
                    except:
                        pass
                    return
                
                # Send email using sendmail - this uses the authenticated user as envelope sender
                # The From header in the message can be different, but envelope must match auth
                to_email = recipient['email']
                
                # CRITICAL: Ensure authentication is still valid before sending
                # Some servers require re-authentication if connection is idle
                # For servers that use AUTH PLAIN via docmd, we need to be more careful
                try:
                    # Verify connection is still alive and authenticated
                    noop_response = server.noop()
                    if noop_response and len(noop_response) > 0:
                        if noop_response[0] != 250:
                            raise Exception(f"Connection not properly authenticated (NOOP: {noop_response[0]})")
                        print(f"✓ Connection verified (NOOP: {noop_response[0]})")
                    else:
                        raise Exception("NOOP returned empty response")
                except Exception as verify_error:
                    # Connection lost or not authenticated, re-authenticate
                    print(f"⚠ Connection verification failed, re-authenticating: {verify_error}")
                    auth_success = False
                    try:
                        if isinstance(smtp_password, bytes):
                            smtp_password = smtp_password.decode('utf-8')
                        # Try standard login first
                        try:
                            server.login(smtp_username, smtp_password)
                            auth_success = True
                            print("✓ Re-authenticated successfully with login()")
                        except:
                            # Try AUTH PLAIN
                            try:
                                import base64
                                auth_string = base64.b64encode(f"\0{smtp_username}\0{smtp_password}".encode()).decode()
                                response = server.docmd('AUTH', 'PLAIN ' + auth_string)
                                if response[0] == 235:
                                    auth_success = True
                                    print("✓ Re-authenticated successfully with AUTH PLAIN")
                            except:
                                pass
                        
                        if not auth_success:
                            raise Exception("Re-authentication failed")
                    except Exception as reauth_error:
                        error_msg = f"Re-authentication failed: {str(reauth_error)}"
                        print(f"✗ {error_msg}")
                        self.mark_failed(queue_item['queue_id'], error_msg)
                        try:
                            server.quit()
                        except:
                            pass
                        return
                
                # Use sendmail with authenticated email as envelope sender
                # This prevents bounces due to authentication mismatches
                # IMPORTANT: Use smtp_username as envelope sender (MAIL FROM) to match authentication
                # For some servers, we need to explicitly set MAIL FROM to the authenticated user
                
                # Ensure the From header in the message matches the authenticated user
                # This is critical for servers that check authentication
                if msg['From'] and smtp_username:
                    # Extract email from From header
                    from_header = msg['From']
                    # If From doesn't match authenticated user, update it
                    if smtp_username not in from_header:
                        # Keep the display name but use authenticated email
                        from_name = from_header.split('<')[0].strip().strip('"')
                        if from_name:
                            msg['From'] = f'"{from_name}" <{smtp_username}>'
                        else:
                            msg['From'] = smtp_username
                
                # Send email - use smtp_username as envelope sender (MAIL FROM)
                # CRITICAL: For servers that require authentication, ensure we're authenticated
                # Some servers check authentication state before allowing sendmail
                try:
                    # Verify we're still authenticated before sending
                    noop_check = server.noop()
                    if noop_check and len(noop_check) > 0 and noop_check[0] != 250:
                        raise Exception("Not authenticated - NOOP failed")
                except Exception as auth_check_error:
                    print(f"⚠ Authentication check failed before send: {auth_check_error}")
                    # Try to re-authenticate
                    try:
                        if isinstance(smtp_password, bytes):
                            smtp_password = smtp_password.decode('utf-8')
                        server.login(smtp_username, smtp_password)
                        print("✓ Re-authenticated before sending")
                    except:
                        # If login fails, try AUTH PLAIN again
                        try:
                            import base64
                            auth_string = base64.b64encode(f"\0{smtp_username}\0{smtp_password}".encode()).decode()
                            response = server.docmd('AUTH', 'PLAIN ' + auth_string)
                            if response and len(response) > 0 and response[0] == 235:
                                print("✓ Re-authenticated with AUTH PLAIN before sending")
                                # Set auth state again
                                if hasattr(server, '_auth_object'):
                                    server._auth_object = True
                            else:
                                raise Exception("Re-authentication failed")
                        except Exception as reauth_error:
                            error_msg = f"Failed to re-authenticate before sending: {reauth_error}"
                            print(f"✗ {error_msg}")
                            self.mark_failed(queue_item['queue_id'], error_msg)
                            server.quit()
                            return
                
                # Now send the email - verify it actually succeeds
                try:
                    # sendmail returns a dict of failed recipients (empty dict = success)
                    failed_recipients = server.sendmail(smtp_username, [to_email], msg.as_string())
                    if failed_recipients:
                        # Some recipients failed
                        error_msg = f"SMTP sendmail returned failed recipients: {failed_recipients}"
                        print(f"✗ {error_msg}")
                        self.mark_failed(queue_item['queue_id'], error_msg)
                        server.quit()
                        return
                    else:
                        # Success - no failed recipients
                        print(f"✓ Email sent successfully to {to_email} from {smtp_username} (SMTP Server ID: {queue_item.get('smtp_server_id')})")
                        print(f"✓ SMTP sendmail() returned empty dict (all recipients accepted)")
                except smtplib.SMTPRecipientsRefused as e:
                    error_msg = f"Recipient refused by SMTP server: {str(e)}"
                    print(f"✗ {error_msg}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    server.quit()
                    return
                except smtplib.SMTPDataError as e:
                    error_msg = f"SMTP data error during send: {str(e)}"
                    print(f"✗ {error_msg}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    server.quit()
                    return
                except Exception as send_error:
                    error_msg = f"Unexpected error during sendmail: {str(send_error)}"
                    print(f"✗ {error_msg}")
                    import traceback
                    traceback.print_exc()
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    server.quit()
                    return
                # Save email to IMAP Sent folder if configured (before quitting SMTP)
                # This must happen AFTER successful sendmail() but BEFORE server.quit()
                try:
                    # Ensure IMAP config is in smtp_config
                    if not smtp_config.get('imap_host') and queue_item.get('imap_host'):
                        smtp_config['imap_host'] = queue_item.get('imap_host')
                        smtp_config['imap_port'] = queue_item.get('imap_port', 993)
                        smtp_config['save_to_sent'] = queue_item.get('save_to_sent', 1)
                    
                    if smtp_config.get('imap_host') and smtp_config.get('save_to_sent', 1):
                        print(f"📁 Saving email to IMAP Sent folder: {smtp_config.get('imap_host')}")
                        self.save_to_imap_sent(msg, smtp_config)
                        print(f"✓ Email saved to IMAP Sent folder")
                    else:
                        print(f"⚠ IMAP not configured or save_to_sent disabled - skipping IMAP save")
                except Exception as imap_error:
                    print(f"⚠ Warning: Could not save to IMAP Sent folder: {imap_error}")
                    import traceback
                    traceback.print_exc()
                    # Don't fail the send if IMAP save fails - email was already sent
                
                server.quit()
                
                # Update rate limiter and warmup
                if smtp_server_id:
                    rate_limiter.increment_sent_count(smtp_server_id)
                    warmup_manager.update_warmup_progress(smtp_server_id)
                
                # Mark as sent and save to sent_emails table
                recipient_info = {
                    'email': recipient['email'],
                    'first_name': recipient.get('first_name', ''),
                    'last_name': recipient.get('last_name', '')
                }
                campaign_info = {
                    'subject': campaign['subject'],
                    'sender_name': campaign.get('sender_name', ''),
                    'sender_email': campaign.get('sender_email', ''),
                    'html_content': campaign.get('html_content', '')
                }
                # Mark as sent - wrap in try-except to ensure status is updated even if this fails
                try:
                    self.mark_sent(
                        queue_item['queue_id'], 
                        queue_item['campaign_id'], 
                        queue_item['recipient_id'],
                        email_message=msg,
                        recipient_info=recipient_info,
                        campaign_info=campaign_info,
                        smtp_server_id=queue_item.get('smtp_server_id')
                    )
                    print(f"✓ Email marked as sent in database (Queue ID: {queue_item['queue_id']})")
                except Exception as mark_error:
                    import traceback
                    print(f"✗ CRITICAL: Failed to mark email as sent in database: {mark_error}")
                    print(traceback.format_exc())
                    # Try to at least update queue status to failed so it doesn't stay in processing
                    try:
                        self.mark_failed(queue_item['queue_id'], f"Error saving to database: {mark_error}")
                    except:
                        pass
                
            except smtplib.SMTPAuthenticationError as auth_error:
                error_msg = f"Authentication failed: {str(auth_error)}. Check username and password."
                print(f"✗ Authentication Error: {error_msg}")
                self.mark_failed(queue_item['queue_id'], error_msg)
                try:
                    server.quit()
                except:
                    pass
            except smtplib.SMTPException as smtp_error:
                error_msg = f"SMTP error: {str(smtp_error)}"
                print(f"✗ SMTP Error sending to {recipient.get('email', 'unknown')}: {error_msg}")
                self.mark_failed(queue_item['queue_id'], error_msg)
                try:
                    server.quit()
                except:
                    pass
            except Exception as conn_error:
                error_msg = f"Connection error: {str(conn_error)}"
                print(f"✗ Connection Error: {error_msg}")
                import traceback
                print(traceback.format_exc())
                self.mark_failed(queue_item['queue_id'], error_msg)
                try:
                    server.quit()
                except:
                    pass
            
        except Exception as e:
            error_msg = str(e)
            import traceback
            print(f"✗ Error sending email to {queue_item.get('email', 'unknown')}: {error_msg}")
            print(traceback.format_exc())
            # Ensure queue status is updated on any exception
            try:
                self.mark_failed(queue_item.get('queue_id'), error_msg)
            except Exception as mark_error:
                print(f"✗ CRITICAL: Failed to mark email as failed in queue: {mark_error}")
                print(traceback.format_exc())
    
    def prepare_email(self, campaign, recipient, smtp_config, campaign_id=None, recipient_id=None, personalization_prompt=None):
        """Prepare email message with merge tags and optional LLM personalization"""
        msg = MIMEMultipart('mixed')  # Changed to 'mixed' to support attachments
        
        # Get sender information
        sender_email = campaign.get('sender_email', '')
        sender_name = campaign.get('sender_name', '')
        smtp_username = smtp_config.get('username', '')
        
        # CRITICAL: Use SMTP authenticated email as From to prevent bounces
        # Many SMTP servers require the From address to match the authenticated user
        if smtp_username:
            # Format sender properly
            msg['From'] = formataddr((sender_name, smtp_username))
            # Set Reply-To to the original sender email if different
            if sender_email and sender_email != smtp_username:
                msg['Reply-To'] = formataddr((sender_name, sender_email))
            else:
                msg['Reply-To'] = formataddr((sender_name, smtp_username))
        else:
            msg['From'] = formataddr((sender_name, sender_email))
            msg['Reply-To'] = formataddr((sender_name, sender_email))
        
        # Headers - use simple email format for To
        msg['To'] = recipient['email']
        msg['Subject'] = self.replace_merge_tags(campaign['subject'], recipient)
        
        # Add important headers to prevent bounces and spam
        msg['Message-ID'] = f"<{uuid.uuid4()}@anaghasolution.com>"
        # Use IST timezone for email Date header
        ist_aware = get_ist_now_aware()
        msg['Date'] = format_datetime(ist_aware)
        msg['MIME-Version'] = '1.0'
        msg['X-Mailer'] = 'ANAGHA SOLUTION Email Client v1.0'
        msg['X-Priority'] = '3'
        msg['Content-Type'] = 'multipart/mixed; boundary="{}"'.format(msg.get_boundary())
        
        # Get HTML content
        html_content = campaign.get('html_content', '')
        
        # Two email sending modes:
        # 1. LLM Personalization Mode (use_personalization = True): Uses AI to personalize each email
        # 2. Direct Mode (use_personalization = False): Uses template as-is with merge tags only
        
        use_personalization = campaign.get('use_personalization', False)
        if not use_personalization:
            # Try to get from queue_item if passed separately
            use_personalization = getattr(self, '_current_queue_item', {}).get('use_personalization', False)
        
        # Convert to boolean if it's an integer
        if isinstance(use_personalization, int):
            use_personalization = bool(use_personalization)
        
        print(f"📧 Email Mode: {'LLM Personalization' if use_personalization else 'Direct (Template Only)'}")
        
        if use_personalization:
            # MODE 1: LLM Personalization - Use AI to personalize email content
            try:
                from core.personalization import EmailPersonalizer
                from core.quota_manager import QuotaManager
                from core.observability import ObservabilityManager
                
                # Get user_id from campaign or queue_item
                user_id = campaign.get('user_id') or getattr(self, '_current_user_id', None)
                
                personalizer = EmailPersonalizer(db_manager=self.db, user_id=user_id)
                
                # Get recipient context
                name = recipient.get('first_name', '') + ' ' + recipient.get('last_name', '')
                name = name.strip()
                company = recipient.get('company', '') or recipient.get('company_name', '')
                context = recipient.get('context', '')
                
                # Get custom prompt from campaign
                custom_prompt = campaign.get('personalization_prompt')
                
                # Pre-process template: Replace merge tags with actual values before sending to LLM
                # This helps the LLM understand the context better
                template_for_personalization = html_content
                if name:
                    first_name = recipient.get('first_name', '') or (name.split()[0] if name.split() else name)
                    template_for_personalization = template_for_personalization.replace('{{first_name}}', first_name)
                    template_for_personalization = template_for_personalization.replace('{{name}}', name)
                    template_for_personalization = template_for_personalization.replace('{first_name}', first_name)
                    template_for_personalization = template_for_personalization.replace('{name}', name)
                if company:
                    template_for_personalization = template_for_personalization.replace('{{company}}', company)
                    template_for_personalization = template_for_personalization.replace('{company}', company)
                if recipient.get('email'):
                    template_for_personalization = template_for_personalization.replace('{{email}}', recipient.get('email'))
                    template_for_personalization = template_for_personalization.replace('{email}', recipient.get('email'))
                if recipient.get('city'):
                    template_for_personalization = template_for_personalization.replace('{{city}}', recipient.get('city'))
                    template_for_personalization = template_for_personalization.replace('{city}', recipient.get('city'))
                
                # Track LLM usage start
                quota_mgr = QuotaManager(self.db)
                obs_mgr = ObservabilityManager(self.db)
                
                # Personalize the content (use prompt from parameter or campaign)
                prompt_to_use = personalization_prompt or custom_prompt
                print(f"🤖 Calling LLM personalization with pre-processed template")
                print(f"   Original template length: {len(html_content)}")
                print(f"   Pre-processed template length: {len(template_for_personalization)}")
                
                html_content = personalizer.personalize_email(
                    template_for_personalization,  # Use pre-processed template
                    name, 
                    company, 
                    context,
                    custom_prompt=prompt_to_use
                )
                
                print(f"✓ LLM personalization completed, result length: {len(html_content)}")
                
                # Record LLM usage (tokens are already recorded in personalizer)
                if user_id:
                    try:
                        obs_mgr.record_metric(user_id, 'llm', 'personalization_used', 1.0, {
                            'campaign_id': campaign_id,
                            'recipient_id': recipient_id
                        })
                    except Exception as obs_error:
                        # Don't fail email sending if metrics recording fails
                        print(f"⚠ Warning: Could not record LLM metric: {obs_error}")
                    
            except Exception as e:
                print(f"⚠️ Warning: LLM Personalization failed, falling back to direct template: {e}")
                import traceback
                traceback.print_exc()
                # Continue with original html_content (fallback to direct mode)
        else:
            # MODE 2: Direct Mode - Use template as-is with merge tags only (no LLM)
            # Merge tags like {{first_name}}, {{company}} will be replaced, but no AI personalization
            print(f"✓ Direct Mode: Using template with merge tags only (no LLM)")
                # Continue with original content
        
        # Extract attachment paths if embedded in HTML
        attachment_paths = []
        if '<!--ATTACHMENTS:' in html_content:
            import re
            match = re.search(r'<!--ATTACHMENTS:(.*?)-->', html_content)
            if match:
                attachment_paths = [p.strip() for p in match.group(1).split(',') if p.strip()]
                # Remove attachment comment from HTML
                html_content = re.sub(r'<!--ATTACHMENTS:.*?-->', '', html_content)
        
        # Check if content is plain text (no HTML tags) and convert to HTML
        import re as regex_module
        has_html_tags = bool(regex_module.search(r'<[^>]+>', html_content))
        
        if not has_html_tags and html_content.strip():
            # Convert plain text to HTML, preserving ALL formatting including line breaks
            # First, normalize line endings
            html_content = html_content.replace('\r\n', '\n').replace('\r', '\n')
            
            # Preserve double newlines as paragraph breaks
            # Preserve single newlines as <br> tags
            # Handle bullet points (lines starting with *)
            lines = html_content.split('\n')
            html_lines = []
            in_paragraph = False
            
            for line in lines:
                line = line.rstrip()  # Remove trailing whitespace but keep leading
                
                if not line.strip():
                    # Empty line - end current paragraph if any
                    if in_paragraph:
                        html_lines.append('</p>')
                        in_paragraph = False
                    html_lines.append('')  # Add spacing
                elif line.strip().startswith('*'):
                    # Bullet point - format as list item
                    if in_paragraph:
                        html_lines.append('</p>')
                        in_paragraph = False
                    bullet_text = line.strip()[1:].strip()  # Remove * and trim
                    html_lines.append(f'<ul style="margin: 5px 0; padding-left: 20px;"><li style="margin: 3px 0;">{bullet_text}</li></ul>')
                else:
                    # Regular text line
                    if not in_paragraph:
                        html_lines.append('<p style="margin: 0 0 10px 0; line-height: 1.6;">')
                        in_paragraph = True
                    # Escape HTML special characters
                    line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    html_lines.append(line)
                    # Add <br> for line continuation within paragraph
                    html_lines.append('<br>')
            
            # Close last paragraph if open
            if in_paragraph:
                html_lines.append('</p>')
            
            html_content = '\n'.join(html_lines)
            
            # Wrap in proper HTML structure if not already wrapped
            if not html_content.strip().startswith('<'):
                html_content = f'<div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333;">{html_content}</div>'
        
        # Replace merge tags
        html_content = self.replace_merge_tags(html_content, recipient)
        
        # Add unsubscribe link
        if self.should_add_unsubscribe():
            unsubscribe_url = self.generate_unsubscribe_url(recipient['email'])
            html_content = self.add_unsubscribe_link(html_content, unsubscribe_url)
        
        # Add tracking pixel if we have IDs
        if campaign_id and recipient_id:
            tracking_pixel = self.generate_tracking_pixel(campaign_id, recipient_id)
            html_content = self.add_tracking_pixel(html_content, tracking_pixel)
        
        # Create multipart alternative for text/html
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        
        # Create text version (strip HTML tags for plain text) - preserve formatting
        import re as regex_module
        import html as html_module
        
        # First, convert HTML list items to text format
        text_content = html_content
        
        # Convert <ul><li> to bullet points
        text_content = regex_module.sub(r'<ul[^>]*>', '', text_content)
        text_content = regex_module.sub(r'</ul>', '', text_content)
        text_content = regex_module.sub(r'<li[^>]*>', '* ', text_content)
        text_content = regex_module.sub(r'</li>', '\n', text_content)
        
        # Convert <p> tags to double newlines
        text_content = regex_module.sub(r'<p[^>]*>', '', text_content)
        text_content = regex_module.sub(r'</p>', '\n\n', text_content)
        
        # Convert <br> tags to single newlines
        text_content = text_content.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        
        # Remove all other HTML tags
        text_content = regex_module.sub(r'<[^>]+>', '', text_content)
        
        # Unescape HTML entities
        text_content = html_module.unescape(text_content)
        
        # Clean up excessive newlines but preserve structure
        text_content = regex_module.sub(r'\n{3,}', '\n\n', text_content)
        text_content = text_content.strip()
        
        # Ensure text content is not empty
        if not text_content:
            text_content = "Please view this email in an HTML-compatible email client."
        
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        msg_alternative.attach(text_part)
        
        # Wrap HTML content in proper HTML structure if not already wrapped
        if not html_content.strip().lower().startswith('<html'):
            html_wrapped = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333; margin: 0; padding: 20px;">
{html_content}
</body>
</html>"""
            html_content = html_wrapped
        
        # Create HTML part with proper encoding
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg_alternative.attach(html_part)
        
        # Add attachments
        for attachment_path in attachment_paths:
            if os.path.exists(attachment_path):
                try:
                    with open(attachment_path, 'rb') as f:
                        attachment = MIMEBase('application', 'octet-stream')
                        attachment.set_payload(f.read())
                        encoders.encode_base64(attachment)
                        
                        filename = os.path.basename(attachment_path)
                        # Remove campaign_id prefix if present
                        if filename.startswith('temp_'):
                            filename = filename[5:]
                        elif '_' in filename and filename.split('_')[0].isdigit():
                            filename = '_'.join(filename.split('_')[1:])
                        
                        attachment.add_header(
                            'Content-Disposition',
                            f'attachment; filename= {filename}'
                        )
                        msg.attach(attachment)
                except Exception as e:
                    print(f"Error attaching file {attachment_path}: {e}")
        
        return msg
    
    def replace_merge_tags(self, text, recipient):
        """Replace merge tags in text"""
        if not text:
            return ''
        
        # Get values with fallback to empty string if None
        first_name = recipient.get('first_name') or ''
        last_name = recipient.get('last_name') or ''
        full_name = f"{first_name} {last_name}".strip() or recipient.get('name') or ''
        
        replacements = {
            '{name}': full_name,
            '{first_name}': first_name,
            '{last_name}': last_name,
            '{email}': recipient.get('email') or '',
            '{company}': recipient.get('company') or recipient.get('company_name') or '',
            '{city}': recipient.get('city') or '',
            '{title}': recipient.get('title') or '',
            '{phone}': recipient.get('phone') or '',
        }
        
        result = str(text)  # Ensure text is a string
        for tag, value in replacements.items():
            # Ensure value is a string (handle None)
            value_str = str(value) if value is not None else ''
            result = result.replace(tag, value_str)
        
        return result
    
    def generate_unsubscribe_url(self, email):
        """Generate unsubscribe URL"""
        # In a real application, this would be a web server URL
        # For now, we'll use a local tracking mechanism
        token = str(uuid.uuid4())
        return f"unsubscribe?email={email}&token={token}"
    
    def add_unsubscribe_link(self, html, url):
        """Add unsubscribe link to HTML"""
        unsubscribe_html = f'<p style="font-size: 12px; color: #999;"><a href="{url}">Unsubscribe</a></p>'
        
        # Try to add before closing body tag
        if '</body>' in html:
            html = html.replace('</body>', unsubscribe_html + '</body>')
        else:
            html += unsubscribe_html
        
        return html
    
    def generate_tracking_pixel(self, campaign_id, recipient_id):
        """Generate tracking pixel URL"""
        # In a real application, this would be a web server URL
        token = str(uuid.uuid4())
        return f"track?campaign={campaign_id}&recipient={recipient_id}&token={token}&type=open"
    
    def add_tracking_pixel(self, html, pixel_url):
        """Add tracking pixel to HTML"""
        pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none;" />'
        
        # Try to add before closing body tag
        if '</body>' in html:
            html = html.replace('</body>', pixel_html + '</body>')
        else:
            html += pixel_html
        
        return html
    
    def should_add_unsubscribe(self):
        """Check if unsubscribe link should be added"""
        return True  # Always add for compliance
    
    def get_smtp_config(self, smtp_id):
        """Get SMTP server configuration"""
        if not smtp_id:
            # Get default SMTP server
            default_server = self.db.get_default_smtp_server()
            if default_server:
                # Ensure password is properly decoded
                # Password should already be decrypted by get_default_smtp_server()
                return default_server
            # Fallback to first active server
            servers = self.db.get_smtp_servers()
            if servers:
                server = servers[0]
                # Password should already be decrypted by get_smtp_servers()
                return server
            return None
        
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            # Use Supabase
            result = self.db.supabase.client.table('smtp_servers').select('*').eq('id', smtp_id).eq('is_active', 1).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                # Decrypt password
                if 'password' in server and server['password']:
                    try:
                        from core.encryption import get_encryption_manager
                        encryptor = get_encryption_manager()
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        # If decryption fails, might be plaintext from old data
                        password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
                return server
            return None
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ? AND is_active = 1", (smtp_id,))
            row = cursor.fetchone()
            if row:
                server = dict(row)
                # Decrypt password
                if 'password' in server and server['password']:
                    try:
                        from core.encryption import get_encryption_manager
                        encryptor = get_encryption_manager()
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        # If decryption fails, might be plaintext from old data
                        password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
                return server
            return None
    
    def save_to_imap_sent(self, msg, smtp_config):
        """Save sent email to IMAP Sent folder"""
        try:
            # Check if IMAP is configured and enabled
            imap_host = smtp_config.get('imap_host')
            save_to_sent = smtp_config.get('save_to_sent', 1)
            
            if not imap_host or not save_to_sent or save_to_sent == 0:
                print(f"⚠ IMAP not configured: imap_host={imap_host}, save_to_sent={save_to_sent}")
                return  # IMAP not configured or disabled
            
            imap_port = int(smtp_config.get('imap_port', 993))
            username = smtp_config.get('username', '').strip()
            password = smtp_config.get('password', '').strip()
            
            if not username or not password:
                print(f"⚠ IMAP credentials missing: username={bool(username)}, password={bool(password)}")
                return
            
            print(f"📁 Connecting to IMAP: {imap_host}:{imap_port} as {username}")
            
            # Connect to IMAP server
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass  # TLS not supported
            
            # Login
            print(f"📁 Authenticating to IMAP...")
            imap.login(username, password)
            print(f"✓ IMAP authenticated")
            
            # Select Sent folder (try common names)
            sent_folders = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent', '"Sent"', '"Sent Items"']
            selected_folder = None
            
            for folder in sent_folders:
                try:
                    status, _ = imap.select(folder)
                    if status == 'OK':
                        selected_folder = folder
                        print(f"✓ Found Sent folder: {folder}")
                        break
                except Exception as folder_error:
                    print(f"  Folder '{folder}' not found: {folder_error}")
                    continue
            
            if not selected_folder:
                # Try to use INBOX as fallback
                print(f"⚠ No standard Sent folder found, trying INBOX as fallback...")
                try:
                    status, _ = imap.select('INBOX')
                    if status == 'OK':
                        selected_folder = 'INBOX'
                        print(f"✓ Using INBOX as fallback")
                    else:
                        print(f"✗ INBOX selection failed")
                        imap.logout()
                        return
                except Exception as inbox_error:
                    print(f"✗ INBOX selection error: {inbox_error}")
                    imap.logout()
                    return
            
            # Append email to Sent folder
            email_str = msg.as_string()
            # Convert to bytes if needed
            if isinstance(email_str, str):
                email_bytes = email_str.encode('utf-8')
            else:
                email_bytes = email_str
            
            print(f"📁 Appending email to {selected_folder}...")
            result = imap.append(selected_folder, None, None, email_bytes)
            print(f"✓ IMAP append result: {result}")
            
            imap.logout()
            print(f"✓ Email saved to IMAP Sent folder: {selected_folder}")
            
        except Exception as e:
            # Don't raise - just log the error
            print(f"⚠ IMAP save error: {e}")
            import traceback
            traceback.print_exc()
    
    def mark_sent(self, queue_id, campaign_id, recipient_id, email_message=None, recipient_info=None, campaign_info=None, smtp_server_id=None):
        """Mark email as sent and save to sent_emails table"""
        # Use IST timezone for timestamp
        now = get_ist_now()
        
        # Check if using Supabase
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        
        # Get recipient and campaign info if not provided
        if not recipient_info:
            if use_supabase:
                result = self.db.supabase.client.table('recipients').select('email, first_name, last_name').eq('id', recipient_id).execute()
                if result.data and len(result.data) > 0:
                    rec = result.data[0]
                    recipient_info = {
                        'email': rec.get('email', ''),
                        'first_name': rec.get('first_name', '') or '',
                        'last_name': rec.get('last_name', '') or ''
                    }
            else:
                # SQLite
                conn = self.db.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT email, first_name, last_name FROM recipients WHERE id = ?", (recipient_id,))
                rec_row = cursor.fetchone()
                if rec_row:
                    recipient_info = {
                        'email': rec_row[0],
                        'first_name': rec_row[1] or '',
                        'last_name': rec_row[2] or ''
                    }
        
        if not campaign_info:
            if use_supabase:
                result = self.db.supabase.client.table('campaigns').select('subject, sender_name, sender_email, html_content, user_id').eq('id', campaign_id).execute()
                if result.data and len(result.data) > 0:
                    camp = result.data[0]
                    campaign_info = {
                        'subject': camp.get('subject', ''),
                        'sender_name': camp.get('sender_name', '') or '',
                        'sender_email': camp.get('sender_email', ''),
                        'html_content': camp.get('html_content', '') or '',
                        'user_id': camp.get('user_id')
                    }
            else:
                # SQLite
                conn = self.db.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT subject, sender_name, sender_email, html_content, user_id FROM campaigns WHERE id = ?", (campaign_id,))
                camp_row = cursor.fetchone()
                if camp_row:
                    campaign_info = {
                        'subject': camp_row[0],
                        'sender_name': camp_row[1] or '',
                        'sender_email': camp_row[2],
                        'html_content': camp_row[3] or '',
                        'user_id': camp_row[4] if len(camp_row) > 4 else None
                    }
        
        # Extract text content from email message if available
        text_content = ''
        html_content = campaign_info.get('html_content', '') if campaign_info else ''
        message_id = None
        
        if email_message:
            # Extract message ID
            message_id = email_message.get('Message-ID', '')
            
            # Extract text and HTML content from message
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == 'text/plain':
                        try:
                            text_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            text_content = str(part.get_payload())
                    elif content_type == 'text/html' and not html_content:
                        try:
                            html_content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            html_content = str(part.get_payload())
            else:
                content_type = email_message.get_content_type()
                payload = email_message.get_payload(decode=True)
                if payload:
                    try:
                        content = payload.decode('utf-8', errors='ignore')
                        if content_type == 'text/plain':
                            text_content = content
                        elif content_type == 'text/html':
                            html_content = content
                    except:
                        pass
        
        # Save to sent_emails table
        recipient_name = f"{recipient_info.get('first_name', '')} {recipient_info.get('last_name', '')}".strip() if recipient_info else ''
        recipient_email = recipient_info.get('email', '') if recipient_info else ''
        
        if use_supabase:
            # Supabase
            sent_email_data = {
                'campaign_id': campaign_id,
                'recipient_id': recipient_id,
                'recipient_email': recipient_email,
                'recipient_name': recipient_name,
                'subject': campaign_info.get('subject', '') if campaign_info else '',
                'sender_name': campaign_info.get('sender_name', '') if campaign_info else '',
                'sender_email': campaign_info.get('sender_email', '') if campaign_info else '',
                'html_content': html_content,
                'text_content': text_content,
                'sent_at': now.isoformat(),
                'status': 'sent',
                'smtp_server_id': smtp_server_id,
                'message_id': message_id
            }
            self.db.supabase.client.table('sent_emails').insert(sent_email_data).execute()
            
            # Update queue
            self.db.supabase.client.table('email_queue').update({
                'status': 'sent',
                'sent_at': now.isoformat()
            }).eq('id', queue_id).execute()
            
            # Update campaign_recipients (if table exists)
            try:
                self.db.supabase.client.table('campaign_recipients').update({
                    'status': 'sent',
                    'sent_at': now.isoformat()
                }).eq('campaign_id', campaign_id).eq('recipient_id', recipient_id).execute()
            except:
                pass  # Table might not exist
            
            # Check if all emails for this campaign are sent
            result = self.db.supabase.client.table('email_queue').select('id', count='exact').eq('campaign_id', campaign_id).in_('status', ['pending', 'processing']).execute()
            pending_count = result.count if result.count else 0
            
            if pending_count == 0:
                self.db.supabase.client.table('campaigns').update({
                    'status': 'sent',
                    'sent_at': now.isoformat()
                }).eq('id', campaign_id).execute()
                print(f"Campaign {campaign_id} marked as sent (all emails delivered)")
            
            # Update daily stats (with user_id)
            user_id = campaign_info.get('user_id') if campaign_info else None
            if not user_id:
                # Try to get from campaign
                camp_result = self.db.supabase.client.table('campaigns').select('user_id').eq('id', campaign_id).execute()
                if camp_result.data and len(camp_result.data) > 0:
                    user_id = camp_result.data[0].get('user_id')
            
            if user_id:
                today = get_ist_now().date().isoformat()
                # Try to get existing stats
                stats_result = self.db.supabase.client.table('daily_stats').select('*').eq('user_id', user_id).eq('date', today).execute()
                if stats_result.data and len(stats_result.data) > 0:
                    existing = stats_result.data[0]
                    self.db.supabase.client.table('daily_stats').update({
                        'emails_sent': (existing.get('emails_sent', 0) or 0) + 1,
                        'emails_delivered': (existing.get('emails_delivered', 0) or 0) + 1
                    }).eq('id', existing['id']).execute()
                else:
                    self.db.supabase.client.table('daily_stats').insert({
                        'user_id': user_id,
                        'date': today,
                        'emails_sent': 1,
                        'emails_delivered': 1
                    }).execute()
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sent_emails (
                    campaign_id, recipient_id, recipient_email, recipient_name,
                    subject, sender_name, sender_email, html_content, text_content,
                    sent_at, status, smtp_server_id, message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign_id, recipient_id, recipient_email, recipient_name,
                campaign_info.get('subject', '') if campaign_info else '',
                campaign_info.get('sender_name', '') if campaign_info else '',
                campaign_info.get('sender_email', '') if campaign_info else '',
                html_content, text_content,
                now, 'sent', smtp_server_id, message_id
            ))
            
            # Update queue
            cursor.execute("""
                UPDATE email_queue 
                SET status = 'sent', sent_at = ?
                WHERE id = ?
            """, (now, queue_id))
            
            # Update campaign_recipients
            cursor.execute("""
                UPDATE campaign_recipients 
                SET status = 'sent', sent_at = ?
                WHERE campaign_id = ? AND recipient_id = ?
            """, (now, campaign_id, recipient_id))
            
            # Check if all emails for this campaign are sent (including processing)
            cursor.execute("""
                SELECT COUNT(*) FROM email_queue 
                WHERE campaign_id = ? AND status IN ('pending', 'processing')
            """, (campaign_id,))
            pending_count = cursor.fetchone()[0]
            
            # If no pending emails, update campaign status to 'sent'
            if pending_count == 0:
                cursor.execute("""
                    UPDATE campaigns SET status = 'sent', sent_at = ?
                    WHERE id = ?
                """, (now, campaign_id))
                print(f"Campaign {campaign_id} marked as sent (all emails delivered)")
            
                # Update daily stats - use IST date (with user_id)
                user_id = campaign_info.get('user_id') if campaign_info else None
                if not user_id:
                    cursor.execute("SELECT user_id FROM campaigns WHERE id = ?", (campaign_id,))
                    row = cursor.fetchone()
                    if row:
                        user_id = row[0]
                
                if user_id:
                    today = get_ist_now().date()
                    cursor.execute("""
                        INSERT OR REPLACE INTO daily_stats (user_id, date, emails_sent, emails_delivered)
                        VALUES (?, ?, 
                            COALESCE((SELECT emails_sent FROM daily_stats WHERE user_id = ? AND date = ?), 0) + 1,
                            COALESCE((SELECT emails_delivered FROM daily_stats WHERE user_id = ? AND date = ?), 0) + 1
                        )
                    """, (user_id, today, user_id, today, user_id, today))
            
            conn.commit()
    
    def mark_failed(self, queue_id, error_msg):
        """Mark email as failed"""
        try:
            # Check if using Supabase FIRST before trying to use SQLite methods
            use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
            
            if use_supabase:
                # Try to get attempts count (column might not exist)
                current_attempts = 0
                try:
                    result = self.db.supabase.client.table('email_queue').select('attempts').eq('id', queue_id).execute()
                    if result.data and len(result.data) > 0:
                        current_attempts = result.data[0].get('attempts', 0) or 0
                except:
                    # Column doesn't exist, use 0
                    current_attempts = 0
                
                # Update status (only include attempts if column exists)
                update_data = {
                    'status': 'failed',
                    'error_message': str(error_msg)[:500]  # Limit error message length
                }
                # Only add attempts if we successfully retrieved it (column exists)
                if current_attempts >= 0:  # Will try to update attempts
                    try:
                        update_data['attempts'] = current_attempts + 1
                        self.db.supabase.client.table('email_queue').update(update_data).eq('id', queue_id).execute()
                    except:
                        # If attempts column doesn't exist, update without it
                        del update_data['attempts']
                        self.db.supabase.client.table('email_queue').update(update_data).eq('id', queue_id).execute()
                else:
                    self.db.supabase.client.table('email_queue').update(update_data).eq('id', queue_id).execute()
            else:
                # SQLite
                conn = self.db.connect()
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE email_queue
                    SET status = 'failed', attempts = attempts + 1, error_message = ?
                    WHERE id = ?
                """, (str(error_msg)[:500], queue_id))
                
                conn.commit()
        except Exception as e:
            print(f"Error marking email as failed: {e}")
            import traceback
            traceback.print_exc()
    
    def mark_skipped(self, queue_id, reason):
        """Mark email as skipped"""
        try:
            # Check if using Supabase FIRST before trying to use SQLite methods
            use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
            
            if use_supabase:
                self.db.supabase.client.table('email_queue').update({
                    'status': 'skipped',
                    'error_message': str(reason)[:500] if reason else None
                }).eq('id', queue_id).execute()
            else:
                # SQLite
                conn = self.db.connect()
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE email_queue
                    SET status = 'skipped', error_message = ?
                    WHERE id = ?
                """, (str(reason)[:500] if reason else None, queue_id))
                
                conn.commit()
        except Exception as e:
            print(f"Error marking email as skipped: {e}")
            import traceback
            traceback.print_exc()

