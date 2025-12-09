"""
ANAGHA SOLUTION - Web Application
Flask-based web interface for bulk email software
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_cors import CORS
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from core.email_sender import EmailSender
import pandas as pd
from datetime import datetime
import json
<<<<<<< HEAD
=======
from email.utils import parsedate_to_datetime
try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None
>>>>>>> 5cd6a8d (New version with the dashboard)

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
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

# Initialize database
db = DatabaseManager()
db.initialize_database()

# Global email sender instance
email_sender = None

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

<<<<<<< HEAD
=======
@app.route('/inbox')
def inbox():
    """Inbox page for viewing incoming emails"""
    return render_template('inbox.html')

# Inbox API Routes
import imaplib
import email
from email.header import decode_header

@app.route('/api/inbox/fetch/<int:account_id>')
def api_fetch_inbox(account_id):
    """Fetch emails from IMAP server - only fetches new emails, stores locally"""
    try:
        folder = request.args.get('folder', 'INBOX')
        limit = request.args.get('limit', 100, type=int)  # Increased limit to fetch more emails
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        # Get SMTP/IMAP config for this account
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({'error': 'Account not found'}), 404
        
        account = dict(row)
        
        # Get stored emails from local database (unless force refresh)
        stored_emails = []
        stored_uids = set()
        if not force_refresh:
            stored_emails = db.get_stored_emails(account_id, folder, 'imap')
            stored_uids = db.get_stored_email_uids(account_id, folder, 'imap')
            print(f"Found {len(stored_emails)} stored emails for account {account_id}, folder {folder}")
        
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
        
        # Decode password if it's URL-encoded (handles special characters like *)
        import urllib.parse
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass
            # Ensure it's a string, not bytes
            if isinstance(password, bytes):
                password = password.decode('utf-8')
        
        if not imap_host or not username or not password:
            error_msg = 'IMAP settings not configured for this account'
            if not imap_host:
                error_msg += ' (IMAP host missing)'
            if not username:
                error_msg += ' (Username missing)'
            if not password:
                error_msg += ' (Password missing)'
            print(f"✗ {error_msg} for account {account_id} ({username})")
            return jsonify({'error': error_msg}), 400
        
        # Log connection attempt
        print(f"🔗 Attempting IMAP connection for account {account_id} ({username})")
        print(f"   Host: {imap_host}:{imap_port}")
        print(f"   Folder: {folder}")
        
        # Connect to IMAP server
        imap = None
        try:
            if imap_port == 993:
                print(f"   Using SSL connection (port {imap_port})")
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                print(f"   Using non-SSL connection (port {imap_port})")
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    print("   Attempting STARTTLS...")
                    imap.starttls()
                    print("   ✓ STARTTLS successful")
                except Exception as tls_error:
                    print(f"   ⚠ STARTTLS failed (may not be required): {tls_error}")
                    pass
            
            print(f"   Attempting login as {username}...")
            imap.login(username, password)
            print(f"   ✓ Login successful")
        except imaplib.IMAP4.error as imap_error:
            error_msg = f'IMAP authentication failed: {str(imap_error)}'
            print(f"✗ {error_msg}")
            if imap:
                try:
                    imap.logout()
                except:
                    pass
            return jsonify({'error': error_msg, 'details': 'Check username and password'}), 500
        except Exception as conn_error:
            error_msg = f'Failed to connect to IMAP server: {str(conn_error)}'
            print(f"✗ {error_msg}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            if imap:
                try:
                    imap.logout()
                except:
                    pass
            return jsonify({'error': error_msg, 'details': str(conn_error)}), 500
        
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
        print(f"   Searching for emails in folder: {selected_folder_name}")
        try:
            status, messages = imap.search(None, 'ALL')
            if status != 'OK':
                imap.logout()
                error_msg = f'Failed to search emails in folder {selected_folder_name}'
                print(f"✗ {error_msg}")
                return jsonify({'error': error_msg}), 500
                print(f"   ✓ Search completed successfully")
        except Exception as search_error:
            imap.logout()
            error_msg = f'Error searching emails: {str(search_error)}'
            print(f"✗ {error_msg}")
            return jsonify({'error': error_msg}), 500
        
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
        
        print(f"Found {len(email_ids)} emails in {folder} on server")
        
        # Filter out already stored emails (unless force refresh)
        if not force_refresh and stored_uids:
            email_ids = [uid for uid in email_ids 
                        if (uid.decode() if isinstance(uid, bytes) else str(uid)) not in stored_uids]
            print(f"After filtering stored emails, {len(email_ids)} new emails to fetch")
        
        # Get last N emails (most recent) - only fetch new ones
        email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
        email_ids = email_ids[::-1]  # Reverse to show newest first
        
        # If no new emails to fetch, return stored emails
        if not email_ids and stored_emails:
            print(f"No new emails to fetch, returning {len(stored_emails)} stored emails")
            return jsonify({
                'success': True,
                'emails': stored_emails,
                'total': len(stored_emails),
                'folder': folder,
                'new_emails': 0,
                'stored_emails': len(stored_emails)
            })
        
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
                
                # Skip if already stored (double check)
                if email_uid in stored_uids:
                    continue
                
                email_data = {
                    'uid': email_uid,
                    'subject': subject or '(No Subject)',
                    'from': from_addr or 'Unknown',
                    'to': msg.get('To', ''),
                    'date': msg.get('Date', ''),
                    'body': '',  # Will be loaded on demand
                    'html': '',  # Will be loaded on demand
                    'unread': unread
                }
                
                # Save to local database
                db.save_fetched_email(
                    account_id=account_id,
                    email_uid=email_uid,
                    folder=folder,
                    subject=email_data['subject'],
                    from_addr=email_data['from'],
                    to_addr=email_data['to'],
                    date=email_data['date'],
                    body='',
                    html_body='',
                    unread=unread,
                    protocol='imap'
                )
                
                emails.append(email_data)
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
        
        # Combine stored emails with newly fetched emails
        all_emails = stored_emails + emails
        
        # Sort by date (newest first) - properly parse dates
        def parse_date_for_sort(email_item):
            date_str = email_item.get('date', '')
            if not date_str:
                return datetime.min
            try:
                # Try RFC822 format first (most common for email dates)
                try:
                    parsed_date = parsedate_to_datetime(date_str)
                    if parsed_date:
                        return parsed_date
                except:
                    pass
                
                # Fallback to dateutil parser if available
                if date_parser:
                    try:
                        return date_parser.parse(date_str)
                    except:
                        pass
                
                # Try standard datetime parsing
                try:
                    return datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
                
                # Last resort - try basic Date constructor
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass
                
                return datetime.min
            except Exception as e:
                print(f"Error parsing date '{date_str}': {e}")
                return datetime.min
        
        all_emails.sort(key=parse_date_for_sort, reverse=True)
        
        print(f"Email fetch summary: {successful_fetches} new emails fetched, {len(stored_emails)} from storage, {len(all_emails)} total")
        
        return jsonify({
            'success': True,
            'emails': all_emails,
            'total': len(all_emails),
            'folder': folder,
            'new_emails': len(emails),
            'stored_emails': len(stored_emails)
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = f'Error fetching inbox: {str(e)}'
        print(f"✗ {error_msg}")
        print(f"   Full traceback:\n{error_trace}")
        return jsonify({'error': error_msg, 'details': error_trace}), 500

@app.route('/api/inbox/diagnose/<int:account_id>')
def api_diagnose_account(account_id):
    """Diagnose email account configuration and connection"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({'error': 'Account not found'}), 404
        
        account = dict(row)
        diagnostics = {
            'account_id': account_id,
            'account_name': account.get('name', 'Unknown'),
            'username': account.get('username', ''),
            'issues': [],
            'recommendations': []
        }
        
        # Check IMAP configuration
        imap_host = account.get('imap_host')
        imap_port = account.get('imap_port', 993)
        username = account.get('username', '')
        password = account.get('password', '')
        incoming_protocol = account.get('incoming_protocol', 'imap')
        
        if not imap_host:
            diagnostics['issues'].append('IMAP host is not configured')
            smtp_host = account.get('host', '')
            if smtp_host:
                suggested_imap = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
                diagnostics['recommendations'].append(f'Try IMAP host: {suggested_imap}')
        
        if not username:
            diagnostics['issues'].append('Username is missing')
        
        if not password:
            diagnostics['issues'].append('Password is missing')
        
        # Try to test connection
        if imap_host and username and password:
            try:
                import urllib.parse
                test_password = password
                if isinstance(test_password, bytes):
                    test_password = test_password.decode('utf-8')
                try:
                    test_password = urllib.parse.unquote(test_password)
                except:
                    pass
                
                if imap_port == 993:
                    test_imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=10)
                else:
                    test_imap = imaplib.IMAP4(imap_host, imap_port, timeout=10)
                    try:
                        test_imap.starttls()
                    except:
                        pass
                
                test_imap.login(username, test_password)
                test_imap.select('INBOX', readonly=True)
                status, messages = test_imap.search(None, 'ALL')
                email_count = len(messages[0].split()) if status == 'OK' and messages[0] else 0
                test_imap.logout()
                
                diagnostics['connection_test'] = 'success'
                diagnostics['email_count'] = email_count
                diagnostics['recommendations'].append('Connection test passed!')
            except Exception as test_error:
                diagnostics['connection_test'] = 'failed'
                diagnostics['connection_error'] = str(test_error)
                diagnostics['issues'].append(f'Connection test failed: {str(test_error)}')
                if 'authentication' in str(test_error).lower():
                    diagnostics['recommendations'].append('Check username and password')
                elif 'timeout' in str(test_error).lower():
                    diagnostics['recommendations'].append('Check IMAP host and port')
                elif 'ssl' in str(test_error).lower() or 'certificate' in str(test_error).lower():
                    diagnostics['recommendations'].append('Try different port or SSL settings')
        
        return jsonify({'success': True, 'diagnostics': diagnostics})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/inbox/fetch-body/<int:account_id>/<email_uid>')
def api_fetch_email_body(account_id, email_uid):
    """Fetch full email body on demand - checks local database first"""
    try:
        folder = request.args.get('folder', 'INBOX')
        protocol = request.args.get('protocol', 'imap')
        
        # Check if body is already stored locally
        stored_body = db.get_stored_email_body(account_id, email_uid, folder, protocol)
        if stored_body and (stored_body.get('body') or stored_body.get('html')):
            print(f"Returning stored email body for {email_uid}")
            return jsonify({
                'success': True,
                'body': stored_body.get('body', ''),
                'html': stored_body.get('html', ''),
                'from_cache': True
            })
        
        # Get account config
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
        
        # Save body to local database for future use
        db.update_fetched_email_body(account_id, email_uid, folder, body, html_body, 'imap')
        
        return jsonify({
            'success': True,
            'body': body,
            'html': html_body,
            'from_cache': False
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

>>>>>>> 5cd6a8d (New version with the dashboard)
@app.route('/api/sent-emails')
def api_get_sent_emails():
    """Get sent emails"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
<<<<<<< HEAD
=======

        # --- BACKFILL MISSING sender_email BEFORE FETCHING ---
        try:
            # 1) Backfill from email_queue (the queue stores the actual sender email chosen)
            cursor.execute("""
                UPDATE sent_emails
                SET sender_email = (
                    SELECT eq.sender_email
                    FROM email_queue eq
                    WHERE eq.campaign_id = sent_emails.campaign_id
                      AND eq.recipient_id = sent_emails.recipient_id
                      AND eq.sender_email IS NOT NULL
                      AND eq.sender_email != ''
                    ORDER BY eq.sent_at DESC
                    LIMIT 1
                )
                WHERE (sender_email IS NULL OR sender_email = '')
                  AND EXISTS (
                      SELECT 1 FROM email_queue eq
                      WHERE eq.campaign_id = sent_emails.campaign_id
                        AND eq.recipient_id = sent_emails.recipient_id
                        AND eq.sender_email IS NOT NULL
                        AND eq.sender_email != ''
                  )
            """)
            if cursor.rowcount:
                print(f"✅ Backfilled {cursor.rowcount} sent_emails rows from email_queue")
                conn.commit()
        except Exception as backfill_q_err:
            print(f"⚠ Backfill from email_queue failed: {backfill_q_err}")
            conn.rollback()

        try:
            # 2) Backfill remaining blanks from SMTP username
            cursor.execute("""
                UPDATE sent_emails
                SET sender_email = (
                    SELECT username FROM smtp_servers
                    WHERE id = sent_emails.smtp_server_id
                      AND username IS NOT NULL
                      AND username != ''
                )
                WHERE (sender_email IS NULL OR sender_email = '')
                  AND smtp_server_id IS NOT NULL
            """)
            if cursor.rowcount:
                print(f"✅ Backfilled {cursor.rowcount} sent_emails rows from smtp_servers.username")
                conn.commit()
        except Exception as backfill_smtp_err:
            print(f"⚠ Backfill from smtp_servers failed: {backfill_smtp_err}")
            conn.rollback()
>>>>>>> 5cd6a8d (New version with the dashboard)
        
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
<<<<<<< HEAD
        sent_emails = [dict(row) for row in cursor.fetchall()]
=======
        rows = cursor.fetchall()
        
        # Convert rows to dicts and ensure sender_email is not None, format dates in IST
        sent_emails = []
        for row in rows:
            email_dict = dict(row)
            
            # Debug: Log the raw sender_email value
            raw_sender_email = email_dict.get('sender_email')
            # Handle None, empty string, or whitespace-only strings
            if raw_sender_email:
                raw_sender_email = str(raw_sender_email).strip()
            else:
                raw_sender_email = ''
            
            print(f"📧 Processing sent email {email_dict.get('id')}: raw sender_email = '{raw_sender_email}'")
            
            # Ensure sender_email is not None or empty
            if not raw_sender_email or raw_sender_email == '':
                print(f"   ⚠ sender_email is empty for email {email_dict.get('id')}, trying to recover...")
                recovered_sender = None
                
                # 1) Try email_queue (has the chosen sender email)
                if not recovered_sender:
                    try:
                        cursor.execute("""
                            SELECT sender_email FROM email_queue 
                            WHERE campaign_id = ? AND recipient_id = ? AND sender_email IS NOT NULL AND sender_email != ''
                            ORDER BY sent_at DESC LIMIT 1
                        """, (email_dict.get('campaign_id'), email_dict.get('recipient_id')))
                        qrow = cursor.fetchone()
                        if qrow and qrow[0] and str(qrow[0]).strip():
                            recovered_sender = str(qrow[0]).strip()
                            print(f"   ✅ Recovered sender_email from email_queue: {recovered_sender}")
                    except Exception as e:
                        print(f"   ⚠ Error reading email_queue: {e}")
                
                # 2) Try SMTP username
                if not recovered_sender and email_dict.get('smtp_server_id'):
                    try:
                        cursor.execute("SELECT username FROM smtp_servers WHERE id = ?", (email_dict['smtp_server_id'],))
                        smtp_row = cursor.fetchone()
                        if smtp_row and smtp_row[0] and str(smtp_row[0]).strip():
                            recovered_sender = str(smtp_row[0]).strip()
                            print(f"   ✅ Recovered sender_email from SMTP username: {recovered_sender}")
                    except Exception as e:
                        print(f"   ⚠ Error getting SMTP server email: {e}")
                
                # 3) If still empty, leave as N/A but do not override a real value
                email_dict['sender_email'] = recovered_sender if recovered_sender else 'N/A'
                
                # Persist any recovered non-empty sender
                if recovered_sender:
                    try:
                        cursor.execute("""
                            UPDATE sent_emails
                            SET sender_email = ?
                            WHERE id = ?
                        """, (recovered_sender, email_dict.get('id')))
                        conn.commit()
                    except Exception as persist_err:
                        print(f"   ⚠ Could not persist recovered sender_email: {persist_err}")
                        conn.rollback()
            else:
                print(f"   ✅ Using existing sender_email: {raw_sender_email}")
            
            # Ensure sender_email is a string and not empty
            if email_dict.get('sender_email'):
                email_dict['sender_email'] = str(email_dict['sender_email']).strip()
            # Final safety: if still empty, try SMTP username one last time, else set N/A
            if not email_dict.get('sender_email') or email_dict['sender_email'] == '':
                if email_dict.get('smtp_server_id'):
                    try:
                        cursor.execute("SELECT username FROM smtp_servers WHERE id = ?", (email_dict['smtp_server_id'],))
                        smtp_row_final = cursor.fetchone()
                        if smtp_row_final and smtp_row_final[0] and str(smtp_row_final[0]).strip():
                            email_dict['sender_email'] = str(smtp_row_final[0]).strip()
                            cursor.execute("""
                                UPDATE sent_emails
                                SET sender_email = ?
                                WHERE id = ?
                            """, (email_dict['sender_email'], email_dict.get('id')))
                            conn.commit()
                            print(f"   ✅ Final fix persisted for email {email_dict.get('id')}: {email_dict['sender_email']}")
                        else:
                            email_dict['sender_email'] = 'N/A'
                    except Exception as last_fallback_error:
                        print(f"   ⚠ Final sender_email fallback error: {last_fallback_error}")
                        conn.rollback()
                        email_dict['sender_email'] = 'N/A'
                else:
                    email_dict['sender_email'] = 'N/A'
            
            # Format sent_at date in IST (Kolkata timezone) for proper display
            if email_dict.get('sent_at'):
                try:
                    from datetime import datetime
                    import pytz
                    
                    # Parse the sent_at timestamp
                    sent_at = email_dict['sent_at']
                    sent_at_dt = None
                    
                    if isinstance(sent_at, str):
                        # Try to parse the string
                        try:
                            # Handle different date formats
                            if 'T' in sent_at:
                                # ISO format - handle with timezone
                                if '+' in sent_at or 'Z' in sent_at:
                                    # Has timezone info
                                    sent_at_dt = datetime.fromisoformat(sent_at.replace('Z', '+00:00'))
                                else:
                                    # No timezone - assume UTC
                                    sent_at_dt = datetime.fromisoformat(sent_at.replace('T', ' ').split('.')[0])
                                    sent_at_dt = pytz.UTC.localize(sent_at_dt)
                            else:
                                # Format like "2025-12-08 13:49:13" - assume UTC (database stores in UTC)
                                clean_date = sent_at.split('.')[0]  # Remove microseconds
                                sent_at_dt = datetime.strptime(clean_date, '%Y-%m-%d %H:%M:%S')
                                # Assume UTC since SQLite stores without timezone
                                sent_at_dt = pytz.UTC.localize(sent_at_dt)
                        except Exception as parse_error:
                            print(f"   ⚠ Error parsing date string '{sent_at}': {parse_error}")
                            # Try alternative parsing
                            try:
                                sent_at_dt = datetime.strptime(sent_at.split('.')[0], '%Y-%m-%d %H:%M:%S')
                                sent_at_dt = pytz.UTC.localize(sent_at_dt)
                            except:
                                raise parse_error
                    elif isinstance(sent_at, datetime):
                        sent_at_dt = sent_at
                        # If naive, assume UTC
                        if sent_at_dt.tzinfo is None:
                            sent_at_dt = pytz.UTC.localize(sent_at_dt)
                    else:
                        # Try to convert to string and parse
                        sent_at_str = str(sent_at)
                        sent_at_dt = datetime.strptime(sent_at_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        sent_at_dt = pytz.UTC.localize(sent_at_dt)
                    
                    # Ensure we have a timezone-aware datetime
                    if sent_at_dt.tzinfo is None:
                        sent_at_dt = pytz.UTC.localize(sent_at_dt)
                    
                    # Convert to Kolkata timezone (IST = UTC+5:30)
                    kolkata_tz = pytz.timezone('Asia/Kolkata')
                    sent_at_ist = sent_at_dt.astimezone(kolkata_tz)
                    
                    # Format as ISO string with +05:30 timezone offset for frontend
                    # Format: 2025-12-08T20:07:00+05:30
                    email_dict['sent_at'] = sent_at_ist.strftime('%Y-%m-%dT%H:%M:%S+05:30')
                    email_dict['sent_at_formatted'] = sent_at_ist.strftime('%Y-%m-%d %H:%M:%S IST')
                    
                    # Debug: Show conversion
                    print(f"   📅 Email {email_dict.get('id')}: UTC={sent_at_dt.strftime('%Y-%m-%d %H:%M:%S %Z')} → IST={sent_at_ist.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                except Exception as date_error:
                    # If date formatting fails, keep original but log error
                    print(f"⚠ Error formatting sent_at date: {date_error} for email {email_dict.get('id')}")
                    import traceback
                    traceback.print_exc()
                    # Keep original sent_at value but try to add timezone
                    try:
                        if isinstance(email_dict['sent_at'], str) and 'T' not in email_dict['sent_at']:
                            # Add UTC and convert
                            temp_dt = datetime.strptime(email_dict['sent_at'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                            temp_dt = pytz.UTC.localize(temp_dt)
                            kolkata_tz = pytz.timezone('Asia/Kolkata')
                            temp_ist = temp_dt.astimezone(kolkata_tz)
                            email_dict['sent_at'] = temp_ist.strftime('%Y-%m-%dT%H:%M:%S+05:30')
                    except:
                        pass
            
            sent_emails.append(email_dict)
>>>>>>> 5cd6a8d (New version with the dashboard)
        
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/sent-emails/<int:email_id>')
def api_get_sent_email(email_id):
    """Get a single sent email"""
    try:
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
        return jsonify({'error': str(e)}), 500

@app.route('/sent-items')
def sent_items():
    """Sent Items page"""
    return render_template('sent_items.html')

@app.route('/settings')
def settings_page():
    """Settings page"""
    return render_template('settings.html')

<<<<<<< HEAD
=======
# Settings API Routes

@app.route('/api/settings')
def api_get_settings():
    """Get all settings"""
    try:
        settings = db.get_all_settings()
        # Convert string values to appropriate types
        result = {
            'email_delay': int(settings.get('email_delay', 30)),
            'max_per_hour': int(settings.get('max_per_hour', 100)),
            'email_priority': int(settings.get('email_priority', 5))
        }
        return jsonify({'success': True, 'settings': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/delay', methods=['POST'])
def api_set_delay():
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
        
        db.set_setting('email_delay', str(delay))
        
        # Update the global email sender if it exists
        global email_sender
        if email_sender:
            email_sender.interval = float(delay)
            print(f"✓ Email delay updated to {delay} seconds")
        
        return jsonify({'success': True, 'email_delay': delay})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/other', methods=['POST'])
def api_set_other_settings():
    """Set other settings"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        if 'max_per_hour' in data:
            db.set_setting('max_per_hour', str(data['max_per_hour']))
        
        if 'email_priority' in data:
            db.set_setting('email_priority', str(data['email_priority']))
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

>>>>>>> 5cd6a8d (New version with the dashboard)
# API Routes

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    """Get dashboard statistics"""
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
def api_create_campaign():
    """Create a new campaign"""
    try:
        # Handle both JSON and form data
        if request.content_type and 'application/json' in request.content_type:
            # JSON request
            data = request.get_json() if request.is_json else {}
            attachments = []
        else:
            # Form data (multipart/form-data for file uploads)
<<<<<<< HEAD
            data = request.form.to_dict()
            attachments = request.files.getlist('attachments')
=======
            attachments = request.files.getlist('attachments')
            
            # Convert form data to dict, preserving list values for selected_smtp_servers
            data = {}
            for key in request.form:
                values = request.form.getlist(key)
                if len(values) == 1:
                    data[key] = values[0]
                else:
                    data[key] = values
>>>>>>> 5cd6a8d (New version with the dashboard)
        
        # Determine message content based on type
        message_type = data.get('message_type', 'html')
        if message_type == 'text':
            # Convert text to HTML for storage
            text_content = data.get('text_content', '')
            html_content = text_content.replace('\n', '<br>')
        else:
            html_content = data.get('html_content', '')
        
<<<<<<< HEAD
=======
        # Get all 4 sender email IDs
        sender_email_1 = data.get('sender_email_1', '').strip()
        sender_email_2 = data.get('sender_email_2', '').strip()
        sender_email_3 = data.get('sender_email_3', '').strip()
        sender_email_4 = data.get('sender_email_4', '').strip()
        
        # Get main sender email (legacy support, can be empty)
        sender_email = data.get('sender_email', '').strip()
        sender_name = data.get('sender_name', '').strip()
        
        # If sender_name is empty but sender_email is provided, extract name from email
        if not sender_name and sender_email:
            sender_name = sender_email.split('@')[0]
        elif not sender_name and sender_email_1:
            sender_name = sender_email_1.split('@')[0]
        
>>>>>>> 5cd6a8d (New version with the dashboard)
        # Create campaign first to get ID
        campaign_id = db.create_campaign(
            name=data.get('name'),
            subject=data.get('subject'),
<<<<<<< HEAD
            sender_name=data.get('sender_name'),
            sender_email=data.get('sender_email'),
=======
            sender_name=sender_name or 'ANAGHA SOLUTION',
            sender_email=sender_email,  # Can be empty - will use SMTP account email
>>>>>>> 5cd6a8d (New version with the dashboard)
            reply_to=None,
            html_content=html_content,
            template_id=data.get('template_id')
        )
        
        # Save attachments if any
        attachment_paths = []
        if attachments:
<<<<<<< HEAD
            os.makedirs('attachments', exist_ok=True)
            for attachment in attachments:
                if attachment and attachment.filename:
                    filename = f"{campaign_id}_{attachment.filename}"
                    filepath = os.path.join('attachments', filename)
=======
            # Use absolute path for attachments directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            attachments_dir = os.path.join(script_dir, 'attachments')
            os.makedirs(attachments_dir, exist_ok=True)
            for attachment in attachments:
                if attachment and attachment.filename:
                    filename = f"{campaign_id}_{attachment.filename}"
                    filepath = os.path.join(attachments_dir, filename)
>>>>>>> 5cd6a8d (New version with the dashboard)
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
            recipients = db.get_recipients()
            if not recipients:
                return jsonify({'success': True, 'campaign_id': campaign_id, 
                              'warning': 'Campaign created but no recipients found to send to'})
            
            recipient_ids = [r['id'] for r in recipients]
            
<<<<<<< HEAD
            # Get default SMTP server
            default_server = db.get_default_smtp_server()
            if not default_server:
                smtp_servers = db.get_smtp_servers()
                if not smtp_servers:
                    return jsonify({'success': True, 'campaign_id': campaign_id,
                                  'warning': 'Campaign created but no SMTP server configured'})
                smtp_id = smtp_servers[0]['id']
            else:
                smtp_id = default_server['id']
=======
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
            
            # Validate selected servers - allow any number of servers (not just 4)
            if selected_smtp_servers and len(selected_smtp_servers) < 1:
                return jsonify({'error': 'Please select at least 1 SMTP server.'}), 400
            
            # Check if SMTP servers are configured
            if not selected_smtp_servers:
                smtp_servers = db.get_smtp_servers()
                if not smtp_servers:
                    return jsonify({'error': 'No SMTP server configured. Please select at least 1 SMTP server.'}), 400
                # Use all active servers if none selected
                selected_smtp_servers = [s['id'] for s in smtp_servers]
                print(f"⚠ No SMTP servers selected, using all {len(selected_smtp_servers)} active servers")
>>>>>>> 5cd6a8d (New version with the dashboard)
            
            # Update campaign status to 'sending'
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            conn.commit()
            
<<<<<<< HEAD
            # Add to queue
            db.add_to_queue(campaign_id, recipient_ids, smtp_id)
=======
            # Create sender email mapping: Map each SMTP server ID to its corresponding email ID
            # Email ID 1 → SMTP Server 1, Email ID 2 → SMTP Server 2, etc.
            sender_emails_map = {}
            if selected_smtp_servers:
                # Sort SMTP servers by ID to ensure consistent mapping
                sorted_smtp_servers = sorted(selected_smtp_servers)
                sender_emails = [sender_email_1, sender_email_2, sender_email_3, sender_email_4]
                
                for idx, smtp_id in enumerate(sorted_smtp_servers):
                    if idx < len(sender_emails) and sender_emails[idx]:
                        sender_emails_map[smtp_id] = sender_emails[idx]
                        print(f"📧 Mapped SMTP Server {smtp_id} → Email ID: {sender_emails[idx]}")
                    else:
                        print(f"📧 SMTP Server {smtp_id} → Will use SMTP account email (no email ID provided)")
            
            # Add to queue with round-robin distribution using selected servers
            emails_per_server = 20  # 20 emails per SMTP server
            db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, 
                          emails_per_server=emails_per_server, 
                          selected_smtp_servers=selected_smtp_servers,
                          sender_emails_map=sender_emails_map)
>>>>>>> 5cd6a8d (New version with the dashboard)
            print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
            
            # Start sending in background thread
            import threading
            global email_sender
            
            def start_sender():
                try:
                    global email_sender
                    if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
<<<<<<< HEAD
                        email_sender = EmailSender(db, interval=1.0, max_threads=3)
                        email_sender.start_sending()
                        print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients")
=======
                        # Get delay from settings
                        email_delay = db.get_email_delay()
                        email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                        email_sender.start_sending()
                        print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients ({email_delay} sec delay)")
>>>>>>> 5cd6a8d (New version with the dashboard)
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
def api_import_recipients():
    """Import recipients from file"""
<<<<<<< HEAD
=======
    filepath = None
>>>>>>> 5cd6a8d (New version with the dashboard)
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
<<<<<<< HEAD
        # Save file temporarily
        filename = file.filename
        filepath = os.path.join('temp', filename)
        os.makedirs('temp', exist_ok=True)
        file.save(filepath)
        
        # Read file
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
=======
        # Check file size (max 50MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            return jsonify({'error': f'File is too large. Maximum size is 50MB. Your file is {file_size / (1024*1024):.2f}MB'}), 400
        
        # Save file temporarily
        filename = file.filename
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(script_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Use a unique filename to avoid conflicts
        import uuid
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(temp_dir, unique_filename)
        
        print(f"📥 Importing recipients from file: {filename} ({file_size / 1024:.2f} KB)")
        file.save(filepath)
        print(f"✓ File saved to: {filepath}")
        
        # Read file
        try:
            print(f"📖 Reading file: {filename}")
            if filename.lower().endswith('.csv'):
                # Try different encodings for CSV
                try:
                    df = pd.read_csv(filepath, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(filepath, encoding='latin-1')
                    except:
                        df = pd.read_csv(filepath, encoding='iso-8859-1')
            elif filename.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
            else:
                return jsonify({'error': 'Unsupported file format. Please use CSV or Excel (.xlsx, .xls) files.'}), 400
            
            print(f"✓ File read successfully. Found {len(df)} rows")
        except Exception as read_error:
            error_msg = f'Error reading file: {str(read_error)}'
            print(f"✗ {error_msg}")
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            return jsonify({'error': error_msg, 'details': 'Please ensure the file is a valid CSV or Excel file.'}), 400
        
        # Check if dataframe is empty
        if df.empty:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            return jsonify({'error': 'File is empty. Please ensure the file contains data.'}), 400
>>>>>>> 5cd6a8d (New version with the dashboard)
        
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
<<<<<<< HEAD
            return jsonify({'error': 'CSV/Excel file must contain an email column'}), 400
        
        recipients = df.to_dict('records')
        count = db.add_recipients(recipients)
        
        # Clean up
        os.remove(filepath)
        
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
=======
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            available_columns = ', '.join(df.columns.tolist())
            return jsonify({
                'error': 'CSV/Excel file must contain an email column',
                'details': f'Available columns: {available_columns}'
            }), 400
        
        # Clean email addresses and remove invalid ones
        print(f"🧹 Cleaning email addresses...")
        df['email'] = df['email'].astype(str).str.lower().str.strip()
        df = df[df['email'].str.contains('@', na=False)]  # Remove rows without @
        df = df[df['email'].str.len() > 3]  # Remove very short emails
        
        if df.empty:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            return jsonify({'error': 'No valid email addresses found in the file'}), 400
        
        print(f"✓ Found {len(df)} valid email addresses")
        
        # Convert to list of dicts
        recipients = df.to_dict('records')
        
        # Add to database
        print(f"💾 Saving {len(recipients)} recipients to database...")
        count = db.add_recipients(recipients)
        print(f"✓ Successfully imported {count} recipients")
        
        # Clean up
        if filepath and os.path.exists(filepath):
            try:
        os.remove(filepath)
            except Exception as cleanup_error:
                print(f"⚠ Warning: Could not delete temp file: {cleanup_error}")
        
        return jsonify({'success': True, 'count': count})
    except pd.errors.EmptyDataError:
        error_msg = 'File is empty or corrupted'
        print(f"✗ {error_msg}")
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = f'Error importing recipients: {str(e)}'
        print(f"✗ {error_msg}")
        print(f"   Traceback:\n{error_trace}")
        
        # Clean up temp file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        
        return jsonify({'error': error_msg, 'details': str(e)}), 500
>>>>>>> 5cd6a8d (New version with the dashboard)

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
def api_list_recipients():
    """Get list of all recipients"""
    try:
        list_name = request.args.get('list_name')
        recipients = db.get_recipients(list_name=list_name)
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
def api_add_smtp():
    """Add SMTP server"""
    try:
<<<<<<< HEAD
        data = request.json if request.is_json else request.form.to_dict()
        
        # Validate required fields
        if not all([data.get('name'), data.get('host'), data.get('port'), 
                   data.get('username'), data.get('password')]):
            return jsonify({'error': 'All fields are required'}), 400
=======
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
>>>>>>> 5cd6a8d (New version with the dashboard)
        
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
        
<<<<<<< HEAD
=======
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
        
>>>>>>> 5cd6a8d (New version with the dashboard)
        server_id = db.add_smtp_server(
            name=data.get('name'),
            host=data.get('host'),
            port=int(data.get('port')),
            username=data.get('username'),
            password=password,  # Use decoded password
            use_tls=use_tls,
            use_ssl=use_ssl,
<<<<<<< HEAD
            max_per_hour=int(data.get('max_per_hour', 100))
=======
            max_per_hour=int(data.get('max_per_hour', 100)),
            imap_host=imap_host,
            imap_port=imap_port,
            save_to_sent=save_to_sent,
            pop3_host=pop3_host,
            pop3_port=pop3_port,
            pop3_ssl=pop3_ssl,
            pop3_leave_on_server=pop3_leave_on_server,
            incoming_protocol=incoming_protocol
>>>>>>> 5cd6a8d (New version with the dashboard)
        )
        
        # If this is the first server or user wants it as default, set it
        set_as_default = data.get('set_as_default', False)
        if set_as_default:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE smtp_servers SET is_default = 0")
            cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
        
<<<<<<< HEAD
        return jsonify({'success': True, 'server_id': server_id})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500
=======
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
    """Fetch emails from POP3 server - only fetches new emails, stores locally"""
    try:
        import poplib
        limit = request.args.get('limit', 100, type=int)  # Increased limit to fetch more emails
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        folder = 'INBOX'  # POP3 typically only has one folder
        
        # Get account config
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
        
        # Get stored emails from local database (unless force refresh)
        stored_emails = []
        stored_uids = set()
        if not force_refresh:
            stored_emails = db.get_stored_emails(account_id, folder, 'pop3')
            stored_uids = db.get_stored_email_uids(account_id, folder, 'pop3')
            print(f"Found {len(stored_emails)} stored POP3 emails for account {account_id}")
        
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
        
        # If no new emails to fetch, return stored emails
        if not force_refresh and stored_emails and num_messages <= len(stored_emails):
            print(f"No new POP3 emails to fetch, returning {len(stored_emails)} stored emails")
            return jsonify({
                'success': True,
                'emails': stored_emails,
                'total': len(stored_emails),
                'folder': folder,
                'new_emails': 0,
                'stored_emails': len(stored_emails),
                'protocol': 'POP3'
            })
        
        # Fetch last N messages (most recent)
        start_msg = max(1, num_messages - limit + 1)
        
        emails = []
        for i in range(num_messages, start_msg - 1, -1):
            email_uid = str(i)
            
            # Skip if already stored (unless force refresh)
            if not force_refresh and email_uid in stored_uids:
                continue
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
                
                email_data = {
                    'uid': email_uid,
                    'subject': subject or '(No Subject)',
                    'from': from_addr or 'Unknown',
                    'to': msg.get('To', ''),
                    'date': msg.get('Date', ''),
                    'body': body[:1000] if body else '',
                    'html': html_body[:5000] if html_body else '',
                    'unread': True
                }
                
                # Save to local database
                db.save_fetched_email(
                    account_id=account_id,
                    email_uid=email_uid,
                    folder=folder,
                    subject=email_data['subject'],
                    from_addr=email_data['from'],
                    to_addr=email_data['to'],
                    date=email_data['date'],
                    body=email_data['body'],
                    html_body=email_data['html'],
                    unread=True,
                    protocol='pop3'
                )
                
                emails.append(email_data)
                
            except Exception as email_error:
                print(f"Error processing POP3 message {i}: {email_error}")
                continue
        
        pop3.quit()
        
        # Combine stored emails with newly fetched emails
        all_emails = stored_emails + emails
        
        # Sort by date (newest first) - properly parse dates
        def parse_date_for_sort(email_item):
            date_str = email_item.get('date', '')
            if not date_str:
                return datetime.min
            try:
                # Try RFC822 format first (most common for email dates)
                try:
                    parsed_date = parsedate_to_datetime(date_str)
                    if parsed_date:
                        return parsed_date
                except:
                    pass
                
                # Fallback to dateutil parser if available
                if date_parser:
                    try:
                        return date_parser.parse(date_str)
                    except:
                        pass
                
                # Try standard datetime parsing
                try:
                    return datetime.strptime(date_str[:19], '%Y-%m-%d %H:%M:%S')
                except:
                    pass
                
                # Last resort - try basic Date constructor
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    pass
                
                return datetime.min
            except Exception as e:
                print(f"Error parsing date '{date_str}': {e}")
                return datetime.min
        
        all_emails.sort(key=parse_date_for_sort, reverse=True)
        
        print(f"POP3 fetch summary: {len(emails)} new emails fetched, {len(stored_emails)} from storage, {len(all_emails)} total")
        
        return jsonify({
            'success': True,
            'emails': all_emails,
            'total': len(all_emails),
            'folder': folder,
            'new_emails': len(emails),
            'stored_emails': len(stored_emails),
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
        
        # Decode password if URL-encoded
        import urllib.parse
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass
            if isinstance(password, bytes):
                password = password.decode('utf-8')
        
        # Test IMAP connection
        try:
            print(f"Testing IMAP connection: {imap_host}:{imap_port} as {username}")
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
            print("✓ IMAP login successful")
            
            # Try to select INBOX
            status, data = imap.select('INBOX', readonly=True)
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
            
        except imaplib.IMAP4.error as imap_error:
            error_msg = f'IMAP authentication failed: {str(imap_error)}'
            print(f"✗ {error_msg}")
            return jsonify({'error': error_msg, 'details': 'Check username and password'}), 500
        except Exception as conn_error:
            error_msg = f'IMAP connection failed: {str(conn_error)}'
            print(f"✗ {error_msg}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            return jsonify({'error': error_msg, 'details': str(conn_error)}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500
>>>>>>> 5cd6a8d (New version with the dashboard)

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

<<<<<<< HEAD
=======
@app.route('/api/smtp/update/<int:server_id>', methods=['POST', 'PUT'])
def api_update_smtp(server_id):
    """Update existing SMTP server settings"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
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
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

>>>>>>> 5cd6a8d (New version with the dashboard)
@app.route('/api/smtp/list', methods=['GET'])
def api_list_smtp():
    """Get list of all SMTP servers"""
    try:
        servers = db.get_smtp_servers(active_only=False)
        # Get default server ID
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
                    cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (default_server_id,))
                    conn.commit()
                    break
        
        return jsonify({'success': True, 'servers': servers, 'default_server_id': default_server_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/set-default/<int:server_id>', methods=['POST'])
def api_set_default_smtp(server_id):
    """Set default SMTP server for sending"""
    try:
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/get/<int:server_id>', methods=['GET'])
def api_get_smtp(server_id):
    """Get SMTP server configuration"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (server_id,))
        row = cursor.fetchone()
        
        if row:
            server = dict(row)
            # Don't expose password in response for security (but we'll use it for testing)
            return jsonify({'success': True, 'server': server})
        else:
            return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/delete/<int:server_id>', methods=['DELETE'])
def api_delete_smtp(server_id):
    """Delete SMTP server"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM smtp_servers WHERE id = ?", (server_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'SMTP server deleted'})
        else:
            return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/toggle/<int:server_id>', methods=['POST'])
def api_toggle_smtp(server_id):
    """Toggle SMTP server active status"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        is_active = data.get('is_active', 1)
        if isinstance(is_active, str):
            is_active = 1 if is_active.lower() in ('true', 'on', '1') else 0
        
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE smtp_servers SET is_active = ? WHERE id = ?", (is_active, server_id))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Server status updated'})
        else:
            return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/save', methods=['POST'])
def api_save_template():
    """Save template"""
    try:
<<<<<<< HEAD
        data = request.json
        template_id = db.save_template(
            name=data.get('name'),
            category=data.get('category'),
            html_content=data.get('html_content')
        )
        return jsonify({'success': True, 'template_id': template_id})
=======
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
>>>>>>> 5cd6a8d (New version with the dashboard)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns')
def api_get_campaigns():
    """Get all campaigns"""
    try:
        campaigns = db.get_campaigns()
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
        
<<<<<<< HEAD
        # Add to queue
        db.add_to_queue(campaign_id, recipient_ids, smtp_id)
=======
        # Add to queue with round-robin distribution (20 emails per SMTP server)
        emails_per_server = 20  # 20 emails per SMTP server
        db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, emails_per_server=emails_per_server)
>>>>>>> 5cd6a8d (New version with the dashboard)
        print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
        
        # Start sending in background thread
        import threading
        global email_sender
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
<<<<<<< HEAD
                    email_sender = EmailSender(db, interval=1.0, max_threads=3)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients")
=======
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients ({email_delay} sec delay)")
>>>>>>> 5cd6a8d (New version with the dashboard)
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
        
<<<<<<< HEAD
        # Update all campaigns to 'sending' and add to queue
        sent_count = 0
        for campaign_id in campaign_ids:
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            db.add_to_queue(campaign_id, recipient_ids, smtp_id)
=======
        # Update all campaigns to 'sending' and add to queue with round-robin distribution
        emails_per_server = 20  # 20 emails per SMTP server
        sent_count = 0
        for campaign_id in campaign_ids:
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, emails_per_server=emails_per_server)
>>>>>>> 5cd6a8d (New version with the dashboard)
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
<<<<<<< HEAD
                    email_sender = EmailSender(db, interval=1.0, max_threads=3)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for {sent_count} campaigns with {len(recipient_ids)} recipients each")
=======
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for {sent_count} campaigns with {len(recipient_ids)} recipients each ({email_delay} sec delay)")
>>>>>>> 5cd6a8d (New version with the dashboard)
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

if __name__ == '__main__':
<<<<<<< HEAD
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('temp', exist_ok=True)
=======
    # Get absolute path to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create directories if they don't exist (using absolute paths)
    os.makedirs(os.path.join(script_dir, 'templates'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'static'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'temp'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'attachments'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)
>>>>>>> 5cd6a8d (New version with the dashboard)
    
    print("=" * 50)
    print("ANAGHA SOLUTION - Web Server Starting...")
    print("=" * 50)
    print("Access the application at:")
<<<<<<< HEAD
    print("  http://localhost:5000")
    print("  http://127.0.0.1:5000")
=======
    print("  http://localhost:5001")
    print("  http://127.0.0.1:5001")
>>>>>>> 5cd6a8d (New version with the dashboard)
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Run with proper configuration
<<<<<<< HEAD
    app.run(
        host='127.0.0.1',  # Use 127.0.0.1 instead of 0.0.0.0 for local access
        port=5000,
=======
    # Using port 5001 to avoid conflict with macOS AirPlay Receiver on port 5000
    app.run(
        host='127.0.0.1',  # Use 127.0.0.1 instead of 0.0.0.0 for local access
        port=5001,
>>>>>>> 5cd6a8d (New version with the dashboard)
        debug=True,
        threaded=True,
        use_reloader=False
    )

