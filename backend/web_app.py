"""
ANAGHA SOLUTION - Web Application
Flask-based web interface for bulk email software
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_cors import CORS
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from database.db_manager import DatabaseManager
from core.email_sender import EmailSender
from core.auth import AuthManager
from core.middleware import require_auth, optional_auth, get_current_user, set_auth_manager
from core.rate_limiter import RateLimiter
from core.warmup import WarmupManager
from core.billing import BillingManager
from core.warmup_manager import WarmupManager
from core.observability import ObservabilityManager
from database.migrations import MigrationManager
import pandas as pd
from datetime import datetime
import json

# Get paths relative to backend directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_root, 'frontend')

app = Flask(__name__, 
            template_folder=os.path.join(frontend_dir, 'templates'),
            static_folder=os.path.join(frontend_dir, 'static'))
app.secret_key = 'anagha_solution_secret_key_2024'
CORS(app, resources={r"/*": {"origins": "*"}})

# Disable strict slashes to avoid 403 errors
app.url_map.strict_slashes = False

# Add error handlers
@app.errorhandler(403)
def forbidden(error):
    return jsonify({'error': 'Access forbidden. Please check server configuration.'}), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Initialize database - check if Supabase is configured
database_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
if database_type == 'supabase':
    try:
        from database.supabase_manager import SupabaseDatabaseManager
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        if supabase_url and supabase_key:
            print("Initializing Supabase database...")
            db = SupabaseDatabaseManager(supabase_url, supabase_key)
            print("✓ Using Supabase database")
            # Ensure tables are created
            db.initialize_database()
        else:
            print("⚠️  Supabase URL/Key not found, falling back to SQLite")
            db = DatabaseManager()
            db.initialize_database()
    except Exception as e:
        import traceback
        print(f"⚠️  Error initializing Supabase: {e}")
        traceback.print_exc()
        print("Falling back to SQLite...")
        db = DatabaseManager()
        db.initialize_database()
else:
    print("Initializing SQLite database...")
    db = DatabaseManager()
    db.initialize_database()
    print("✓ SQLite database initialized")

# Initialize managers
from database.settings_manager import SettingsManager
from database.migrations import MigrationManager
from core.warmup_manager import WarmupManager as EnhancedWarmupManager
from core.observability import ObservabilityManager

settings_manager = SettingsManager(db)
auth_manager = AuthManager(db)
# Set auth manager in middleware so it uses the same instance
set_auth_manager(auth_manager)
rate_limiter = RateLimiter(db)
warmup_manager = WarmupManager(db)  # Keep old one for compatibility
enhanced_warmup_manager = EnhancedWarmupManager(db)
billing_manager = BillingManager(db)
observability_manager = ObservabilityManager(db)

# Run migrations and create indexes
migration_manager = MigrationManager(db)
migration_manager.migrate_schema()
migration_manager.create_indexes()
print("✓ Database migrations and indexes created")

# Global email sender instance
email_sender = None

# Authentication Routes
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Register new user"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        company_name = data.get('company_name', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_manager.register_user(email, password, first_name, last_name, company_name)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Login user"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_manager.login_user(email, password)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'token': result['token'],
                'user': {
                    'id': result['user_id'],
                    'email': result['email'],
                    'first_name': result.get('first_name', ''),
                    'last_name': result.get('last_name', '')
                }
            })
        else:
            return jsonify({'error': result.get('error', 'Login failed')}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
@optional_auth
def api_get_current_user(user_id):
    """Get current user info - validates token"""
    try:
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        user = auth_manager.get_user(user_id)
        if user:
            # Don't return sensitive info
            user.pop('password_hash', None)
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        import traceback
        print(f"Error in /api/auth/me: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def api_change_password(user_id):
    """Change user password"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return jsonify({'error': 'Old and new passwords are required'}), 400
        
        result = auth_manager.change_password(user_id, old_password, new_password)
        return jsonify(result) if result.get('success') else jsonify(result), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    """Dashboard page"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'ANAGHA SOLUTION Web Server is running'})

@app.route('/campaign-builder')
def campaign_builder():
    """Campaign builder page"""
    templates = db.get_templates()
    return render_template('campaign_builder.html', templates=templates)

@app.route('/recipients')
def recipients():
    """Recipients management page"""
    recipients_list = db.get_recipients()
    # Make sure recipients are not deleted - this was the bug
    return render_template('recipients.html', recipients=recipients_list)

@app.route('/leads')
def leads():
    """Leads management page"""
    return render_template('leads.html')

@app.route('/smtp-config')
def smtp_config():
    """SMTP configuration page"""
    servers = db.get_smtp_servers(active_only=False)
    return render_template('smtp_config.html', servers=servers)

@app.route('/templates')
def templates():
    """Template library page"""
    templates_list = db.get_templates()
    return render_template('templates.html', templates=templates_list)

@app.route('/analytics')
def analytics():
    """Analytics page"""
    campaigns = db.get_campaigns()
    return render_template('analytics.html', campaigns=campaigns)

@app.route('/sent-items')
def sent_items_page():
    """Sent Items page"""
    return render_template('sent_items.html')

@app.route('/inbox')
def inbox():
    """Inbox page for viewing incoming emails"""
    return render_template('inbox.html')

@app.route('/login')
def login_page():
    """Login page"""
    return render_template('login.html')

@app.route('/register')
def register_page():
    """Register page"""
    return render_template('register.html')

@app.route('/terms')
def terms_page():
    """Terms of Service page"""
    return render_template('terms.html')

@app.route('/privacy')
def privacy_page():
    """Privacy Policy page"""
    return render_template('privacy.html')

@app.route('/gdpr')
def gdpr_page():
    """GDPR Compliance page"""
    return render_template('gdpr.html')

# Inbox API Routes
import imaplib
import email
from email.header import decode_header

@app.route('/api/inbox/fetch/<int:account_id>')
def api_fetch_inbox(account_id):
    """Fetch emails from IMAP server - optimized to fetch only headers first"""
    try:
        folder = request.args.get('folder', 'INBOX')
        limit = request.args.get('limit', 100, type=int)  # Increased limit to fetch more emails
        
        # Get SMTP/IMAP config for this account
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        # Get IMAP settings - try imap_host first, then construct from smtp host
        imap_host = account.get('imap_host')
        if not imap_host:
            # Try to construct IMAP host from SMTP host
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        password = account.get('password', '')
        
        if not imap_host or not username or not password:
            return jsonify({'error': 'IMAP settings not configured for this account'}), 400
        
        # Connect to IMAP server
        try:
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass
            
            imap.login(username, password)
        except Exception as conn_error:
            return jsonify({'error': f'Failed to connect to IMAP server: {str(conn_error)}'}), 500
        
        # Try to select the folder (handle different naming conventions)
        folder_variants = [folder]
        if folder == 'INBOX':
            folder_variants = ['INBOX']
        elif folder == 'Sent':
            folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent', '"Sent"', '"Sent Items"']
        elif folder == 'Drafts':
            folder_variants = ['Drafts', 'Draft', 'INBOX.Drafts']
        elif folder == 'Trash':
            folder_variants = ['Trash', 'Deleted', 'Deleted Items', 'INBOX.Trash']
        elif folder == 'Spam':
            folder_variants = ['Spam', 'Junk', 'Junk E-mail', 'INBOX.Spam', 'INBOX.Junk']
        
        selected = False
        for f in folder_variants:
            try:
                status, _ = imap.select(f, readonly=True)
                if status == 'OK':
                    selected = True
                    break
            except:
                continue
        
        if not selected:
            imap.logout()
            return jsonify({'error': f'Could not access folder: {folder}'}), 400
        
        # Search for all emails
        status, messages = imap.search(None, 'ALL')
        if status != 'OK':
            imap.logout()
            return jsonify({'error': 'Failed to search emails'}), 500
        
        if not messages or not messages[0]:
            imap.logout()
            return jsonify({
                'success': True,
                'emails': [],
                'total': 0,
                'folder': folder,
                'message': 'No emails found in this folder'
            })
        
        email_ids = messages[0].split()
        
        if not email_ids:
            imap.logout()
            return jsonify({
                'success': True,
                'emails': [],
                'total': 0,
                'folder': folder,
                'message': 'No emails found in this folder'
            })
        
        print(f"Found {len(email_ids)} emails in {folder}, fetching last {limit}")
        
        # Get last N emails (most recent)
        email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
        email_ids = email_ids[::-1]  # Reverse to show newest first
        
        # OPTIMIZATION: Fetch only headers and flags first (much faster)
        # Use batch fetch for better performance
        if not email_ids:
            imap.logout()
            return jsonify({
                'success': True,
                'emails': [],
                'total': 0,
                'folder': folder
            })
        
        # OPTIMIZATION: Fetch headers and flags individually (more reliable than batch)
        emails = []
        successful_fetches = 0
        failed_fetches = 0
        
        for email_id in email_ids:
            try:
                # Fetch flags first
                unread = True  # Default to unread
                try:
                    status_flags, flags_data = imap.fetch(email_id, '(FLAGS)')
                    if status_flags == 'OK' and flags_data:
                        for flag_part in flags_data:
                            if isinstance(flag_part, tuple):
                                flag_str = str(flag_part)
                                if 'FLAGS' in flag_str:
                                    unread = '\\Seen' not in flag_str
                except:
                    pass  # Use default unread if flags fetch fails
                
                # Fetch headers
                status, msg_data = imap.fetch(email_id, '(BODY.PEEK[HEADER])')
                if status != 'OK' or not msg_data:
                    failed_fetches += 1
                    print(f"Failed to fetch headers for email {email_id}")
                    continue
                
                msg = None
                
                # Parse the response - handle different response formats
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        if len(response_part) >= 2:
                            part_header, part_data = response_part[0], response_part[1]
                            
                            # Get header data
                            if isinstance(part_data, bytes):
                                try:
                                    msg = email.message_from_bytes(part_data)
                                    break  # Found the message, exit loop
                                except Exception as parse_error:
                                    # Try alternative parsing methods
                                    try:
                                        # Try decoding first
                                        decoded = part_data.decode('utf-8', errors='ignore')
                                        msg = email.message_from_string(decoded)
                                        break
                                    except:
                                        try:
                                            # Try with latin-1 encoding
                                            decoded = part_data.decode('latin-1', errors='ignore')
                                            msg = email.message_from_string(decoded)
                                            break
                                        except:
                                            continue
                            elif isinstance(part_data, str):
                                try:
                                    msg = email.message_from_string(part_data)
                                    break
                                except:
                                    continue
                    elif isinstance(response_part, bytes):
                        # Sometimes response comes as bytes directly
                        try:
                            msg = email.message_from_bytes(response_part)
                            break
                        except:
                            try:
                                msg = email.message_from_string(response_part.decode('utf-8', errors='ignore'))
                                break
                            except:
                                continue
                
                if not msg:
                    failed_fetches += 1
                    print(f"Could not parse message for email {email_id}")
                    continue
                
                # Decode subject
                subject = msg.get('Subject', '')
                if subject:
                    try:
                        decoded_parts = decode_header(subject)
                        subject = ''
                        for part, encoding in decoded_parts:
                            if isinstance(part, bytes):
                                subject += part.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                subject += str(part)
                    except:
                        subject = str(subject)
                
                # Decode from
                from_addr = msg.get('From', '')
                if from_addr:
                    try:
                        decoded_parts = decode_header(from_addr)
                        from_decoded = ''
                        for part, encoding in decoded_parts:
                            if isinstance(part, bytes):
                                from_decoded += part.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                from_decoded += str(part)
                        from_addr = from_decoded
                    except:
                        from_addr = str(from_addr)
                
                email_uid = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                
                emails.append({
                    'uid': email_uid,
                    'subject': subject or '(No Subject)',
                    'from': from_addr or 'Unknown',
                    'to': msg.get('To', ''),
                    'date': msg.get('Date', ''),
                    'body': '',  # Will be loaded on demand
                    'html': '',  # Will be loaded on demand
                    'unread': unread
                })
                successful_fetches += 1
                
            except Exception as email_error:
                failed_fetches += 1
                import traceback
                error_details = traceback.format_exc()
                print(f"Error processing email {email_id}: {email_error}")
                print(f"Error details: {error_details}")
                # Continue processing other emails even if one fails
                continue
        
        print(f"Email fetch summary: {successful_fetches} successful, {failed_fetches} failed out of {len(email_ids)} total")
        
        # If we got some emails but not all, log it
        if successful_fetches > 0 and successful_fetches < len(email_ids):
            print(f"Warning: Only fetched {successful_fetches} out of {len(email_ids)} emails")
        
        # If no emails were fetched, try fallback method with full RFC822 (slower but more reliable)
        if len(emails) == 0 and len(email_ids) > 0:
            print("Trying fallback method with RFC822...")
            emails = []
            for email_id in email_ids[:10]:  # Limit to 10 for fallback
                try:
                    status, msg_data = imap.fetch(email_id, '(RFC822 FLAGS)')
                    if status != 'OK' or not msg_data:
                        continue
                    
                    msg = None
                    unread = True
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            part_header, part_data = response_part
                            
                            # Check flags
                            if isinstance(part_header, bytes):
                                header_str = part_header.decode('utf-8', errors='ignore')
                            else:
                                header_str = str(part_header)
                            
                            if 'FLAGS' in header_str:
                                unread = '\\Seen' not in header_str
                            
                            # Get message
                            if isinstance(part_data, bytes):
                                try:
                                    msg = email.message_from_bytes(part_data)
                                except:
                                    continue
                    
                    if not msg:
                        continue
                    
                    # Extract headers only (ignore body for now)
                    subject = msg.get('Subject', '') or '(No Subject)'
                    from_addr = msg.get('From', '') or 'Unknown'
                    
                    # Decode if needed
                    try:
                        decoded_parts = decode_header(subject)
                        subject = ''.join([p.decode(e or 'utf-8', errors='ignore') if isinstance(p, bytes) else str(p) 
                                         for p, e in decoded_parts])
                    except:
                        pass
                    
                    try:
                        decoded_parts = decode_header(from_addr)
                        from_addr = ''.join([p.decode(e or 'utf-8', errors='ignore') if isinstance(p, bytes) else str(p) 
                                           for p, e in decoded_parts])
                    except:
                        pass
                    
                    emails.append({
                        'uid': email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                        'subject': subject,
                        'from': from_addr,
                        'to': msg.get('To', ''),
                        'date': msg.get('Date', ''),
                        'body': '',
                        'html': '',
                        'unread': unread
                    })
                except Exception as e:
                    print(f"Fallback error for {email_id}: {e}")
                    continue
        
        imap.logout()
        
        return jsonify({
            'success': True,
            'emails': emails,
            'total': len(emails),
            'folder': folder
        })
        
    except Exception as e:
        import traceback
        print(f"Error fetching inbox: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/fetch-body/<int:account_id>/<email_uid>')
def api_fetch_email_body(account_id, email_uid):
    """Fetch full email body on demand (optimized - only when user views email)"""
    try:
        folder = request.args.get('folder', 'INBOX')
        
        # Get account config
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        imap_host = account.get('imap_host')
        if not imap_host:
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        password = account.get('password', '')
        
        # Connect to IMAP
        try:
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass
            imap.login(username, password)
        except Exception as conn_error:
            return jsonify({'error': f'Failed to connect: {str(conn_error)}'}), 500
        
        # Select folder
        folder_variants = [folder]
        if folder == 'Sent':
            folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent']
        elif folder == 'Drafts':
            folder_variants = ['Drafts', 'Draft', 'INBOX.Drafts']
        elif folder == 'Trash':
            folder_variants = ['Trash', 'Deleted', 'Deleted Items', 'INBOX.Trash']
        elif folder == 'Spam':
            folder_variants = ['Spam', 'Junk', 'Junk E-mail', 'INBOX.Spam']
        
        selected = False
        for f in folder_variants:
            try:
                status, _ = imap.select(f, readonly=True)
                if status == 'OK':
                    selected = True
                    break
            except:
                continue
        
        if not selected:
            imap.logout()
            return jsonify({'error': f'Could not access folder: {folder}'}), 400
        
        # Fetch full email body
        email_id = email_uid.encode() if isinstance(email_uid, str) else email_uid
        status, msg_data = imap.fetch(email_id, '(RFC822)')
        
        if status != 'OK' or not msg_data:
            imap.logout()
            return jsonify({'error': 'Failed to fetch email body'}), 500
        
        body = ''
        html_body = ''
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Get body
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain' and not body:
                            try:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                body = str(part.get_payload())
                        elif content_type == 'text/html' and not html_body:
                            try:
                                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                html_body = str(part.get_payload())
                else:
                    content_type = msg.get_content_type()
                    payload = msg.get_payload(decode=True)
                    if payload:
                        try:
                            content = payload.decode('utf-8', errors='ignore')
                            if content_type == 'text/html':
                                html_body = content
                            else:
                                body = content
                        except:
                            body = str(msg.get_payload())
                break
        
        imap.logout()
        
        return jsonify({
            'success': True,
            'body': body,
            'html': html_body
        })
        
    except Exception as e:
        import traceback
        print(f"Error fetching email body: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/delete', methods=['POST'])
def api_delete_emails():
    """Delete emails from IMAP server"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        account_id = data.get('account_id')
        folder = data.get('folder', 'INBOX')
        uids = data.get('uids', [])
        
        if not account_id:
            return jsonify({'error': 'Account ID required'}), 400
        
        if not uids:
            return jsonify({'error': 'No email UIDs provided'}), 400
        
        # Get account config
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        # Get IMAP settings
        imap_host = account.get('imap_host')
        if not imap_host:
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        password = account.get('password', '')
        
        # Connect to IMAP
        if imap_port == 993:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
        else:
            imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
            try:
                imap.starttls()
            except:
                pass
        
        imap.login(username, password)
        
        # Select folder
        folder_variants = [folder]
        if folder == 'Sent':
            folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent']
        elif folder == 'Drafts':
            folder_variants = ['Drafts', 'Draft', 'INBOX.Drafts']
        elif folder == 'Trash':
            folder_variants = ['Trash', 'Deleted', 'Deleted Items', 'INBOX.Trash']
        elif folder == 'Spam':
            folder_variants = ['Spam', 'Junk', 'Junk E-mail', 'INBOX.Spam']
        
        selected = False
        for f in folder_variants:
            try:
                status, _ = imap.select(f)
                if status == 'OK':
                    selected = True
                    break
            except:
                continue
        
        if not selected:
            imap.logout()
            return jsonify({'error': f'Could not access folder: {folder}'}), 400
        
        # Delete emails by marking as deleted
        deleted_count = 0
        for uid in uids:
            try:
                # Mark for deletion
                imap.store(uid.encode() if isinstance(uid, str) else uid, '+FLAGS', '\\Deleted')
                deleted_count += 1
            except Exception as del_error:
                print(f"Error deleting email {uid}: {del_error}")
                continue
        
        # Expunge to permanently remove
        imap.expunge()
        imap.logout()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        import traceback
        print(f"Error deleting emails: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sent-emails')
def api_get_sent_emails():
    """Get sent emails"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase methods
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)
            search = request.args.get('search', '')
            
            # Get sent emails with joins (Supabase doesn't support complex JOINs easily)
            # For now, get sent_emails and enrich with campaign/recipient data separately
            query = db.supabase.client.table('sent_emails').select('*')
            
            if search:
                # Supabase text search - filter in Python for now (or use multiple queries)
                # For better performance, could use Supabase RPC function
                pass  # Will filter after fetching
            
            query = query.order('sent_at', desc=True).range(offset, offset + limit - 1)
            result = query.execute()
            sent_emails = result.data if result.data else []
            
            # Filter by search term if provided
            if search:
                search_lower = search.lower()
                sent_emails = [e for e in sent_emails if 
                              search_lower in (e.get('recipient_email', '') or '').lower() or
                              search_lower in (e.get('subject', '') or '').lower() or
                              search_lower in (e.get('sender_email', '') or '').lower()]
            
            # Enrich with campaign and recipient data
            for email in sent_emails:
                if email.get('campaign_id'):
                    campaign = db.supabase.client.table('campaigns').select('name').eq('id', email['campaign_id']).execute()
                    email['campaign_name'] = campaign.data[0]['name'] if campaign.data else None
                if email.get('recipient_id'):
                    recipient = db.supabase.client.table('recipients').select('first_name,last_name').eq('id', email['recipient_id']).execute()
                    if recipient.data:
                        email['first_name'] = recipient.data[0].get('first_name')
                        email['last_name'] = recipient.data[0].get('last_name')
            
            # Get total count
            if search:
                # For search, count filtered results
                total = len(sent_emails)
            else:
                count_query = db.supabase.client.table('sent_emails').select('id', count='exact')
                count_result = count_query.execute()
                total = count_result.count if hasattr(count_result, 'count') else len(sent_emails)
            
            return jsonify({
                'success': True,
                'sent_emails': sent_emails,
                'total': total
            })
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Get query parameters
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)
            search = request.args.get('search', '')
            
            query = """
                SELECT se.*, c.name as campaign_name, r.first_name, r.last_name
                FROM sent_emails se
                LEFT JOIN campaigns c ON se.campaign_id = c.id
                LEFT JOIN recipients r ON se.recipient_id = r.id
                WHERE 1=1
            """
            params = []
            
            if search:
                query += " AND (se.recipient_email LIKE ? OR se.subject LIKE ? OR se.sender_email LIKE ?)"
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])
            
            query += " ORDER BY se.sent_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            sent_emails = [dict(row) for row in cursor.fetchall()]
            
            # Get total count
            count_query = "SELECT COUNT(*) FROM sent_emails se WHERE 1=1"
            count_params = []
            if search:
                count_query += " AND (se.recipient_email LIKE ? OR se.subject LIKE ? OR se.sender_email LIKE ?)"
                search_term = f"%{search}%"
                count_params.extend([search_term, search_term, search_term])
            cursor.execute(count_query, count_params)
            total = cursor.fetchone()[0]
            
            return jsonify({
                'success': True,
                'sent_emails': sent_emails,
                'total': total
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sent-emails/<int:email_id>')
def api_get_sent_email(email_id):
    """Get a single sent email"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase methods
            result = db.supabase.client.table('sent_emails').select('*').eq('id', email_id).execute()
            
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Email not found'}), 404
            
            email = result.data[0]
            
            # Enrich with campaign and recipient data
            if email.get('campaign_id'):
                campaign = db.supabase.client.table('campaigns').select('name').eq('id', email['campaign_id']).execute()
                email['campaign_name'] = campaign.data[0]['name'] if campaign.data else None
            if email.get('recipient_id'):
                recipient = db.supabase.client.table('recipients').select('first_name,last_name').eq('id', email['recipient_id']).execute()
                if recipient.data:
                    email['first_name'] = recipient.data[0].get('first_name')
                    email['last_name'] = recipient.data[0].get('last_name')
            
            return jsonify({'success': True, 'email': email})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT se.*, c.name as campaign_name, r.first_name, r.last_name
                FROM sent_emails se
                LEFT JOIN campaigns c ON se.campaign_id = c.id
                LEFT JOIN recipients r ON se.recipient_id = r.id
                WHERE se.id = ?
            """, (email_id,))
            row = cursor.fetchone()
            
            if row:
                return jsonify({'success': True, 'email': dict(row)})
            else:
                return jsonify({'error': 'Email not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/sent-items')
def sent_items():
    """Sent Items page"""
    return render_template('sent_items.html')

@app.route('/settings')
def settings_page():
    """Settings page"""
    return render_template('settings.html')

# Settings API Routes

@app.route('/api/settings')
@optional_auth
def api_get_settings(user_id):
    """Get all settings"""
    try:
        # Get from persistent storage
        settings = settings_manager.get_all_settings(user_id=user_id)
        
        # Convert string values to appropriate types
        result = {
            'email_delay': int(settings.get('email_delay', 30)),
            'max_per_hour': int(settings.get('max_per_hour', 100)),
            'email_priority': int(settings.get('email_priority', 5)),
            'emails_per_server': int(settings.get('emails_per_server', 20)),
            'use_threading': settings.get('use_threading', 'false').lower() == 'true'
        }
        return jsonify({'success': True, 'settings': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/delay', methods=['POST'])
@optional_auth
def api_set_delay(user_id):
    """Set email delay setting"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        delay = data.get('email_delay', 30)
        
        # Validate delay value
        delay = int(delay)
        if delay < 1:
            delay = 1
        if delay > 600:
            delay = 600
        
        # Save to persistent storage
        settings_manager.set_setting('email_delay', str(delay), user_id=user_id)
        
        # Update the global email sender if it exists
        global email_sender
        if email_sender:
            email_sender.interval = float(delay)
            print(f"✓ Email delay updated to {delay} seconds")
        
        return jsonify({'success': True, 'email_delay': delay})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/other', methods=['POST'])
@optional_auth
def api_set_other_settings(user_id):
    """Set other settings"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        if 'max_per_hour' in data:
            settings_manager.set_setting('max_per_hour', data['max_per_hour'], user_id=user_id)
        
        if 'email_priority' in data:
            settings_manager.set_setting('email_priority', data['email_priority'], user_id=user_id)
        
        if 'emails_per_server' in data:
            settings_manager.set_setting('emails_per_server', data['emails_per_server'], user_id=user_id)
        
        if 'use_threading' in data:
            settings_manager.set_setting('use_threading', data['use_threading'], user_id=user_id)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/emails-per-server', methods=['POST'])
@optional_auth
def api_set_emails_per_server(user_id):
    """Set emails per server setting"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        emails_per_server = int(data.get('emails_per_server', 20))
        
        if emails_per_server < 1:
            emails_per_server = 1
        if emails_per_server > 100:
            emails_per_server = 100
        
        # Save to persistent storage
        settings_manager.set_setting('emails_per_server', str(emails_per_server), user_id=user_id)
        return jsonify({'success': True, 'emails_per_server': emails_per_server})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/api-keys', methods=['GET'])
@optional_auth
def api_get_api_keys(user_id):
    """Get API keys (masked)"""
    try:
        from core.config import Config
        
        # Get from persistent storage first
        perplexity_key = settings_manager.get_setting('PERPLEXITY_API_KEY', user_id=user_id) or Config.get_perplexity_key()
        openrouter_key = settings_manager.get_setting('OPENROUTER_API_KEY', user_id=user_id) or Config.get_openrouter_key()
        openrouter_model = settings_manager.get_setting('OPENROUTER_MODEL', user_id=user_id) or Config.OPENROUTER_MODEL
        
        def mask_key(key):
            if not key or len(key) < 8:
                return ''
            return key[:4] + '*' * (len(key) - 8) + key[-4:]
        
        return jsonify({
            'success': True,
            'keys': {
                'perplexity_api_key': mask_key(perplexity_key) if perplexity_key else '',
                'openrouter_api_key': mask_key(openrouter_key) if openrouter_key else '',
                'openrouter_model': openrouter_model
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/api-keys', methods=['POST'])
@optional_auth
def api_set_api_keys(user_id):
    """Set API keys"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        from core.config import Config
        
        if data.get('perplexity_api_key'):
            settings_manager.set_setting('PERPLEXITY_API_KEY', data['perplexity_api_key'], user_id=user_id)
            Config.set_perplexity_key(data['perplexity_api_key'])
        
        if data.get('openrouter_api_key'):
            settings_manager.set_setting('OPENROUTER_API_KEY', data['openrouter_api_key'], user_id=user_id)
            Config.set_openrouter_key(data['openrouter_api_key'])
        
        if data.get('openrouter_model'):
            settings_manager.set_setting('OPENROUTER_MODEL', data['openrouter_model'], user_id=user_id)
            Config._update_env_file('OPENROUTER_MODEL', data['openrouter_model'])
            Config.OPENROUTER_MODEL = data['openrouter_model']
        
        return jsonify({'success': True, 'message': 'API keys saved successfully'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Database Configuration API
@app.route('/api/settings/database', methods=['GET'])
@optional_auth
def api_get_database_config(user_id):
    """Get database configuration"""
    try:
        from core.config import Config
        
        # Get from persistent storage first, then env
        config = {
            'database_type': settings_manager.get_setting('DATABASE_TYPE', user_id=user_id) or os.getenv('DATABASE_TYPE', 'sqlite'),
            'supabase_url': settings_manager.get_setting('SUPABASE_URL', user_id=user_id) or Config.get('SUPABASE_URL') or os.getenv('SUPABASE_URL', ''),
            'supabase_key': settings_manager.get_setting('SUPABASE_KEY', user_id=user_id) or Config.get('SUPABASE_KEY') or os.getenv('SUPABASE_KEY', '')
        }
        
        # Mask key if present
        if config['supabase_key'] and len(config['supabase_key']) > 8:
            key = config['supabase_key']
            config['supabase_key'] = key[:4] + '*' * (len(key) - 8) + key[-4:]
        
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/database', methods=['POST'])
@optional_auth
def api_set_database_config(user_id):
    """Set database configuration"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        from core.config import Config
        
        if data.get('database_type'):
            settings_manager.set_setting('DATABASE_TYPE', data['database_type'], user_id=user_id)
            Config._update_env_file('DATABASE_TYPE', data['database_type'])
        
        if data.get('supabase_url'):
            settings_manager.set_setting('SUPABASE_URL', data['supabase_url'], user_id=user_id)
            Config._update_env_file('SUPABASE_URL', data['supabase_url'])
        
        if data.get('supabase_key'):
            settings_manager.set_setting('SUPABASE_KEY', data['supabase_key'], user_id=user_id)
            Config._update_env_file('SUPABASE_KEY', data['supabase_key'])
        
        return jsonify({'success': True, 'message': 'Database configuration saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/test-supabase', methods=['POST'])
def api_test_supabase():
    """Test Supabase connection - DYNAMIC"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        url = data.get('url')
        key = data.get('key')
        
        if not url or not key:
            return jsonify({'error': 'URL and Key are required'}), 400
        
        try:
            from core.supabase_client import SupabaseClient
            client = SupabaseClient(url, key)
            connected = client.test_connection()
            
            if connected:
                # Test a simple query
                try:
                    result = client.client.table('users').select('id').limit(1).execute()
                    return jsonify({
                        'success': True, 
                        'message': 'Supabase connection successful',
                        'details': {
                            'url': url.split('//')[1].split('.')[0] if '//' in url else url,
                            'query_test': 'passed',
                            'timestamp': datetime.now().isoformat()
                        }
                    })
                except:
                    return jsonify({
                        'success': True,
                        'message': 'Supabase connection successful (tables may need migration)',
                        'details': {
                            'url': url.split('//')[1].split('.')[0] if '//' in url else url,
                            'timestamp': datetime.now().isoformat()
                        }
                    })
            else:
                return jsonify({'success': False, 'error': 'Connection test failed'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Connection error: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/database-status', methods=['GET'])
def api_get_database_status():
    """Get database connection status - DYNAMIC"""
    try:
        # Get from settings (persistent) or env
        database_type = settings_manager.get_setting('DATABASE_TYPE') or os.getenv('DATABASE_TYPE', 'sqlite')
        connected = False
        error_message = None
        
        if database_type == 'supabase':
            try:
                supabase_url = settings_manager.get_setting('SUPABASE_URL') or os.getenv('SUPABASE_URL')
                supabase_key = settings_manager.get_setting('SUPABASE_KEY') or os.getenv('SUPABASE_KEY')
                
                if supabase_url and supabase_key:
                    from core.supabase_client import SupabaseClient
                    client = SupabaseClient(supabase_url, supabase_key)
                    connected = client.test_connection()
                else:
                    error_message = 'Supabase URL or Key not configured'
            except Exception as e:
                connected = False
                error_message = str(e)
        else:
            # SQLite - always connected if file exists
            try:
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(backend_dir, 'anagha_solution.db')
                connected = os.path.exists(db_path)
            except Exception as e:
                connected = False
                error_message = str(e)
        
        return jsonify({
            'success': True,
            'status': {
                'connected': connected,
                'database_type': database_type,
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Deployment Configuration API
@app.route('/api/settings/deployment', methods=['GET'])
@optional_auth
def api_get_deployment_config(user_id):
    """Get deployment configuration"""
    try:
        from core.config import Config
        
        # Get from persistent storage first
        config = {
            'env_vars': settings_manager.get_setting('DEPLOYMENT_ENV_VARS', user_id=user_id) or Config.get('DEPLOYMENT_ENV_VARS') or '',
            'deployment_url': settings_manager.get_setting('DEPLOYMENT_URL', user_id=user_id) or Config.get('DEPLOYMENT_URL') or ''
        }
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/deployment', methods=['POST'])
@optional_auth
def api_set_deployment_config(user_id):
    """Set deployment configuration"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        from core.config import Config
        
        if data.get('env_vars'):
            settings_manager.set_setting('DEPLOYMENT_ENV_VARS', data['env_vars'], user_id=user_id)
            Config._update_env_file('DEPLOYMENT_ENV_VARS', data['env_vars'])
        
        if data.get('deployment_url'):
            settings_manager.set_setting('DEPLOYMENT_URL', data['deployment_url'], user_id=user_id)
            Config._update_env_file('DEPLOYMENT_URL', data['deployment_url'])
        
        return jsonify({'success': True, 'message': 'Deployment settings saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

# Email Sending Control API
@app.route('/api/email-sender/status', methods=['GET'])
def api_get_sender_status():
    """Get email sender status"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({
                'status': 'stopped',
                'is_sending': False,
                'is_paused': False,
                'message': 'Email sender not initialized'
            })
        
        status = email_sender.get_status()
        return jsonify({
            'status': status,
            'is_sending': email_sender.is_sending,
            'is_paused': getattr(email_sender, 'is_paused', False),
            'message': f'Email sender is {status}'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/email-sender/stop', methods=['POST'])
def api_stop_sender():
    """Stop email sending"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({'error': 'Email sender not initialized'}), 400
        
        email_sender.stop_sending()
        return jsonify({
            'success': True,
            'message': 'Email sending stopped',
            'status': 'stopped'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/email-sender/pause', methods=['POST'])
def api_pause_sender():
    """Pause email sending"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({'error': 'Email sender not initialized'}), 400
        
        if not email_sender.is_sending:
            return jsonify({'error': 'Email sender is not running'}), 400
        
        email_sender.pause_sending()
        return jsonify({
            'success': True,
            'message': 'Email sending paused',
            'status': 'paused'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/email-sender/resume', methods=['POST'])
def api_resume_sender():
    """Resume email sending"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({'error': 'Email sender not initialized'}), 400
        
        # Allow resume if sender is paused (even if is_sending is True)
        # Or if sender exists but is stopped, we can't resume - need to restart
        if not email_sender.is_sending:
            return jsonify({
                'error': 'Email sender is not running. Please start a campaign to begin sending.',
                'code': 'not_running'
            }), 400
        
        # Check if paused
        is_paused = getattr(email_sender, 'is_paused', False)
        if not is_paused:
            return jsonify({
                'error': 'Email sending is not paused',
                'code': 'not_paused'
            }), 400
        
        email_sender.resume_sending()
        return jsonify({
            'success': True,
            'message': 'Email sending resumed',
            'status': 'sending'
        })
    except Exception as e:
        import traceback
        print(f"Error resuming sender: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# API Routes

@app.route('/api/dashboard/stats')
@optional_auth
def api_dashboard_stats(user_id):
    """Get dashboard statistics with observability metrics"""
    try:
        queue_stats = db.get_queue_stats()
        daily_stats = db.get_daily_stats()
        
        total_sent = daily_stats.get('emails_sent', 0)
        delivered = daily_stats.get('emails_delivered', 0)
        bounced = daily_stats.get('emails_bounced', 0)
        spam = daily_stats.get('spam_reports', 0)
        
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
        spam_rate = (spam / total_sent * 100) if total_sent > 0 else 0
        
        recipients = db.get_recipients()
        subscriber_count = len(recipients)
        
        # Get observability metrics
        try:
            obs_metrics = observability_manager.get_dashboard_metrics(user_id)
        except:
            obs_metrics = {}
        
        return jsonify({
            'sent_today': queue_stats.get('sent_today', 0),
            'pending': queue_stats.get('pending', 0),
            'delivery_rate': round(delivery_rate, 1),
            'bounce_rate': round(bounce_rate, 1),
            'spam_rate': round(spam_rate, 1),
            'subscribers': subscriber_count,
            'daily_stats': daily_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaign/create', methods=['POST'])
@require_auth
def api_create_campaign(user_id):
    """Create a new campaign"""
    try:
        # Handle both JSON and form data
        if request.content_type and 'application/json' in request.content_type:
            # JSON request
            data = request.get_json() if request.is_json else {}
            attachments = []
        else:
            # Form data (multipart/form-data for file uploads)
            attachments = request.files.getlist('attachments')
            
            # Convert form data to dict, preserving list values for selected_smtp_servers
            data = {}
            for key in request.form:
                values = request.form.getlist(key)
                if len(values) == 1:
                    data[key] = values[0]
                else:
                    data[key] = values
        
        # Determine message content based on type
        message_type = data.get('message_type', 'html')
        if message_type == 'text':
            # Convert text to HTML for storage
            text_content = data.get('text_content', '')
            html_content = text_content.replace('\n', '<br>')
        else:
            html_content = data.get('html_content', '')
        
        # Check if personalization is enabled
        use_personalization = data.get('use_personalization') == 'on' or data.get('use_personalization') == True
        
        # Create campaign first to get ID
        campaign_id = db.create_campaign(
            name=data.get('name'),
            subject=data.get('subject'),
            sender_name=data.get('sender_name'),
            sender_email=data.get('sender_email'),
            reply_to=None,
            html_content=html_content,
            template_id=data.get('template_id'),
            use_personalization=use_personalization,
            user_id=user_id
        )
        
        # Save attachments if any
        attachment_paths = []
        if attachments:
            # Use absolute path for attachments directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            attachments_dir = os.path.join(script_dir, 'attachments')
            os.makedirs(attachments_dir, exist_ok=True)
            for attachment in attachments:
                if attachment and attachment.filename:
                    filename = f"{campaign_id}_{attachment.filename}"
                    filepath = os.path.join(attachments_dir, filename)
                    attachment.save(filepath)
                    attachment_paths.append(filepath)
        
        # Update campaign with attachment paths if any
        if attachment_paths:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE campaigns SET html_content = html_content || ? 
                WHERE id = ?
            """, (f"\n<!--ATTACHMENTS:{','.join(attachment_paths)}-->", campaign_id))
            conn.commit()
        
        # If sending immediately
        send_now = data.get('send_now')
        send_now_bool = (send_now == 'on' or send_now == True or send_now == 'true' or 
                        str(send_now).lower() == 'true' or send_now == '1')
        
        if send_now_bool:
            recipients = db.get_recipients(user_id=user_id)
            if not recipients:
                return jsonify({'success': True, 'campaign_id': campaign_id, 
                              'warning': 'Campaign created but no recipients found to send to'})
            
            recipient_ids = [r['id'] for r in recipients]
            
            # Get selected SMTP servers from form data
            # IMPORTANT: FormData with multiple values with same key needs special handling
            selected_smtp_servers = None
            
            # Try to get from request.form.getlist first (handles multiple values correctly)
            if request.method == 'POST' and not (request.content_type and 'application/json' in request.content_type):
                selected_servers_list = request.form.getlist('selected_smtp_servers')
                if selected_servers_list:
                    print(f"📋 Got selected_smtp_servers from request.form.getlist: {selected_servers_list}")
                    try:
                        selected_smtp_servers = [int(sid) for sid in selected_servers_list if sid and str(sid).strip()]
                        if len(selected_smtp_servers) > 0:
                            print(f"📧 Using {len(selected_smtp_servers)} selected SMTP servers: {selected_smtp_servers}")
                        else:
                            print("⚠ Warning: selected_servers_list is empty after filtering")
                            selected_smtp_servers = None
                    except (ValueError, TypeError) as e:
                        print(f"✗ Error parsing selected SMTP servers from getlist: {e}")
                        selected_smtp_servers = None
            
            # Fallback to data dict if not found in form
            if not selected_smtp_servers and 'selected_smtp_servers' in data:
                selected_servers = data.get('selected_smtp_servers', [])
                print(f"📋 Fallback: Got selected_smtp_servers from data dict: {selected_servers} (type: {type(selected_servers)})")
                
                # Handle both list and single value
                if isinstance(selected_servers, str):
                    selected_servers = [selected_servers]
                elif not isinstance(selected_servers, list):
                    selected_servers = [selected_servers] if selected_servers else []
                
                if selected_servers:
                    try:
                        selected_smtp_servers = [int(sid) for sid in selected_servers if sid and str(sid).strip()]
                        if len(selected_smtp_servers) > 0:
                            print(f"📧 Using {len(selected_smtp_servers)} selected SMTP servers: {selected_smtp_servers}")
                        else:
                            print("⚠ Warning: selected_servers list is empty after filtering")
                            selected_smtp_servers = None
                    except (ValueError, TypeError) as e:
                        print(f"✗ Error parsing selected SMTP servers: {e}")
                        print(f"   Raw selected_servers: {selected_servers}")
                        import traceback
                        traceback.print_exc()
                        selected_smtp_servers = None
                else:
                    print("⚠ Warning: selected_servers is empty or None")
                    selected_smtp_servers = None
            
            if not selected_smtp_servers:
                print("⚠ No selected SMTP servers found in request")
            
            # Validate selected servers
            if selected_smtp_servers and len(selected_smtp_servers) != 4:
                return jsonify({'error': f'Please select exactly 4 SMTP servers. You selected {len(selected_smtp_servers)}.'}), 400
            
            # Check if SMTP servers are configured
            if not selected_smtp_servers:
                smtp_servers = db.get_smtp_servers()
                if not smtp_servers:
                    return jsonify({'error': 'No SMTP server configured. Please select 4 SMTP servers.'}), 400
            
            # Update campaign status to 'sending'
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            conn.commit()
            
            # Add to queue with round-robin distribution using selected servers
            emails_per_server = 20  # 20 emails per SMTP server
            db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, 
                          emails_per_server=emails_per_server, 
                          selected_smtp_servers=selected_smtp_servers)
            print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
            
            # Start sending in background thread
            import threading
            global email_sender
            
            def start_sender():
                try:
                    global email_sender
                    if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                        # Get delay from settings
                        email_delay = db.get_email_delay()
                        email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                        email_sender.start_sending()
                        print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients ({email_delay} sec delay)")
                    else:
                        print("ℹ Email sender already running, queue will be processed")
                except Exception as e:
                    print(f"✗ Error starting email sender: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start in background thread
            sender_thread = threading.Thread(target=start_sender, daemon=True)
            sender_thread.start()
            
            # Give it a moment to start
            import time
            time.sleep(0.5)
        
        return jsonify({'success': True, 'campaign_id': campaign_id})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error creating campaign: {error_details}")
        return jsonify({'error': str(e), 'details': error_details}), 500

@app.route('/api/recipients/import', methods=['POST'])
@require_auth
def api_import_recipients(user_id):
    """Import recipients from file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save file temporarily
        filename = file.filename
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(script_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, filename)
        file.save(filepath)
        
        # Read file
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Normalize columns
        df.columns = df.columns.str.lower().str.strip()
        
        column_mapping = {
            'email': 'email',
            'e-mail': 'email',
            'email address': 'email',
            'firstname': 'first_name',
            'first name': 'first_name',
            'fname': 'first_name',
            'lastname': 'last_name',
            'last name': 'last_name',
            'lname': 'last_name',
            'company': 'company',
            'city': 'city',
            'phone': 'phone',
            'list': 'list_name',
            'listname': 'list_name'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        if 'email' not in df.columns:
            return jsonify({'error': 'CSV/Excel file must contain an email column'}), 400
        
        recipients = df.to_dict('records')
        count = db.add_recipients(recipients, user_id=user_id)
        
        # Clean up
        os.remove(filepath)
        
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/add', methods=['POST'])
def api_add_recipient():
    """Add a single recipient"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        recipient = {
            'email': data.get('email', '').lower().strip(),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'company': data.get('company', ''),
            'city': data.get('city', ''),
            'phone': data.get('phone', ''),
            'list_name': data.get('list_name', 'default')
        }
        
        count = db.add_recipients([recipient])
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/list', methods=['GET'])
@require_auth
def api_list_recipients(user_id):
    """Get list of all recipients"""
    try:
        list_name = request.args.get('list_name')
        recipients = db.get_recipients(list_name=list_name, user_id=user_id)
        return jsonify({'success': True, 'recipients': recipients})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/delete/<int:recipient_id>', methods=['DELETE'])
def api_delete_recipient(recipient_id):
    """Delete a single recipient"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        # Delete from recipients table
        cursor.execute("DELETE FROM recipients WHERE id = ?", (recipient_id,))
        deleted = cursor.rowcount > 0
        
        # Also remove from campaign_recipients if exists
        cursor.execute("DELETE FROM campaign_recipients WHERE recipient_id = ?", (recipient_id,))
        
        # Remove from email queue
        cursor.execute("DELETE FROM email_queue WHERE recipient_id = ?", (recipient_id,))
        
        conn.commit()
        
        if deleted:
            return jsonify({'success': True, 'message': 'Recipient deleted'})
        else:
            return jsonify({'error': 'Recipient not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/delete/bulk', methods=['POST'])
def api_delete_recipients_bulk():
    """Delete multiple recipients"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        recipient_ids = data.get('recipient_ids', [])
        
        if not recipient_ids:
            return jsonify({'error': 'No recipient IDs provided'}), 400
        
        conn = db.connect()
        cursor = conn.cursor()
        
        # Create placeholders for SQL IN clause
        placeholders = ','.join(['?'] * len(recipient_ids))
        
        # Delete from recipients
        cursor.execute(f"DELETE FROM recipients WHERE id IN ({placeholders})", recipient_ids)
        deleted_count = cursor.rowcount
        
        # Delete from campaign_recipients
        cursor.execute(f"DELETE FROM campaign_recipients WHERE recipient_id IN ({placeholders})", recipient_ids)
        
        # Delete from email queue
        cursor.execute(f"DELETE FROM email_queue WHERE recipient_id IN ({placeholders})", recipient_ids)
        
        conn.commit()
        
        return jsonify({'success': True, 'deleted_count': deleted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/delete/all', methods=['DELETE'])
def api_delete_all_recipients():
    """Delete all recipients"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM recipients")
        count = cursor.fetchone()[0]
        
        # Delete all recipients
        cursor.execute("DELETE FROM recipients")
        
        # Also clear related data
        cursor.execute("DELETE FROM campaign_recipients")
        cursor.execute("DELETE FROM email_queue WHERE recipient_id IS NOT NULL")
        
        conn.commit()
        
        return jsonify({'success': True, 'deleted_count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/add', methods=['POST'])
@require_auth
def api_add_smtp(user_id):
    """Add SMTP server"""
    try:
        # Handle both JSON and form data
        if request.is_json and request.json:
            data = request.json
        else:
            # Try to get JSON from request
            try:
                data = request.get_json(silent=True)
                if not data:
                    # Fall back to form data
                    data = request.form.to_dict()
            except:
                data = request.form.to_dict()
        
        # Debug: Print received data (without password)
        debug_data = {k: v for k, v in data.items() if k != 'password'}
        print(f"📧 Received SMTP add request: {debug_data}")
        
        # Validate required fields
        required_fields = ['name', 'host', 'port', 'username', 'password']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            error_msg = f'Missing required fields: {", ".join(missing_fields)}'
            print(f"✗ Validation error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Decode password if it's URL-encoded (handles special characters like *)
        import urllib.parse
        password = data.get('password')
        if password:
            # Try to decode URL encoding if present
            try:
                password = urllib.parse.unquote(password)
            except:
                pass  # If decoding fails, use as-is
            # Ensure it's a string, not bytes
            if isinstance(password, bytes):
                password = password.decode('utf-8')
        
        use_ssl = data.get('use_ssl', True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.lower() in ('true', 'on', '1')
        
        use_tls = data.get('use_tls', False)
        if isinstance(use_tls, str):
            use_tls = use_tls.lower() in ('true', 'on', '1')
        
        # Get IMAP settings
        imap_host = data.get('imap_host', '')
        imap_port = int(data.get('imap_port', 993)) if data.get('imap_port') else 993
        save_to_sent = data.get('save_to_sent', True)
        if isinstance(save_to_sent, str):
            save_to_sent = save_to_sent.lower() in ('true', 'on', '1')
        
        # Get POP3 settings
        pop3_host = data.get('pop3_host', '')
        pop3_port = int(data.get('pop3_port', 995)) if data.get('pop3_port') else 995
        pop3_ssl = data.get('pop3_ssl', True)
        if isinstance(pop3_ssl, str):
            pop3_ssl = pop3_ssl.lower() in ('true', 'on', '1')
        pop3_leave_on_server = data.get('pop3_leave_on_server', True)
        if isinstance(pop3_leave_on_server, str):
            pop3_leave_on_server = pop3_leave_on_server.lower() in ('true', 'on', '1')
        incoming_protocol = data.get('incoming_protocol', 'imap')
        
        # Detect provider type
        provider_type = data.get('provider_type', 'smtp')
        username = data.get('username', '')
        if not provider_type or provider_type == 'smtp':
            provider_type = rate_limiter.detect_provider(username)
        
        server_id = db.add_smtp_server(
            name=data.get('name'),
            host=data.get('host'),
            port=int(data.get('port')),
            username=username,
            password=password,  # Use decoded password
            use_tls=use_tls,
            use_ssl=use_ssl,
            max_per_hour=int(data.get('max_per_hour', 100)),
            imap_host=imap_host,
            imap_port=imap_port,
            save_to_sent=save_to_sent,
            pop3_host=pop3_host,
            pop3_port=pop3_port,
            pop3_ssl=pop3_ssl,
            pop3_leave_on_server=pop3_leave_on_server,
            incoming_protocol=incoming_protocol,
            user_id=user_id,
            provider_type=provider_type
        )
        
        # If this is the first server or user wants it as default, set it
        set_as_default = data.get('set_as_default', False)
        if set_as_default:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE smtp_servers SET is_default = 0")
            cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
        
        print(f"✅ SMTP server added successfully with ID: {server_id}")
        return jsonify({
            'success': True, 
            'server_id': server_id,
            'message': f'SMTP server "{data.get("name")}" added successfully'
        })
    except ValueError as ve:
        error_msg = f'Invalid data format: {str(ve)}'
        print(f"✗ Validation error: {error_msg}")
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"✗ Error adding SMTP server: {str(e)}")
        print(f"Trace: {error_trace}")
        return jsonify({
            'error': str(e), 
            'message': 'Failed to add SMTP server. Please check all fields and try again.',
            'trace': error_trace
        }), 500

@app.route('/api/pop3/test', methods=['POST'])
def api_test_pop3():
    """Test POP3 connection"""
    try:
        import poplib
        data = request.json if request.is_json else request.form.to_dict()
        
        pop3_host = data.get('pop3_host')
        pop3_port = int(data.get('pop3_port', 995))
        username = data.get('username')
        password = data.get('password')
        use_ssl = data.get('use_ssl', True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.lower() in ('true', 'on', '1')
        
        if not pop3_host or not username or not password:
            return jsonify({'error': 'POP3 host, username and password are required'}), 400
        
        # Decode password if URL-encoded
        import urllib.parse
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass
        
        # Test POP3 connection
        try:
            if use_ssl or pop3_port == 995:
                pop3 = poplib.POP3_SSL(pop3_host, pop3_port, timeout=30)
            else:
                pop3 = poplib.POP3(pop3_host, pop3_port, timeout=30)
            
            # Login
            pop3.user(username)
            pop3.pass_(password)
            
            # Get mailbox stats
            num_messages, mailbox_size = pop3.stat()
            
            pop3.quit()
            
            return jsonify({
                'success': True,
                'message': f'POP3 connection successful! Found {num_messages} emails ({mailbox_size} bytes).'
            })
            
        except Exception as conn_error:
            return jsonify({'error': f'POP3 connection failed: {str(conn_error)}'}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/inbox/fetch-pop3/<int:account_id>')
def api_fetch_pop3(account_id):
    """Fetch emails from POP3 server"""
    try:
        import poplib
        limit = request.args.get('limit', 100, type=int)  # Increased limit to fetch more emails
        
        # Get account config
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        pop3_host = account.get('pop3_host')
        if not pop3_host:
            return jsonify({'error': 'POP3 settings not configured for this account'}), 400
        
        pop3_port = int(account.get('pop3_port', 995))
        username = account.get('username', '')
        password = account.get('password', '')
        use_ssl = account.get('pop3_ssl', 1)
        
        if not username or not password:
            return jsonify({'error': 'Email credentials missing'}), 400
        
        # Connect to POP3 server
        try:
            if use_ssl or pop3_port == 995:
                pop3 = poplib.POP3_SSL(pop3_host, pop3_port, timeout=30)
            else:
                pop3 = poplib.POP3(pop3_host, pop3_port, timeout=30)
            
            pop3.user(username)
            pop3.pass_(password)
        except Exception as conn_error:
            return jsonify({'error': f'Failed to connect to POP3 server: {str(conn_error)}'}), 500
        
        # Get message list
        num_messages, _ = pop3.stat()
        
        # Fetch last N messages (most recent)
        start_msg = max(1, num_messages - limit + 1)
        
        emails = []
        for i in range(num_messages, start_msg - 1, -1):
            try:
                # Get message
                response, lines, octets = pop3.retr(i)
                msg_content = b'\r\n'.join(lines)
                msg = email.message_from_bytes(msg_content)
                
                # Decode subject
                subject = msg.get('Subject', '')
                if subject:
                    decoded_parts = decode_header(subject)
                    subject = ''
                    for part, encoding in decoded_parts:
                        if isinstance(part, bytes):
                            subject += part.decode(encoding or 'utf-8', errors='ignore')
                        else:
                            subject += part
                
                # Decode from
                from_addr = msg.get('From', '')
                if from_addr:
                    decoded_parts = decode_header(from_addr)
                    from_decoded = ''
                    for part, encoding in decoded_parts:
                        if isinstance(part, bytes):
                            from_decoded += part.decode(encoding or 'utf-8', errors='ignore')
                        else:
                            from_decoded += str(part)
                    from_addr = from_decoded
                
                # Get body
                body = ''
                html_body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain' and not body:
                            try:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                body = str(part.get_payload())
                        elif content_type == 'text/html' and not html_body:
                            try:
                                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                html_body = str(part.get_payload())
                else:
                    content_type = msg.get_content_type()
                    payload = msg.get_payload(decode=True)
                    if payload:
                        try:
                            content = payload.decode('utf-8', errors='ignore')
                            if content_type == 'text/html':
                                html_body = content
                            else:
                                body = content
                        except:
                            body = str(msg.get_payload())
                
                emails.append({
                    'uid': str(i),
                    'subject': subject,
                    'from': from_addr,
                    'to': msg.get('To', ''),
                    'date': msg.get('Date', ''),
                    'body': body[:1000] if body else '',
                    'html': html_body[:5000] if html_body else '',
                    'unread': True
                })
                
            except Exception as email_error:
                print(f"Error processing POP3 message {i}: {email_error}")
                continue
        
        pop3.quit()
        
        return jsonify({
            'success': True,
            'emails': emails,
            'total': len(emails),
            'protocol': 'POP3'
        })
        
    except Exception as e:
        import traceback
        print(f"Error fetching POP3 emails: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/imap/test', methods=['POST'])
def api_test_imap():
    """Test IMAP connection"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        imap_host = data.get('imap_host')
        imap_port = int(data.get('imap_port', 993))
        username = data.get('username')
        password = data.get('password')
        
        if not imap_host or not username or not password:
            return jsonify({'error': 'IMAP host, username and password are required'}), 400
        
        # Decode password if URL-encoded
        import urllib.parse
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass
        
        # Test IMAP connection
        try:
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass
            
            # Login
            imap.login(username, password)
            
            # Try to select INBOX
            status, _ = imap.select('INBOX', readonly=True)
            if status != 'OK':
                imap.logout()
                return jsonify({'error': 'Could not access INBOX'}), 500
            
            # Get email count
            status, messages = imap.search(None, 'ALL')
            email_count = len(messages[0].split()) if status == 'OK' and messages[0] else 0
            
            imap.logout()
            
            return jsonify({
                'success': True,
                'message': f'IMAP connection successful! Found {email_count} emails in INBOX.'
            })
            
        except Exception as conn_error:
            return jsonify({'error': f'IMAP connection failed: {str(conn_error)}'}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/smtp/test', methods=['POST'])
def api_test_smtp():
    """Test SMTP connection"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        import smtplib
        import urllib.parse
        
        host = data.get('host')
        port = int(data.get('port'))
        username = data.get('username')
        password = data.get('password')
        
        # Decode password if it's URL-encoded (handles special characters like *)
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass  # If decoding fails, use as-is
            # Ensure it's a string, not bytes
            if isinstance(password, bytes):
                password = password.decode('utf-8')
        
        use_ssl = data.get('use_ssl', True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.lower() in ('true', 'on', '1')
        use_tls = data.get('use_tls', False)
        if isinstance(use_tls, str):
            use_tls = use_tls.lower() in ('true', 'on', '1')
        
        # Test connection with timeout
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=30)
            else:
                server = smtplib.SMTP(host, port, timeout=30)
                if use_tls:
                    server.starttls()
            
            # Test login
            server.login(username, password)
            
            # Test sending (NOOP command)
            server.noop()
            
            server.quit()
            
            return jsonify({'success': True, 'message': 'Connection test successful!'})
        except smtplib.SMTPConnectError as e:
            return jsonify({'error': f'Connection failed: {str(e)}. Check host and port.'}), 500
        except smtplib.SMTPAuthenticationError as e:
            return jsonify({'error': f'Authentication failed: {str(e)}. Check username and password.'}), 500
        except smtplib.SMTPException as e:
            return jsonify({'error': f'SMTP error: {str(e)}'}), 500
        except Exception as e:
            return jsonify({'error': f'Connection error: {str(e)}'}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': f'Test failed: {str(e)}', 'details': traceback.format_exc()}), 500

@app.route('/api/smtp/update/<int:server_id>', methods=['POST', 'PUT'])
def api_update_smtp(server_id):
    """Update existing SMTP server settings"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        # Check if using Supabase
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if server exists
            result = db.supabase.client.table('smtp_servers').select('id').eq('id', server_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Server not found'}), 404
            
            # Build update data
            update_data = {}
            
            if 'name' in data:
                update_data['name'] = data['name']
            if 'host' in data:
                update_data['host'] = data['host']
            if 'port' in data:
                update_data['port'] = int(data['port'])
            if 'username' in data:
                update_data['username'] = data['username']
            if 'password' in data and data['password']:
                import urllib.parse
                password = data['password']
                try:
                    password = urllib.parse.unquote(password)
                except:
                    pass
                update_data['password'] = password
            if 'use_ssl' in data:
                use_ssl = data['use_ssl']
                if isinstance(use_ssl, str):
                    use_ssl = use_ssl.lower() in ('true', 'on', '1')
                update_data['use_ssl'] = 1 if use_ssl else 0
            if 'use_tls' in data:
                use_tls = data['use_tls']
                if isinstance(use_tls, str):
                    use_tls = use_tls.lower() in ('true', 'on', '1')
                update_data['use_tls'] = 1 if use_tls else 0
            if 'imap_host' in data:
                update_data['imap_host'] = data['imap_host']
            if 'imap_port' in data:
                update_data['imap_port'] = int(data['imap_port']) if data['imap_port'] else 993
            if 'save_to_sent' in data:
                save_to_sent = data['save_to_sent']
                if isinstance(save_to_sent, str):
                    save_to_sent = save_to_sent.lower() in ('true', 'on', '1')
                update_data['save_to_sent'] = 1 if save_to_sent else 0
            if 'max_per_hour' in data:
                update_data['max_per_hour'] = int(data['max_per_hour'])
            if 'pop3_host' in data:
                update_data['pop3_host'] = data['pop3_host']
            if 'pop3_port' in data:
                update_data['pop3_port'] = int(data['pop3_port']) if data['pop3_port'] else 995
            if 'pop3_ssl' in data:
                pop3_ssl = data['pop3_ssl']
                if isinstance(pop3_ssl, str):
                    pop3_ssl = pop3_ssl.lower() in ('true', 'on', '1')
                update_data['pop3_ssl'] = 1 if pop3_ssl else 0
            if 'pop3_leave_on_server' in data:
                pop3_leave = data['pop3_leave_on_server']
                if isinstance(pop3_leave, str):
                    pop3_leave = pop3_leave.lower() in ('true', 'on', '1')
                update_data['pop3_leave_on_server'] = 1 if pop3_leave else 0
            if 'incoming_protocol' in data:
                update_data['incoming_protocol'] = data['incoming_protocol']
            
            if not update_data:
                return jsonify({'error': 'No fields to update'}), 400
            
            # Execute update
            db.supabase.client.table('smtp_servers').update(update_data).eq('id', server_id).execute()
            
            return jsonify({'success': True, 'message': 'Email account updated successfully'})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Check if server exists
            cursor.execute("SELECT id FROM smtp_servers WHERE id = ?", (server_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Server not found'}), 404
            
            # Build update query dynamically based on provided fields
            updates = []
            params = []
            
            if 'name' in data:
                updates.append("name = ?")
                params.append(data['name'])
            if 'host' in data:
                updates.append("host = ?")
                params.append(data['host'])
            if 'port' in data:
                updates.append("port = ?")
                params.append(int(data['port']))
            if 'username' in data:
                updates.append("username = ?")
                params.append(data['username'])
            if 'password' in data and data['password']:
                import urllib.parse
                password = data['password']
                try:
                    password = urllib.parse.unquote(password)
                except:
                    pass
                updates.append("password = ?")
                params.append(password)
            if 'use_ssl' in data:
                use_ssl = data['use_ssl']
                if isinstance(use_ssl, str):
                    use_ssl = use_ssl.lower() in ('true', 'on', '1')
                updates.append("use_ssl = ?")
                params.append(1 if use_ssl else 0)
            if 'use_tls' in data:
                use_tls = data['use_tls']
                if isinstance(use_tls, str):
                    use_tls = use_tls.lower() in ('true', 'on', '1')
                updates.append("use_tls = ?")
                params.append(1 if use_tls else 0)
            if 'imap_host' in data:
                updates.append("imap_host = ?")
                params.append(data['imap_host'])
            if 'imap_port' in data:
                updates.append("imap_port = ?")
                params.append(int(data['imap_port']) if data['imap_port'] else 993)
            if 'save_to_sent' in data:
                save_to_sent = data['save_to_sent']
                if isinstance(save_to_sent, str):
                    save_to_sent = save_to_sent.lower() in ('true', 'on', '1')
                updates.append("save_to_sent = ?")
                params.append(1 if save_to_sent else 0)
            if 'max_per_hour' in data:
                updates.append("max_per_hour = ?")
                params.append(int(data['max_per_hour']))
            
            # POP3 settings
            if 'pop3_host' in data:
                updates.append("pop3_host = ?")
                params.append(data['pop3_host'])
            if 'pop3_port' in data:
                updates.append("pop3_port = ?")
                params.append(int(data['pop3_port']) if data['pop3_port'] else 995)
            if 'pop3_ssl' in data:
                pop3_ssl = data['pop3_ssl']
                if isinstance(pop3_ssl, str):
                    pop3_ssl = pop3_ssl.lower() in ('true', 'on', '1')
                updates.append("pop3_ssl = ?")
                params.append(1 if pop3_ssl else 0)
            if 'pop3_leave_on_server' in data:
                pop3_leave = data['pop3_leave_on_server']
                if isinstance(pop3_leave, str):
                    pop3_leave = pop3_leave.lower() in ('true', 'on', '1')
                updates.append("pop3_leave_on_server = ?")
                params.append(1 if pop3_leave else 0)
            if 'incoming_protocol' in data:
                updates.append("incoming_protocol = ?")
                params.append(data['incoming_protocol'])
            
            if not updates:
                return jsonify({'error': 'No fields to update'}), 400
            
            # Add server_id to params
            params.append(server_id)
            
            # Execute update
            query = f"UPDATE smtp_servers SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Email account updated successfully'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/smtp/list', methods=['GET'])
@require_auth
def api_list_smtp(user_id):
    """Get list of all SMTP servers"""
    try:
        servers = db.get_smtp_servers(active_only=False, user_id=user_id)
        # Get default server ID
        default_server_id = None
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            default_result = db.supabase.client.table('smtp_servers').select('id').eq('is_default', 1).limit(1).execute()
            if default_result.data and len(default_result.data) > 0:
                default_server_id = default_result.data[0]['id']
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM smtp_servers WHERE is_default = 1 LIMIT 1")
            default_row = cursor.fetchone()
            default_server_id = default_row[0] if default_row else None
        
        # If no default, set first active server as default
        if not default_server_id and servers:
            for server in servers:
                if server.get('is_active'):
                    default_server_id = server['id']
                    if hasattr(db, 'use_supabase') and db.use_supabase:
                        # Use Supabase
                        db.supabase.client.table('smtp_servers').update({'is_default': 1}).eq('id', default_server_id).execute()
                    else:
                        # SQLite
                        conn = db.connect()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (default_server_id,))
                        conn.commit()
                    break
        
        return jsonify({'success': True, 'servers': servers, 'default_server_id': default_server_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/set-default/<int:server_id>', methods=['POST'])
def api_set_default_smtp(server_id):
    """Set default SMTP server for sending"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            # First, get all servers with is_default = 1 and unset them
            default_servers = db.supabase.client.table('smtp_servers').select('id').eq('is_default', 1).execute()
            if default_servers.data:
                for server in default_servers.data:
                    db.supabase.client.table('smtp_servers').update({'is_default': 0}).eq('id', server['id']).execute()
            
            # Set new default
            result = db.supabase.client.table('smtp_servers').update({'is_default': 1}).eq('id', server_id).execute()
            
            if result.data and len(result.data) > 0:
                return jsonify({'success': True, 'message': 'Default SMTP server updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Unset all defaults
            cursor.execute("UPDATE smtp_servers SET is_default = 0")
            
            # Set new default
            cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True, 'message': 'Default SMTP server updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/get/<int:server_id>', methods=['GET'])
def api_get_smtp(server_id):
    """Get SMTP server configuration"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', server_id).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                return jsonify({'success': True, 'server': server})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (server_id,))
            row = cursor.fetchone()
            
            if row:
                server = dict(row)
                return jsonify({'success': True, 'server': server})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/delete/<int:server_id>', methods=['DELETE'])
def api_delete_smtp(server_id):
    """Delete SMTP server"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            result = db.supabase.client.table('smtp_servers').delete().eq('id', server_id).execute()
            
            if result.data and len(result.data) > 0:
                return jsonify({'success': True, 'message': 'SMTP server deleted'})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM smtp_servers WHERE id = ?", (server_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True, 'message': 'SMTP server deleted'})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/toggle/<int:server_id>', methods=['POST'])
def api_toggle_smtp(server_id):
    """Toggle SMTP server active status"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        is_active = data.get('is_active', 1)
        if isinstance(is_active, str):
            is_active = 1 if is_active.lower() in ('true', 'on', '1') else 0
        
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            result = db.supabase.client.table('smtp_servers').update({'is_active': is_active}).eq('id', server_id).execute()
            
            if result.data and len(result.data) > 0:
                return jsonify({'success': True, 'message': 'Server status updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE smtp_servers SET is_active = ? WHERE id = ?", (is_active, server_id))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True, 'message': 'Server status updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/save', methods=['POST'])
def api_save_template():
    """Save template"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
        
        # Validate required fields
        name = data.get('name', '').strip()
        category = data.get('category', 'Other').strip() or 'Other'
        html_content = data.get('html_content', '').strip()
        
        if not name:
            return jsonify({'error': 'Template name is required'}), 400
        
        if not html_content:
            return jsonify({'error': 'HTML content is required'}), 400
        
        template_id = db.save_template(
            name=name,
            category=category,
            html_content=html_content
        )
        return jsonify({'success': True, 'template_id': template_id, 'message': 'Template saved successfully'})
    except Exception as e:
        import traceback
        print(f"Error saving template: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/list', methods=['GET'])
def api_list_templates():
    """Get all templates"""
    try:
        category = request.args.get('category')
        templates = db.get_templates(category=category)
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/<int:template_id>', methods=['GET'])
def api_get_template(template_id):
    """Get a single template"""
    try:
        templates = db.get_templates()
        template = next((t for t in templates if t['id'] == template_id), None)
        if template:
            return jsonify({'success': True, 'template': template})
        else:
            return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/delete/<int:template_id>', methods=['DELETE'])
def api_delete_template(template_id):
    """Delete a template"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Template deleted'})
        else:
            return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns')
@require_auth
def api_get_campaigns(user_id):
    """Get all campaigns"""
    try:
        campaigns = db.get_campaigns(user_id=user_id)
        return jsonify({'campaigns': campaigns})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/delete/<int:campaign_id>', methods=['DELETE'])
def api_delete_campaign(campaign_id):
    """Delete a single campaign"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        # Delete campaign and related data
        cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        deleted = cursor.rowcount > 0
        
        # Delete related queue items
        cursor.execute("DELETE FROM email_queue WHERE campaign_id = ?", (campaign_id,))
        
        # Delete campaign recipients
        cursor.execute("DELETE FROM campaign_recipients WHERE campaign_id = ?", (campaign_id,))
        
        # Delete tracking data
        cursor.execute("DELETE FROM tracking WHERE campaign_id = ?", (campaign_id,))
        
        conn.commit()
        
        if deleted:
            return jsonify({'success': True, 'message': 'Campaign deleted'})
        else:
            return jsonify({'error': 'Campaign not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/delete/bulk', methods=['POST'])
def api_delete_campaigns_bulk():
    """Delete multiple campaigns"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        campaign_ids = data.get('campaign_ids', [])
        
        if not campaign_ids:
            return jsonify({'error': 'No campaign IDs provided'}), 400
        
        conn = db.connect()
        cursor = conn.cursor()
        
        # Create placeholders for SQL IN clause
        placeholders = ','.join(['?'] * len(campaign_ids))
        
        # Delete campaigns
        cursor.execute(f"DELETE FROM campaigns WHERE id IN ({placeholders})", campaign_ids)
        deleted_count = cursor.rowcount
        
        # Delete related queue items
        cursor.execute(f"DELETE FROM email_queue WHERE campaign_id IN ({placeholders})", campaign_ids)
        
        # Delete campaign recipients
        cursor.execute(f"DELETE FROM campaign_recipients WHERE campaign_id IN ({placeholders})", campaign_ids)
        
        # Delete tracking data
        cursor.execute(f"DELETE FROM tracking WHERE campaign_id IN ({placeholders})", campaign_ids)
        
        conn.commit()
        
        return jsonify({'success': True, 'deleted_count': deleted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/delete/drafts', methods=['DELETE'])
def api_delete_draft_campaigns():
    """Delete all draft campaigns"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'draft'")
        count = cursor.fetchone()[0]
        
        # Get draft campaign IDs
        cursor.execute("SELECT id FROM campaigns WHERE status = 'draft'")
        draft_ids = [row[0] for row in cursor.fetchall()]
        
        if not draft_ids:
            return jsonify({'success': True, 'deleted_count': 0, 'message': 'No draft campaigns found'})
        
        # Create placeholders
        placeholders = ','.join(['?'] * len(draft_ids))
        
        # Delete campaigns
        cursor.execute(f"DELETE FROM campaigns WHERE id IN ({placeholders})", draft_ids)
        
        # Delete related queue items
        cursor.execute(f"DELETE FROM email_queue WHERE campaign_id IN ({placeholders})", draft_ids)
        
        # Delete campaign recipients
        cursor.execute(f"DELETE FROM campaign_recipients WHERE campaign_id IN ({placeholders})", draft_ids)
        
        # Delete tracking data
        cursor.execute(f"DELETE FROM tracking WHERE campaign_id IN ({placeholders})", draft_ids)
        
        conn.commit()
        
        return jsonify({'success': True, 'deleted_count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/send/<int:campaign_id>', methods=['POST'])
def api_send_campaign(campaign_id):
    """Send a draft campaign"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        # Get campaign
        cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        campaign = dict(row)
        
        # Check if campaign is draft
        if campaign['status'] != 'draft':
            return jsonify({'error': f'Campaign is not a draft (status: {campaign["status"]})'}), 400
        
        # Get recipients
        recipients = db.get_recipients()
        if not recipients:
            return jsonify({'error': 'No recipients found'}), 400
        
        recipient_ids = [r['id'] for r in recipients]
        
        # Get default SMTP server
        default_server = db.get_default_smtp_server()
        if not default_server:
            smtp_servers = db.get_smtp_servers()
            if not smtp_servers:
                return jsonify({'error': 'No SMTP server configured'}), 400
            smtp_id = smtp_servers[0]['id']
        else:
            smtp_id = default_server['id']
        
        # Update campaign status to 'sending'
        cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
        conn.commit()
        
        # Add to queue with round-robin distribution (20 emails per SMTP server)
        emails_per_server = 20  # 20 emails per SMTP server
        db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, emails_per_server=emails_per_server)
        print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
        
        # Start sending in background thread
        import threading
        global email_sender
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients ({email_delay} sec delay)")
                else:
                    print("ℹ Email sender already running, queue will be processed")
            except Exception as e:
                print(f"✗ Error starting email sender: {e}")
                import traceback
                traceback.print_exc()
        
        # Start in background thread
        sender_thread = threading.Thread(target=start_sender, daemon=True)
        sender_thread.start()
        
        return jsonify({'success': True, 'message': f'Campaign queued for sending to {len(recipient_ids)} recipients'})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error sending campaign: {error_details}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/send/bulk', methods=['POST'])
def api_send_campaigns_bulk():
    """Send multiple draft campaigns"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        campaign_ids = data.get('campaign_ids', [])
        
        if not campaign_ids:
            return jsonify({'error': 'No campaign IDs provided'}), 400
        
        conn = db.connect()
        cursor = conn.cursor()
        
        # Verify all campaigns are drafts
        placeholders = ','.join(['?'] * len(campaign_ids))
        cursor.execute(f"SELECT id, status FROM campaigns WHERE id IN ({placeholders})", campaign_ids)
        campaigns = cursor.fetchall()
        
        if len(campaigns) != len(campaign_ids):
            return jsonify({'error': 'Some campaigns not found'}), 404
        
        # Check all are drafts
        non_drafts = [c[0] for c in campaigns if c[1] != 'draft']
        if non_drafts:
            return jsonify({'error': f'Campaigns {non_drafts} are not drafts'}), 400
        
        # Get recipients
        recipients = db.get_recipients()
        if not recipients:
            return jsonify({'error': 'No recipients found'}), 400
        
        recipient_ids = [r['id'] for r in recipients]
        
        # Get default SMTP server
        default_server = db.get_default_smtp_server()
        if not default_server:
            smtp_servers = db.get_smtp_servers()
            if not smtp_servers:
                return jsonify({'error': 'No SMTP server configured'}), 400
            smtp_id = smtp_servers[0]['id']
        else:
            smtp_id = default_server['id']
        
        # Update all campaigns to 'sending' and add to queue with round-robin distribution
        emails_per_server = 20  # 20 emails per SMTP server
        sent_count = 0
        for campaign_id in campaign_ids:
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, emails_per_server=emails_per_server)
            sent_count += 1
            print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
        
        conn.commit()
        
        # Start sending in background thread
        import threading
        global email_sender
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for {sent_count} campaigns with {len(recipient_ids)} recipients each ({email_delay} sec delay)")
                else:
                    print("ℹ Email sender already running, queue will be processed")
            except Exception as e:
                print(f"✗ Error starting email sender: {e}")
                import traceback
                traceback.print_exc()
        
        # Start in background thread
        sender_thread = threading.Thread(target=start_sender, daemon=True)
        sender_thread.start()
        
        return jsonify({'success': True, 'sent_count': sent_count, 'message': f'{sent_count} campaign(s) queued for sending'})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error sending campaigns: {error_details}")
        return jsonify({'error': str(e)}), 500

# Lead Scraping API Routes
@app.route('/api/leads/scrape', methods=['POST'])
@require_auth
def api_scrape_leads(user_id):
    """Start a lead scraping job"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        icp_description = data.get('icp_description', '')
        
        if not icp_description:
            return jsonify({'error': 'ICP description is required'}), 400
        
        from core.lead_scraper import LeadScraper
        scraper = LeadScraper(db)
        
        # Create job record first to get job_id
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            job_id = db.create_scraping_job(icp_description, user_id)
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lead_scraping_jobs (icp_description, status, user_id)
                VALUES (?, 'running', ?)
            """, (icp_description, user_id))
            job_id = cursor.lastrowid
            conn.commit()
        
        # Use Celery task for background processing
        try:
            from core.tasks import scrape_leads_task
            scrape_leads_task.delay(icp_description, job_id, user_id)
        except:
            # Fallback to threading if Celery not available
            import threading
            def run_scraping():
                try:
                    result = scraper.run_full_scraping_job(icp_description, job_id=job_id)
                    print(f"Scraping job {result.get('job_id')} completed: {result.get('leads_found')} leads found, {result.get('verified_leads')} verified")
                except Exception as e:
                    print(f"Error in scraping job: {e}")
                    import traceback
                    traceback.print_exc()
                    # Update job status to failed
                    if hasattr(db, 'use_supabase') and db.use_supabase:
                        db.update_scraping_job(job_id, status='failed')
                    else:
                        conn = db.connect()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE lead_scraping_jobs 
                            SET status = 'failed'
                            WHERE id = ?
                        """, (job_id,))
                        conn.commit()
            
            thread = threading.Thread(target=run_scraping, daemon=True)
            thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Lead scraping job started. Check leads page for results.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/list', methods=['GET'])
@require_auth
def api_list_leads(user_id):
    """Get list of leads"""
    try:
        verified_only = request.args.get('verified_only', 'false').lower() == 'true'
        company_name = request.args.get('company_name', '')
        
        leads = db.get_leads(verified_only=verified_only, company_name=company_name, user_id=user_id)
        return jsonify({'success': True, 'leads': leads, 'count': len(leads)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/add', methods=['POST'])
@require_auth
def api_add_lead(user_id):
    """Add a single lead"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        lead_id = db.add_lead(
            name=data.get('name', ''),
            company_name=data.get('company_name', ''),
            domain=data.get('domain', ''),
            email=data.get('email', ''),
            title=data.get('title', ''),
            source=data.get('source', 'manual'),
            user_id=user_id
        )
        
        return jsonify({'success': True, 'lead_id': lead_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/verify/<int:lead_id>', methods=['POST'])
@optional_auth
def api_verify_lead(user_id, lead_id):
    """Verify a lead's email"""
    try:
        from core.email_verifier import EmailVerifier
        verifier = EmailVerifier(db)
        
        # Verify user owns this lead
        if user_id:
            # Check if using Supabase
            if hasattr(db, 'use_supabase') and db.use_supabase:
                lead = db.get_lead_by_id(lead_id)
                if not lead:
                    return jsonify({'error': 'Lead not found'}), 404
                if lead.get('user_id') != user_id:
                    return jsonify({'error': 'Unauthorized'}), 403
            else:
                # SQLite
                conn = db.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM leads WHERE id = ?", (lead_id,))
                row = cursor.fetchone()
                if row and row[0] != user_id:
                    return jsonify({'error': 'Unauthorized'}), 403
        
        result = verifier.verify_lead_email(lead_id)
        
        # If verified, add to recipients
        if result.get('is_valid') and user_id:
            try:
                lead = db.get_lead_by_id(lead_id)
                if lead and lead.get('email'):
                    # Add to recipients using add_recipients (plural) method
                    name = lead.get('name', '')
                    name_parts = name.split(maxsplit=1) if name else []
                    first_name = name_parts[0] if len(name_parts) > 0 else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    db.add_recipients([{
                        'email': lead['email'],
                        'first_name': first_name,
                        'last_name': last_name,
                        'company': lead.get('company_name', ''),
                        'list_name': 'verified_leads'
                    }], user_id=user_id)
            except Exception as e:
                print(f"Error adding lead to recipients: {e}")
        
        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"Verify lead error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/verify/batch', methods=['POST'])
@optional_auth
def api_verify_leads_batch(user_id):
    """Verify multiple leads"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        lead_ids = data.get('lead_ids', [])
        
        if not lead_ids:
            return jsonify({'error': 'No lead IDs provided'}), 400
        
        # Verify user owns these leads
        if user_id:
            # Check if using Supabase
            if hasattr(db, 'use_supabase') and db.use_supabase:
                # Get all leads and filter by user_id
                valid_ids = []
                for lead_id in lead_ids:
                    lead = db.get_lead_by_id(lead_id)
                    if lead and lead.get('user_id') == user_id:
                        valid_ids.append(lead_id)
                if len(valid_ids) != len(lead_ids):
                    return jsonify({'error': 'Some leads not found or unauthorized'}), 403
                lead_ids = valid_ids
            else:
                # SQLite
                conn = db.connect()
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(lead_ids))
                cursor.execute(f"SELECT id FROM leads WHERE id IN ({placeholders}) AND user_id = ?", lead_ids + [user_id])
                valid_ids = [row[0] for row in cursor.fetchall()]
                if len(valid_ids) != len(lead_ids):
                    return jsonify({'error': 'Some leads not found or unauthorized'}), 403
                lead_ids = valid_ids
        
        from core.email_verifier import EmailVerifier
        verifier = EmailVerifier(db)
        
        results = verifier.verify_batch_leads(lead_ids, delay=1.0)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        import traceback
        print(f"Batch verify error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/scraping-jobs', methods=['GET'])
@optional_auth
def api_get_scraping_jobs(user_id):
    """Get all scraping jobs"""
    try:
        jobs = db.get_scraping_jobs(user_id=user_id)
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/scraping-job/<int:job_id>/status', methods=['GET'])
def api_get_scraping_job_status(job_id):
    """Get real-time status of a scraping job"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase methods
            job = db.get_scraping_job(job_id)
            if not job:
                return jsonify({'error': 'Job not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lead_scraping_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Job not found'}), 404
            
            job = dict(row)
        
        return jsonify({
            'success': True,
            'job': {
                'id': job['id'],
                'status': job.get('status', ''),
                'current_step': job.get('current_step', ''),
                'progress_percent': job.get('progress_percent', 0),
                'companies_found': job.get('companies_found', 0),
                'leads_found': job.get('leads_found', 0),
                'verified_leads': job.get('verified_leads', 0)
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/recent', methods=['GET'])
@optional_auth
def api_get_recent_leads(user_id):
    """Get recently added/updated leads for real-time updates"""
    try:
        limit = request.args.get('limit', 50, type=int)
        job_id = request.args.get('job_id', type=int)
        
        conn = db.connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if job_id:
            query += " AND source = ?"
            params.append(f'scraper_job_{job_id}')
        
        query += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        leads = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({'success': True, 'leads': leads, 'count': len(leads)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Inbox Monitoring API Routes
@app.route('/api/inbox/monitor/<int:account_id>', methods=['POST'])
def api_monitor_inbox(account_id):
    """Monitor inbox for responses and follow-ups"""
    try:
        from core.inbox_monitor import InboxMonitor
        monitor = InboxMonitor(db)
        
        result = monitor.monitor_and_update(account_id)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/responses', methods=['GET'])
def api_get_responses():
    """Get email responses"""
    try:
        hot_leads_only = request.args.get('hot_leads_only', 'false').lower() == 'true'
        responses = db.get_email_responses(hot_leads_only=hot_leads_only)
        return jsonify({'success': True, 'responses': responses, 'count': len(responses)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/follow-ups', methods=['GET'])
def api_get_follow_ups():
    """Get emails that need follow-ups"""
    try:
        follow_ups = db.get_follow_ups_needed()
        return jsonify({'success': True, 'follow_ups': follow_ups, 'count': len(follow_ups)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Personalization API Routes
@app.route('/api/personalize', methods=['POST'])
def api_personalize_email():
    """Personalize an email template"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        template = data.get('template', '')
        name = data.get('name', '')
        company = data.get('company', '')
        context = data.get('context', '')
        
        if not template:
            return jsonify({'error': 'Template is required'}), 400
        
        from core.personalization import EmailPersonalizer
        personalizer = EmailPersonalizer()
        
        personalized = personalizer.personalize_email(template, name, company, context)
        
        return jsonify({
            'success': True,
            'personalized_content': personalized
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GDPR API Routes
@app.route('/api/gdpr/request-access', methods=['POST'])
@require_auth
def api_request_data_access(user_id):
    """Request data access (GDPR)"""
    try:
        user = auth_manager.get_user(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # In production, send email with data export
        return jsonify({
            'success': True,
            'message': 'Data access request received. You will receive an email with your data.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/request-deletion', methods=['POST'])
@require_auth
def api_request_data_deletion(user_id):
    """Request data deletion (GDPR)"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET is_active = 0,
                subscription_status = 'canceled'
            WHERE id = ?
        """, (user_id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Account marked for deletion. Data will be permanently deleted in 30 days.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/export-data', methods=['GET'])
@require_auth
def api_export_data(user_id):
    """Export user data (GDPR)"""
    try:
        user = auth_manager.get_user(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = {
            'user': {k: v for k, v in user.items() if k != 'password_hash'},
            'campaigns': db.get_campaigns(user_id=user_id),
            'leads': db.get_leads(user_id=user_id),
            'recipients': db.get_recipients(user_id=user_id),
            'smtp_servers': db.get_smtp_servers(user_id=user_id, active_only=False)
        }
        
        # Remove passwords
        for server in data['smtp_servers']:
            server.pop('password', None)
        
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Stripe Configuration API
@app.route('/api/settings/stripe', methods=['GET'])
@optional_auth
def api_get_stripe_config(user_id):
    """Get Stripe configuration"""
    try:
        from core.config import Config
        
        config = {
            'stripe_secret_key': settings_manager.get_setting('STRIPE_SECRET_KEY', user_id=user_id) or os.getenv('STRIPE_SECRET_KEY', ''),
            'stripe_publishable_key': settings_manager.get_setting('STRIPE_PUBLISHABLE_KEY', user_id=user_id) or os.getenv('STRIPE_PUBLISHABLE_KEY', ''),
            'subscription_plan': settings_manager.get_setting('SUBSCRIPTION_PLAN', user_id=user_id) or 'free'
        }
        
        # Mask secret key
        if config['stripe_secret_key']:
            key = config['stripe_secret_key']
            config['stripe_secret_key'] = key[:4] + '*' * (len(key) - 8) + key[-4:] if len(key) > 8 else '****'
        
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/stripe', methods=['POST'])
@optional_auth
def api_set_stripe_config(user_id):
    """Set Stripe configuration"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        from core.config import Config
        
        if data.get('stripe_secret_key'):
            settings_manager.set_setting('STRIPE_SECRET_KEY', data['stripe_secret_key'], user_id=user_id)
            Config._update_env_file('STRIPE_SECRET_KEY', data['stripe_secret_key'])
        
        if data.get('stripe_publishable_key'):
            settings_manager.set_setting('STRIPE_PUBLISHABLE_KEY', data['stripe_publishable_key'], user_id=user_id)
            Config._update_env_file('STRIPE_PUBLISHABLE_KEY', data['stripe_publishable_key'])
        
        if data.get('subscription_plan'):
            settings_manager.set_setting('SUBSCRIPTION_PLAN', data['subscription_plan'], user_id=user_id)
        
        return jsonify({'success': True, 'message': 'Stripe configuration saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/subscription-info', methods=['GET'])
@require_auth
def api_get_subscription_info(user_id):
    """Get subscription information"""
    try:
        info = billing_manager.get_subscription_info(user_id)
        return jsonify({'success': True, 'subscription': info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/test-redis', methods=['POST'])
@optional_auth
def api_test_redis(user_id):
    """Test Redis connection - DYNAMIC"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        redis_url = data.get('redis_url') or settings_manager.get_setting('REDIS_URL', user_id=user_id) or os.getenv('REDIS_URL')
        
        if not redis_url:
            return jsonify({'success': False, 'error': 'Redis URL not configured'})
        
        try:
            import redis
            # Handle SSL connections (Upstash, etc.)
            ssl_params = {}
            if 'rediss://' in redis_url or 'ssl=true' in redis_url.lower():
                # For SSL connections, disable certificate verification if needed
                # Upstash and some providers use self-signed certificates
                ssl_params = {
                    'ssl_cert_reqs': None,  # Disable certificate verification
                    'ssl_check_hostname': False
                }
            
            r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5, **ssl_params)
            r.ping()
            
            # Test basic operations
            test_key = 'anagha_test_connection'
            r.set(test_key, 'test', ex=10)
            value = r.get(test_key)
            r.delete(test_key)
            
            return jsonify({
                'success': True, 
                'message': 'Redis connection successful',
                'details': {
                    'host': redis_url.split('@')[-1].split('/')[0] if '@' in redis_url else redis_url.split('/')[-1],
                    'test_operation': 'passed',
                    'timestamp': datetime.now().isoformat()
                }
            })
        except redis.ConnectionError as e:
            return jsonify({'success': False, 'error': f'Redis connection failed: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Redis error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/redis-status', methods=['GET'])
@optional_auth
def api_get_redis_status(user_id):
    """Get Redis connection status - DYNAMIC"""
    try:
        redis_url = settings_manager.get_setting('REDIS_URL', user_id=user_id) or os.getenv('REDIS_URL')
        connected = False
        error_message = None
        
        if redis_url:
            try:
                import redis
                # Handle SSL connections (Upstash, etc.)
                ssl_params = {}
                if 'rediss://' in redis_url or 'ssl=true' in redis_url.lower():
                    ssl_params = {
                        'ssl_cert_reqs': None,  # Disable certificate verification
                        'ssl_check_hostname': False
                    }
                
                r = redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3, **ssl_params)
                r.ping()
                connected = True
            except Exception as e:
                error_message = str(e)
        else:
            error_message = 'Redis URL not configured'
        
        return jsonify({
            'success': True,
            'status': {
                'connected': connected,
                'configured': bool(redis_url),
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get absolute path to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create directories if they don't exist (using absolute paths)
    os.makedirs(os.path.join(script_dir, 'templates'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'static'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'temp'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'attachments'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)
    
    print("=" * 50)
    print("ANAGHA SOLUTION - Web Server Starting...")
    print("=" * 50)
    print("Access the application at:")
    print("  http://localhost:5001")
    print("  http://127.0.0.1:5001")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Run with proper configuration
    # Using port 5001 to avoid conflict with macOS AirPlay Receiver on port 5000
    app.run(
        host='127.0.0.1',  # Use 127.0.0.1 instead of 0.0.0.0 for local access
        port=5001,
        debug=True,
        threaded=True,
        use_reloader=False
    )

