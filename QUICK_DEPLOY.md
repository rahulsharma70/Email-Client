# Quick Deployment Guide

## 🚀 Fast Track to Production

### Step 1: Setup Supabase (5 minutes)

1. Go to https://supabase.com and create account
2. Create new project
3. Copy **Project URL** and **anon key** from Settings → API
4. Add to `.env`:
   ```
   DATABASE_TYPE=supabase
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_KEY=your-anon-key-here
   ```

### Step 2: Initialize Database (2 minutes)

**Option A: Automatic (if service key available)**
```bash
python3 backend/database/init_supabase.py
```

**Option B: Manual (recommended)**
1. Go to Supabase Dashboard → SQL Editor
2. Open `supabase_migration.sql` file
3. Copy all SQL
4. Paste into SQL Editor
5. Click "Run"

**Verify:** Go to Table Editor - you should see all tables

### Step 3: Deploy to Railway (10 minutes)

1. Sign up at https://railway.app
2. Install CLI: `npm i -g @railway/cli`
3. Login: `railway login`
4. In project: `railway init`
5. Add Redis: `railway add redis`
6. Set environment variables in Railway dashboard:
   - All variables from `.env` file
   - `REDIS_URL` auto-filled from Redis service
7. Deploy: `railway up`

### Step 4: Setup Celery Worker

1. Create new service: `railway service create celery-worker`
2. Set start command: `celery -A backend.core.celery_app worker --loglevel=info`
3. Add same environment variables
4. Deploy: `railway up`

### Step 5: Test

1. Visit your Railway URL
2. Register a new account
3. Login
4. Start using the platform!

---

## ✅ Checklist

- [ ] Supabase project created
- [ ] Database tables created (check Table Editor)
- [ ] Railway account created
- [ ] App deployed to Railway
- [ ] Redis service added
- [ ] Celery worker deployed
- [ ] Environment variables set
- [ ] Registration works
- [ ] Login works
- [ ] Can access dashboard

---

## 🔧 Troubleshooting

**Tables not in Supabase?**
- Run `supabase_migration.sql` manually in SQL Editor

**Registration fails?**
- Check database tables exist
- Check JWT_SECRET_KEY is set
- Check logs in Railway dashboard

**Celery not working?**
- Check Redis connection
- Verify REDIS_URL is set
- Check worker logs

---

**Full deployment guide:** See `DEPLOYMENT_GUIDE.md`


