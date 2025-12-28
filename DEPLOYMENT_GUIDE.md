# Complete SaaS Deployment Guide

## 🚀 Production-Ready Deployment for ANAGHA SOLUTION

This guide provides step-by-step instructions to deploy the complete multi-tenant SaaS email platform.

---

## 📋 Prerequisites

1. **Supabase Account** (Free tier available)
   - Sign up at https://supabase.com
   - Create a new project
   - Note your Project URL and API Key

2. **Redis Instance** (for Celery workers)
   - Option A: Redis Cloud (free tier)
   - Option B: Railway/Render Redis addon
   - Option C: Self-hosted Redis

3. **Deployment Platform** (choose one):
   - **Railway** (recommended - easiest)
   - **Render** (good alternative)
   - **Heroku** (legacy)
   - **AWS/GCP/Azure** (advanced)

4. **Domain Name** (optional but recommended)
   - For production use

5. **Stripe Account** (for billing)
   - Sign up at https://stripe.com
   - Get API keys from dashboard

---

## 🔧 Step 1: Local Setup & Testing

### 1.1 Clone and Install

```bash
# Clone repository
git clone <your-repo-url>
cd Email-Client

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 1.2 Configure Environment Variables

Create `.env` file in project root:

```bash
# Database Configuration
DATABASE_TYPE=supabase  # or 'sqlite' for local dev
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here

# JWT Secret (generate a strong random string)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production

# Redis Configuration
REDIS_URL=redis://localhost:6379/0  # For local dev
# For production: redis://:password@host:port/0

# API Keys
PERPLEXITY_API_KEY=your-perplexity-api-key
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=openai/gpt-4-turbo-preview

# Email Verification (optional)
EMAIL_VERIFICATION_PROVIDER=zerobounce  # or 'smtp'
EMAIL_VERIFICATION_API_KEY=your-zerobounce-key

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# Encryption Key (auto-generated, but can set manually)
ENCRYPTION_KEY=your-32-byte-base64-encoded-key

# Deployment URL (for production)
DEPLOYMENT_URL=https://your-domain.com
```

### 1.3 Initialize Supabase Database

**Option A: Automatic (if service key available)**

```bash
python3 backend/database/init_supabase.py
```

**Option B: Manual (recommended for first time)**

1. Go to Supabase Dashboard → SQL Editor
2. Open `supabase_migration.sql` (generated automatically)
3. Copy all SQL statements
4. Paste into SQL Editor
5. Click "Run"

**Verify tables created:**
- Go to Supabase Dashboard → Table Editor
- You should see: `users`, `leads`, `campaigns`, `recipients`, `smtp_servers`, etc.

### 1.4 Test Locally

```bash
# Start Redis (if local)
redis-server

# Start Celery worker (in separate terminal)
celery -A backend.core.celery_app worker --loglevel=info

# Start Flask app
cd backend
python web_app.py
```

Visit: http://localhost:5001

---

## 🌐 Step 2: Deploy to Railway (Recommended)

### 2.1 Setup Railway Account

1. Sign up at https://railway.app
2. Install Railway CLI: `npm i -g @railway/cli`
3. Login: `railway login`

### 2.2 Create Railway Project

```bash
# In project root
railway init

# Link to existing project (if you have one)
railway link
```

### 2.3 Add Services

**Add Redis:**
```bash
railway add redis
```

**Add PostgreSQL (optional, if not using Supabase):**
```bash
railway add postgresql
```

### 2.4 Configure Environment Variables

In Railway Dashboard → Variables, add:

```env
DATABASE_TYPE=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
JWT_SECRET_KEY=your-secret-key
REDIS_URL=${{Redis.REDIS_URL}}  # Auto-filled from Redis service
PERPLEXITY_API_KEY=your-key
OPENROUTER_API_KEY=your-key
STRIPE_SECRET_KEY=your-key
STRIPE_PUBLISHABLE_KEY=your-key
ENCRYPTION_KEY=your-key
DEPLOYMENT_URL=https://your-app.railway.app
```

### 2.5 Create Railway Configuration

Create `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "cd backend && gunicorn -w 4 -b 0.0.0.0:$PORT web_app:app",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 2.6 Deploy

```bash
# Deploy
railway up

# Or connect GitHub repo for auto-deploy
railway github
```

### 2.7 Setup Celery Worker

Create separate Railway service for Celery:

```bash
# Create new service
railway service create celery-worker

# Set start command
railery service set startCommand "celery -A backend.core.celery_app worker --loglevel=info"

# Deploy
railway up
```

---

## 🌐 Step 3: Deploy to Render (Alternative)

### 3.1 Setup Render Account

1. Sign up at https://render.com
2. Connect GitHub repository

### 3.2 Create Web Service

1. Dashboard → New → Web Service
2. Connect your repository
3. Configure:

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
cd backend && gunicorn -w 4 -b 0.0.0.0:$PORT web_app:app
```

**Environment Variables:**
- Add all variables from `.env` file
- Set `PORT=10000` (Render auto-assigns)

### 3.3 Create Redis Instance

1. Dashboard → New → Redis
2. Note connection URL
3. Add to environment variables as `REDIS_URL`

### 3.4 Create Celery Worker Service

1. Dashboard → New → Background Worker
2. Same repository
3. Start Command:
```bash
celery -A backend.core.celery_app worker --loglevel=info
```
4. Add same environment variables

### 3.5 Deploy

- Render auto-deploys on git push
- Or manually trigger from dashboard

---

## 🔐 Step 4: Security Configuration

### 4.1 Update JWT Secret

Generate strong secret:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to environment variables.

### 4.2 Enable HTTPS

- Railway: Automatic with custom domain
- Render: Automatic with custom domain
- Add custom domain in platform dashboard

### 4.3 Configure CORS

Update `backend/web_app.py`:
```python
CORS(app, resources={
    r"/*": {
        "origins": ["https://your-domain.com"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

### 4.4 Set Up Rate Limiting

Already configured in code. Adjust in `backend/core/rate_limiter.py` if needed.

---

## 📊 Step 5: Initialize Database (Production)

### 5.1 Run Migration

**Option A: Via Script**
```bash
python3 backend/database/init_supabase.py
```

**Option B: Via Supabase Dashboard**
1. Go to Supabase Dashboard → SQL Editor
2. Run `supabase_migration.sql`

### 5.2 Verify Tables

Check Supabase Dashboard → Table Editor:
- ✓ users
- ✓ leads
- ✓ campaigns
- ✓ recipients
- ✓ smtp_servers
- ✓ email_queue
- ✓ templates
- ✓ email_tracking
- ✓ daily_stats
- ✓ app_settings
- ✓ llm_usage_metrics
- ✓ observability_metrics
- ✓ alerts

---

## 🧪 Step 6: Test Deployment

### 6.1 Health Check

```bash
curl https://your-app.railway.app/health
```

Expected: `{"status": "ok", "message": "..."}`

### 6.2 Test Registration

```bash
curl -X POST https://your-app.railway.app/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
  }'
```

Expected: `{"success": true, "token": "...", "user_id": 1}`

### 6.3 Test Login

```bash
curl -X POST https://your-app.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'
```

Expected: `{"success": true, "token": "...", "user": {...}}`

### 6.4 Test Protected Endpoint

```bash
curl https://your-app.railway.app/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🔄 Step 7: Continuous Deployment

### 7.1 GitHub Actions (Optional)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Railway

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - name: Deploy to Railway
        run: |
          npm i -g @railway/cli
          railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

### 7.2 Environment Variables in CI/CD

- Never commit `.env` file
- Store secrets in platform's secret management
- Use GitHub Secrets for CI/CD

---

## 📈 Step 8: Monitoring & Maintenance

### 8.1 Application Monitoring

**Railway:**
- Built-in metrics dashboard
- Logs available in dashboard

**Render:**
- Metrics in service dashboard
- Logs streaming available

**Third-party:**
- Sentry for error tracking
- Datadog/New Relic for APM

### 8.2 Database Monitoring

**Supabase:**
- Dashboard → Database → Metrics
- Monitor query performance
- Set up alerts for high usage

### 8.3 Celery Monitoring

**Flower (optional):**
```bash
pip install flower
celery -A backend.core.celery_app flower
```

Access at: `http://your-domain.com:5555`

---

## 🚨 Step 9: Troubleshooting

### Issue: Tables not created in Supabase

**Solution:**
1. Check Supabase URL and Key in environment
2. Run migration manually in SQL Editor
3. Verify service role key if using auto-creation

### Issue: Celery workers not processing

**Solution:**
1. Check Redis connection
2. Verify `REDIS_URL` environment variable
3. Check worker logs for errors

### Issue: Registration/Login fails

**Solution:**
1. Verify database tables exist
2. Check JWT_SECRET_KEY is set
3. Check database connection
4. Review application logs

### Issue: Static files not loading

**Solution:**
1. Verify `static_folder` path in Flask config
2. Check file permissions
3. Verify deployment includes `frontend/static/` directory

---

## ✅ Step 10: Post-Deployment Checklist

- [ ] Database tables created and verified
- [ ] Environment variables configured
- [ ] Registration endpoint working
- [ ] Login endpoint working
- [ ] Celery workers running
- [ ] Redis connected
- [ ] HTTPS enabled
- [ ] Custom domain configured (optional)
- [ ] Stripe keys configured
- [ ] API keys configured
- [ ] Monitoring set up
- [ ] Backup strategy in place

---

## 📚 Additional Resources

- **Supabase Docs**: https://supabase.com/docs
- **Railway Docs**: https://docs.railway.app
- **Render Docs**: https://render.com/docs
- **Celery Docs**: https://docs.celeryproject.org
- **Stripe Docs**: https://stripe.com/docs

---

## 🎉 Success!

Your multi-tenant SaaS email platform is now deployed and ready for production use!

**Next Steps:**
1. Create your first user account
2. Configure SMTP servers
3. Import/scrape leads
4. Create campaigns
5. Start sending emails!

---

**Need Help?**
- Check logs in deployment platform dashboard
- Review error messages in application logs
- Verify all environment variables are set correctly
- Ensure database tables are created
