# Flow Analysis & Implementation Plan

## Current State Analysis

### ✅ What's Currently Working

#### 1. User Registration & Authentication
- ✅ User registration (`/api/auth/register`)
- ✅ User login (`/api/auth/login`)
- ✅ JWT token generation and verification
- ✅ Password hashing (bcrypt)
- ✅ User account management
- **Status**: Fully functional

#### 2. Basic Billing Infrastructure
- ✅ `BillingManager` class exists
- ✅ Plan definitions (free, start, growth, pro, agency)
- ✅ Stripe customer creation
- ✅ Subscription creation method
- ✅ Usage tracking structure
- **Status**: Backend structure exists, but incomplete integration

#### 3. Quota Management
- ✅ `QuotaManager` class with plan-based limits
- ✅ Email quota checking
- ✅ Lead scraping quota
- ✅ LLM token quota tracking
- ✅ Domain limits per plan
- **Status**: Fully functional

#### 4. Email Verification
- ✅ Email verification module (`EmailVerifier`)
- ✅ SMTP verification with rate limiting
- ✅ Paid API support (ZeroBounce)
- ✅ Lead email verification
- **Status**: Functional, but missing signup email verification flow

#### 5. Core Features
- ✅ Lead scraping (Perplexity API)
- ✅ Campaign management
- ✅ Email sending with rate limiting
- ✅ Warmup automation
- ✅ Observability metrics
- **Status**: Fully functional

---

### ❌ What's Missing

#### 1. Landing Page & Pricing Page
- ❌ No landing page (`/` or `/index.html`)
- ❌ No pricing page (`/pricing`)
- ❌ No public-facing marketing pages
- **Impact**: Users can't discover or see pricing before signing up

#### 2. Email Verification Flow (Signup → Verify → Payment)
- ❌ No email verification token generation on signup
- ❌ No email sending on registration
- ❌ No `/verify-email/<token>` endpoint
- ❌ No redirect to Stripe after email verification
- ❌ No email verification status tracking in database
- **Impact**: Users can signup without verifying email, breaking the required flow

#### 3. Stripe Checkout Integration
- ❌ No `/api/billing/create-checkout-session` endpoint
- ❌ No frontend Stripe Checkout integration
- ❌ No redirect to Stripe hosted checkout
- ❌ No checkout session creation with user metadata
- **Impact**: Users can't subscribe after signup

#### 4. Stripe Webhook Handler (CRITICAL MISSING)
- ❌ No `/api/webhooks/stripe` endpoint
- ❌ No webhook signature verification
- ❌ No event handling for:
  - `checkout.session.completed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
- ❌ No subscription data storage after payment
- **Impact**: Payments won't activate accounts - CRITICAL BLOCKER

#### 5. Post-Payment Account Activation
- ❌ No automatic tenant setup after payment
- ❌ No usage counter initialization
- ❌ No warmup schedule creation
- ❌ No domain limits assignment
- ❌ No one-time password generation
- ❌ No access email sending
- **Impact**: Paid users won't get activated accounts

#### 6. Onboarding Wizard
- ❌ No onboarding flow detection
- ❌ No onboarding wizard UI
- ❌ No step-by-step onboarding:
  - Add sending domain
  - DNS verification (SPF/DKIM/DMARC)
  - Add inbox
  - Auto warmup start
  - Custom tracking domain
  - Lead import
- ❌ No onboarding completion tracking
- **Impact**: Users will fail deliverability without proper setup

#### 7. DNS Verification (SPF/DKIM/DMARC)
- ❌ No DNS record checker
- ❌ No SPF record validation
- ❌ No DKIM key generation/validation
- ❌ No DMARC record validation
- ❌ No DNS setup wizard
- **Impact**: Users can't verify domains for sending

#### 8. Policy Enforcement (Mail Server Limits)
- ⚠️ Partial: Rate limiting exists but not enforced at policy level
- ❌ No daily send limit enforcement per plan
- ❌ No warmup speed enforcement
- ❌ No domain rotation enforcement
- ❌ No bounce threshold enforcement
- ❌ No sender reputation score tracking
- **Impact**: Users may exceed limits and get blocked

#### 9. Backend Rules & Quotas
- ✅ Basic quotas exist (email, leads, LLM tokens)
- ❌ No LLM cost quota per plan (only token quota)
- ❌ No lead extraction quota enforcement
- ❌ No email verification quota enforcement
- ❌ No concurrency limit per tenant
- ❌ No auto-pause on bounce threshold
- ❌ No seed inbox deliverability tests
- **Impact**: Cost overruns and deliverability issues

#### 10. Continuous Billing Sync
- ❌ No periodic subscription status sync with Stripe
- ❌ No cancellation handling
- ❌ No renewal handling
- ❌ No proration handling
- ❌ No failed payment handling
- ❌ No automatic downgrade on failed payment
- **Impact**: Subscription status can become out of sync

#### 11. Abuse Prevention
- ❌ No anti-spam limits
- ❌ No banned domain list
- ❌ No bulk-import detection for bad leads
- ❌ No scam keyword detection
- ❌ No rate limiting on account creation
- ❌ No user fingerprinting for multi-account detection
- **Impact**: Platform vulnerable to abuse

---

## Implementation Plan

### Phase 1: Critical Payment Flow (Priority 1) ⚠️ BLOCKER

#### 1.1 Email Verification Flow
**Files to Create/Modify:**
- `backend/core/email_verifier.py` - Add signup email verification
- `backend/web_app.py` - Add email verification endpoints
- `frontend/templates/verify_email.html` - Verification page
- `frontend/templates/register.html` - Add email verification step

**Tasks:**
1. Add `email_verification_token` column to `users` table
2. Generate verification token on registration
3. Send verification email with token
4. Create `/verify-email/<token>` endpoint
5. Mark email as verified in database
6. Redirect to Stripe checkout after verification

**Estimated Time**: 4-6 hours

#### 1.2 Stripe Checkout Integration
**Files to Create/Modify:**
- `backend/web_app.py` - Add checkout session endpoint
- `frontend/static/js/checkout.js` - Stripe.js integration
- `frontend/templates/checkout.html` - Checkout page

**Tasks:**
1. Create `/api/billing/create-checkout-session` endpoint
2. Create Stripe Checkout session with:
   - Customer email
   - Plan selection
   - Success/cancel URLs
   - Metadata (user_id, plan_id)
3. Redirect user to Stripe hosted checkout
4. Handle checkout success redirect

**Estimated Time**: 3-4 hours

#### 1.3 Stripe Webhook Handler (CRITICAL)
**Files to Create/Modify:**
- `backend/web_app.py` - Add webhook endpoint
- `backend/core/billing.py` - Add webhook event handlers

**Tasks:**
1. Create `/api/webhooks/stripe` endpoint (POST)
2. Verify webhook signature using Stripe secret
3. Handle `checkout.session.completed`:
   - Get user_id from metadata
   - Update subscription status
   - Activate account
4. Handle `customer.subscription.created`:
   - Store subscription data
   - Generate plan limits
   - Create usage counters
   - Create tenant row
   - Activate account
5. Handle `customer.subscription.updated`:
   - Update subscription status
   - Update plan limits
6. Handle `customer.subscription.deleted`:
   - Deactivate account
   - Downgrade to free plan
7. Handle `invoice.payment_succeeded`:
   - Confirm subscription active
8. Handle `invoice.payment_failed`:
   - Mark payment as failed
   - Send notification
   - Optionally downgrade after grace period

**Estimated Time**: 6-8 hours

#### 1.4 Post-Payment Account Activation
**Files to Create/Modify:**
- `backend/core/billing.py` - Add activation logic
- `backend/core/auth.py` - Add credential generation
- `backend/core/email_sender.py` - Add access email sending

**Tasks:**
1. Create `activate_account_after_payment(user_id, plan_id)` function:
   - Generate one-time login password
   - Create refresh token pair (if using JWT refresh)
   - Generate tenant ID (if using multi-tenant architecture)
   - Initialize usage quotas based on plan
   - Create warmup schedule
   - Set domain limits based on plan
   - Mark account as active
2. Send access email with:
   - Login credentials
   - Platform URL
   - Getting started guide
3. Create usage counter records:
   - `emails_sent_this_month = 0`
   - `leads_scraped_this_month = 0`
   - `llm_tokens_used_this_month = 0`
   - `campaigns_created_this_month = 0`

**Estimated Time**: 4-5 hours

**Total Phase 1**: 17-23 hours

---

### Phase 2: Onboarding & DNS Verification (Priority 2)

#### 2.1 Onboarding Wizard
**Files to Create/Modify:**
- `frontend/templates/onboarding.html` - Multi-step wizard
- `frontend/static/js/onboarding.js` - Wizard logic
- `backend/web_app.py` - Onboarding endpoints
- `backend/database/db_manager.py` - Add `onboarding_completed` column

**Tasks:**
1. Detect first login after payment
2. Redirect to onboarding if not completed
3. Create multi-step wizard:
   - Step 1: Add sending domain (or Gmail/OAuth)
   - Step 2: Verify DNS (SPF/DKIM/DMARC)
   - Step 3: Add inbox → auto warmup begins
   - Step 4: Add custom tracking domain
   - Step 5: (Optional) Import leads
4. Track onboarding progress
5. Mark onboarding as completed
6. Redirect to dashboard after completion

**Estimated Time**: 8-10 hours

#### 2.2 DNS Verification (SPF/DKIM/DMARC)
**Files to Create/Modify:**
- `backend/core/dns_verifier.py` - NEW FILE
- `backend/web_app.py` - DNS verification endpoints
- `frontend/templates/onboarding.html` - DNS verification UI

**Tasks:**
1. Create `DNSVerifier` class:
   - SPF record validation
   - DKIM key generation and validation
   - DMARC record validation
   - DNS record lookup
2. Generate DKIM keys for domains
3. Provide DNS setup instructions
4. Verify DNS records are correctly configured
5. Store verification status in database

**Estimated Time**: 6-8 hours

**Total Phase 2**: 14-18 hours

---

### Phase 3: Policy Enforcement & Backend Rules (Priority 3)

#### 3.1 Enhanced Policy Enforcement
**Files to Create/Modify:**
- `backend/core/policy_enforcer.py` - NEW FILE
- `backend/core/email_sender.py` - Add policy checks
- `backend/core/quota_manager.py` - Enhance quota checks

**Tasks:**
1. Enforce daily send limits per plan
2. Enforce warmup speed (prevent manual override)
3. Enforce domain rotation (if multiple domains)
4. Enforce bounce thresholds:
   - Auto-pause on >5% bounce rate
   - Alert on >2% bounce rate
5. Track sender reputation score
6. Block sending if reputation too low

**Estimated Time**: 6-8 hours

#### 3.2 Enhanced Backend Rules
**Files to Create/Modify:**
- `backend/core/quota_manager.py` - Add missing quotas
- `backend/core/lead_scraper.py` - Add quota checks
- `backend/core/email_verifier.py` - Add quota checks

**Tasks:**
1. Add LLM cost quota per plan (not just tokens)
2. Enforce lead extraction quota
3. Enforce email verification quota
4. Add concurrency limit per tenant
5. Add daily email cap enforcement
6. Add domain reputation throttling
7. Add auto-pause on bounce threshold
8. Add seed inbox deliverability tests

**Estimated Time**: 8-10 hours

**Total Phase 3**: 14-18 hours

---

### Phase 4: Billing Sync & Abuse Prevention (Priority 4)

#### 4.1 Continuous Billing Sync
**Files to Create/Modify:**
- `backend/core/billing_sync.py` - NEW FILE
- `backend/core/tasks.py` - Add periodic sync task
- `backend/web_app.py` - Add manual sync endpoint

**Tasks:**
1. Create periodic task (every 6 hours) to sync subscription status
2. Handle cancellation:
   - Update subscription status
   - Set account expiration date
   - Send cancellation email
3. Handle renewal:
   - Update subscription end date
   - Reset usage counters
   - Send renewal confirmation
4. Handle proration:
   - Calculate prorated amounts
   - Update billing period
5. Handle failed payments:
   - Mark payment as failed
   - Send payment failure email
   - Give grace period (7 days)
   - Auto-downgrade to free after grace period
   - Suspend account if no payment

**Estimated Time**: 6-8 hours

#### 4.2 Abuse Prevention
**Files to Create/Modify:**
- `backend/core/abuse_prevention.py` - NEW FILE
- `backend/web_app.py` - Add abuse checks to endpoints
- `backend/core/auth.py` - Add rate limiting to registration

**Tasks:**
1. Anti-spam limits:
   - Max emails per hour per user
   - Max recipients per campaign
   - Max campaigns per day
2. Banned domain list:
   - Database table for banned domains
   - Check against list before sending
   - Admin interface to manage list
3. Bulk-import detection:
   - Detect rapid lead imports (>1000 in 1 hour)
   - Flag for review
   - Require manual approval
4. Scam keyword detection:
   - List of scam keywords
   - Check email content
   - Block or flag campaigns
5. Rate limit account creation:
   - Max 3 accounts per IP per day
   - Max 1 account per email domain per day
6. User fingerprinting:
   - Track IP, user agent, browser fingerprint
   - Detect multi-account abusers
   - Flag suspicious accounts

**Estimated Time**: 8-10 hours

**Total Phase 4**: 14-18 hours

---

### Phase 5: Landing & Pricing Pages (Priority 5)

#### 5.1 Landing Page
**Files to Create:**
- `frontend/templates/index.html` - Landing page
- `frontend/static/css/landing.css` - Landing page styles

**Tasks:**
1. Create attractive landing page with:
   - Hero section
   - Features overview
   - Social proof
   - CTA to pricing/signup
2. Add navigation to pricing and signup

**Estimated Time**: 4-6 hours

#### 5.2 Pricing Page
**Files to Create:**
- `frontend/templates/pricing.html` - Pricing page
- `frontend/static/js/pricing.js` - Pricing page logic

**Tasks:**
1. Display all subscription tiers
2. Show features per plan
3. Add "Start / Subscribe" buttons
4. Redirect to signup (if not logged in) or checkout (if logged in)

**Estimated Time**: 3-4 hours

**Total Phase 5**: 7-10 hours

---

## Summary

### Current Flow Status
```
❌ 1. Landing Page → MISSING
❌ 2. Pricing Page → MISSING
⚠️ 3. Signup → EXISTS (but no email verification)
❌ 4. Email Verification → MISSING
❌ 5. Stripe Checkout → MISSING
❌ 6. Stripe Webhook → MISSING (CRITICAL)
❌ 7. Post-Payment Activation → MISSING
❌ 8. Onboarding Wizard → MISSING
⚠️ 9. Policy Enforcement → PARTIAL
⚠️ 10. Backend Rules → PARTIAL
❌ 11. Billing Sync → MISSING
❌ 12. Abuse Prevention → MISSING
```

### Implementation Timeline

**Phase 1 (Critical)**: 17-23 hours
- Email verification flow
- Stripe checkout
- Stripe webhook handler
- Post-payment activation

**Phase 2 (High Priority)**: 14-18 hours
- Onboarding wizard
- DNS verification

**Phase 3 (Medium Priority)**: 14-18 hours
- Policy enforcement
- Backend rules

**Phase 4 (Lower Priority)**: 14-18 hours
- Billing sync
- Abuse prevention

**Phase 5 (Nice to Have)**: 7-10 hours
- Landing page
- Pricing page

**Total Estimated Time**: 66-87 hours (~8-11 working days)

### Critical Path
The product **cannot function as a SaaS** without Phase 1. Users can signup but:
- Can't verify email
- Can't subscribe
- Payments won't activate accounts
- No tenant setup after payment

**Recommendation**: Complete Phase 1 immediately before any other work.

---

## Next Steps

1. **Immediate Action**: Start Phase 1.1 (Email Verification Flow)
2. **Set up Stripe**: Configure Stripe products and webhook endpoint
3. **Test Webhook**: Use Stripe CLI for local webhook testing
4. **Database Migration**: Add required columns (email_verification_token, onboarding_completed, etc.)
5. **Environment Variables**: Add STRIPE_WEBHOOK_SECRET to .env

---

## Files to Create

### New Files Needed:
1. `backend/core/dns_verifier.py` - DNS verification
2. `backend/core/policy_enforcer.py` - Policy enforcement
3. `backend/core/billing_sync.py` - Billing synchronization
4. `backend/core/abuse_prevention.py` - Abuse prevention
5. `frontend/templates/index.html` - Landing page
6. `frontend/templates/pricing.html` - Pricing page
7. `frontend/templates/onboarding.html` - Onboarding wizard
8. `frontend/templates/verify_email.html` - Email verification
9. `frontend/templates/checkout.html` - Stripe checkout
10. `frontend/static/js/checkout.js` - Stripe.js integration
11. `frontend/static/js/onboarding.js` - Onboarding logic
12. `frontend/static/css/landing.css` - Landing page styles

### Files to Modify:
1. `backend/web_app.py` - Add all new endpoints
2. `backend/core/auth.py` - Add email verification
3. `backend/core/billing.py` - Add webhook handlers, activation logic
4. `backend/core/quota_manager.py` - Add missing quotas
5. `backend/database/db_manager.py` - Add new columns
6. `supabase_migration.sql` - Add new columns/tables
7. `frontend/templates/register.html` - Add email verification step

---

## Database Schema Changes Needed

```sql
-- Add to users table
ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN email_verification_token TEXT;
ALTER TABLE users ADD COLUMN email_verification_sent_at TIMESTAMP;
ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN tenant_id TEXT; -- If using multi-tenant architecture
ALTER TABLE users ADD COLUMN one_time_password TEXT;
ALTER TABLE users ADD COLUMN account_activated_at TIMESTAMP;

-- Create domains table for DNS verification
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    spf_verified INTEGER DEFAULT 0,
    dkim_verified INTEGER DEFAULT 0,
    dmarc_verified INTEGER DEFAULT 0,
    dkim_public_key TEXT,
    dkim_private_key TEXT,
    verification_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create usage_counters table
CREATE TABLE IF NOT EXISTS usage_counters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    counter_type TEXT NOT NULL, -- 'emails', 'leads', 'llm_tokens', 'campaigns'
    current_value INTEGER DEFAULT 0,
    reset_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, counter_type)
);

-- Create banned_domains table
CREATE TABLE IF NOT EXISTS banned_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    reason TEXT,
    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_fingerprints table for abuse detection
CREATE TABLE IF NOT EXISTS user_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    browser_fingerprint TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## Environment Variables to Add

```bash
# Stripe Webhook
STRIPE_WEBHOOK_SECRET=whsec_...

# Email Verification
EMAIL_VERIFICATION_ENABLED=true
EMAIL_FROM_ADDRESS=noreply@yourdomain.com
EMAIL_FROM_NAME=Your SaaS Name

# Onboarding
ONBOARDING_REQUIRED=true

# Abuse Prevention
MAX_ACCOUNTS_PER_IP=3
MAX_ACCOUNTS_PER_DOMAIN=1
MAX_EMAILS_PER_HOUR=1000
MAX_RECIPIENTS_PER_CAMPAIGN=10000
```

---

This plan provides a complete roadmap to transform the current codebase into a fully functional SaaS platform with the exact flow you specified.
