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
                    # Get campaign personalization setting
                    conn = self.db.connect()
                    cursor = conn.cursor()
                    cursor.execute("SELECT use_personalization FROM campaigns WHERE id = ?", (queue_item.get('campaign_id'),))
                    row = cursor.fetchone()
                    use_personalization = row[0] if row and row[0] else 0
                    queue_item['use_personalization'] = bool(use_personalization)
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
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Use a transaction with row-level locking to prevent duplicate processing
            # First, find and lock a pending item
            # First, get queue items with valid SMTP server assignments
            # We need to ensure the SMTP server exists and is active
            cursor.execute("""
                SELECT eq.id as queue_id, eq.campaign_id, eq.recipient_id, eq.smtp_server_id,
                       c.name as campaign_name, c.subject, c.sender_name, c.sender_email, 
                       c.reply_to, c.html_content,
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
                # Use UPDATE with WHERE status='pending' to ensure atomic operation
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
                
                # Return the queue item
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
            if smtp_server_id:
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
                smtp_config = {
                    'host': queue_item['host'],
                    'port': queue_item['port'],
                    'username': queue_item['username'],
                    'password': queue_item['password'],
                    'use_ssl': queue_item.get('use_ssl', 0),
                    'use_tls': queue_item.get('use_tls', 0)
                }
                print(f"   Using SMTP config from queue JOIN: {queue_item.get('username')} @ {queue_item.get('host')}")
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
                'use_personalization': queue_item.get('use_personalization', False)
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
            
            # Prepare email
            msg = self.prepare_email(campaign, recipient, smtp_config, 
                                   queue_item['campaign_id'], queue_item['recipient_id'])
            
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
                try:
                    # Standard login - this should work for most servers
                    server.login(smtp_username, smtp_password)
                    auth_success = True
                    print(f"✓ Authenticated successfully as {smtp_username}")
                except smtplib.SMTPAuthenticationError as auth_error:
                    error_msg = f"Authentication failed: {str(auth_error)}"
                    print(f"✗ {error_msg}")
                    print(f"  Username: {smtp_username}")
                    print(f"  Password present: {bool(smtp_password)}")
                    print(f"  Error code: {getattr(auth_error, 'smtp_code', 'N/A')}")
                    print(f"  Error message: {getattr(auth_error, 'smtp_error', 'N/A')}")
                    
                    # Try alternative authentication if AUTH PLAIN is available
                    if not auth_success and 'PLAIN' in auth_methods:
                        try:
                            print("  Trying AUTH PLAIN method...")
                            import base64
                            auth_string = base64.b64encode(f"\0{smtp_username}\0{smtp_password}".encode()).decode()
                            server.docmd('AUTH', 'PLAIN ' + auth_string)
                            auth_success = True
                            print(f"✓ Authenticated successfully using AUTH PLAIN")
                        except Exception as plain_error:
                            print(f"  AUTH PLAIN also failed: {plain_error}")
                    
                    if not auth_success:
                        self.mark_failed(queue_item['queue_id'], error_msg)
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
                
                # Use sendmail with authenticated email as envelope sender
                # This prevents bounces due to authentication mismatches
                try:
                    server.sendmail(smtp_username, [to_email], msg.as_string())
                    print(f"✓ Email sent successfully to {to_email} from {smtp_username} (SMTP Server ID: {queue_item.get('smtp_server_id')})")
                except smtplib.SMTPRecipientsRefused as e:
                    error_msg = f"Recipient refused: {str(e)}"
                    print(f"✗ {error_msg}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    server.quit()
                    return
                except smtplib.SMTPDataError as e:
                    error_msg = f"SMTP data error: {str(e)}"
                    print(f"✗ {error_msg}")
                    self.mark_failed(queue_item['queue_id'], error_msg)
                    server.quit()
                    return
                
                # Save email to IMAP Sent folder if configured (before quitting SMTP)
                try:
                    self.save_to_imap_sent(msg, smtp_config)
                except Exception as imap_error:
                    print(f"⚠ Warning: Could not save to IMAP Sent folder: {imap_error}")
                    # Don't fail the send if IMAP save fails
                
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
                self.mark_sent(
                    queue_item['queue_id'], 
                    queue_item['campaign_id'], 
                    queue_item['recipient_id'],
                    email_message=msg,
                    recipient_info=recipient_info,
                    campaign_info=campaign_info,
                    smtp_server_id=queue_item.get('smtp_server_id')
                )
                
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
            self.mark_failed(queue_item['queue_id'], error_msg)
    
    def prepare_email(self, campaign, recipient, smtp_config, campaign_id=None, recipient_id=None):
        """Prepare email message with merge tags"""
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
        
        # Check if personalization is enabled for this campaign
        # Check both campaign dict and queue_item
        use_personalization = campaign.get('use_personalization', False)
        if not use_personalization:
            # Try to get from queue_item if passed separately
            use_personalization = getattr(self, '_current_queue_item', {}).get('use_personalization', False)
        if use_personalization:
            try:
                from core.personalization import EmailPersonalizer
                personalizer = EmailPersonalizer()
                
                # Get recipient context
                name = recipient.get('first_name', '') + ' ' + recipient.get('last_name', '')
                company = recipient.get('company', '')
                context = recipient.get('context', '')
                
                # Personalize the content
                html_content = personalizer.personalize_email(html_content, name.strip(), company, context)
            except Exception as e:
                print(f"Warning: Personalization failed, using original template: {e}")
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
        replacements = {
            '{name}': recipient.get('first_name', '') + ' ' + recipient.get('last_name', ''),
            '{first_name}': recipient.get('first_name', ''),
            '{last_name}': recipient.get('last_name', ''),
            '{email}': recipient.get('email', ''),
            '{company}': recipient.get('company', ''),
            '{city}': recipient.get('city', ''),
        }
        
        result = text
        for tag, value in replacements.items():
            result = result.replace(tag, value)
        
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
                if 'password' in default_server and default_server['password']:
                    password = default_server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    default_server['password'] = password
                return default_server
            # Fallback to first active server
            servers = self.db.get_smtp_servers()
            if servers:
                server = servers[0]
                # Ensure password is properly decoded
                if 'password' in server and server['password']:
                    password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
                return server
            return None
        
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE id = ? AND is_active = 1", (smtp_id,))
        row = cursor.fetchone()
        if row:
            server = dict(row)
            # Ensure password is properly decoded
            if 'password' in server and server['password']:
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
                return  # IMAP not configured or disabled
            
            imap_port = int(smtp_config.get('imap_port', 993))
            username = smtp_config.get('username', '').strip()
            password = smtp_config.get('password', '').strip()
            
            if not username or not password:
                return
            
            print(f"Attempting to save email to IMAP Sent folder: {imap_host}:{imap_port}")
            
            # Connect to IMAP server
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=10)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=10)
                try:
                    imap.starttls()
                except:
                    pass  # TLS not supported
            
            # Login
            imap.login(username, password)
            
            # Select Sent folder (try common names)
            sent_folders = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent', '"Sent"', '"Sent Items"']
            selected_folder = None
            
            for folder in sent_folders:
                try:
                    status, _ = imap.select(folder)
                    if status == 'OK':
                        selected_folder = folder
                        break
                except:
                    continue
            
            if not selected_folder:
                # Try to use INBOX as fallback
                try:
                    status, _ = imap.select('INBOX')
                    if status == 'OK':
                        selected_folder = 'INBOX'
                    else:
                        imap.logout()
                        return
                except:
                    imap.logout()
                    return
            
            # Append email to Sent folder
            email_str = msg.as_string()
            # Convert to bytes if needed
            if isinstance(email_str, str):
                email_bytes = email_str.encode('utf-8')
            else:
                email_bytes = email_str
            
            imap.append(selected_folder, None, None, email_bytes)
            
            imap.logout()
            print(f"✓ Email saved to IMAP Sent folder: {selected_folder}")
            
        except Exception as e:
            # Don't raise - just log the error
            print(f"⚠ IMAP save error: {e}")
            import traceback
            traceback.print_exc()
    
    def mark_sent(self, queue_id, campaign_id, recipient_id, email_message=None, recipient_info=None, campaign_info=None, smtp_server_id=None):
        """Mark email as sent and save to sent_emails table"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Use IST timezone for timestamp
        now = get_ist_now()
        
        # Get recipient and campaign info if not provided
        if not recipient_info:
            cursor.execute("SELECT email, first_name, last_name FROM recipients WHERE id = ?", (recipient_id,))
            rec_row = cursor.fetchone()
            if rec_row:
                recipient_info = {
                    'email': rec_row[0],
                    'first_name': rec_row[1] or '',
                    'last_name': rec_row[2] or ''
                }
        
        if not campaign_info:
            cursor.execute("SELECT subject, sender_name, sender_email, html_content FROM campaigns WHERE id = ?", (campaign_id,))
            camp_row = cursor.fetchone()
            if camp_row:
                campaign_info = {
                    'subject': camp_row[0],
                    'sender_name': camp_row[1] or '',
                    'sender_email': camp_row[2],
                    'html_content': camp_row[3] or ''
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
        
        # Update daily stats - use IST date
        today = get_ist_now().date()
        cursor.execute("""
            INSERT OR REPLACE INTO daily_stats (date, emails_sent, emails_delivered)
            VALUES (?, 
                COALESCE((SELECT emails_sent FROM daily_stats WHERE date = ?), 0) + 1,
                COALESCE((SELECT emails_delivered FROM daily_stats WHERE date = ?), 0) + 1
            )
        """, (today, today, today))
        
        conn.commit()
    
    def mark_failed(self, queue_id, error_msg):
        """Mark email as failed"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE email_queue 
            SET status = 'failed', attempts = attempts + 1
            WHERE id = ?
        """, (queue_id,))
        
        conn.commit()
    
    def mark_skipped(self, queue_id, reason):
        """Mark email as skipped"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE email_queue 
            SET status = 'skipped'
            WHERE id = ?
        """, (queue_id,))
        
        conn.commit()

