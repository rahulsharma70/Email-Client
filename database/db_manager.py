"""
Database Manager for ANAGHA SOLUTION
Handles all database operations using SQLite
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

class DatabaseManager:
    def __init__(self, db_path: str = "anagha_solution.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def initialize_database(self):
        """Create all necessary tables"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # SMTP Servers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smtp_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                use_tls INTEGER DEFAULT 1,
                use_ssl INTEGER DEFAULT 0,
                max_per_hour INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1,
                is_default INTEGER DEFAULT 0,
                imap_host TEXT,
                imap_port INTEGER DEFAULT 993,
                save_to_sent INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add IMAP columns if they don't exist
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN imap_host TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN imap_port INTEGER DEFAULT 993")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN save_to_sent INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        
        # Add is_default column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN is_default INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Email Campaigns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                reply_to TEXT,
                html_content TEXT,
                template_id INTEGER,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheduled_at TIMESTAMP,
                sent_at TIMESTAMP
            )
        """)
        
        # Recipients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                first_name TEXT,
                last_name TEXT,
                company TEXT,
                city TEXT,
                phone TEXT,
                list_name TEXT,
                is_verified INTEGER DEFAULT 0,
                is_unsubscribed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Campaign Recipients (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_recipients (
                campaign_id INTEGER,
                recipient_id INTEGER,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP,
                opened_at TIMESTAMP,
                clicked_at TIMESTAMP,
                bounced INTEGER DEFAULT 0,
                spam_reported INTEGER DEFAULT 0,
                PRIMARY KEY (campaign_id, recipient_id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (recipient_id) REFERENCES recipients(id)
            )
        """)
        
        # Templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                html_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Email Queue table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                recipient_id INTEGER,
                smtp_server_id INTEGER,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheduled_at TIMESTAMP,
                sent_at TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (recipient_id) REFERENCES recipients(id),
                FOREIGN KEY (smtp_server_id) REFERENCES smtp_servers(id)
            )
        """)
        
        # Tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                recipient_id INTEGER,
                event_type TEXT NOT NULL,
                event_data TEXT,
                ip_address TEXT,
                user_agent TEXT,
                location TEXT,
                device_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (recipient_id) REFERENCES recipients(id)
            )
        """)
        
        # Blacklist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Daily Stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                emails_sent INTEGER DEFAULT 0,
                emails_delivered INTEGER DEFAULT 0,
                emails_bounced INTEGER DEFAULT 0,
                emails_opened INTEGER DEFAULT 0,
                emails_clicked INTEGER DEFAULT 0,
                spam_reports INTEGER DEFAULT 0,
                unsubscribes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sent Emails table - stores all sent emails for tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sent_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                recipient_id INTEGER,
                recipient_email TEXT NOT NULL,
                recipient_name TEXT,
                subject TEXT NOT NULL,
                sender_name TEXT,
                sender_email TEXT NOT NULL,
                html_content TEXT,
                text_content TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'sent',
                smtp_server_id INTEGER,
                message_id TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (recipient_id) REFERENCES recipients(id),
                FOREIGN KEY (smtp_server_id) REFERENCES smtp_servers(id)
            )
        """)
        
        # Create index for faster queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_recipient ON sent_emails(recipient_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_campaign ON sent_emails(campaign_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_date ON sent_emails(sent_at)")
        except:
            pass
        
        conn.commit()
        return conn
    
    def get_sent_emails(self, limit: int = 100, offset: int = 0, recipient_email: str = None, campaign_id: int = None) -> List[Dict]:
        """Get sent emails from sent_emails table"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT se.*, c.name as campaign_name, r.first_name, r.last_name
            FROM sent_emails se
            LEFT JOIN campaigns c ON se.campaign_id = c.id
            LEFT JOIN recipients r ON se.recipient_id = r.id
            WHERE 1=1
        """
        params = []
        
        if recipient_email:
            query += " AND se.recipient_email LIKE ?"
            params.append(f"%{recipient_email}%")
        
        if campaign_id:
            query += " AND se.campaign_id = ?"
            params.append(campaign_id)
        
        query += " ORDER BY se.sent_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_sent_emails_count(self, recipient_email: str = None, campaign_id: int = None) -> int:
        """Get total count of sent emails"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) FROM sent_emails WHERE 1=1"
        params = []
        
        if recipient_email:
            query += " AND recipient_email LIKE ?"
            params.append(f"%{recipient_email}%")
        
        if campaign_id:
            query += " AND campaign_id = ?"
            params.append(campaign_id)
        
        cursor.execute(query, params)
        return cursor.fetchone()[0]
    
    def add_smtp_server(self, name: str, host: str, port: int, username: str, 
                       password: str, use_tls: bool = True, use_ssl: bool = False, 
                       max_per_hour: int = 100, imap_host: str = None, 
                       imap_port: int = 993, save_to_sent: bool = True):
        """Add a new SMTP server"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Check if this is the first server - set as default
        cursor.execute("SELECT COUNT(*) FROM smtp_servers")
        count = cursor.fetchone()[0]
        is_default = 1 if count == 0 else 0
        
        cursor.execute("""
            INSERT INTO smtp_servers (name, host, port, username, password, use_tls, use_ssl, 
                                     max_per_hour, is_default, imap_host, imap_port, save_to_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, host, port, username, password, 1 if use_tls else 0, 1 if use_ssl else 0, 
              max_per_hour, is_default, imap_host, imap_port, 1 if save_to_sent else 0))
        conn.commit()
        return cursor.lastrowid
    
    def get_smtp_servers(self, active_only: bool = True) -> List[Dict]:
        """Get all SMTP servers"""
        conn = self.connect()
        cursor = conn.cursor()
        query = "SELECT * FROM smtp_servers"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY is_default DESC, created_at ASC"
        cursor.execute(query)
        servers = []
        for row in cursor.fetchall():
            server = dict(row)
            # Ensure password is a string (not bytes) and properly decoded
            if 'password' in server and server['password']:
                password = server['password']
                if isinstance(password, bytes):
                    password = password.decode('utf-8')
                server['password'] = password
            servers.append(server)
        return servers
    
    def get_default_smtp_server(self) -> Optional[Dict]:
        """Get default SMTP server"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE is_default = 1 AND is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            server = dict(row)
            # Ensure password is a string (not bytes) and properly decoded
            if 'password' in server and server['password']:
                password = server['password']
                if isinstance(password, bytes):
                    password = password.decode('utf-8')
                server['password'] = password
            return server
        # Fallback to first active server
        cursor.execute("SELECT * FROM smtp_servers WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            server = dict(row)
            # Ensure password is a string (not bytes) and properly decoded
            if 'password' in server and server['password']:
                password = server['password']
                if isinstance(password, bytes):
                    password = password.decode('utf-8')
                server['password'] = password
            return server
        return None
    
    def create_campaign(self, name: str, subject: str, sender_name: str, 
                       sender_email: str, reply_to: str = None, html_content: str = "",
                       template_id: int = None) -> int:
        """Create a new email campaign"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campaigns (name, subject, sender_name, sender_email, reply_to, html_content, template_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, subject, sender_name, sender_email, reply_to, html_content, template_id))
        conn.commit()
        return cursor.lastrowid
    
    def get_campaigns(self) -> List[Dict]:
        """Get all campaigns"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def add_recipients(self, recipients: List[Dict]) -> int:
        """Add recipients (handles duplicates)"""
        conn = self.connect()
        cursor = conn.cursor()
        count = 0
        for recipient in recipients:
            try:
                cursor.execute("""
                    INSERT INTO recipients (email, first_name, last_name, company, city, phone, list_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    recipient.get('email', '').lower().strip(),
                    recipient.get('first_name', ''),
                    recipient.get('last_name', ''),
                    recipient.get('company', ''),
                    recipient.get('city', ''),
                    recipient.get('phone', ''),
                    recipient.get('list_name', 'default')
                ))
                count += 1
            except sqlite3.IntegrityError:
                # Duplicate email, skip
                continue
        conn.commit()
        return count
    
    def get_recipients(self, list_name: str = None, unsubscribed_only: bool = False) -> List[Dict]:
        """Get recipients"""
        conn = self.connect()
        cursor = conn.cursor()
        query = "SELECT * FROM recipients WHERE 1=1"
        params = []
        if list_name:
            query += " AND list_name = ?"
            params.append(list_name)
        if not unsubscribed_only:
            query += " AND is_unsubscribed = 0"
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def add_to_queue(self, campaign_id: int, recipient_ids: List[int], smtp_server_id: int = None):
        """Add emails to sending queue"""
        conn = self.connect()
        cursor = conn.cursor()
        added_count = 0
        for recipient_id in recipient_ids:
            try:
                # Check if recipient is unsubscribed
                cursor.execute("SELECT is_unsubscribed FROM recipients WHERE id = ?", (recipient_id,))
                recipient = cursor.fetchone()
                if recipient and recipient[0]:
                    continue  # Skip unsubscribed recipients
                
                cursor.execute("""
                    INSERT OR IGNORE INTO campaign_recipients (campaign_id, recipient_id)
                    VALUES (?, ?)
                """, (campaign_id, recipient_id))
                
                # CRITICAL: Check if this email is already in queue to prevent duplicates
                cursor.execute("""
                    SELECT id FROM email_queue 
                    WHERE campaign_id = ? AND recipient_id = ? AND status IN ('pending', 'processing')
                """, (campaign_id, recipient_id))
                existing = cursor.fetchone()
                
                if existing:
                    # Already in queue, skip
                    continue
                
                cursor.execute("""
                    INSERT INTO email_queue (campaign_id, recipient_id, smtp_server_id, status)
                    VALUES (?, ?, ?, 'pending')
                """, (campaign_id, recipient_id, smtp_server_id))
                added_count += 1
            except Exception as e:
                print(f"Error adding recipient {recipient_id} to queue: {e}")
                continue
        conn.commit()
        print(f"Added {added_count} emails to queue for campaign {campaign_id}")
        return added_count
    
    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Pending emails
        cursor.execute("SELECT COUNT(*) FROM email_queue WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        # Sent today
        today = datetime.now().date()
        cursor.execute("""
            SELECT COUNT(*) FROM email_queue 
            WHERE DATE(sent_at) = ? AND status = 'sent'
        """, (today,))
        sent_today = cursor.fetchone()[0]
        
        return {
            'pending': pending,
            'sent_today': sent_today
        }
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """Get daily statistics"""
        conn = self.connect()
        cursor = conn.cursor()
        if not date:
            date = datetime.now().date()
        
        cursor.execute("SELECT * FROM daily_stats WHERE date = ?", (date,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {
            'emails_sent': 0,
            'emails_delivered': 0,
            'emails_bounced': 0,
            'emails_opened': 0,
            'emails_clicked': 0,
            'spam_reports': 0,
            'unsubscribes': 0
        }
    
    def save_template(self, name: str, category: str, html_content: str) -> int:
        """Save email template"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO templates (name, category, html_content)
            VALUES (?, ?, ?)
        """, (name, category, html_content))
        conn.commit()
        return cursor.lastrowid
    
    def get_templates(self, category: str = None) -> List[Dict]:
        """Get templates"""
        conn = self.connect()
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT * FROM templates WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT * FROM templates ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def track_event(self, campaign_id: int, recipient_id: int, event_type: str,
                   event_data: str = None, ip_address: str = None, 
                   user_agent: str = None, location: str = None, device_type: str = None):
        """Track email events (open, click, etc.)"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tracking (campaign_id, recipient_id, event_type, event_data, 
                                ip_address, user_agent, location, device_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (campaign_id, recipient_id, event_type, event_data, ip_address, user_agent, location, device_type))
        conn.commit()
    
    def unsubscribe_email(self, email: str):
        """Unsubscribe an email"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE recipients SET is_unsubscribed = 1 WHERE email = ?
        """, (email.lower().strip(),))
        conn.commit()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

