# Quick Start - Supabase + Railway/Render Deployment

## 🚀 Quick Setup

### 1. Supabase Setup (5 minutes)
1. Go to https://supabase.com and create account
2. Create new project
3. Copy Project URL and API Key from Settings > API
4. Add to Settings page in the app

### 2. Deploy to Railway (5 minutes)
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize
railway init

# Add environment variables
railway variables set SUPABASE_URL=https://xxxxx.supabase.co
railway variables set SUPABASE_KEY=your_key
railway variables set JWT_SECRET_KEY=random_secret
railway variables set DATABASE_TYPE=supabase

# Deploy
railway up
```

### 3. Deploy to Render (5 minutes)
1. Go to https://render.com
2. New > Web Service
3. Connect GitHub repo
4. Set build: `pip install -r requirements.txt`
5. Set start: `gunicorn --bind 0.0.0.0:$PORT web_app:app`
6. Add environment variables
7. Deploy!

## 📋 All Settings in One Place

Go to **Settings** page in the app to configure:
- ✅ Supabase database connection
- ✅ API keys (Perplexity, OpenRouter)
- ✅ Deployment settings
- ✅ Database connection status
- ✅ Environment variables

Everything is controlled from the Settings page - no manual file editing needed!

## 📚 Full Documentation

See `DEPLOYMENT_GUIDE.md` for detailed instructions.

