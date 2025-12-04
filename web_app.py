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

@app.route('/api/sent-emails')
def api_get_sent_emails():
    """Get sent emails"""
    try:
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
            data = request.form.to_dict()
            attachments = request.files.getlist('attachments')
        
        # Determine message content based on type
        message_type = data.get('message_type', 'html')
        if message_type == 'text':
            # Convert text to HTML for storage
            text_content = data.get('text_content', '')
            html_content = text_content.replace('\n', '<br>')
        else:
            html_content = data.get('html_content', '')
        
        # Create campaign first to get ID
        campaign_id = db.create_campaign(
            name=data.get('name'),
            subject=data.get('subject'),
            sender_name=data.get('sender_name'),
            sender_email=data.get('sender_email'),
            reply_to=None,
            html_content=html_content,
            template_id=data.get('template_id')
        )
        
        # Save attachments if any
        attachment_paths = []
        if attachments:
            os.makedirs('attachments', exist_ok=True)
            for attachment in attachments:
                if attachment and attachment.filename:
                    filename = f"{campaign_id}_{attachment.filename}"
                    filepath = os.path.join('attachments', filename)
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
            
            # Update campaign status to 'sending'
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            conn.commit()
            
            # Add to queue
            db.add_to_queue(campaign_id, recipient_ids, smtp_id)
            print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
            
            # Start sending in background thread
            import threading
            global email_sender
            
            def start_sender():
                try:
                    global email_sender
                    if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                        email_sender = EmailSender(db, interval=1.0, max_threads=3)
                        email_sender.start_sending()
                        print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients")
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
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
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
        count = db.add_recipients(recipients)
        
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
        data = request.json if request.is_json else request.form.to_dict()
        
        # Validate required fields
        if not all([data.get('name'), data.get('host'), data.get('port'), 
                   data.get('username'), data.get('password')]):
            return jsonify({'error': 'All fields are required'}), 400
        
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
        
        server_id = db.add_smtp_server(
            name=data.get('name'),
            host=data.get('host'),
            port=int(data.get('port')),
            username=data.get('username'),
            password=password,  # Use decoded password
            use_tls=use_tls,
            use_ssl=use_ssl,
            max_per_hour=int(data.get('max_per_hour', 100))
        )
        
        # If this is the first server or user wants it as default, set it
        set_as_default = data.get('set_as_default', False)
        if set_as_default:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE smtp_servers SET is_default = 0")
            cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
        
        return jsonify({'success': True, 'server_id': server_id})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

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
        data = request.json
        template_id = db.save_template(
            name=data.get('name'),
            category=data.get('category'),
            html_content=data.get('html_content')
        )
        return jsonify({'success': True, 'template_id': template_id})
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
        
        # Add to queue
        db.add_to_queue(campaign_id, recipient_ids, smtp_id)
        print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
        
        # Start sending in background thread
        import threading
        global email_sender
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                    email_sender = EmailSender(db, interval=1.0, max_threads=3)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients")
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
        
        # Update all campaigns to 'sending' and add to queue
        sent_count = 0
        for campaign_id in campaign_ids:
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            db.add_to_queue(campaign_id, recipient_ids, smtp_id)
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
                    email_sender = EmailSender(db, interval=1.0, max_threads=3)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for {sent_count} campaigns with {len(recipient_ids)} recipients each")
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
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('temp', exist_ok=True)
    
    print("=" * 50)
    print("ANAGHA SOLUTION - Web Server Starting...")
    print("=" * 50)
    print("Access the application at:")
    print("  http://localhost:5000")
    print("  http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Run with proper configuration
    app.run(
        host='127.0.0.1',  # Use 127.0.0.1 instead of 0.0.0.0 for local access
        port=5000,
        debug=True,
        threaded=True,
        use_reloader=False
    )

