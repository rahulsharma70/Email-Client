"""
Database Migrations for ANAGHA SOLUTION
Handles schema migrations and indexing
"""

import sqlite3
from typing import List, Dict
from database.db_manager import DatabaseManager
from core.supabase_client import SupabaseClient

class MigrationManager:
    """Manages database migrations and schema updates"""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize migration manager"""
        self.db = db_manager
        self.use_supabase = hasattr(db_manager, 'use_supabase') and db_manager.use_supabase
    
    def create_indexes(self):
        """Create all necessary indexes for performance"""
        indexes = [
            # User isolation indexes
            ("idx_campaigns_user_id", "campaigns", "user_id"),
            ("idx_leads_user_id", "leads", "user_id"),
            ("idx_recipients_user_id", "recipients", "user_id"),
            ("idx_smtp_servers_user_id", "smtp_servers", "user_id"),
            ("idx_email_queue_user_id", "email_queue", "campaign_id"),
            
            # Performance indexes
            ("idx_email_queue_status", "email_queue", "status"),
            ("idx_email_queue_sent_at", "email_queue", "sent_at"),
            ("idx_email_queue_scheduled_at", "email_queue", "scheduled_at"),
            ("idx_campaign_recipients_campaign_id", "campaign_recipients", "campaign_id"),
            ("idx_campaign_recipients_recipient_id", "campaign_recipients", "recipient_id"),
            ("idx_tracking_campaign_id", "tracking", "campaign_id"),
            ("idx_tracking_recipient_id", "tracking", "recipient_id"),
            ("idx_tracking_event_type", "tracking", "event_type"),
            ("idx_tracking_created_at", "tracking", "created_at"),
            
            # Warmup indexes
            ("idx_smtp_servers_warmup_stage", "smtp_servers", "warmup_stage"),
            
            # Lead indexes
            ("idx_leads_email", "leads", "email"),
            ("idx_leads_verification_status", "leads", "verification_status"),
            ("idx_leads_created_at", "leads", "created_at"),
            
            # Settings indexes
            ("idx_app_settings_user_key", "app_settings", "user_id, setting_key"),
        ]
        
        if self.use_supabase:
            self._create_supabase_indexes(indexes)
        else:
            self._create_sqlite_indexes(indexes)
    
    def _create_sqlite_indexes(self, indexes: List[tuple]):
        """Create indexes in SQLite"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        for index_name, table_name, columns in indexes:
            try:
                # Check if index exists
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name=?
                """, (index_name,))
                
                if not cursor.fetchone():
                    # Create index
                    if ',' in columns:
                        # Composite index
                        column_list = columns
                    else:
                        column_list = columns
                    
                    cursor.execute(f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON {table_name}({column_list})
                    """)
                    print(f"✓ Created index: {index_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ Error creating index {index_name}: {e}")
        
        conn.commit()
    
    def _create_supabase_indexes(self, indexes: List[tuple]):
        """Create indexes in Supabase (PostgreSQL)"""
        if not hasattr(self.db, 'supabase') or not self.db.supabase:
            print("✗ Supabase client not available")
            return
        
        # For Supabase, we'll use SQL execution
        # Note: Supabase may require service key for index creation
        try:
            for index_name, table_name, columns in indexes:
                # Check if index exists (would need to query pg_indexes)
                # For now, just attempt to create
                if ',' in columns:
                    column_list = columns.replace(',', ', ')
                else:
                    column_list = columns
                
                sql = f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {table_name}({column_list})
                """
                
                # Execute via Supabase (if service key available)
                # This would typically be done via SQL editor in Supabase dashboard
                print(f"⚠ Index SQL for {index_name}: {sql}")
                print("   Note: Run this in Supabase SQL editor with service key")
        except Exception as e:
            print(f"✗ Error creating Supabase indexes: {e}")
    
    def migrate_schema(self):
        """Run all pending migrations"""
        migrations = [
            self._migration_add_warmup_columns,
            self._migration_add_oauth_columns,
            self._migration_add_llm_tracking,
            self._migration_add_metrics_tables,
        ]
        
        for migration in migrations:
            try:
                migration()
            except Exception as e:
                print(f"✗ Migration failed: {migration.__name__}: {e}")
    
    def _migration_add_warmup_columns(self):
        """Add warmup tracking columns to smtp_servers"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        columns_to_add = [
            ('warmup_stage', 'INTEGER DEFAULT 0'),
            ('warmup_emails_sent', 'INTEGER DEFAULT 0'),
            ('warmup_start_date', 'TIMESTAMP'),
            ('warmup_last_sent_date', 'TIMESTAMP'),
            ('warmup_open_rate', 'REAL DEFAULT 0.0'),
            ('warmup_reply_rate', 'REAL DEFAULT 0.0'),
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"""
                    ALTER TABLE smtp_servers 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✓ Added column: smtp_servers.{column_name}")
            except sqlite3.OperationalError:
                # Column already exists
                pass
        
        conn.commit()
    
    def _migration_add_oauth_columns(self):
        """Add OAuth columns to smtp_servers"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        columns_to_add = [
            ('oauth_token', 'TEXT'),
            ('oauth_refresh_token', 'TEXT'),
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                cursor.execute(f"""
                    ALTER TABLE smtp_servers 
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✓ Added column: smtp_servers.{column_name}")
            except sqlite3.OperationalError:
                pass
        
        conn.commit()
    
    def _migration_add_llm_tracking(self):
        """Add LLM usage tracking to app_settings"""
        # This is handled by settings_manager, but we ensure the table exists
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Ensure app_settings table exists with user_id
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    setting_key TEXT NOT NULL,
                    setting_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, setting_key),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Add user_id if it doesn't exist
            try:
                cursor.execute("ALTER TABLE app_settings ADD COLUMN user_id INTEGER")
            except sqlite3.OperationalError:
                pass
            
            conn.commit()
            print("✓ LLM tracking table ready")
        except sqlite3.OperationalError as e:
            print(f"✗ Error: {e}")
    
    def _migration_add_metrics_tables(self):
        """Add metrics and observability tables"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Metrics table for observability
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metric_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                alert_type TEXT NOT NULL,
                alert_message TEXT NOT NULL,
                alert_level TEXT DEFAULT 'warning',
                is_resolved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        print("✓ Metrics tables created")
    
    def validate_tenant_isolation(self) -> List[Dict]:
        """Validate that all queries properly filter by user_id"""
        # This is a static analysis helper - would need to check code
        # For now, return a checklist
        return [
            {
                'table': 'campaigns',
                'has_user_id': True,
                'validated': False
            },
            {
                'table': 'leads',
                'has_user_id': True,
                'validated': False
            },
            {
                'table': 'recipients',
                'has_user_id': True,
                'validated': False
            },
            {
                'table': 'smtp_servers',
                'has_user_id': True,
                'validated': False
            },
        ]


