# ANAGHA SOLUTION - Email Marketing Platform

A comprehensive multi-tenant SaaS email marketing platform with lead scraping, email verification, AI personalization, and automated follow-ups.

## Features

- ✅ **Multi-Tenant Architecture** - User accounts, JWT authentication, resource isolation
- ✅ **Lead Management** - Scraping, verification, deduplication, follow-up tracking
- ✅ **Email Campaigns** - Bulk sending, templates, personalization
- ✅ **AI Personalization** - LLM-powered email customization
- ✅ **Background Workers** - Celery for async processing
- ✅ **Rate Limiting** - Provider-specific limits (Gmail, Outlook, etc.)
- ✅ **Email Warmup** - Gradual volume increase for new accounts
- ✅ **Billing Integration** - Stripe subscriptions and usage-based billing
- ✅ **Supabase Support** - Cloud PostgreSQL database
- ✅ **Deployment Ready** - Railway and Render configurations

## Project Structure

```
Email-Client/
├── backend/              # Backend code
│   ├── core/            # Core modules (auth, billing, email, etc.)
│   ├── database/        # Database managers (SQLite, Supabase)
│   └── web_app.py       # Flask application
├── frontend/            # Frontend code
│   ├── templates/      # HTML templates
│   └── static/         # CSS, JS, images
├── Dockerfile          # Container configuration
├── railway.json        # Railway deployment
├── render.yaml         # Render deployment
└── requirements.txt    # Dependencies
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Settings
Go to Settings page and configure:
- Database (SQLite or Supabase)
- API keys (Perplexity, OpenRouter)
- Stripe (if using billing)
- Redis (if using Celery)

### 3. Run Application
```bash
cd backend
python web_app.py
```

## Deployment

### Railway
1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Deploy: `railway up`

### Render
1. Go to https://render.com
2. Create new Web Service
3. Connect GitHub repository
4. Set build: `pip install -r requirements.txt`
5. Set start: `gunicorn --bind 0.0.0.0:$PORT web_app:app`

## Documentation

- **Deployment Guide**: See `DEPLOYMENT_GUIDE.md`
- **Complete Setup**: See `COMPLETE_SETUP_GUIDE.md`
- **Quick Deployment**: See `README_DEPLOYMENT.md`

## Environment Variables

Required:
- `DATABASE_TYPE` - `sqlite` or `supabase`
- `SUPABASE_URL` - Supabase project URL (if using Supabase)
- `SUPABASE_KEY` - Supabase API key (if using Supabase)
- `JWT_SECRET_KEY` - Secret for JWT tokens

Optional:
- `STRIPE_SECRET_KEY` - Stripe API key
- `REDIS_URL` - Redis connection URL
- `PERPLEXITY_API_KEY` - Perplexity API key
- `OPENROUTER_API_KEY` - OpenRouter API key

## License

Proprietary - ANAGHA SOLUTION
