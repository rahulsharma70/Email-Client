-- Supabase Migration Script (consolidated & fixed)
-- Run in: Dashboard > SQL Editor > New Query

BEGIN;

-- Optional: drop existing tables (uncomment if you intend to reset)
-- DROP TABLE IF EXISTS email_queue CASCADE;
-- DROP TABLE IF EXISTS sent_emails CASCADE;
-- DROP TABLE IF EXISTS email_tracking CASCADE;
-- DROP TABLE IF EXISTS campaigns CASCADE;
-- DROP TABLE IF EXISTS recipients CASCADE;
-- DROP TABLE IF EXISTS leads CASCADE;
-- DROP TABLE IF EXISTS smtp_servers CASCADE;
-- DROP TABLE IF EXISTS lead_scraping_jobs CASCADE;
-- DROP TABLE IF EXISTS templates CASCADE;
-- DROP TABLE IF EXISTS app_settings CASCADE;
-- DROP TABLE IF EXISTS daily_stats CASCADE;
-- DROP TABLE IF EXISTS llm_usage_metrics CASCADE;
-- DROP TABLE IF EXISTS observability_metrics CASCADE;
-- DROP TABLE IF EXISTS alerts CASCADE;
-- DROP TABLE IF EXISTS email_responses CASCADE;

-- Users
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
    email_verified INTEGER DEFAULT 0,
    email_verification_token TEXT,
    email_verification_sent_at TIMESTAMP,
    one_time_password TEXT,
    account_activated_at TIMESTAMP,
    onboarding_completed INTEGER DEFAULT 0,
    onboarding_step INTEGER DEFAULT 0,
    onboarding_data TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add email verification and onboarding columns if they don't exist (for existing tables)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='email_verified') THEN
        ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='email_verification_token') THEN
        ALTER TABLE users ADD COLUMN email_verification_token TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='email_verification_sent_at') THEN
        ALTER TABLE users ADD COLUMN email_verification_sent_at TIMESTAMP;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='one_time_password') THEN
        ALTER TABLE users ADD COLUMN one_time_password TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='account_activated_at') THEN
        ALTER TABLE users ADD COLUMN account_activated_at TIMESTAMP;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='onboarding_completed') THEN
        ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='onboarding_step') THEN
        ALTER TABLE users ADD COLUMN onboarding_step INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='onboarding_data') THEN
        ALTER TABLE users ADD COLUMN onboarding_data TEXT;
    END IF;
END $$;

-- Leads
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

-- Templates
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

-- Campaigns (template_id FK added -> SET NULL on delete)
CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    sender_name TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    reply_to TEXT,
    html_content TEXT,
    template_id BIGINT REFERENCES templates(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'draft',
    use_personalization INTEGER DEFAULT 0,
    personalization_prompt TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP
);

-- Recipients
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

-- SMTP Servers
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
    warmup_start_date DATE,
    warmup_last_sent_date DATE,
    warmup_open_rate REAL DEFAULT 0.0,
    warmup_reply_rate REAL DEFAULT 0.0,
    oauth_token TEXT,
    oauth_refresh_token TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Email queue
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

-- Sent emails
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

-- Email tracking (opens, clicks, bounces, unsubscribes)
CREATE TABLE IF NOT EXISTS email_tracking (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE CASCADE,
    recipient_id BIGINT REFERENCES recipients(id) ON DELETE CASCADE,
    email_address TEXT NOT NULL,
    event_type TEXT DEFAULT 'sent',
    sent_at TIMESTAMP,
    opened_at TIMESTAMP,
    clicked_at TIMESTAMP,
    bounced INTEGER DEFAULT 0,
    unsubscribed INTEGER DEFAULT 0,
    bounce_type TEXT,
    bounce_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add user_id and event_type columns if they don't exist (for existing tables)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='email_tracking' AND column_name='user_id') THEN
        ALTER TABLE email_tracking ADD COLUMN user_id BIGINT REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='email_tracking' AND column_name='event_type') THEN
        ALTER TABLE email_tracking ADD COLUMN event_type TEXT DEFAULT 'sent';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='email_tracking' AND column_name='bounce_type') THEN
        ALTER TABLE email_tracking ADD COLUMN bounce_type TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='email_tracking' AND column_name='bounce_reason') THEN
        ALTER TABLE email_tracking ADD COLUMN bounce_reason TEXT;
    END IF;
END $$;

-- Email responses (missing previously; added to support indexes)
CREATE TABLE IF NOT EXISTS email_responses (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE SET NULL,
    recipient_id BIGINT REFERENCES recipients(id) ON DELETE SET NULL,
    sent_email_id BIGINT REFERENCES sent_emails(id) ON DELETE CASCADE,
    recipient_email TEXT,
    subject TEXT,
    body TEXT,
    response_content TEXT,
    response_type TEXT DEFAULT 'reply',
    received_at TIMESTAMP,
    is_reply INTEGER DEFAULT 0,
    is_hot_lead INTEGER DEFAULT 0,
    follow_up_needed INTEGER DEFAULT 0,
    follow_up_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Lead scraping jobs
CREATE TABLE IF NOT EXISTS lead_scraping_jobs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    icp_description TEXT NOT NULL,
    lead_type TEXT DEFAULT 'B2B',
    status TEXT DEFAULT 'pending',
    companies_found INTEGER DEFAULT 0,
    leads_found INTEGER DEFAULT 0,
    verified_leads INTEGER DEFAULT 0,
    current_step TEXT DEFAULT 'starting',
    progress_percent INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Add lead_type column if it doesn't exist (for existing tables)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='lead_scraping_jobs' AND column_name='lead_type') THEN
        ALTER TABLE lead_scraping_jobs ADD COLUMN lead_type TEXT DEFAULT 'B2B';
    END IF;
END $$;

-- App settings
CREATE TABLE IF NOT EXISTS app_settings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, setting_key)
);

-- Daily stats
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

-- LLM usage metrics
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

-- Observability metrics
CREATE TABLE IF NOT EXISTS observability_metrics (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    tags TEXT,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL,
    alert_message TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    is_resolved INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Domains table for DNS verification and domain rotation
CREATE TABLE IF NOT EXISTS domains (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    spf_verified INTEGER DEFAULT 0,
    dkim_verified INTEGER DEFAULT 0,
    dmarc_verified INTEGER DEFAULT 0,
    dkim_public_key TEXT,
    dkim_private_key TEXT,
    dkim_selector TEXT,
    verification_status TEXT DEFAULT 'pending',
    reputation_score REAL DEFAULT 0.0,
    reputation_status TEXT DEFAULT 'neutral',
    reputation_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, domain)
);

-- Banned domains table for abuse prevention
CREATE TABLE IF NOT EXISTS banned_domains (
    id BIGSERIAL PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    reason TEXT,
    banned_at TIMESTAMP DEFAULT NOW()
);

-- User fingerprints table for abuse detection
CREATE TABLE IF NOT EXISTS user_fingerprints (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    ip_address TEXT,
    user_agent TEXT,
    browser_fingerprint TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX IF NOT EXISTS idx_recipients_user_id ON recipients(user_id);
CREATE INDEX IF NOT EXISTS idx_smtp_servers_user_id ON smtp_servers(user_id);
CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status);
CREATE INDEX IF NOT EXISTS idx_sent_emails_campaign_id ON sent_emails(campaign_id);
CREATE INDEX IF NOT EXISTS idx_sent_emails_recipient_id ON sent_emails(recipient_id);
CREATE INDEX IF NOT EXISTS idx_sent_emails_sent_at ON sent_emails(sent_at);
CREATE INDEX IF NOT EXISTS idx_domains_user_id ON domains(user_id);
CREATE INDEX IF NOT EXISTS idx_domains_domain ON domains(domain);
CREATE INDEX IF NOT EXISTS idx_banned_domains_domain ON banned_domains(domain);
CREATE INDEX IF NOT EXISTS idx_user_fingerprints_user_id ON user_fingerprints(user_id);

-- Add missing columns to email_responses if they don't exist
DO $$ 
BEGIN
    -- Add sent_email_id if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'email_responses' AND column_name = 'sent_email_id') THEN
        ALTER TABLE email_responses ADD COLUMN sent_email_id BIGINT REFERENCES sent_emails(id) ON DELETE CASCADE;
    END IF;
    
    -- Add response_content if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'email_responses' AND column_name = 'response_content') THEN
        ALTER TABLE email_responses ADD COLUMN response_content TEXT;
    END IF;
    
    -- Add response_type if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'email_responses' AND column_name = 'response_type') THEN
        ALTER TABLE email_responses ADD COLUMN response_type TEXT DEFAULT 'reply';
    END IF;
    
    -- Add is_hot_lead if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'email_responses' AND column_name = 'is_hot_lead') THEN
        ALTER TABLE email_responses ADD COLUMN is_hot_lead INTEGER DEFAULT 0;
    END IF;
END $$;

-- Indexes that reference email_responses (now present)
CREATE INDEX IF NOT EXISTS idx_email_responses_recipient ON email_responses(recipient_email);
CREATE INDEX IF NOT EXISTS idx_email_responses_followup ON email_responses(follow_up_needed, follow_up_date);
CREATE INDEX IF NOT EXISTS idx_email_responses_hot_lead ON email_responses(is_hot_lead) WHERE is_hot_lead = 1;

CREATE INDEX IF NOT EXISTS idx_settings_user_key ON app_settings(user_id, setting_key);

COMMIT;
