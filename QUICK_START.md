# 🚀 Quick Start Guide - ANAGHA SOLUTION

## ✅ Backend is Production Ready!

All issues have been fixed. The software is ready to run as a fully automated, multi-tenant SaaS platform.

## 📋 Setup Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env` File
```bash
# Minimum required
JWT_SECRET_KEY=change-this-to-a-random-secret-key-in-production

# For full functionality (optional)
PERPLEXITY_API_KEY=your-key-here
OPENROUTER_API_KEY=your-key-here
```

### 3. Run the Application
```bash
cd backend
python web_app.py
```

The app will:
- ✅ Auto-initialize database
- ✅ Run migrations
- ✅ Create indexes
- ✅ Start on http://127.0.0.1:5001

## 🎯 First Time Usage

### Step 1: Register a User
```bash
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "securepassword123",
    "first_name": "Admin",
    "last_name": "User"
  }'
```

### Step 2: Login
```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "securepassword123"
  }'
```

**Save the token from the response!**

### Step 3: Access the Web UI
1. Open browser: http://127.0.0.1:5001
2. If prompted, login with your credentials
3. Token will be stored automatically

### Step 4: Configure API Keys (Optional)
1. Go to Settings page
2. Enter Perplexity API key (for lead scraping)
3. Enter OpenRouter API key (for AI personalization)
4. Click Save

### Step 5: Start Using
- **Leads**: Scrape and manage leads
- **Campaigns**: Create email campaigns
- **SMTP**: Add email accounts
- **Analytics**: View performance metrics

## 🔧 What Works Now

✅ **Authentication** - JWT-based, fully functional
✅ **Lead Scraping** - Perplexity API integration
✅ **Lead Verification** - SMTP/MX verification
✅ **Database** - Auto-initialized with all tables
✅ **Multi-tenancy** - Complete user isolation
✅ **API Endpoints** - All working with proper auth
✅ **Frontend** - Token management and error handling

## 🐛 Troubleshooting

### "Authentication required" error
**Solution**: 
1. Make sure you're logged in
2. Check browser console for token errors
3. Try logging in again

### Leads not loading
**Solution**:
1. Check browser console (F12)
2. Verify token is in localStorage: `localStorage.getItem('jwt_token')`
3. Try refreshing the page

### Lead scraper not working
**Solution**:
1. Check PERPLEXITY_API_KEY is set in Settings
2. Verify API key is valid
3. Check job status in database

### Database errors
**Solution**:
- Database auto-initializes on startup
- Check `backend/anagha_solution.db` exists
- Verify file permissions

## 📊 Complete Feature List

- ✅ User registration & authentication
- ✅ Lead scraping (Perplexity API)
- ✅ Email verification (MX + SMTP)
- ✅ Campaign creation & management
- ✅ Email sending (SMTP)
- ✅ Rate limiting & warmup
- ✅ Background workers (Celery)
- ✅ Observability metrics
- ✅ Billing integration (Stripe)
- ✅ Multi-tenant architecture

## 🎉 Ready to Use!

The backend is **fully functional** and ready for production use. All authentication, database, and functionality issues have been resolved.

**Start the server and begin using the platform!**


