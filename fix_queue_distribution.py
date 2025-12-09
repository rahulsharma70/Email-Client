#!/usr/bin/env python3
"""
Script to fix queue distribution - redistribute pending emails across SMTP servers
"""
import sqlite3
import os

def fix_queue_distribution():
    """Redistribute pending emails across available SMTP servers"""
    db_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'dashboard', 'anagha_solution.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all pending emails
    cursor.execute("""
        SELECT id, campaign_id, recipient_id, smtp_server_id
        FROM email_queue
        WHERE status = 'pending'
        ORDER BY id
    """)
    
    pending_items = cursor.fetchall()
    
    if not pending_items:
        print("No pending emails in queue")
        conn.close()
        return
    
    print(f"Found {len(pending_items)} pending emails")
    
    # Get active SMTP servers
    cursor.execute("""
        SELECT id FROM smtp_servers
        WHERE is_active = 1
        ORDER BY id ASC
    """)
    
    active_servers = [row[0] for row in cursor.fetchall()]
    
    if not active_servers:
        print("No active SMTP servers found!")
        conn.close()
        return
    
    print(f"Active SMTP servers: {active_servers}")
    
    # Redistribute: 20 emails per server
    emails_per_server = 20
    num_servers = len(active_servers)
    total_to_send = min(len(pending_items), emails_per_server * num_servers)
    
    print(f"Redistributing {total_to_send} emails across {num_servers} servers ({emails_per_server} per server)")
    
    # Redistribute emails
    redistributed = 0
    for index, (queue_id, campaign_id, recipient_id, old_smtp_id) in enumerate(pending_items[:total_to_send]):
        # Calculate which server to use (round-robin)
        server_index = (index // emails_per_server) % num_servers
        new_smtp_id = active_servers[server_index]
        
        # Update queue item
        cursor.execute("""
            UPDATE email_queue
            SET smtp_server_id = ?
            WHERE id = ?
        """, (new_smtp_id, queue_id))
        
        redistributed += 1
        
        if index < 5 or (index + 1) % 20 == 0:
            print(f"  Queue {queue_id}: SMTP {old_smtp_id} → {new_smtp_id} (Server index {server_index})")
    
    conn.commit()
    
    # Verify distribution
    cursor.execute("""
        SELECT smtp_server_id, COUNT(*) as count
        FROM email_queue
        WHERE status = 'pending'
        GROUP BY smtp_server_id
        ORDER BY smtp_server_id
    """)
    
    distribution = cursor.fetchall()
    print(f"\n✅ Redistributed {redistributed} emails")
    print("\n📊 New Distribution:")
    for smtp_id, count in distribution:
        print(f"   Server {smtp_id}: {count} emails")
    
    conn.close()
    print("\n✅ Queue distribution fixed!")

if __name__ == '__main__':
    fix_queue_distribution()

