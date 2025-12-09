# Multi-Tenant Setup Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```

Required variables:
- `JWT_SECRET_KEY` - Random secret for JWT tokens
- `STRIPE_SECRET_KEY` - Stripe API key (for billing)
- `REDIS_URL` - Redis connection (for Celery)
- API keys (Perplexity, OpenRouter)

### 3. Start Services

**Terminal 1 - Redis:**
```bash
redis-server
```

**Terminal 2 - Celery Worker:**
```bash
celery -A core.celery_app worker --loglevel=info
```

**Terminal 3 - Flask App:**
```bash
python web_app.py
```

### 4. First User Registration

Use the API to register:
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "secure_password",
    "first_name": "Admin",
    "last_name": "User"
  }'
```

## Features Implemented

✅ **Lead Deduplication** - Prevents duplicate leads, tracks follow-ups
✅ **Multi-Tenancy** - User accounts, JWT auth, resource isolation
✅ **Background Workers** - Celery for async email sending
✅ **Rate Limiting** - Provider-specific limits (Gmail, Outlook, etc.)
✅ **Email Warmup** - Gradual volume increase for new accounts
✅ **Billing** - Stripe integration for subscriptions
✅ **Compliance** - Terms, Privacy Policy, GDPR

## API Usage

### Authentication
All protected routes require JWT token in header:
```
Authorization: Bearer <token>
```

### Example: Create Campaign
```bash
curl -X POST http://localhost:5000/api/campaign/create \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Campaign",
    "subject": "Hello",
    ...
  }'
```

## Database

The system automatically:
- Creates `users` table
- Adds `user_id` columns to existing tables
- Maintains foreign key relationships
- Isolates data per user

## Next Steps

1. **Frontend**: Add login/register pages
2. **Stripe**: Configure products and prices
3. **Testing**: Test all features with multiple users
4. **Deployment**: Deploy with proper environment variables

