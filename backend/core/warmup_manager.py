"""
Enhanced Warmup Manager for ANAGHA SOLUTION
Centralized warmup automation with DB tracking and metrics
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
from database.db_manager import DatabaseManager
import random
import time

class WarmupManager:
    """Manages email account warmup with persistent state and metrics tracking"""
    
    # Warmup stages (30-day program)
    WARMUP_STAGES = [
        {'day': 1, 'emails_per_day': 5, 'spacing_minutes': 30},
        {'day': 2, 'emails_per_day': 8, 'spacing_minutes': 25},
        {'day': 3, 'emails_per_day': 12, 'spacing_minutes': 20},
        {'day': 4, 'emails_per_day': 15, 'spacing_minutes': 18},
        {'day': 5, 'emails_per_day': 20, 'spacing_minutes': 15},
        {'day': 6, 'emails_per_day': 25, 'spacing_minutes': 12},
        {'day': 7, 'emails_per_day': 30, 'spacing_minutes': 10},
        {'day': 8, 'emails_per_day': 35, 'spacing_minutes': 9},
        {'day': 9, 'emails_per_day': 40, 'spacing_minutes': 8},
        {'day': 10, 'emails_per_day': 45, 'spacing_minutes': 7},
        {'day': 11, 'emails_per_day': 50, 'spacing_minutes': 6},
        {'day': 12, 'emails_per_day': 55, 'spacing_minutes': 5},
        {'day': 13, 'emails_per_day': 60, 'spacing_minutes': 5},
        {'day': 14, 'emails_per_day': 65, 'spacing_minutes': 4},
        {'day': 15, 'emails_per_day': 70, 'spacing_minutes': 4},
        {'day': 16, 'emails_per_day': 75, 'spacing_minutes': 4},
        {'day': 17, 'emails_per_day': 80, 'spacing_minutes': 3},
        {'day': 18, 'emails_per_day': 85, 'spacing_minutes': 3},
        {'day': 19, 'emails_per_day': 90, 'spacing_minutes': 3},
        {'day': 20, 'emails_per_day': 95, 'spacing_minutes': 3},
        {'day': 21, 'emails_per_day': 100, 'spacing_minutes': 2},
        {'day': 22, 'emails_per_day': 105, 'spacing_minutes': 2},
        {'day': 23, 'emails_per_day': 110, 'spacing_minutes': 2},
        {'day': 24, 'emails_per_day': 115, 'spacing_minutes': 2},
        {'day': 25, 'emails_per_day': 120, 'spacing_minutes': 2},
        {'day': 26, 'emails_per_day': 125, 'spacing_minutes': 2},
        {'day': 27, 'emails_per_day': 130, 'spacing_minutes': 2},
        {'day': 28, 'emails_per_day': 135, 'spacing_minutes': 2},
        {'day': 29, 'emails_per_day': 140, 'spacing_minutes': 2},
        {'day': 30, 'emails_per_day': 150, 'spacing_minutes': 1},
    ]
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize warmup manager"""
        self.db = db_manager
    
    def get_warmup_stage(self, smtp_server_id: int) -> Dict:
        """Get current warmup stage for an SMTP server"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT warmup_stage, warmup_emails_sent, warmup_start_date, 
                   warmup_last_sent_date, warmup_open_rate, warmup_reply_rate
            FROM smtp_servers
            WHERE id = ?
        """, (smtp_server_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'stage': row[0] or 0,
            'emails_sent': row[1] or 0,
            'start_date': row[2],
            'last_sent_date': row[3],
            'open_rate': row[4] or 0.0,
            'reply_rate': row[5] or 0.0
        }
    
    def start_warmup(self, smtp_server_id: int):
        """Start warmup process for an SMTP server"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        now = datetime.now()
        cursor.execute("""
            UPDATE smtp_servers
            SET warmup_stage = 1,
                warmup_emails_sent = 0,
                warmup_start_date = ?,
                warmup_last_sent_date = NULL,
                warmup_open_rate = 0.0,
                warmup_reply_rate = 0.0
            WHERE id = ?
        """, (now, smtp_server_id))
        conn.commit()
    
    def get_stage_config(self, stage: int) -> Dict:
        """Get configuration for a specific warmup stage"""
        if stage < 1 or stage > len(self.WARMUP_STAGES):
            # Return final stage config if beyond warmup
            return self.WARMUP_STAGES[-1]
        return self.WARMUP_STAGES[stage - 1]
    
    def calculate_next_send_time(self, smtp_server_id: int) -> Optional[datetime]:
        """Calculate when next warmup email should be sent"""
        warmup_info = self.get_warmup_stage(smtp_server_id)
        if not warmup_info or warmup_info['stage'] == 0:
            return None
        
        stage_config = self.get_stage_config(warmup_info['stage'])
        emails_per_day = stage_config['emails_per_day']
        spacing_minutes = stage_config['spacing_minutes']
        
        # Check if we've sent enough emails today
        today = datetime.now().date()
        last_sent = warmup_info['last_sent_date']
        
        if last_sent:
            last_sent_date = datetime.fromisoformat(last_sent).date() if isinstance(last_sent, str) else last_sent.date()
            if last_sent_date == today:
                # Check how many sent today
                conn = self.db.connect()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM email_queue
                    WHERE smtp_server_id = ? 
                    AND DATE(sent_at) = DATE('now')
                    AND status = 'sent'
                """, (smtp_server_id,))
                sent_today = cursor.fetchone()[0]
                
                if sent_today >= emails_per_day:
                    # Move to next day
                    tomorrow = datetime.now().replace(hour=9, minute=0, second=0) + timedelta(days=1)
                    return tomorrow
                else:
                    # Send next email after spacing interval
                    last_sent_time = datetime.fromisoformat(warmup_info['last_sent_date']) if isinstance(warmup_info['last_sent_date'], str) else warmup_info['last_sent_date']
                    next_time = last_sent_time + timedelta(minutes=spacing_minutes)
                    # Add random jitter (10% of spacing)
                    jitter = random.uniform(0, spacing_minutes * 0.1)
                    return next_time + timedelta(minutes=jitter)
            else:
                # New day, start fresh
                return datetime.now().replace(hour=9, minute=0, second=0)
        else:
            # First email, start at 9 AM
            return datetime.now().replace(hour=9, minute=0, second=0)
    
    def should_send_warmup_email(self, smtp_server_id: int) -> bool:
        """Check if it's time to send a warmup email"""
        next_time = self.calculate_next_send_time(smtp_server_id)
        if not next_time:
            return False
        return datetime.now() >= next_time
    
    def record_warmup_email_sent(self, smtp_server_id: int):
        """Record that a warmup email was sent"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        now = datetime.now()
        warmup_info = self.get_warmup_stage(smtp_server_id)
        
        if warmup_info:
            new_count = (warmup_info['emails_sent'] or 0) + 1
            stage_config = self.get_stage_config(warmup_info['stage'])
            
            # Check if we should advance to next stage
            days_since_start = (now.date() - datetime.fromisoformat(warmup_info['start_date']).date()).days if warmup_info['start_date'] else 0
            new_stage = min(warmup_info['stage'] + 1, len(self.WARMUP_STAGES)) if days_since_start >= warmup_info['stage'] else warmup_info['stage']
            
            cursor.execute("""
                UPDATE smtp_servers
                SET warmup_emails_sent = ?,
                    warmup_stage = ?,
                    warmup_last_sent_date = ?
                WHERE id = ?
            """, (new_count, new_stage, now, smtp_server_id))
            conn.commit()
    
    def update_warmup_metrics(self, smtp_server_id: int, open_rate: float, reply_rate: float):
        """Update warmup metrics (open rate, reply rate)"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Get current metrics
        warmup_info = self.get_warmup_stage(smtp_server_id)
        if not warmup_info:
            return
        
        # Calculate weighted average (recent metrics weighted more)
        current_open = warmup_info['open_rate'] or 0.0
        current_reply = warmup_info['reply_rate'] or 0.0
        
        # Exponential moving average (alpha = 0.3)
        alpha = 0.3
        new_open_rate = alpha * open_rate + (1 - alpha) * current_open
        new_reply_rate = alpha * reply_rate + (1 - alpha) * current_reply
        
        cursor.execute("""
            UPDATE smtp_servers
            SET warmup_open_rate = ?,
                warmup_reply_rate = ?
            WHERE id = ?
        """, (new_open_rate, new_reply_rate, smtp_server_id))
        conn.commit()
    
    def auto_adjust_cadence(self, smtp_server_id: int) -> Dict:
        """Auto-adjust warmup cadence based on metrics"""
        warmup_info = self.get_warmup_stage(smtp_server_id)
        if not warmup_info:
            return {'adjusted': False}
        
        open_rate = warmup_info['open_rate'] or 0.0
        reply_rate = warmup_info['reply_rate'] or 0.0
        
        stage_config = self.get_stage_config(warmup_info['stage'])
        current_emails = stage_config['emails_per_day']
        current_spacing = stage_config['spacing_minutes']
        
        adjustments = {
            'emails_per_day': current_emails,
            'spacing_minutes': current_spacing,
            'adjusted': False
        }
        
        # If open rate is low (< 20%), slow down
        if open_rate < 0.20:
            adjustments['emails_per_day'] = max(5, int(current_emails * 0.8))
            adjustments['spacing_minutes'] = min(30, int(current_spacing * 1.2))
            adjustments['adjusted'] = True
            adjustments['reason'] = 'Low open rate detected'
        
        # If bounce rate is high (> 5%), slow down significantly
        # (We'd need to track bounces separately)
        
        # If reply rate is good (> 10%), can speed up slightly
        if reply_rate > 0.10 and open_rate > 0.30:
            adjustments['emails_per_day'] = min(150, int(current_emails * 1.1))
            adjustments['spacing_minutes'] = max(1, int(current_spacing * 0.9))
            adjustments['adjusted'] = True
            adjustments['reason'] = 'Good engagement metrics'
        
        return adjustments
    
    def get_warmup_status(self, smtp_server_id: int) -> Dict:
        """Get comprehensive warmup status"""
        warmup_info = self.get_warmup_stage(smtp_server_id)
        if not warmup_info or warmup_info['stage'] == 0:
            return {
                'status': 'not_started',
                'stage': 0,
                'progress': 0.0
            }
        
        stage = warmup_info['stage']
        total_stages = len(self.WARMUP_STAGES)
        progress = (stage / total_stages) * 100
        
        stage_config = self.get_stage_config(stage)
        next_send = self.calculate_next_send_time(smtp_server_id)
        
        return {
            'status': 'warming_up' if stage < total_stages else 'completed',
            'stage': stage,
            'total_stages': total_stages,
            'progress': progress,
            'emails_sent': warmup_info['emails_sent'],
            'emails_per_day': stage_config['emails_per_day'],
            'spacing_minutes': stage_config['spacing_minutes'],
            'open_rate': warmup_info['open_rate'],
            'reply_rate': warmup_info['reply_rate'],
            'next_send_time': next_send.isoformat() if next_send else None,
            'start_date': warmup_info['start_date']
        }


