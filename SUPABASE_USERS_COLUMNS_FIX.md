# Supabase Users Table Columns Fix

## Issue Fixed

**Error**: `column users.email_verified does not exist`

**Root Cause**: The Supabase migration SQL was missing the email verification and onboarding columns that were added to the SQLite schema.

## Solution

Added missing columns to the `users` table in Supabase:

1. **Email Verification Columns**:
   - `email_verified` (INTEGER DEFAULT 0)
   - `email_verification_token` (TEXT)
   - `email_verification_sent_at` (TIMESTAMP)

2. **Account Activation Columns**:
   - `one_time_password` (TEXT)
   - `account_activated_at` (TIMESTAMP)

3. **Onboarding Columns**:
   - `onboarding_completed` (INTEGER DEFAULT 0)
   - `onboarding_step` (INTEGER DEFAULT 0)
   - `onboarding_data` (TEXT)

## Files Modified

1. `supabase_migration.sql` - Added columns to CREATE TABLE and ALTER TABLE statements
2. `backend/database/supabase_schema.py` - Updated users table schema

## Migration Steps

### For New Supabase Instances
The updated migration SQL will create tables with all required columns.

### For Existing Supabase Instances
Run the following in Supabase SQL Editor:

```sql
-- Add email verification and onboarding columns if they don't exist
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
```

Or simply run the updated `supabase_migration.sql` file - it includes the DO block to add columns automatically.

## Verification

After running the migration, verify columns exist:
```sql
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' 
ORDER BY ordinal_position;
```

You should see all the new columns listed.

---

Fix completed! ✅
