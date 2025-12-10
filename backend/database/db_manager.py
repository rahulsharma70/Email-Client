"""
Database Manager for ANAGHA SOLUTION
Handles all database operations using SQLite
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional

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
        from datetime import timedelta
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

class DatabaseManager:
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
        
        # SMTP Servers table - with user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smtp_servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
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
                provider_type TEXT DEFAULT 'smtp',
                daily_sent_count INTEGER DEFAULT 0,
                last_sent_date DATE,
                warmup_stage INTEGER DEFAULT 0,
                warmup_emails_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add user_id and new columns if they don't exist
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN provider_type TEXT DEFAULT 'smtp'")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN daily_sent_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN last_sent_date DATE")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN warmup_stage INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE smtp_servers ADD COLUMN warmup_emails_sent INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
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
        
        # Email Campaigns table - with user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                reply_to TEXT,
                html_content TEXT,
                template_id INTEGER,
                status TEXT DEFAULT 'draft',
                use_personalization INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheduled_at TIMESTAMP,
                sent_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add user_id and use_personalization columns if they don't exist
        try:
            cursor.execute("ALTER TABLE campaigns ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE campaigns ADD COLUMN use_personalization INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Recipients table - with user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                company TEXT,
                city TEXT,
                phone TEXT,
                list_name TEXT,
                is_verified INTEGER DEFAULT 0,
                is_unsubscribed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, email)
            )
        """)
        
        # Add user_id if it doesn't exist
        try:
            cursor.execute("ALTER TABLE recipients ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        
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
        
        # Users table - multi-tenant support
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                company_name TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                subscription_plan TEXT DEFAULT 'free',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                subscription_status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Leads table - stores lead information with user_id and follow_up_count
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                company_name TEXT NOT NULL,
                domain TEXT,
                email TEXT,
                title TEXT,
                is_verified INTEGER DEFAULT 0,
                verification_status TEXT DEFAULT 'pending',
                verification_date TIMESTAMP,
                source TEXT,
                follow_up_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add user_id and follow_up_count columns if they don't exist
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN follow_up_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # Lead scraping jobs table - with user_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_scraping_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                icp_description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                companies_found INTEGER DEFAULT 0,
                leads_found INTEGER DEFAULT 0,
                verified_leads INTEGER DEFAULT 0,
                current_step TEXT DEFAULT 'starting',
                progress_percent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Add new columns if they don't exist
        try:
            cursor.execute("ALTER TABLE lead_scraping_jobs ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE lead_scraping_jobs ADD COLUMN current_step TEXT DEFAULT 'starting'")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE lead_scraping_jobs ADD COLUMN progress_percent INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # Email responses and follow-ups tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_email_id INTEGER,
                recipient_email TEXT NOT NULL,
                subject TEXT,
                response_type TEXT DEFAULT 'reply',
                is_hot_lead INTEGER DEFAULT 0,
                follow_up_needed INTEGER DEFAULT 0,
                follow_up_date TIMESTAMP,
                response_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sent_email_id) REFERENCES sent_emails(id)
            )
        """)
        
        # Create indexes for faster queries
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_verified ON leads(is_verified)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_responses_recipient ON email_responses(recipient_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_responses_followup ON email_responses(follow_up_needed, follow_up_date)")
        except:
            pass
        
        # Settings table - stores application settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
                       imap_port: int = 993, save_to_sent: bool = True,
                       pop3_host: str = None, pop3_port: int = 995,
                       pop3_ssl: bool = True, pop3_leave_on_server: bool = True,
                       incoming_protocol: str = 'imap', user_id: int = None,
                       provider_type: str = 'smtp', oauth_token: str = None,
                       oauth_refresh_token: str = None):
        """Add a new SMTP server with IMAP and POP3 settings - ENCRYPTED"""
        from core.encryption import get_encryption_manager
        encryptor = get_encryption_manager()
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # Encrypt sensitive data
        encrypted_password = encryptor.encrypt(password)
        encrypted_oauth = encryptor.encrypt(oauth_token) if oauth_token else None
        encrypted_refresh = encryptor.encrypt(oauth_refresh_token) if oauth_refresh_token else None
        
        # Check if this is the first server for this user - set as default
        if user_id:
            cursor.execute("SELECT COUNT(*) FROM smtp_servers WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM smtp_servers")
        count = cursor.fetchone()[0]
        is_default = 1 if count == 0 else 0
        
        # Detect provider type from email
        from core.rate_limiter import RateLimiter
        rate_limiter = RateLimiter(self)
        detected_provider = rate_limiter.detect_provider(username)
        final_provider_type = provider_type if provider_type != 'smtp' else detected_provider
        
        cursor.execute("""
            INSERT INTO smtp_servers (name, host, port, username, password, use_tls, use_ssl, 
                                     max_per_hour, is_default, imap_host, imap_port, save_to_sent,
                                     pop3_host, pop3_port, pop3_ssl, pop3_leave_on_server, 
                                     incoming_protocol, user_id, provider_type, oauth_token, oauth_refresh_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, host, port, username, encrypted_password, 1 if use_tls else 0, 1 if use_ssl else 0, 
              max_per_hour, is_default, imap_host, imap_port, 1 if save_to_sent else 0,
              pop3_host, pop3_port, 1 if pop3_ssl else 0, 1 if pop3_leave_on_server else 0, 
              incoming_protocol, user_id, final_provider_type, encrypted_oauth, encrypted_refresh))
        conn.commit()
        return cursor.lastrowid
    
    def get_smtp_servers(self, active_only: bool = True, user_id: int = None) -> List[Dict]:
        """Get all SMTP servers with decrypted passwords"""
        from core.encryption import get_encryption_manager
        encryptor = get_encryption_manager()
        
        conn = self.connect()
        cursor = conn.cursor()
        query = "SELECT * FROM smtp_servers WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if active_only:
            query += " AND is_active = 1"
        
        query += " ORDER BY is_default DESC, created_at ASC"
        cursor.execute(query, params)
        servers = []
        for row in cursor.fetchall():
            server = dict(row)
            # Decrypt password
            if 'password' in server and server['password']:
                try:
                    server['password'] = encryptor.decrypt(server['password'])
                except:
                    # If decryption fails, might be plaintext from old data
                    password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
            servers.append(server)
        return servers
    
    def get_default_smtp_server(self) -> Optional[Dict]:
        """Get default SMTP server with decrypted password"""
        from core.encryption import get_encryption_manager
        encryptor = get_encryption_manager()
        
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM smtp_servers WHERE is_default = 1 AND is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            server = dict(row)
            # Decrypt password
            if 'password' in server and server['password']:
                try:
                    server['password'] = encryptor.decrypt(server['password'])
                except:
                    # If decryption fails, might be plaintext from old data
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
            # Decrypt password
            if 'password' in server and server['password']:
                try:
                    server['password'] = encryptor.decrypt(server['password'])
                except:
                    # If decryption fails, might be plaintext from old data
                    password = server['password']
                    if isinstance(password, bytes):
                        password = password.decode('utf-8')
                    server['password'] = password
            return server
        return None
    
    def create_campaign(self, name: str, subject: str, sender_name: str, 
                       sender_email: str, reply_to: str = None, html_content: str = "",
                       template_id: int = None, use_personalization: bool = False, user_id: int = None,
                       personalization_prompt: str = None) -> int:
        """Create a new email campaign"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Add personalization_prompt column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE campaigns ADD COLUMN personalization_prompt TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column may already exist
        
        cursor.execute("""
            INSERT INTO campaigns (name, subject, sender_name, sender_email, reply_to, html_content, template_id, use_personalization, user_id, personalization_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, subject, sender_name, sender_email, reply_to, html_content, template_id, 1 if use_personalization else 0, user_id, personalization_prompt))
        conn.commit()
        return cursor.lastrowid
    
    def get_campaigns(self, user_id: int = None) -> List[Dict]:
        """Get all campaigns (filtered by user_id if provided)"""
        conn = self.connect()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def add_recipients(self, recipients: List[Dict], user_id: int = None) -> int:
        """Add recipients (handles duplicates)"""
        conn = self.connect()
        cursor = conn.cursor()
        count = 0
        for recipient in recipients:
            try:
                email = recipient.get('email', '').lower().strip()
                cursor.execute("""
                    INSERT INTO recipients (email, first_name, last_name, company, city, phone, list_name, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email,
                    recipient.get('first_name', ''),
                    recipient.get('last_name', ''),
                    recipient.get('company', ''),
                    recipient.get('city', ''),
                    recipient.get('phone', ''),
                    recipient.get('list_name', 'default'),
                    user_id
                ))
                count += 1
            except sqlite3.IntegrityError:
                # Duplicate email, skip
                continue
        conn.commit()
        return count
    
    def get_recipients(self, list_name: str = None, unsubscribed_only: bool = False, user_id: int = None) -> List[Dict]:
        """Get recipients"""
        conn = self.connect()
        cursor = conn.cursor()
        query = "SELECT * FROM recipients WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if list_name:
            query += " AND list_name = ?"
            params.append(list_name)
        if not unsubscribed_only:
            query += " AND is_unsubscribed = 0"
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def add_to_queue(self, campaign_id: int, recipient_ids: List[int], smtp_server_id: int = None, 
                     emails_per_server: int = 20, selected_smtp_servers: List[int] = None):
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
                    
                    cursor.execute("""
                        INSERT INTO email_queue (campaign_id, recipient_id, smtp_server_id, status)
                        VALUES (?, ?, ?, 'pending')
                    """, (campaign_id, recipient_id, smtp_server_id))
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
                    # Server index = (email_index // emails_per_server) % num_servers
                    server_index = (index // emails_per_server) % len(smtp_servers)
                    assigned_smtp_id = smtp_servers[server_index]
                    
                    # Debug: Log assignment for verification (first 5, last 5, and every 20th)
                    if index < 5 or index >= len(recipient_ids_to_process) - 5 or (index + 1) % 20 == 0:
                        server_name = self._get_smtp_server_name(conn, assigned_smtp_id)
                        print(f"   📧 Email {index + 1}/{len(recipient_ids_to_process)}: Server index {server_index} → SMTP Server {assigned_smtp_id} ({server_name})")
                    
                    # Verify assignment before inserting
                    if assigned_smtp_id not in smtp_servers:
                        print(f"   ⚠ ERROR: Assigned SMTP ID {assigned_smtp_id} not in available servers {smtp_servers}!")
                        continue
                    
                    cursor.execute("""
                        INSERT INTO email_queue (campaign_id, recipient_id, smtp_server_id, status)
                        VALUES (?, ?, ?, 'pending')
                    """, (campaign_id, recipient_id, assigned_smtp_id))
                    added_count += 1
                    
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
                print("\n📊 Email Distribution Summary:")
                total_distributed = 0
                for smtp_id, count in distribution:
                    server_name = self._get_smtp_server_name(conn, smtp_id)
                    print(f"   Server {smtp_id} ({server_name}): {count} emails")
                    total_distributed += count
                    # Verify each server has exactly emails_per_server emails
                    if count != emails_per_server:
                        print(f"   ⚠ Warning: Server {smtp_id} has {count} emails, expected {emails_per_server}")
                print(f"   Total: {total_distributed} emails distributed across {len(distribution)} servers")
        
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
    
    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Pending emails
        cursor.execute("SELECT COUNT(*) FROM email_queue WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        # Sent today - use IST date
        today = get_ist_now().date()
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
            date = get_ist_now().date()
        
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
    
    def get_leads(self, verified_only: bool = False, company_name: str = None, user_id: int = None) -> List[Dict]:
        """Get leads from database"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if verified_only:
            query += " AND is_verified = 1"
        
        if company_name:
            query += " AND company_name LIKE ?"
            params.append(f"%{company_name}%")
        
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_lead(self, lead_id: int) -> Optional[Dict]:
        """Get a single lead by ID"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def add_lead(self, name: str, company_name: str, domain: str, email: str, 
                 title: str = None, source: str = 'manual', user_id: int = None) -> int:
        """Add a single lead with deduplication"""
        conn = self.connect()
        cursor = conn.cursor()
        email_lower = email.lower().strip()
        
        try:
            # Check if lead exists
            if user_id:
                cursor.execute("""
                    SELECT id, follow_up_count FROM leads 
                    WHERE email = ? AND user_id = ?
                """, (email_lower, user_id))
            else:
                cursor.execute("""
                    SELECT id, follow_up_count FROM leads 
                    WHERE email = ?
                """, (email_lower,))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing lead
                follow_up_count = (existing[1] or 0) + 1
                cursor.execute("""
                    UPDATE leads 
                    SET name = ?, company_name = ?, domain = ?, title = ?, 
                        follow_up_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (name, company_name, domain, title, follow_up_count, existing[0]))
                conn.commit()
                return existing[0]
            
            # Insert new lead
            cursor.execute("""
                INSERT INTO leads (name, company_name, domain, email, title, source, user_id, follow_up_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (name, company_name, domain, email_lower, title, source, user_id))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Handle unique constraint violation
            if user_id:
                cursor.execute("SELECT id FROM leads WHERE email = ? AND user_id = ?", (email_lower, user_id))
            else:
                cursor.execute("SELECT id FROM leads WHERE email = ?", (email_lower,))
            row = cursor.fetchone()
            return row[0] if row else None
    
    def update_lead_verification(self, lead_id: int, is_verified: bool, 
                                  verification_status: str = None):
        """Update lead verification status"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE leads 
            SET is_verified = ?, verification_status = ?, 
                verification_date = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if is_verified else 0, verification_status, lead_id))
        conn.commit()
    
    def get_scraping_jobs(self, user_id: int = None) -> List[Dict]:
        """Get all scraping jobs"""
        conn = self.connect()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("SELECT * FROM lead_scraping_jobs WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM lead_scraping_jobs ORDER BY created_at DESC")
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_lead_by_id(self, lead_id: int) -> Optional[Dict]:
        """Get a lead by ID"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_email_responses(self, hot_leads_only: bool = False) -> List[Dict]:
        """Get email responses"""
        conn = self.connect()
        cursor = conn.cursor()
        
        query = """
            SELECT er.*, se.subject as original_subject, se.sent_at
            FROM email_responses er
            LEFT JOIN sent_emails se ON er.sent_email_id = se.id
            WHERE 1=1
        """
        params = []
        
        if hot_leads_only:
            query += " AND er.is_hot_lead = 1"
        
        query += " ORDER BY er.created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_follow_ups_needed(self) -> List[Dict]:
        """Get emails that need follow-ups"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT er.*, se.recipient_email, se.subject, se.sent_at,
                   r.name, r.company
            FROM email_responses er
            JOIN sent_emails se ON er.sent_email_id = se.id
            LEFT JOIN recipients r ON se.recipient_email = r.email
            WHERE er.follow_up_needed = 1
              AND (er.follow_up_date IS NULL OR er.follow_up_date <= datetime('now'))
            ORDER BY er.follow_up_date ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

