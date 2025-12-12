# SMTP Authentication & B2B/B2C Lead Scraping Fixes

## Issues Fixed

### 1. SMTP Authentication Error ✅
**Problem**: `Recipient refused: Please turn on SMTP Authentication`

**Root Cause**: 
- Authentication might be failing silently
- Connection might be reset after login
- Password might need to be re-encoded

**Solution**:
- Enhanced authentication with multiple fallback methods (LOGIN, PLAIN)
- Added connection verification with NOOP command before sending
- Added re-authentication if connection is lost
- Ensured password is always a string (not bytes)
- Added detailed error logging

**Files Modified**:
- `backend/core/email_sender.py` - Enhanced authentication logic

### 2. B2B/B2C Lead Scraping Options ✅
**Problem**: Only B2B (company → decision makers) scraping was available

**Solution**:
- Added `lead_type` field (B2B or B2C) to scraping jobs
- Created `extract_individuals_from_icp()` method for B2C scraping
- Modified `run_full_scraping_job()` to handle both types
- Updated UI to allow selection between B2B and B2C
- Updated database schema to store lead_type

**Files Modified**:
- `backend/core/lead_scraper.py` - Added B2C extraction logic
- `backend/web_app.py` - Updated API to accept lead_type
- `backend/core/tasks.py` - Updated task to pass lead_type
- `frontend/templates/leads.html` - Added lead type selector
- `backend/database/supabase_manager.py` - Added lead_type to job creation
- `supabase_migration.sql` - Added lead_type column

## B2B vs B2C Scraping

### B2B Mode (Default)
**Flow**: ICP → Companies → Decision Makers → Email Patterns → Verification

**Use Case**: Target companies and find decision makers (CEOs, VPs, Directors)

**Example ICP**: "SaaS companies with 50-200 employees in marketing tech"

### B2C Mode (New)
**Flow**: ICP → Individual People → Email Patterns → Verification

**Use Case**: Target individual people directly (students, engineers, freelancers)

**Example ICP**: "Software engineers working in tech companies, San Francisco, 3-5 years experience"

## Database Changes

### lead_scraping_jobs Table
```sql
ALTER TABLE lead_scraping_jobs ADD COLUMN lead_type TEXT DEFAULT 'B2B';
```

**Values**: 'B2B' or 'B2C'

## SMTP Authentication Improvements

### Enhanced Authentication Flow
1. **Standard Login**: Try `server.login()` first
2. **Connection Verification**: Use `server.noop()` to verify connection
3. **Re-authentication**: If connection lost, re-authenticate before sending
4. **Fallback Methods**: Try AUTH PLAIN and AUTH LOGIN if standard fails
5. **Password Encoding**: Ensure password is string (decode bytes if needed)

### Error Handling
- Detailed error messages with authentication method attempted
- Graceful fallback between authentication methods
- Connection state verification before sending

## Testing Checklist

### SMTP Authentication
- [ ] Test with various SMTP servers (Gmail, Outlook, custom)
- [ ] Verify authentication works with different password types
- [ ] Check that connection persists through email sending
- [ ] Test re-authentication when connection is lost

### B2B Scraping
- [ ] Select "B2B" mode
- [ ] Enter ICP description for companies
- [ ] Verify companies are found
- [ ] Verify decision makers are extracted
- [ ] Verify leads are created correctly

### B2C Scraping
- [ ] Select "B2C" mode
- [ ] Enter ICP description for individuals
- [ ] Verify individuals are found
- [ ] Verify leads are created correctly
- [ ] Check that individuals have proper fields (name, email, profession)

## UI Changes

### Lead Scraping Modal
- Added dropdown to select "B2B" or "B2C"
- Updated placeholder text to show examples for both types
- Added help text explaining the difference

### Form Submission
- Includes `lead_type` in API request
- Validates lead_type before submission

## API Changes

### POST /api/leads/scrape
**New Parameter**:
```json
{
  "icp_description": "...",
  "lead_type": "B2B" // or "B2C"
}
```

**Default**: If `lead_type` not provided, defaults to 'B2B'

---

All fixes completed! 🎉
