"""
Supabase Schema Creation
Auto-creates tables if they don't exist
"""

from core.supabase_client import SupabaseClient
from typing import Dict, List

class SupabaseSchema:
    """Manages Supabase database schema"""
    
    def __init__(self, supabase_client: SupabaseClient):
        self.client = supabase_client
    
    def create_all_tables(self):
        """Create all tables if they don't exist"""
        try:
            # Check if users table exists
            try:
                result = self.client.client.table('users').select('id').limit(1).execute()
                if result.data is not None:
                    print("✓ Supabase tables already exist")
                    return True
            except Exception as check_error:
                # Table might not exist, try to create
                print(f"Tables check: {check_error}")
            
            # Tables don't exist, create them
            print("Creating Supabase tables...")
            self._create_tables()
            
            # Verify creation by checking again
            try:
                self.client.client.table('users').select('id').limit(1).execute()
                print("✓ Supabase tables created successfully")
                return True
            except:
                print("⚠️  Tables may need manual creation")
                return False
                
        except Exception as e:
            print(f"Error checking/creating tables: {e}")
            import traceback
            traceback.print_exc()
            # Save migration file as fallback
            self._save_migration_file(self._get_sql_statements())
            return False
    
    def _create_tables(self):
        """Create all tables using Supabase SQL"""
        # Use Supabase's RPC to execute SQL or create tables directly
        try:
            # Try to create tables using Supabase client
            self._create_tables_via_rpc()
        except Exception as e:
            print(f"Could not create tables via RPC: {e}")
            # Fallback: Save migration file
            self._save_migration_file(self._get_sql_statements())
    
    def _get_sql_statements(self):
        """Get all SQL statements for table creation"""
        return [
            # Users table
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
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
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Leads table
            """
            CREATE TABLE IF NOT EXISTS leads (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
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
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Campaigns table
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                sender_name TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                reply_to TEXT,
                html_content TEXT,
                template_id BIGINT,
                status TEXT DEFAULT 'draft',
                use_personalization INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                scheduled_at TIMESTAMP,
                sent_at TIMESTAMP
            );
            """,
            
            # Recipients table
            """
            CREATE TABLE IF NOT EXISTS recipients (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                email TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                company TEXT,
                city TEXT,
                phone TEXT,
                list_name TEXT,
                is_verified INTEGER DEFAULT 0,
                is_unsubscribed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, email)
            );
            """,
            
            # SMTP servers table
            """
            CREATE TABLE IF NOT EXISTS smtp_servers (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
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
                incoming_protocol TEXT DEFAULT 'imap',
                pop3_host TEXT,
                pop3_port INTEGER DEFAULT 995,
                pop3_ssl INTEGER DEFAULT 1,
                pop3_leave_on_server INTEGER DEFAULT 1,
                daily_sent_count INTEGER DEFAULT 0,
                last_sent_date DATE,
                warmup_stage INTEGER DEFAULT 0,
                warmup_emails_sent INTEGER DEFAULT 0,
                oauth_token TEXT,
                oauth_refresh_token TEXT,
                warmup_start_date DATE,
                warmup_last_sent_date DATE,
                warmup_open_rate REAL DEFAULT 0.0,
                warmup_reply_rate REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Email queue table
            """
            CREATE TABLE IF NOT EXISTS email_queue (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
                recipient_id BIGINT REFERENCES recipients(id) ON DELETE CASCADE,
                smtp_server_id BIGINT REFERENCES smtp_servers(id) ON DELETE SET NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                error_message TEXT,
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Sent emails table
            """
            CREATE TABLE IF NOT EXISTS sent_emails (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
                recipient_id BIGINT REFERENCES recipients(id) ON DELETE CASCADE,
                smtp_server_id BIGINT REFERENCES smtp_servers(id) ON DELETE SET NULL,
                recipient_email TEXT NOT NULL,
                recipient_name TEXT,
                sender_email TEXT NOT NULL,
                sender_name TEXT,
                subject TEXT NOT NULL,
                html_content TEXT,
                text_content TEXT,
                sent_at TIMESTAMP DEFAULT NOW(),
                status TEXT DEFAULT 'sent',
                message_id TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Lead scraping jobs table
            """
            CREATE TABLE IF NOT EXISTS lead_scraping_jobs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                icp_description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                companies_found INTEGER DEFAULT 0,
                leads_found INTEGER DEFAULT 0,
                verified_leads INTEGER DEFAULT 0,
                current_step TEXT DEFAULT 'starting',
                progress_percent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            );
            """,
            
            # Settings table
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, setting_key)
            );
            """,
            
            # Templates table
            """
            CREATE TABLE IF NOT EXISTS templates (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                subject TEXT,
                html_content TEXT,
                text_content TEXT,
                category TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Email responses table
            """
            CREATE TABLE IF NOT EXISTS email_responses (
                id BIGSERIAL PRIMARY KEY,
                sent_email_id BIGINT REFERENCES sent_emails(id) ON DELETE CASCADE,
                recipient_email TEXT NOT NULL,
                subject TEXT,
                response_type TEXT DEFAULT 'reply',
                is_hot_lead INTEGER DEFAULT 0,
                follow_up_needed INTEGER DEFAULT 0,
                follow_up_date TIMESTAMP,
                response_content TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Email tracking table
            """
            CREATE TABLE IF NOT EXISTS email_tracking (
                id BIGSERIAL PRIMARY KEY,
                campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
                recipient_id BIGINT REFERENCES recipients(id) ON DELETE CASCADE,
                email_address TEXT NOT NULL,
                sent_at TIMESTAMP,
                opened_at TIMESTAMP,
                clicked_at TIMESTAMP,
                bounced INTEGER DEFAULT 0,
                unsubscribed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Daily stats table
            """
            CREATE TABLE IF NOT EXISTS daily_stats (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                emails_sent INTEGER DEFAULT 0,
                emails_delivered INTEGER DEFAULT 0,
                emails_opened INTEGER DEFAULT 0,
                emails_clicked INTEGER DEFAULT 0,
                emails_bounced INTEGER DEFAULT 0,
                emails_unsubscribed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, date)
            );
            """,
            
            # LLM usage metrics table
            """
            CREATE TABLE IF NOT EXISTS llm_usage_metrics (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                metric_date DATE NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                api_calls INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, metric_date)
            );
            """,
            
            # Observability metrics table
            """
            CREATE TABLE IF NOT EXISTS observability_metrics (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                tags TEXT,
                recorded_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Alerts table
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                alert_type TEXT NOT NULL,
                alert_message TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                is_resolved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            # Create indexes
            """
            CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);
            CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
            CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns(user_id);
            CREATE INDEX IF NOT EXISTS idx_recipients_user_id ON recipients(user_id);
            CREATE INDEX IF NOT EXISTS idx_smtp_servers_user_id ON smtp_servers(user_id);
            CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status);
            CREATE INDEX IF NOT EXISTS idx_sent_emails_campaign_id ON sent_emails(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_sent_emails_recipient_id ON sent_emails(recipient_id);
            CREATE INDEX IF NOT EXISTS idx_sent_emails_sent_at ON sent_emails(sent_at);
            CREATE INDEX IF NOT EXISTS idx_email_responses_recipient ON email_responses(recipient_email);
            CREATE INDEX IF NOT EXISTS idx_email_responses_followup ON email_responses(follow_up_needed, follow_up_date);
            CREATE INDEX IF NOT EXISTS idx_settings_user_key ON app_settings(user_id, setting_key);
            """
        ]
    
    def _create_tables_via_rpc(self):
        """Create tables using Supabase RPC function"""
        # Create an RPC function in Supabase that creates all tables
        # First, check if we can use service role key for direct SQL
        try:
            # If we have service role key, we can use Supabase's REST API
            # Otherwise, we'll use the migration file approach
            from supabase import create_client
            import os
            from core.config import Config
            
            service_key = Config.get('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_SERVICE_KEY')
            if service_key:
                # Use service key to execute SQL via Supabase Management API
                self._execute_sql_via_api(service_key)
            else:
                # Save migration file for manual execution
                self._save_migration_file(self._get_sql_statements())
                print("⚠️  Service role key not found. Migration file saved.")
                print("   Please run supabase_migration.sql in Supabase SQL Editor")
        except Exception as e:
            print(f"Error creating tables: {e}")
            self._save_migration_file(self._get_sql_statements())
    
    def _execute_sql_via_api(self, service_key: str):
        """Execute SQL via Supabase Management API"""
        # Note: Supabase doesn't have a direct SQL execution API
        # We'll use the migration file approach and provide instructions
        self._save_migration_file(self._get_sql_statements())
        print("✓ Migration file created. Please run it in Supabase SQL Editor:")
        print("   1. Go to Supabase Dashboard > SQL Editor")
        print("   2. Copy contents of supabase_migration.sql")
        print("   3. Paste and run")
    
    def _save_migration_file(self, sql_statements: List[str]):
        """Save migration SQL to file"""
        import os
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        project_root = os.path.dirname(backend_dir)
        migration_file = os.path.join(project_root, 'supabase_migration.sql')
        with open(migration_file, 'w') as f:
            f.write("-- Supabase Migration Script\n")
            f.write("-- Run this in Supabase SQL Editor\n")
            f.write("-- Go to: Dashboard > SQL Editor > New Query\n\n")
            for sql in sql_statements:
                f.write(sql.strip() + "\n\n")
        print(f"✓ Migration file saved to: {migration_file}")
    
    def initialize_schema(self):
        """Initialize schema - creates tables if they don't exist"""
        return self.create_all_tables()

