# New Features Documentation

This document describes the new features added to the Email Client application.

## 1. Leads Management System

### Database Structure
- **Leads Table**: Stores lead information (name, company_name, domain, email, title, verification status)
- **Lead Scraping Jobs Table**: Tracks scraping job progress
- **Email Responses Table**: Tracks email responses and follow-ups

### Features
- Central database storage for all leads
- Manual lead addition
- Lead verification via SMTP handshake
- Export leads to CSV
- Search and filter leads

## 2. Lead Scraper

### Functionality
The lead scraper uses the Perplexity API to:
1. Extract company names from an ICP (Ideal Customer Profile) description
2. For each company, extract 3-5 key decision makers (CEO, CTO, VPs, HODs, etc.)
3. Generate 5 email pattern variations for each decision maker
4. Save leads to the database

### Usage
1. Go to the **Leads** page
2. Click **"Scrape New Leads"**
3. Enter your ICP description (e.g., "B2B SaaS companies with 50-200 employees in marketing technology")
4. Click **"Start Scraping"**
5. The job runs in the background - check back in a few minutes

### API Configuration
Set the `PERPLEXITY_API_KEY` environment variable:
```bash
export PERPLEXITY_API_KEY="your-api-key-here"
```

## 3. Email Verification

### SMTP Handshake Verification
- Verifies email addresses by connecting to the recipient's mail server
- Checks MX records for the domain
- Attempts SMTP RCPT TO command to verify mailbox existence
- Updates lead verification status in database

### Usage
- **Single Verification**: Click the verify button next to a lead
- **Batch Verification**: Select multiple leads and click "Verify Selected"
- Verification results are stored in the database

## 4. Email Personalization

### AI-Powered Personalization
Uses OpenRouter API to personalize emails based on:
- Recipient name
- Company name
- Additional context (optional)

### Usage
1. Create a campaign in **Campaign Builder**
2. Check **"Enable AI Personalization"**
3. Write your email template (can include {name}, {company} placeholders)
4. The system will personalize each email using AI

### API Configuration
Set the `OPENROUTER_API_KEY` environment variable:
```bash
export OPENROUTER_API_KEY="your-api-key-here"
```

### Default Model
Uses `openai/gpt-4o-mini` by default (cost-effective). Can be changed in `core/personalization.py`.

## 5. Inbox Monitoring & Follow-ups

### Features
- **Hot Lead Detection**: Automatically identifies responses with positive indicators
- **Follow-up Tracking**: Tracks emails that need follow-ups (default: 2 days after sending)
- **Response Monitoring**: Monitors inbox for replies to sent emails

### Hot Lead Indicators
Keywords that trigger hot lead status:
- "interested", "sounds good", "let's talk"
- "schedule", "meeting", "call", "demo"
- "pricing", "quote", "tell me more"
- And more...

### Usage
1. Go to **Inbox** page
2. Click **"Monitor Inbox"** to check for new responses
3. View **Hot Leads** tab to see potential customers
4. View **Follow-ups Needed** tab to see emails requiring follow-up
5. Click **"Create Follow-up"** to quickly create a follow-up campaign

### Automatic Follow-up Detection
- Emails sent 2+ days ago without responses are flagged for follow-up
- Follow-up dates are automatically calculated
- System tracks which emails need attention

## API Endpoints

### Leads
- `POST /api/leads/scrape` - Start lead scraping job
- `GET /api/leads/list` - Get list of leads
- `POST /api/leads/add` - Add a lead manually
- `POST /api/leads/verify/<lead_id>` - Verify a single lead
- `POST /api/leads/verify/batch` - Verify multiple leads

### Inbox Monitoring
- `POST /api/inbox/monitor/<account_id>` - Monitor inbox for responses
- `GET /api/inbox/responses` - Get email responses
- `GET /api/inbox/follow-ups` - Get follow-ups needed

### Personalization
- `POST /api/personalize` - Personalize an email template

## Environment Variables

Required for full functionality:
```bash
# Perplexity API (for lead scraping)
export PERPLEXITY_API_KEY="your-perplexity-api-key"

# OpenRouter API (for email personalization)
export OPENROUTER_API_KEY="your-openrouter-api-key"
```

## Installation

1. Install new dependencies:
```bash
pip install -r requirements.txt
```

New dependencies:
- `requests>=2.31.0` - For API calls
- `dnspython>=2.4.0` - For email verification

2. Set environment variables (see above)

3. Restart the application

## Database Migration

The database will automatically create new tables on first run:
- `leads` - Lead storage
- `lead_scraping_jobs` - Scraping job tracking
- `email_responses` - Response and follow-up tracking

The `campaigns` table is automatically updated with a `use_personalization` column.

## Notes

- Lead scraping jobs run in background threads - check back after a few minutes
- Email verification may take time for large batches (1 second delay between verifications)
- Personalization adds API latency - consider this when sending large campaigns
- Hot lead detection uses keyword matching - may need tuning for your use case
- Follow-up detection is automatic but can be manually triggered via "Monitor Inbox"

