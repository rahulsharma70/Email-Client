"""
Inbox Monitoring Module for ANAGHA SOLUTION
Monitors inbox for responses and tracks follow-ups
"""

import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from database.db_manager import DatabaseManager

class InboxMonitor:
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize inbox monitor
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    def fetch_inbox_emails(self, account_id: int, folder: str = 'INBOX', limit: int = 100) -> List[Dict]:
        """
        Fetch emails from inbox
        
        Args:
            account_id: SMTP account ID
            folder: Folder to check (default: INBOX)
            limit: Maximum number of emails to fetch
            
        Returns:
            List of email dictionaries
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        
        if not row:
            return []
        
        account = dict(row)
        
        # Decrypt password if encrypted
        password = account.get('password', '')
        if password:
            try:
                from core.encryption import get_encryption_manager
                encryptor = get_encryption_manager()
                password = encryptor.decrypt(password)
            except:
                # If decryption fails, might be plaintext from old data
                pass
        
        imap_host = account.get('imap_host')
        if not imap_host:
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        
        if not imap_host or not username or not password:
            return []
        
        try:
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
            if folder == 'INBOX':
                folder_variants = ['INBOX']
            elif folder == 'Sent':
                folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent']
            
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
                return []
            
            # Search for emails
            status, messages = imap.search(None, 'ALL')
            if status != 'OK':
                imap.logout()
                return []
            
            email_ids = messages[0].split()
            if not email_ids:
                imap.logout()
                return []
            
            # Get last N emails
            email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
            email_ids = email_ids[::-1]  # Newest first
            
            emails = []
            for email_id in email_ids:
                try:
                    status, msg_data = imap.fetch(email_id, '(RFC822)')
                    if status != 'OK' or not msg_data:
                        continue
                    
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract headers
                    subject = msg.get('Subject', '')
                    if subject:
                        decoded_parts = decode_header(subject)
                        subject = ''.join([p.decode(e or 'utf-8', errors='ignore') if isinstance(p, bytes) else str(p) 
                                         for p, e in decoded_parts])
                    
                    from_addr = msg.get('From', '')
                    to_addr = msg.get('To', '')
                    date_str = msg.get('Date', '')
                    
                    # Get body
                    body = ''
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == 'text/plain':
                                try:
                                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                    break
                                except:
                                    pass
                    else:
                        content_type = msg.get_content_type()
                        payload = msg.get_payload(decode=True)
                        if payload:
                            try:
                                body = payload.decode('utf-8', errors='ignore')
                            except:
                                pass
                    
                    emails.append({
                        'uid': email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                        'subject': subject,
                        'from': from_addr,
                        'to': to_addr,
                        'date': date_str,
                        'body': body
                    })
                except Exception as e:
                    print(f"Error processing email {email_id}: {e}")
                    continue
            
            imap.logout()
            return emails
            
        except Exception as e:
            print(f"Error fetching inbox emails: {e}")
            return []
    
    def check_for_responses(self, account_id: int) -> List[Dict]:
        """
        Check inbox for responses to sent emails
        
        Args:
            account_id: SMTP account ID
            
        Returns:
            List of response dictionaries
        """
        # Get sent emails
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, recipient_email, subject, sent_at
            FROM sent_emails
            WHERE sent_at >= datetime('now', '-30 days')
            ORDER BY sent_at DESC
        """)
        sent_emails = [dict(row) for row in cursor.fetchall()]
        
        # Fetch inbox emails
        inbox_emails = self.fetch_inbox_emails(account_id, limit=200)
        
        # Match responses
        responses = []
        for inbox_email in inbox_emails:
            from_email = self._extract_email_address(inbox_email.get('from', ''))
            subject = inbox_email.get('subject', '').lower()
            
            # Check if this is a reply to any sent email
            for sent_email in sent_emails:
                recipient_email = sent_email.get('recipient_email', '').lower()
                sent_subject = sent_email.get('subject', '').lower()
                
                # Check if from address matches recipient
                if from_email.lower() == recipient_email:
                    # Check if subject is related (reply or contains original subject)
                    if 're:' in subject or sent_subject in subject or subject in sent_subject:
                        # This is likely a response
                        response = {
                            'sent_email_id': sent_email.get('id'),
                            'recipient_email': recipient_email,
                            'subject': inbox_email.get('subject'),
                            'response_content': inbox_email.get('body', ''),
                            'response_type': 'reply',
                            'is_hot_lead': self._check_hot_lead(inbox_email.get('body', '')),
                            'from': from_email
                        }
                        responses.append(response)
                        break
        
        return responses
    
    def _extract_email_address(self, email_string: str) -> str:
        """Extract email address from email string"""
        import re
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_string)
        return match.group(0) if match else email_string
    
    def _check_hot_lead(self, email_body: str) -> bool:
        """
        Check if email indicates a hot lead
        
        Args:
            email_body: Email body text
            
        Returns:
            True if hot lead indicators found
        """
        hot_lead_keywords = [
            'interested', 'interested in', 'sounds good', 'let\'s talk', 'let\'s discuss',
            'schedule', 'meeting', 'call', 'demo', 'trial', 'pricing', 'quote',
            'yes', 'sure', 'definitely', 'absolutely', 'when can we', 'how much',
            'more information', 'tell me more', 'i want', 'i need'
        ]
        
        body_lower = email_body.lower()
        for keyword in hot_lead_keywords:
            if keyword in body_lower:
                return True
        
        return False
    
    def save_responses(self, responses: List[Dict]):
        """
        Save responses to database
        
        Args:
            responses: List of response dictionaries
        """
        # Check if using Supabase
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        
        if use_supabase:
            # Use Supabase table methods
            for response in responses:
                try:
                    # Prepare data for Supabase
                    response_data = {
                        'sent_email_id': response.get('sent_email_id'),
                        'recipient_email': response.get('recipient_email'),
                        'subject': response.get('subject'),
                        'response_type': response.get('response_type', 'reply'),
                        'is_hot_lead': 1 if response.get('is_hot_lead') else 0,
                        'response_content': response.get('response_content', ''),
                        'received_at': response.get('received_at') or response.get('created_at')
                    }
                    
                    # Remove None values
                    response_data = {k: v for k, v in response_data.items() if v is not None}
                    
                    # Try to insert or update (upsert based on recipient_email + subject if unique)
                    # First check if response already exists
                    existing = self.db.supabase.client.table('email_responses').select('id').eq('recipient_email', response_data.get('recipient_email', '')).eq('subject', response_data.get('subject', '')).limit(1).execute()
                    
                    if existing.data and len(existing.data) > 0:
                        # Update existing
                        self.db.supabase.client.table('email_responses').update(response_data).eq('id', existing.data[0]['id']).execute()
                    else:
                        # Insert new
                        self.db.supabase.client.table('email_responses').insert(response_data).execute()
                        
                except Exception as e:
                    print(f"Error saving response to Supabase: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            for response in responses:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO email_responses 
                        (sent_email_id, recipient_email, subject, response_type, is_hot_lead, response_content)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        response.get('sent_email_id'),
                        response.get('recipient_email'),
                        response.get('subject'),
                        response.get('response_type', 'reply'),
                        1 if response.get('is_hot_lead') else 0,
                        response.get('response_content', '')
                    ))
                except Exception as e:
                    print(f"Error saving response: {e}")
                    continue
            
            conn.commit()
    
    def check_follow_ups_needed(self) -> List[Dict]:
        """
        Check which emails need follow-ups
        
        Returns:
            List of emails that need follow-ups
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Get sent emails from last 7 days that haven't received responses
        cursor.execute("""
            SELECT se.id, se.recipient_email, se.subject, se.sent_at,
                   r.name, r.company
            FROM sent_emails se
            LEFT JOIN recipients r ON se.recipient_email = r.email
            LEFT JOIN email_responses er ON se.id = er.sent_email_id
            WHERE se.sent_at >= datetime('now', '-7 days')
              AND er.id IS NULL
              AND se.sent_at <= datetime('now', '-2 days')
            ORDER BY se.sent_at ASC
        """)
        
        follow_ups = []
        for row in cursor.fetchall():
            follow_up = dict(row)
            # Calculate days since sent
            sent_date = datetime.fromisoformat(follow_up['sent_at'].replace(' ', 'T'))
            days_since = (datetime.now() - sent_date).days
            
            if days_since >= 2:  # Follow up after 2 days
                follow_up['days_since_sent'] = days_since
                follow_ups.append(follow_up)
        
        return follow_ups
    
    def mark_follow_up_needed(self, sent_email_id: int, follow_up_date: datetime = None):
        """
        Mark an email as needing follow-up
        
        Args:
            sent_email_id: Sent email ID
            follow_up_date: Date for follow-up (default: 2 days from now)
        """
        if not follow_up_date:
            follow_up_date = datetime.now() + timedelta(days=2)
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO email_responses 
            (sent_email_id, recipient_email, follow_up_needed, follow_up_date)
            SELECT id, recipient_email, 1, ?
            FROM sent_emails
            WHERE id = ?
        """, (follow_up_date, sent_email_id))
        
        conn.commit()
    
    def monitor_and_update(self, account_id: int):
        """
        Monitor inbox and update database with responses and follow-ups
        
        Args:
            account_id: SMTP account ID
        """
        # Check for responses
        responses = self.check_for_responses(account_id)
        if responses:
            self.save_responses(responses)
            print(f"Found {len(responses)} responses")
        
        # Check for follow-ups needed
        follow_ups = self.check_follow_ups_needed()
        for follow_up in follow_ups:
            self.mark_follow_up_needed(follow_up['id'])
        
        return {
            'responses_found': len(responses),
            'follow_ups_needed': len(follow_ups)
        }

