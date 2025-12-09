"""
Background Tasks for ANAGHA SOLUTION
Celery tasks for async processing
"""

from core.celery_app import celery_app
from database.db_manager import DatabaseManager
from core.email_sender import EmailSender
from core.email_verifier import EmailVerifier
from core.lead_scraper import LeadScraper
from core.inbox_monitor import InboxMonitor
from core.rate_limiter import RateLimiter
from core.warmup import WarmupManager
import time

@celery_app.task(name='core.tasks.send_email_task', bind=True, max_retries=3)
def send_email_task(self, queue_item_id: int, user_id: int):
    """
    Background task to send email
    
    Args:
        queue_item_id: Email queue item ID
        user_id: User ID for multi-tenant
    """
    try:
        db = DatabaseManager()
        
        # Get queue item with user_id check
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT eq.*, c.user_id, s.user_id as smtp_user_id
            FROM email_queue eq
            JOIN campaigns c ON eq.campaign_id = c.id
            JOIN smtp_servers s ON eq.smtp_server_id = s.id
            WHERE eq.id = ? AND c.user_id = ? AND s.user_id = ?
        """, (queue_item_id, user_id, user_id))
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'error': 'Queue item not found or access denied'}
        
        # Check rate limits
        rate_limiter = RateLimiter(db)
        smtp_server_id = row['smtp_server_id']
        rate_check = rate_limiter.check_rate_limit(smtp_server_id)
        
        if not rate_check.get('can_send'):
            # Retry later
            raise self.retry(countdown=3600, exc=Exception(rate_check.get('reason')))
        
        # Check warmup
        warmup_manager = WarmupManager(db)
        warmup_check = warmup_manager.can_send_email(smtp_server_id)
        
        if not warmup_check.get('can_send'):
            raise self.retry(countdown=3600, exc=Exception(warmup_check.get('reason')))
        
        # Get delay from warmup
        delay = warmup_check.get('delay_seconds', 30)
        time.sleep(delay)
        
        # Send email using EmailSender
        email_sender = EmailSender(db, interval=0, max_threads=1)
        # Convert row to dict for send_email
        queue_item = dict(row)
        email_sender.send_email(queue_item)
        
        # Update counters
        rate_limiter.increment_sent_count(smtp_server_id)
        warmup_manager.update_warmup_progress(smtp_server_id)
        
        return {'success': True, 'queue_item_id': queue_item_id}
        
    except Exception as e:
        print(f"Error in send_email_task: {e}")
        raise self.retry(exc=e, countdown=60)

@celery_app.task(name='core.tasks.verify_email_task')
def verify_email_task(lead_id: int, user_id: int):
    """Background task to verify email"""
    try:
        db = DatabaseManager()
        verifier = EmailVerifier(db)
        result = verifier.verify_lead_email(lead_id)
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}

@celery_app.task(name='core.tasks.scrape_leads_task')
def scrape_leads_task(icp_description: str, job_id: int, user_id: int):
    """Background task to scrape leads"""
    try:
        db = DatabaseManager()
        scraper = LeadScraper(db)
        result = scraper.run_full_scraping_job(icp_description, job_id=job_id)
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}

@celery_app.task(name='core.tasks.monitor_inbox_task')
def monitor_inbox_task(account_id: int, user_id: int):
    """Background task to monitor inbox"""
    try:
        db = DatabaseManager()
        monitor = InboxMonitor(db)
        result = monitor.monitor_and_update(account_id)
        return result
    except Exception as e:
        return {'success': False, 'error': str(e)}

@celery_app.task(name='core.tasks.process_email_queue')
def process_email_queue(user_id: int):
    """Process email queue for a user"""
    try:
        db = DatabaseManager()
        email_sender = EmailSender(db, interval=30, max_threads=1)
        
        # Get pending emails for user
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT eq.id FROM email_queue eq
            JOIN campaigns c ON eq.campaign_id = c.id
            WHERE eq.status = 'pending' AND c.user_id = ?
            LIMIT 10
        """, (user_id,))
        
        queue_items = cursor.fetchall()
        
        for row in queue_items:
            queue_item_id = row[0]
            send_email_task.delay(queue_item_id, user_id)
            time.sleep(1)  # Stagger task creation
        
        return {'success': True, 'queued': len(queue_items)}
    except Exception as e:
        return {'success': False, 'error': str(e)}

