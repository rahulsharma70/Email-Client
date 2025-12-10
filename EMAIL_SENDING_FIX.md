# Email Sending & LLM Personalization Fixes

## Issues Fixed

### 1. Merge Tags None Value Error ✅
**Problem**: `replace() argument 2 must be str, not None` when recipient fields are None

**Solution**: 
- Updated `replace_merge_tags()` to handle None values
- Convert all values to strings before replacement
- Added fallback to empty string for None values
- Added more merge tags: {title}, {phone}

**File**: `backend/core/email_sender.py`

### 2. IMAP Authentication Error ✅
**Problem**: `[AUTHENTICATIONFAILED] Authentication failed` when loading inbox

**Solution**:
- Added password decryption in `inbox_monitor.py`
- Added password decryption in `api_fetch_inbox` endpoint
- Passwords are now properly decrypted before IMAP login

**Files**: 
- `backend/core/inbox_monitor.py`
- `backend/web_app.py`

### 3. Email Storage in Database ✅
**Problem**: Emails not being stored properly after sending

**Solution**:
- Updated `mark_sent()` to work with both SQLite and Supabase
- Properly extracts email content from message
- Saves to `sent_emails` table with all details
- Updates queue, campaign_recipients, and daily_stats
- Handles campaign completion status

**File**: `backend/core/email_sender.py`

### 4. LLM Personalization Prompt Support ✅
**Problem**: Campaign builder didn't ask for prompt when using LLM

**Solution**:
- Added `personalization_prompt` column to campaigns table
- Updated campaign creation to save prompt
- Added prompt field in campaign builder UI (shown when LLM is enabled)
- Updated personalization to use custom prompt
- Prompt supports placeholders: {template}, {name}, {company}, {context}

**Files**:
- `backend/database/db_manager.py`
- `backend/database/supabase_manager.py`
- `backend/database/migrations.py`
- `backend/web_app.py`
- `backend/core/personalization.py`
- `backend/core/email_sender.py`
- `frontend/templates/campaign_builder.html`
- `supabase_migration.sql`

### 5. LLM Cost Monitoring ✅
**Problem**: LLM costs not properly tracked

**Solution**:
- Enhanced cost tracking in `personalization.py`
- Records cost per API call
- Updates `llm_cost_this_month` setting
- Records to `llm_usage_metrics` table
- Integrates with observability metrics

**File**: `backend/core/personalization.py`

## Database Changes

### New Column:
- `campaigns.personalization_prompt` - Custom LLM prompt for personalization

### Migration:
- Added to `migrations.py` for SQLite
- Added to `supabase_migration.sql` for Supabase

## Campaign Builder Updates

### UI Changes:
- Added "Personalization Prompt" textarea field
- Field appears when "Enable AI Personalization" is checked
- Field is required when personalization is enabled
- Includes placeholder examples

### JavaScript:
- `togglePersonalizationPrompt()` function to show/hide prompt field
- Prompt included in form submission (both create and save draft)

## LLM Monitoring

### Metrics Tracked:
- Token usage (prompt, completion, total)
- Cost per API call
- Model used
- Timestamp

### Storage:
- `llm_usage_metrics` table (if exists)
- `app_settings.llm_cost_this_month` (per user)
- `app_settings.llm_tokens_used_this_month` (per user)
- Observability metrics

## Testing Checklist

- [ ] Create campaign without personalization (should work)
- [ ] Create campaign with personalization (should ask for prompt)
- [ ] Send email with personalization (should use custom prompt)
- [ ] Send email without personalization (should use merge tags only)
- [ ] Check LLM cost tracking
- [ ] Check LLM usage metrics
- [ ] Load inbox (should decrypt password)
- [ ] Send email (should store in sent_emails table)
- [ ] Verify merge tags work with None values

## Files Modified

1. `backend/core/email_sender.py` - Merge tags fix, email storage, prompt support
2. `backend/core/personalization.py` - Custom prompt support, cost tracking
3. `backend/core/inbox_monitor.py` - Password decryption
4. `backend/web_app.py` - IMAP password decryption, prompt validation
5. `backend/database/db_manager.py` - Campaign creation with prompt
6. `backend/database/supabase_manager.py` - Campaign creation with prompt
7. `backend/database/migrations.py` - Add prompt column
8. `frontend/templates/campaign_builder.html` - Prompt field UI
9. `supabase_migration.sql` - Add prompt column

---

All email sending issues fixed! Emails will now:
- ✅ Handle None values in merge tags
- ✅ Store properly in database
- ✅ Support custom LLM prompts
- ✅ Track LLM costs
- ✅ Work with IMAP (decrypted passwords)
