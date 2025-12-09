"""
Database Manager for ANAGHA SOLUTION
Handles all database operations using SQLite
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

class DatabaseManager:
<<<<<<< HEAD
    def __init__(self, db_path: str = "anagha_solution.db"):
=======
    def __init__(self, db_path: str = None):
        # Use absolute path to ensure database persists regardless of working directory
        if db_path is None:
            # Get the directory where this file is located
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "anagha_solution.db")
        else:
            # Convert relative path to absolute
            if not os.path.isabs(db_path):
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                db_path = os.path.join(base_dir, db_path)
        
>>>>>>> 5cd6a8d (New version with the dashboard)
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
        
<<<<<<< HEAD
=======
        # Add POP3 columns if they don't exist
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN pop3_host TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN pop3_port INTEGER DEFAULT 995")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN pop3_ssl INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN pop3_leave_on_server INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN incoming_protocol TEXT DEFAULT 'imap'")
        except sqlite3.OperationalError:
            pass
        
>>>>>>> 5cd6a8d (New version with the dashboard)
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
<<<<<<< HEAD
=======
                sender_email TEXT,
>>>>>>> 5cd6a8d (New version with the dashboard)
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
        
<<<<<<< HEAD
=======
        # Add sender_email column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE email_queue ADD COLUMN sender_email TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
>>>>>>> 5cd6a8d (New version with the dashboard)
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
<<<<<<< HEAD
=======
        # Safety migration: add sender_email/sender_name if legacy DB missing them
        try:
            cursor.execute("ALTER TABLE sent_emails ADD COLUMN sender_email TEXT")
        except:
            pass
        try:
            cursor.execute("ALTER TABLE sent_emails ADD COLUMN sender_name TEXT")
        except:
            pass
>>>>>>> 5cd6a8d (New version with the dashboard)
        
        # Create index for faster queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_recipient ON sent_emails(recipient_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_campaign ON sent_emails(campaign_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sent_emails_date ON sent_emails(sent_at)")
        except:
            pass
        
<<<<<<< HEAD
=======
        # Settings table - stores application settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Fetched Emails table - stores emails fetched from IMAP/POP3 locally
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetched_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                email_uid TEXT NOT NULL,
                folder TEXT NOT NULL,
                subject TEXT,
                from_addr TEXT,
                to_addr TEXT,
                date TEXT,
                body TEXT,
                html_body TEXT,
                unread INTEGER DEFAULT 1,
                protocol TEXT DEFAULT 'imap',
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, email_uid, folder, protocol),
                FOREIGN KEY (account_id) REFERENCES smtp_servers(id)
            )
        """)
        
        # Create index for faster queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fetched_emails_account ON fetched_emails(account_id, folder)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fetched_emails_uid ON fetched_emails(account_id, email_uid, folder, protocol)")
        except:
            pass
        
        # Insert default settings if not exist
        cursor.execute("""
            INSERT OR IGNORE INTO app_settings (setting_key, setting_value)
            VALUES ('email_delay', '30')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO app_settings (setting_key, setting_value)
            VALUES ('max_per_hour', '100')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO app_settings (setting_key, setting_value)
            VALUES ('email_priority', '5')
        """)
        
>>>>>>> 5cd6a8d (New version with the dashboard)
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
<<<<<<< HEAD
                       imap_port: int = 993, save_to_sent: bool = True):
        """Add a new SMTP server"""
=======
                       imap_port: int = 993, save_to_sent: bool = True,
                       pop3_host: str = None, pop3_port: int = 995,
                       pop3_ssl: bool = True, pop3_leave_on_server: bool = True,
                       incoming_protocol: str = 'imap'):
        """Add a new SMTP server with IMAP and POP3 settings"""
>>>>>>> 5cd6a8d (New version with the dashboard)
        conn = self.connect()
        cursor = conn.cursor()
        
        # Check if this is the first server - set as default
        cursor.execute("SELECT COUNT(*) FROM smtp_servers")
        count = cursor.fetchone()[0]
        is_default = 1 if count == 0 else 0
        
        cursor.execute("""
            INSERT INTO smtp_servers (name, host, port, username, password, use_tls, use_ssl, 
<<<<<<< HEAD
                                     max_per_hour, is_default, imap_host, imap_port, save_to_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, host, port, username, password, 1 if use_tls else 0, 1 if use_ssl else 0, 
              max_per_hour, is_default, imap_host, imap_port, 1 if save_to_sent else 0))
=======
                                     max_per_hour, is_default, imap_host, imap_port, save_to_sent,
                                     pop3_host, pop3_port, pop3_ssl, pop3_leave_on_server, incoming_protocol)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, host, port, username, password, 1 if use_tls else 0, 1 if use_ssl else 0, 
              max_per_hour, is_default, imap_host, imap_port, 1 if save_to_sent else 0,
              pop3_host, pop3_port, 1 if pop3_ssl else 0, 1 if pop3_leave_on_server else 0, incoming_protocol))
>>>>>>> 5cd6a8d (New version with the dashboard)
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
<<<<<<< HEAD
                       sender_email: str, reply_to: str = None, html_content: str = "",
=======
                       sender_email: str = None, reply_to: str = None, html_content: str = "",
>>>>>>> 5cd6a8d (New version with the dashboard)
                       template_id: int = None) -> int:
        """Create a new email campaign"""
        conn = self.connect()
        cursor = conn.cursor()
<<<<<<< HEAD
=======
        # Allow sender_email to be None or empty - will use SMTP account email
        sender_email = sender_email or ''
>>>>>>> 5cd6a8d (New version with the dashboard)
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
    
<<<<<<< HEAD
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
    
=======
    def add_to_queue(self, campaign_id: int, recipient_ids: List[int], smtp_server_id: int = None, 
                     emails_per_server: int = 20, selected_smtp_servers: List[int] = None,
                     sender_emails_map: Dict[int, str] = None):
        """
        Add emails to sending queue with round-robin SMTP distribution
        
        Args:
            campaign_id: Campaign ID
            recipient_ids: List of recipient IDs
            smtp_server_id: Optional single SMTP server ID (if None, uses round-robin)
            emails_per_server: Number of emails per SMTP server (default: 20)
            selected_smtp_servers: Optional list of selected SMTP server IDs (if provided, uses only these)
        """
        conn = self.connect()
        cursor = conn.cursor()
        added_count = 0
        
        # If single SMTP server specified, use it for all
        if smtp_server_id:
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
                    
                    # Check if already in queue
                    cursor.execute("""
                        SELECT id FROM email_queue 
                        WHERE campaign_id = ? AND recipient_id = ? AND status IN ('pending', 'processing')
                    """, (campaign_id, recipient_id))
                    existing = cursor.fetchone()
                    
                    if existing:
                        continue
                    
                    # Get sender email for this SMTP server from mapping
                    sender_email_for_queue = None
                    if sender_emails_map and smtp_server_id in sender_emails_map:
                        sender_email_for_queue = sender_emails_map[smtp_server_id]
                    
                    cursor.execute("""
                        INSERT INTO email_queue (campaign_id, recipient_id, smtp_server_id, sender_email, status)
                        VALUES (?, ?, ?, ?, 'pending')
                    """, (campaign_id, recipient_id, smtp_server_id, sender_email_for_queue))
                    added_count += 1
                except Exception as e:
                    print(f"Error adding recipient {recipient_id} to queue: {e}")
                    continue
        else:
            # Round-robin distribution across selected or all active SMTP servers
            print(f"🔍 DEBUG: selected_smtp_servers = {selected_smtp_servers}")
            
            if selected_smtp_servers and len(selected_smtp_servers) > 0:
                # Use selected SMTP servers
                print(f"📋 Using {len(selected_smtp_servers)} selected SMTP servers: {selected_smtp_servers}")
                placeholders = ','.join(['?'] * len(selected_smtp_servers))
                cursor.execute(f"""
                    SELECT id FROM smtp_servers 
                    WHERE id IN ({placeholders}) AND is_active = 1
                    ORDER BY id ASC
                """, selected_smtp_servers)
                smtp_servers = [row[0] for row in cursor.fetchall()]
                
                print(f"✅ Found {len(smtp_servers)} active servers from selection: {smtp_servers}")
                
                if len(smtp_servers) != len(selected_smtp_servers):
                    print(f"⚠ Warning: Some selected SMTP servers are not active. Using {len(smtp_servers)} active servers.")
                    inactive = set(selected_smtp_servers) - set(smtp_servers)
                    if inactive:
                        print(f"   Inactive servers: {inactive}")
            else:
                # Use all active SMTP servers
                print("📋 No selected servers provided, using all active SMTP servers")
                cursor.execute("""
                    SELECT id FROM smtp_servers 
                    WHERE is_active = 1 
                    ORDER BY id ASC
                """)
                smtp_servers = [row[0] for row in cursor.fetchall()]
                print(f"✅ Found {len(smtp_servers)} active servers: {smtp_servers}")
            
            if not smtp_servers:
                print("⚠ No active SMTP servers found! Cannot add emails to queue.")
                return 0
            
            if len(smtp_servers) == 1:
                print(f"⚠ WARNING: Only 1 SMTP server available! All emails will use server {smtp_servers[0]}")
            
            # Calculate total emails to send: emails_per_server * number of servers
            total_emails_to_send = emails_per_server * len(smtp_servers)
            # Limit recipient_ids to only the number we need
            recipient_ids_to_process = recipient_ids[:total_emails_to_send]
            
            print(f"📧 Distributing {len(recipient_ids_to_process)} emails across {len(smtp_servers)} SMTP servers")
            print(f"   {emails_per_server} emails per server (max {total_emails_to_send} total)")
            print(f"   Server IDs: {smtp_servers}")
            
            if len(recipient_ids) > total_emails_to_send:
                print(f"⚠ Limiting to {total_emails_to_send} recipients ({emails_per_server} per server)")
            
            # Distribute emails in round-robin fashion
            for index, recipient_id in enumerate(recipient_ids_to_process):
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
                    
                    # Check if already in queue
                    cursor.execute("""
                        SELECT id FROM email_queue 
                        WHERE campaign_id = ? AND recipient_id = ? AND status IN ('pending', 'processing')
                    """, (campaign_id, recipient_id))
                    existing = cursor.fetchone()
                    
                    if existing:
                        continue
                    
                    # Calculate which SMTP server to use (round-robin)
                    # Formula: server_index = (email_index // emails_per_server) % num_servers
                    # This ensures each server gets exactly emails_per_server emails before moving to next
                    server_index = (index // emails_per_server) % len(smtp_servers)
                    assigned_smtp_id = smtp_servers[server_index]
                    
                    # Get sender email for this SMTP server from mapping
                    # Map: Email ID 1 → SMTP Server 1, Email ID 2 → SMTP Server 2, etc.
                    sender_email_for_queue = None
                    if sender_emails_map:
                        # Map server_index (0-based) to sender email
                        # If we have 4 email IDs, map: 0→email1, 1→email2, 2→email3, 3→email4
                        if server_index < len(smtp_servers) and assigned_smtp_id in sender_emails_map:
                            sender_email_for_queue = sender_emails_map[assigned_smtp_id]
                        elif server_index < len(smtp_servers):
                            # Try to get by index if direct mapping not available
                            email_keys = sorted(sender_emails_map.keys())
                            if server_index < len(email_keys):
                                sender_email_for_queue = sender_emails_map[email_keys[server_index]]
                    
                    # Debug: Log assignment for verification (first 5, last 5, and every 20th)
                    if index < 5 or index >= len(recipient_ids_to_process) - 5 or (index + 1) % 20 == 0:
                        server_name = self._get_smtp_server_name(conn, assigned_smtp_id)
                        sender_info = f" (sender: {sender_email_for_queue or 'SMTP account email'})"
                        print(f"   📧 Email {index + 1}/{len(recipient_ids_to_process)}: Server index {server_index} → SMTP Server {assigned_smtp_id} ({server_name}){sender_info}")
                    
                    # Verify assignment before inserting
                    if assigned_smtp_id not in smtp_servers:
                        print(f"   ⚠ ERROR: Assigned SMTP ID {assigned_smtp_id} not in available servers {smtp_servers}!")
                        continue
                    
                    # CRITICAL: Ensure smtp_server_id is not None before inserting
                    if assigned_smtp_id is None:
                        print(f"   ⚠ ERROR: Cannot insert email {index + 1} - SMTP server ID is None!")
                        print(f"   Available servers: {smtp_servers}")
                        print(f"   Server index calculated: {server_index}")
                        print(f"   Total servers: {len(smtp_servers)}")
                        continue
                    
                    cursor.execute("""
                        INSERT INTO email_queue (campaign_id, recipient_id, smtp_server_id, sender_email, status)
                        VALUES (?, ?, ?, ?, 'pending')
                    """, (campaign_id, recipient_id, assigned_smtp_id, sender_email_for_queue))
                    added_count += 1
                    
                    # Verify the insert was successful
                    if cursor.rowcount == 0:
                        print(f"   ⚠ WARNING: Failed to insert email {index + 1} into queue")
                    
                except Exception as e:
                    print(f"Error adding recipient {recipient_id} to queue: {e}")
                    continue
        
        conn.commit()
        print(f"✅ Added {added_count} emails to queue for campaign {campaign_id}")
        
        # Print distribution summary
        if not smtp_server_id:
            cursor.execute("""
                SELECT smtp_server_id, COUNT(*) as count
                FROM email_queue
                WHERE campaign_id = ? AND status = 'pending'
                GROUP BY smtp_server_id
                ORDER BY smtp_server_id
            """, (campaign_id,))
            distribution = cursor.fetchall()
            if distribution:
                print("\n" + "="*60)
                print("📊 EMAIL DISTRIBUTION SUMMARY")
                print("="*60)
                total_distributed = 0
                for smtp_id, count in distribution:
                    server_name = self._get_smtp_server_name(conn, smtp_id)
                    print(f"   ✅ Server {smtp_id} ({server_name}): {count} emails")
                    total_distributed += count
                    # Verify each server has exactly emails_per_server emails
                    if count != emails_per_server:
                        print(f"   ⚠ Warning: Server {smtp_id} has {count} emails, expected {emails_per_server}")
                print(f"   📧 Total: {total_distributed} emails distributed across {len(distribution)} servers")
                print("="*60)
                
                # Verify distribution is correct
                if len(distribution) > 0:
                    expected_per_server = emails_per_server
                    all_correct = all(count == expected_per_server for _, count in distribution)
                    if all_correct:
                        print(f"   ✓ Distribution verified: All servers have exactly {expected_per_server} emails")
                    else:
                        print(f"   ⚠ Distribution issue: Some servers don't have {expected_per_server} emails")
        
        return added_count
    
    def _get_smtp_server_name(self, conn, smtp_id):
        """Helper to get SMTP server name"""
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM smtp_servers WHERE id = ?", (smtp_id,))
            row = cursor.fetchone()
            return row[0] if row else f"Server {smtp_id}"
        except:
            return f"Server {smtp_id}"
    
>>>>>>> 5cd6a8d (New version with the dashboard)
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
    
<<<<<<< HEAD
=======
    def get_setting(self, key: str, default: str = None) -> str:
        """Get a setting value"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return default
    
    def set_setting(self, key: str, value: str):
        """Set a setting value"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, str(value)))
        conn.commit()
    
    def get_all_settings(self) -> Dict:
        """Get all settings as a dictionary"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT setting_key, setting_value FROM app_settings")
        settings = {}
        for row in cursor.fetchall():
            settings[row[0]] = row[1]
        return settings
    
    def get_email_delay(self) -> int:
        """Get email delay setting in seconds"""
        delay = self.get_setting('email_delay', '30')
        try:
            return int(delay)
        except:
            return 30

    def insert_sent_email(self, campaign_id: int, recipient_id: int, recipient_email: str,
                          recipient_name: str, subject: str, sender_name: str, sender_email: str,
                          html_content: str, text_content: str, sent_at, status: str,
                          smtp_server_id: int = None, message_id: str = None):
        """Insert a sent email record."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO sent_emails (
                    campaign_id, recipient_id, recipient_email, recipient_name,
                    subject, sender_name, sender_email, html_content, text_content,
                    sent_at, status, smtp_server_id, message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign_id, recipient_id, recipient_email, recipient_name,
                subject, sender_name, sender_email, html_content, text_content,
                sent_at, status, smtp_server_id, message_id
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Error inserting sent email: {e}")
            import traceback; traceback.print_exc()
            conn.rollback()
            return None
    
    def save_fetched_email(self, account_id: int, email_uid: str, folder: str, 
                          subject: str, from_addr: str, to_addr: str, date: str,
                          body: str = '', html_body: str = '', unread: bool = True,
                          protocol: str = 'imap'):
        """Save a fetched email to local database"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO fetched_emails 
                (account_id, email_uid, folder, subject, from_addr, to_addr, date, 
                 body, html_body, unread, protocol, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (account_id, email_uid, folder, subject, from_addr, to_addr, date,
                  body, html_body, 1 if unread else 0, protocol))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving fetched email: {e}")
            return False
    
    def get_stored_emails(self, account_id: int, folder: str, protocol: str = 'imap') -> List[Dict]:
        """Get stored emails for an account and folder"""
        conn = self.connect()
        cursor = conn.cursor()
        # Get all stored emails - sorting will be done in Python for better date parsing
        cursor.execute("""
            SELECT email_uid, subject, from_addr, to_addr, date, body, html_body, unread
            FROM fetched_emails
            WHERE account_id = ? AND folder = ? AND protocol = ?
        """, (account_id, folder, protocol))
        emails = []
        for row in cursor.fetchall():
            emails.append({
                'uid': row[0],
                'subject': row[1] or '(No Subject)',
                'from': row[2] or 'Unknown',
                'to': row[3] or '',
                'date': row[4] or '',
                'body': row[5] or '',
                'html': row[6] or '',
                'unread': bool(row[7])
            })
        return emails
    
    def get_stored_email_uids(self, account_id: int, folder: str, protocol: str = 'imap') -> set:
        """Get set of stored email UIDs for an account and folder"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email_uid FROM fetched_emails
            WHERE account_id = ? AND folder = ? AND protocol = ?
        """, (account_id, folder, protocol))
        return {row[0] for row in cursor.fetchall()}
    
    def update_fetched_email_body(self, account_id: int, email_uid: str, folder: str,
                                   body: str, html_body: str, protocol: str = 'imap'):
        """Update email body for a stored email"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE fetched_emails
            SET body = ?, html_body = ?
            WHERE account_id = ? AND email_uid = ? AND folder = ? AND protocol = ?
        """, (body, html_body, account_id, email_uid, folder, protocol))
        conn.commit()
    
    def get_stored_email_body(self, account_id: int, email_uid: str, folder: str, 
                              protocol: str = 'imap') -> Dict:
        """Get stored email body"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT body, html_body FROM fetched_emails
            WHERE account_id = ? AND email_uid = ? AND folder = ? AND protocol = ?
        """, (account_id, email_uid, folder, protocol))
        row = cursor.fetchone()
        if row:
            return {'body': row[0] or '', 'html': row[1] or ''}
        return {'body': '', 'html': ''}
    
>>>>>>> 5cd6a8d (New version with the dashboard)
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

