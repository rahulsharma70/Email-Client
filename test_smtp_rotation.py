#!/usr/bin/env python3
"""
Test script to verify SMTP server rotation is working
"""
import sqlite3
import os

def test_smtp_rotation():
    """Test that queue items are distributed across different SMTP servers"""
    db_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'dashboard', 'anagha_solution.db')
    
    if not os.path.exists(db_path):
        print("Database not found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check pending queue items and their SMTP assignments
    print("=== Testing SMTP Server Rotation ===\n")
    
    cursor.execute("""
        SELECT eq.id, eq.smtp_server_id, s.username, s.host
        FROM email_queue eq
        INNER JOIN smtp_servers s ON eq.smtp_server_id = s.id
        WHERE eq.status = 'pending'
        ORDER BY eq.smtp_server_id ASC, eq.created_at ASC
        LIMIT 10
    """)
    
    items = cursor.fetchall()
    
    if not items:
        print("No pending emails in queue")
        conn.close()
        return
    
    print(f"Found {len(items)} pending emails:\n")
    
    server_counts = {}
    for queue_id, smtp_id, username, host in items:
        if smtp_id not in server_counts:
            server_counts[smtp_id] = []
        server_counts[smtp_id].append((queue_id, username, host))
        print(f"  Queue {queue_id}: SMTP Server {smtp_id} ({username} @ {host})")
    
    print(f"\n=== Distribution Summary ===")
    for smtp_id in sorted(server_counts.keys()):
        count = len(server_counts[smtp_id])
        username = server_counts[smtp_id][0][1]
        print(f"  Server {smtp_id} ({username}): {count} emails")
    
    # Verify the email sender query will pick different servers
    print(f"\n=== Email Sender Query Test ===")
    cursor.execute("""
        SELECT eq.id as queue_id, eq.smtp_server_id, s.username, s.host
        FROM email_queue eq
        INNER JOIN smtp_servers s ON eq.smtp_server_id = s.id
        WHERE eq.status = 'pending'
        ORDER BY eq.smtp_server_id ASC, eq.created_at ASC
        LIMIT 5
    """)
    
    next_items = cursor.fetchall()
    print("Next 5 items email sender will pick:")
    for queue_id, smtp_id, username, host in next_items:
        print(f"  Queue {queue_id}: Server {smtp_id} ({username})")
    
    conn.close()
    print("\n✅ Test complete!")

if __name__ == '__main__':
    test_smtp_rotation()

