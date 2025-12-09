#!/usr/bin/env python3
"""
Script to fix timestamps for already-sent emails to IST (Kolkata) timezone
This script converts existing timestamps to IST if they're stored in a different timezone
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager, get_ist_now
from datetime import datetime, timezone, timedelta

# Timezone support for IST (Kolkata)
try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo('Asia/Kolkata')
    HAS_PYTZ = False
except ImportError:
    # Fallback for Python < 3.9
    try:
        import pytz
        IST = pytz.timezone('Asia/Kolkata')
        HAS_PYTZ = True
    except ImportError:
        from datetime import timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        HAS_PYTZ = False

def parse_timestamp(ts_str):
    """Parse timestamp string to datetime object"""
    if not ts_str:
        return None
    
    # Try various formats
    formats = [
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except:
            continue
    
    # If all formats fail, try parsing as ISO format
    try:
        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
    except:
        pass
    
    return None

def convert_to_ist(ts):
    """Convert timestamp to IST timezone"""
    if ts is None:
        return get_ist_now()
    
    # If timestamp is naive, assume it's already in IST (or system local time)
    # For existing records, we'll assume they're in UTC and convert to IST
    if ts.tzinfo is None:
        # Assume UTC and convert to IST
        try:
            if HAS_PYTZ:
                # pytz - treat naive datetime as UTC
                import pytz
                utc_dt = pytz.utc.localize(ts)
                ist_dt = utc_dt.astimezone(IST)
            else:
                # zoneinfo - treat naive datetime as UTC
                utc_dt = ts.replace(tzinfo=timezone.utc)
                ist_dt = utc_dt.astimezone(IST)
            # Return as naive datetime (for database storage)
            return ist_dt.replace(tzinfo=None)
        except:
            # If conversion fails, just return the original
            return ts
    else:
        # Timezone-aware datetime - convert to IST
        try:
            ist_dt = ts.astimezone(IST)
            return ist_dt.replace(tzinfo=None)
        except:
            return ts.replace(tzinfo=None)

def fix_sent_emails_timestamps():
    """Fix timestamps in sent_emails table"""
    db = DatabaseManager()
    conn = db.connect()
    cursor = conn.cursor()
    
    print("Fixing timestamps in sent_emails table...")
    
    # Get all sent emails
    cursor.execute("SELECT id, sent_at FROM sent_emails WHERE sent_at IS NOT NULL")
    rows = cursor.fetchall()
    
    updated_count = 0
    for row in rows:
        email_id = row[0]
        sent_at_str = row[1]
        
        # Parse timestamp
        sent_at_dt = parse_timestamp(sent_at_str)
        if sent_at_dt is None:
            print(f"  Warning: Could not parse timestamp for email {email_id}: {sent_at_str}")
            continue
        
        # Convert to IST
        ist_timestamp = convert_to_ist(sent_at_dt)
        
        # Update in database
        cursor.execute("UPDATE sent_emails SET sent_at = ? WHERE id = ?", (ist_timestamp, email_id))
        updated_count += 1
        
        if updated_count % 100 == 0:
            print(f"  Updated {updated_count} records...")
    
    conn.commit()
    print(f"✓ Updated {updated_count} records in sent_emails table")
    return updated_count

def fix_email_queue_timestamps():
    """Fix timestamps in email_queue table"""
    db = DatabaseManager()
    conn = db.connect()
    cursor = conn.cursor()
    
    print("Fixing timestamps in email_queue table...")
    
    # Get all queue items with sent_at
    cursor.execute("SELECT id, sent_at FROM email_queue WHERE sent_at IS NOT NULL")
    rows = cursor.fetchall()
    
    updated_count = 0
    for row in rows:
        queue_id = row[0]
        sent_at_str = row[1]
        
        # Parse timestamp
        sent_at_dt = parse_timestamp(sent_at_str)
        if sent_at_dt is None:
            print(f"  Warning: Could not parse timestamp for queue item {queue_id}: {sent_at_str}")
            continue
        
        # Convert to IST
        ist_timestamp = convert_to_ist(sent_at_dt)
        
        # Update in database
        cursor.execute("UPDATE email_queue SET sent_at = ? WHERE id = ?", (ist_timestamp, queue_id))
        updated_count += 1
        
        if updated_count % 100 == 0:
            print(f"  Updated {updated_count} records...")
    
    conn.commit()
    print(f"✓ Updated {updated_count} records in email_queue table")
    return updated_count

def fix_campaign_recipients_timestamps():
    """Fix timestamps in campaign_recipients table"""
    db = DatabaseManager()
    conn = db.connect()
    cursor = conn.cursor()
    
    print("Fixing timestamps in campaign_recipients table...")
    
    # Get all campaign recipients with sent_at
    cursor.execute("SELECT campaign_id, recipient_id, sent_at FROM campaign_recipients WHERE sent_at IS NOT NULL")
    rows = cursor.fetchall()
    
    updated_count = 0
    for row in rows:
        campaign_id = row[0]
        recipient_id = row[1]
        sent_at_str = row[2]
        
        # Parse timestamp
        sent_at_dt = parse_timestamp(sent_at_str)
        if sent_at_dt is None:
            print(f"  Warning: Could not parse timestamp for campaign {campaign_id}, recipient {recipient_id}: {sent_at_str}")
            continue
        
        # Convert to IST
        ist_timestamp = convert_to_ist(sent_at_dt)
        
        # Update in database
        cursor.execute("""
            UPDATE campaign_recipients 
            SET sent_at = ? 
            WHERE campaign_id = ? AND recipient_id = ?
        """, (ist_timestamp, campaign_id, recipient_id))
        updated_count += 1
        
        if updated_count % 100 == 0:
            print(f"  Updated {updated_count} records...")
    
    conn.commit()
    print(f"✓ Updated {updated_count} records in campaign_recipients table")
    return updated_count

def fix_campaigns_timestamps():
    """Fix timestamps in campaigns table"""
    db = DatabaseManager()
    conn = db.connect()
    cursor = conn.cursor()
    
    print("Fixing timestamps in campaigns table...")
    
    # Get all campaigns with sent_at
    cursor.execute("SELECT id, sent_at FROM campaigns WHERE sent_at IS NOT NULL")
    rows = cursor.fetchall()
    
    updated_count = 0
    for row in rows:
        campaign_id = row[0]
        sent_at_str = row[1]
        
        # Parse timestamp
        sent_at_dt = parse_timestamp(sent_at_str)
        if sent_at_dt is None:
            print(f"  Warning: Could not parse timestamp for campaign {campaign_id}: {sent_at_str}")
            continue
        
        # Convert to IST
        ist_timestamp = convert_to_ist(sent_at_dt)
        
        # Update in database
        cursor.execute("UPDATE campaigns SET sent_at = ? WHERE id = ?", (ist_timestamp, campaign_id))
        updated_count += 1
    
    conn.commit()
    print(f"✓ Updated {updated_count} records in campaigns table")
    return updated_count

def main():
    """Main function to fix all timestamps"""
    print("=" * 60)
    print("Fixing timestamps to IST (Kolkata) timezone")
    print("=" * 60)
    print()
    
    try:
        total_updated = 0
        
        # Fix sent_emails table
        total_updated += fix_sent_emails_timestamps()
        print()
        
        # Fix email_queue table
        total_updated += fix_email_queue_timestamps()
        print()
        
        # Fix campaign_recipients table
        total_updated += fix_campaign_recipients_timestamps()
        print()
        
        # Fix campaigns table
        total_updated += fix_campaigns_timestamps()
        print()
        
        print("=" * 60)
        print(f"✓ All timestamps fixed! Total records updated: {total_updated}")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error fixing timestamps: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
