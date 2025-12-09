"""
Email Warmup Module for ANAGHA SOLUTION
Gradually increases email volume for new accounts
"""

from typing import Dict, List
from database.db_manager import DatabaseManager
from datetime import date, timedelta, datetime

class WarmupManager:
    """Manages email warmup for new SMTP accounts"""
    
    # Warmup stages (days, emails per day)
    WARMUP_STAGES = [
        {'day': 1, 'emails': 5, 'delay_min': 300, 'delay_max': 600},   # Day 1: 5 emails, 5-10 min apart
        {'day': 2, 'emails': 8, 'delay_min': 240, 'delay_max': 480},   # Day 2: 8 emails, 4-8 min apart
        {'day': 3, 'emails': 12, 'delay_min': 180, 'delay_max': 360},  # Day 3: 12 emails, 3-6 min apart
        {'day': 4, 'emails': 18, 'delay_min': 120, 'delay_max': 300},  # Day 4: 18 emails, 2-5 min apart
        {'day': 5, 'emails': 25, 'delay_min': 90, 'delay_max': 240},   # Day 5: 25 emails, 1.5-4 min apart
        {'day': 6, 'emails': 35, 'delay_min': 60, 'delay_max': 180},   # Day 6: 35 emails, 1-3 min apart
        {'day': 7, 'emails': 50, 'delay_min': 45, 'delay_max': 120},   # Day 7: 50 emails, 45s-2 min apart
        {'day': 14, 'emails': 75, 'delay_min': 30, 'delay_max': 90},   # Day 14: 75 emails, 30s-1.5 min apart
        {'day': 21, 'emails': 100, 'delay_min': 20, 'delay_max': 60},  # Day 21: 100 emails, 20s-1 min apart
        {'day': 30, 'emails': -1, 'delay_min': 15, 'delay_max': 45},    # Day 30+: Full capacity
    ]
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_warmup_stage(self, smtp_server_id: int) -> Dict:
        """
        Get current warmup stage for SMTP server
        
        Returns:
            Dictionary with stage info and limits
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, created_at, warmup_stage, warmup_emails_sent, daily_sent_count, last_sent_date
            FROM smtp_servers WHERE id = ?
        """, (smtp_server_id,))
        row = cursor.fetchone()
        
        if not row:
            return {'error': 'SMTP server not found'}
        
        server = dict(row)
        created_at = server.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace(' ', 'T'))
        elif hasattr(created_at, 'date'):
            created_at = created_at
        else:
            created_at = datetime.now()
        
        # Calculate days since creation
        days_since_creation = (date.today() - created_at.date()).days if hasattr(created_at, 'date') else 0
        
        # Find appropriate warmup stage
        current_stage = None
        for stage in self.WARMUP_STAGES:
            if days_since_creation >= stage['day']:
                current_stage = stage
            else:
                break
        
        if not current_stage:
            current_stage = self.WARMUP_STAGES[0]
        
        # Check if warmup is complete
        is_warmup_complete = days_since_creation >= 30
        
        return {
            'smtp_server_id': smtp_server_id,
            'days_since_creation': days_since_creation,
            'current_stage': current_stage,
            'max_emails_today': current_stage['emails'] if not is_warmup_complete else -1,  # -1 = unlimited
            'delay_min_seconds': current_stage['delay_min'],
            'delay_max_seconds': current_stage['delay_max'],
            'is_warmup_complete': is_warmup_complete,
            'warmup_stage': server.get('warmup_stage', 0)
        }
    
    def can_send_email(self, smtp_server_id: int) -> Dict:
        """
        Check if email can be sent based on warmup stage
        
        Returns:
            Dictionary with can_send, delay_seconds, reason
        """
        stage_info = self.get_warmup_stage(smtp_server_id)
        
        if 'error' in stage_info:
            return stage_info
        
        if stage_info['is_warmup_complete']:
            return {
                'can_send': True,
                'delay_seconds': stage_info['delay_min_seconds'],
                'reason': 'Warmup complete'
            }
        
        # Check daily limit
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT daily_sent_count, last_sent_date FROM smtp_servers WHERE id = ?
        """, (smtp_server_id,))
        row = cursor.fetchone()
        
        if not row:
            return {'can_send': False, 'reason': 'SMTP server not found'}
        
        daily_sent = row[0] or 0
        last_sent_date = row[1]
        today = date.today()
        
        # Reset if new day
        if not last_sent_date or (isinstance(last_sent_date, str) and datetime.fromisoformat(last_sent_date).date() < today):
            daily_sent = 0
        
        max_emails = stage_info['max_emails_today']
        
        if max_emails > 0 and daily_sent >= max_emails:
            return {
                'can_send': False,
                'reason': f'Warmup limit reached ({daily_sent}/{max_emails} emails today)',
                'remaining': 0,
                'reset_time': datetime.combine(today + timedelta(days=1), datetime.min.time())
            }
        
        # Calculate random delay
        import random
        delay = random.randint(
            stage_info['delay_min_seconds'],
            stage_info['delay_max_seconds']
        )
        
        return {
            'can_send': True,
            'delay_seconds': delay,
            'remaining': max_emails - daily_sent if max_emails > 0 else -1,
            'daily_limit': max_emails,
            'warmup_stage': stage_info['current_stage']
        }
    
    def update_warmup_progress(self, smtp_server_id: int):
        """Update warmup progress after sending email"""
        stage_info = self.get_warmup_stage(smtp_server_id)
        if 'error' in stage_info:
            return
        
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Update warmup stage if needed
        days = stage_info['days_since_creation']
        new_stage = 0
        for idx, stage in enumerate(self.WARMUP_STAGES):
            if days >= stage['day']:
                new_stage = idx
            else:
                break
        
        cursor.execute("""
            UPDATE smtp_servers 
            SET warmup_stage = ?,
                warmup_emails_sent = warmup_emails_sent + 1
            WHERE id = ?
        """, (new_stage, smtp_server_id))
        conn.commit()

