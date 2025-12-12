# Duplicate Lead Removal API

## Automatic Duplicate Removal

Duplicate unverified leads are automatically removed when adding leads:

- ✅ Verified leads are NEVER deleted
- ✅ Duplicate unverified leads (same email) are removed automatically
- ✅ Only the first unverified lead is kept, others are deleted
- ✅ Works for both manual adds and scraping

## Manual Cleanup (Optional)

If you want to manually clean duplicates, you can add this endpoint:

```python
@app.route('/api/leads/clean-duplicates', methods=['POST'])
@require_auth
def api_clean_duplicate_leads(user_id):
    """Remove duplicate unverified leads for the current user"""
    try:
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Get all leads for user
            result = db.supabase.client.table('leads').select('id, email, is_verified').eq('user_id', user_id).execute()
            leads = result.data if result.data else []
        else:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, is_verified FROM leads WHERE user_id = ?", (user_id,))
            leads = [{'id': r[0], 'email': r[1], 'is_verified': r[2]} for r in cursor.fetchall()]
        
        # Group by email
        email_groups = {}
        for lead in leads:
            email = lead['email'].lower().strip()
            if email not in email_groups:
                email_groups[email] = []
            email_groups[email].append(lead)
        
        # Find duplicates (same email, multiple unverified leads)
        removed_count = 0
        for email, email_leads in email_groups.items():
            if len(email_leads) <= 1:
                continue
            
            # Separate verified and unverified
            verified = [l for l in email_leads if l.get('is_verified') == 1]
            unverified = [l for l in email_leads if l.get('is_verified') == 0]
            
            # If multiple unverified, keep first, delete rest
            if len(unverified) > 1:
                ids_to_delete = [l['id'] for l in unverified[1:]]
                for lead_id in ids_to_delete:
                    if use_supabase:
                        db.supabase.client.table('leads').delete().eq('id', lead_id).execute()
                    else:
                        cursor.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
                removed_count += len(ids_to_delete)
        
        if not use_supabase:
            conn.commit()
        
        return jsonify({
            'success': True,
            'removed_count': removed_count,
            'message': f'Removed {removed_count} duplicate unverified leads'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

**Note**: Duplicate removal happens automatically when adding leads. This endpoint is optional for manual cleanup.
