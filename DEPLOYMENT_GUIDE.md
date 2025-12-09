# Deployment Guide - ANAGHA SOLUTION

## Overview
This guide covers deploying ANAGHA SOLUTION to Railway or Render with Supabase backend.

## Prerequisites

1. **Supabase Account**
   - Create account at https://supabase.com
   - Create a new project
   - Get your project URL and API key

2. **GitHub Repository**
   - Push your code to GitHub
   - Repository should be public or connected to deployment platform

3. **API Keys**
   - Perplexity API key (for lead scraping)
   - OpenRouter API key (for email personalization)
   - Stripe API key (for billing)
   - Redis URL (for Celery workers)

## Supabase Setup

### 1. Create Supabase Project
1. Go to https://supabase.com
2. Create new project
3. Wait for database to initialize
4. Go to Settings > API
5. Copy:
   - Project URL
   - `anon` key (for client-side)
   - `service_role` key (for server-side - keep secret!)

### 2. Run Database Migrations
The application will automatically create tables on first run, or you can run migrations manually:

```sql
-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
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

-- Create other tables similarly
-- (See database/db_manager.py for full schema)
```

## Railway Deployment

### Option 1: Railway CLI

1. **Install Railway CLI**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login**
   ```bash
   railway login
   ```

3. **Initialize Project**
   ```bash
   railway init
   ```

4. **Add Environment Variables**
   ```bash
   railway variables set SUPABASE_URL=https://xxxxx.supabase.co
   railway variables set SUPABASE_KEY=your_supabase_key
   railway variables set JWT_SECRET_KEY=your_jwt_secret
   railway variables set STRIPE_SECRET_KEY=sk_...
   railway variables set REDIS_URL=redis://...
   railway variables set PERPLEXITY_API_KEY=...
   railway variables set OPENROUTER_API_KEY=...
   ```

5. **Deploy**
   ```bash
   railway up
   ```

### Option 2: GitHub Integration

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Add environment variables in Railway dashboard
6. Railway will auto-deploy on push

### Railway Configuration

The `railway.json` file is already configured:
- Uses Dockerfile for builds
- Runs with Gunicorn
- Auto-restarts on failure

## Render Deployment

1. **Go to Render**
   - Visit https://render.com
   - Sign up/login

2. **Create Web Service**
   - Click "New" > "Web Service"
   - Connect your GitHub repository
   - Select the repository

3. **Configure Service**
   - **Name**: anagha-solution (or your choice)
   - **Region**: Choose closest to your users
   - **Branch**: main (or your default branch)
   - **Root Directory**: / (root)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120 web_app:app`

4. **Add Environment Variables**
   In Render dashboard, go to Environment section:
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your_supabase_key
   JWT_SECRET_KEY=your_jwt_secret
   STRIPE_SECRET_KEY=sk_...
   REDIS_URL=redis://...
   PERPLEXITY_API_KEY=...
   OPENROUTER_API_KEY=...
   OPENROUTER_MODEL=openai/gpt-4
   DATABASE_TYPE=supabase
   FLASK_APP=web_app.py
   PYTHONUNBUFFERED=1
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Wait for build to complete
   - Your app will be live at `https://your-app.onrender.com`

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase project URL | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | Supabase API key | `eyJhbGc...` |
| `JWT_SECRET_KEY` | Secret for JWT tokens | Random string |
| `DATABASE_TYPE` | Database type | `supabase` or `sqlite` |

### Optional Variables

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe API key for billing |
| `REDIS_URL` | Redis connection for Celery |
| `PERPLEXITY_API_KEY` | Perplexity API for lead scraping |
| `OPENROUTER_API_KEY` | OpenRouter API for personalization |
| `OPENROUTER_MODEL` | Model to use (default: `openai/gpt-4`) |

## Post-Deployment

### 1. Verify Deployment
- Visit your deployment URL
- Check if app loads
- Test registration/login

### 2. Configure Settings
- Go to Settings page in the app
- Configure Supabase connection
- Add API keys
- Test database connection

### 3. Set Up Celery Workers (Optional)
For background tasks, deploy Celery workers:

**Railway:**
- Create new service
- Use same environment variables
- Start command: `celery -A core.celery_app worker --loglevel=info`

**Render:**
- Create Background Worker
- Start command: `celery -A core.celery_app worker --loglevel=info`

### 4. Set Up Redis (Optional)
- Railway: Add Redis service
- Render: Use Redis addon
- Update `REDIS_URL` environment variable

## Troubleshooting

### Database Connection Issues
- Verify Supabase URL and key
- Check Supabase project is active
- Ensure tables are created

### Build Failures
- Check Python version (3.11+)
- Verify all dependencies in requirements.txt
- Check build logs for errors

### Runtime Errors
- Check environment variables are set
- Verify Redis connection (if using Celery)
- Check application logs

## Monitoring

### Railway
- View logs in Railway dashboard
- Set up alerts for errors
- Monitor resource usage

### Render
- View logs in Render dashboard
- Set up health checks
- Monitor metrics

## Custom Domain

### Railway
1. Go to project settings
2. Add custom domain
3. Configure DNS records

### Render
1. Go to service settings
2. Add custom domain
3. Configure DNS records

## Security Notes

- Never commit `.env` file
- Use service role key only server-side
- Rotate JWT secret regularly
- Use HTTPS (enabled by default on Railway/Render)
- Set up rate limiting
- Monitor for suspicious activity

## Support

For issues:
1. Check application logs
2. Verify environment variables
3. Test Supabase connection
4. Check deployment platform status

