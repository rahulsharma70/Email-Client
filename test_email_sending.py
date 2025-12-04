"""
Test script to check email sending functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from core.email_sender import EmailSender

def test_email_sending():
    print("=" * 50)
    print("Testing Email Sending Functionality")
    print("=" * 50)
    
    db = DatabaseManager()
    db.initialize_database()
    
    # Check queue
    queue_stats = db.get_queue_stats()
    print(f"\nQueue Status:")
    print(f"  Pending: {queue_stats.get('pending', 0)}")
    print(f"  Sent Today: {queue_stats.get('sent_today', 0)}")
    
    # Check recipients
    recipients = db.get_recipients()
    print(f"\nRecipients: {len(recipients)}")
    
    # Check SMTP servers
    smtp_servers = db.get_smtp_servers()
    print(f"\nSMTP Servers: {len(smtp_servers)}")
    for server in smtp_servers:
        print(f"  - {server.get('name')} ({server.get('host')}) - {'Active' if server.get('is_active') else 'Inactive'}")
    
    # Check campaigns
    campaigns = db.get_campaigns()
    print(f"\nCampaigns: {len(campaigns)}")
    
    if queue_stats.get('pending', 0) > 0:
        print("\n✅ There are emails in the queue!")
        print("Starting email sender...")
        sender = EmailSender(db, interval=1.0, max_threads=2)
        sender.start_sending()
        print("Email sender started. Check the logs for sending progress.")
    else:
        print("\n⚠️  No emails in queue. Create a campaign and send it first.")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_email_sending()

