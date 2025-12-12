"""
Observability Module for ANAGHA SOLUTION
Metrics, monitoring, and alerting
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from database.db_manager import DatabaseManager
import json

class ObservabilityManager:
    """Manages metrics, monitoring, and alerts"""
    
    # Alert thresholds
    THRESHOLDS = {
        'queue_depth_warning': 1000,
        'queue_depth_critical': 5000,
        'worker_error_rate_warning': 0.05,  # 5%
        'worker_error_rate_critical': 0.15,  # 15%
        'bounce_rate_warning': 0.05,  # 5%
        'bounce_rate_critical': 0.10,  # 10%
        'llm_cost_warning': 100.0,  # $100/day
        'llm_cost_critical': 500.0,  # $500/day
    }
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize observability manager"""
        self.db = db_manager
    
    def record_metric(self, user_id: int, metric_type: str, metric_name: str, 
                     value: float, data: Dict = None):
        """Record a metric"""
        # Check if using Supabase
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        
        metric_data = json.dumps(data) if data else None
        
        if use_supabase:
            # Use Supabase table methods
            try:
                self.db.supabase.client.table('metrics').insert({
                    'user_id': user_id,
                    'metric_type': metric_type,
                    'metric_name': metric_name,
                    'metric_value': value,
                    'metric_data': metric_data
                }).execute()
            except Exception as e:
                print(f"Error recording metric to Supabase: {e}")
                # Silently fail - metrics are not critical
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics (user_id, metric_type, metric_name, metric_value, metric_data)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, metric_type, metric_name, value, metric_data))
            conn.commit()
    
    def get_queue_depth(self, user_id: int = None) -> Dict:
        """Get current email queue depth"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT COUNT(*) FROM email_queue eq
                JOIN campaigns c ON eq.campaign_id = c.id
                WHERE c.user_id = ? AND eq.status = 'pending'
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM email_queue
                WHERE status = 'pending'
            """)
        
        count = cursor.fetchone()[0]
        
        # Record metric
        if user_id:
            self.record_metric(user_id, 'queue', 'queue_depth', float(count))
        
        return {
            'queue_depth': count,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_worker_error_rate(self, user_id: int = None, hours: int = 24) -> Dict:
        """Get worker error rate over last N hours"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        if user_id:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM email_queue eq
                JOIN campaigns c ON eq.campaign_id = c.id
                WHERE c.user_id = ? 
                AND eq.created_at >= ?
            """, (user_id, since))
        else:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM email_queue
                WHERE created_at >= ?
            """, (since,))
        
        row = cursor.fetchone()
        total = row[0] or 0
        failed = row[1] or 0
        
        error_rate = failed / total if total > 0 else 0.0
        
        # Record metric
        if user_id:
            self.record_metric(user_id, 'worker', 'error_rate', error_rate)
        
        return {
            'error_rate': error_rate,
            'total': total,
            'failed': failed,
            'hours': hours,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_send_rate(self, user_id: int = None, hours: int = 1) -> Dict:
        """Get email send rate (emails per hour)"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        if user_id:
            cursor.execute("""
                SELECT COUNT(*) FROM email_queue eq
                JOIN campaigns c ON eq.campaign_id = c.id
                WHERE c.user_id = ? 
                AND eq.status = 'sent'
                AND eq.sent_at >= ?
            """, (user_id, since))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM email_queue
                WHERE status = 'sent'
                AND sent_at >= ?
            """, (since,))
        
        count = cursor.fetchone()[0]
        send_rate = count / hours if hours > 0 else 0.0
        
        # Record metric
        if user_id:
            self.record_metric(user_id, 'send', 'send_rate', send_rate)
        
        return {
            'send_rate': send_rate,
            'emails_sent': count,
            'hours': hours,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_bounce_rate(self, user_id: int = None, hours: int = 24) -> Dict:
        """Get bounce rate over last N hours"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(hours=hours)
        
        if user_id:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN cr.bounced = 1 THEN 1 ELSE 0 END) as bounced
                FROM campaign_recipients cr
                JOIN campaigns c ON cr.campaign_id = c.id
                WHERE c.user_id = ?
                AND cr.sent_at >= ?
            """, (user_id, since))
        else:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN bounced = 1 THEN 1 ELSE 0 END) as bounced
                FROM campaign_recipients
                WHERE sent_at >= ?
            """, (since,))
        
        row = cursor.fetchone()
        total = row[0] or 0
        bounced = row[1] or 0
        
        bounce_rate = bounced / total if total > 0 else 0.0
        
        # Record metric
        if user_id:
            self.record_metric(user_id, 'deliverability', 'bounce_rate', bounce_rate)
        
        return {
            'bounce_rate': bounce_rate,
            'total': total,
            'bounced': bounced,
            'hours': hours,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_llm_cost(self, user_id: int = None, days: int = 1) -> Dict:
        """Get LLM cost over last N days"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        since = datetime.now() - timedelta(days=days)
        
        # Get LLM usage from metrics
        if user_id:
            cursor.execute("""
                SELECT SUM(metric_value) FROM metrics
                WHERE user_id = ?
                AND metric_type = 'llm'
                AND metric_name = 'tokens_used'
                AND created_at >= ?
            """, (user_id, since))
        else:
            cursor.execute("""
                SELECT SUM(metric_value) FROM metrics
                WHERE metric_type = 'llm'
                AND metric_name = 'tokens_used'
                AND created_at >= ?
            """, (since,))
        
        tokens = cursor.fetchone()[0] or 0
        
        # Estimate cost (rough: $0.002 per 1K tokens for GPT-4o-mini)
        cost_per_1k_tokens = 0.002
        estimated_cost = (tokens / 1000) * cost_per_1k_tokens
        
        # Record metric
        if user_id:
            self.record_metric(user_id, 'llm', 'daily_cost', estimated_cost)
        
        return {
            'tokens_used': tokens,
            'estimated_cost': estimated_cost,
            'days': days,
            'timestamp': datetime.now().isoformat()
        }
    
    def check_alerts(self, user_id: int = None) -> List[Dict]:
        """Check all metrics and generate alerts"""
        alerts = []
        
        # Check queue depth
        queue_depth = self.get_queue_depth(user_id)
        if queue_depth['queue_depth'] >= self.THRESHOLDS['queue_depth_critical']:
            alerts.append({
                'type': 'queue_depth',
                'level': 'critical',
                'message': f"Queue depth critical: {queue_depth['queue_depth']} emails pending",
                'value': queue_depth['queue_depth'],
                'threshold': self.THRESHOLDS['queue_depth_critical']
            })
        elif queue_depth['queue_depth'] >= self.THRESHOLDS['queue_depth_warning']:
            alerts.append({
                'type': 'queue_depth',
                'level': 'warning',
                'message': f"Queue depth high: {queue_depth['queue_depth']} emails pending",
                'value': queue_depth['queue_depth'],
                'threshold': self.THRESHOLDS['queue_depth_warning']
            })
        
        # Check worker error rate
        error_rate = self.get_worker_error_rate(user_id)
        if error_rate['error_rate'] >= self.THRESHOLDS['worker_error_rate_critical']:
            alerts.append({
                'type': 'worker_error_rate',
                'level': 'critical',
                'message': f"Worker error rate critical: {error_rate['error_rate']:.1%}",
                'value': error_rate['error_rate'],
                'threshold': self.THRESHOLDS['worker_error_rate_critical']
            })
        elif error_rate['error_rate'] >= self.THRESHOLDS['worker_error_rate_warning']:
            alerts.append({
                'type': 'worker_error_rate',
                'level': 'warning',
                'message': f"Worker error rate high: {error_rate['error_rate']:.1%}",
                'value': error_rate['error_rate'],
                'threshold': self.THRESHOLDS['worker_error_rate_warning']
            })
        
        # Check bounce rate
        bounce_rate = self.get_bounce_rate(user_id)
        if bounce_rate['bounce_rate'] >= self.THRESHOLDS['bounce_rate_critical']:
            alerts.append({
                'type': 'bounce_rate',
                'level': 'critical',
                'message': f"Bounce rate critical: {bounce_rate['bounce_rate']:.1%}",
                'value': bounce_rate['bounce_rate'],
                'threshold': self.THRESHOLDS['bounce_rate_critical']
            })
        elif bounce_rate['bounce_rate'] >= self.THRESHOLDS['bounce_rate_warning']:
            alerts.append({
                'type': 'bounce_rate',
                'level': 'warning',
                'message': f"Bounce rate high: {bounce_rate['bounce_rate']:.1%}",
                'value': bounce_rate['bounce_rate'],
                'threshold': self.THRESHOLDS['bounce_rate_warning']
            })
        
        # Check LLM cost
        llm_cost = self.get_llm_cost(user_id, days=1)
        if llm_cost['estimated_cost'] >= self.THRESHOLDS['llm_cost_critical']:
            alerts.append({
                'type': 'llm_cost',
                'level': 'critical',
                'message': f"LLM cost critical: ${llm_cost['estimated_cost']:.2f}/day",
                'value': llm_cost['estimated_cost'],
                'threshold': self.THRESHOLDS['llm_cost_critical']
            })
        elif llm_cost['estimated_cost'] >= self.THRESHOLDS['llm_cost_warning']:
            alerts.append({
                'type': 'llm_cost',
                'level': 'warning',
                'message': f"LLM cost high: ${llm_cost['estimated_cost']:.2f}/day",
                'value': llm_cost['estimated_cost'],
                'threshold': self.THRESHOLDS['llm_cost_warning']
            })
        
        # Save alerts to database
        for alert in alerts:
            self.create_alert(user_id, alert['type'], alert['message'], alert['level'])
        
        return alerts
    
    def create_alert(self, user_id: int, alert_type: str, message: str, level: str = 'warning'):
        """Create an alert in the database"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alerts (user_id, alert_type, alert_message, alert_level)
            VALUES (?, ?, ?, ?)
        """, (user_id, alert_type, message, level))
        conn.commit()
    
    def get_active_alerts(self, user_id: int = None) -> List[Dict]:
        """Get active (unresolved) alerts"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT id, alert_type, alert_message, alert_level, created_at
                FROM alerts
                WHERE user_id = ? AND is_resolved = 0
                ORDER BY created_at DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, alert_type, alert_message, alert_level, created_at
                FROM alerts
                WHERE is_resolved = 0
                ORDER BY created_at DESC
            """)
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'id': row[0],
                'type': row[1],
                'message': row[2],
                'level': row[3],
                'created_at': row[4]
            })
        
        return alerts
    
    def resolve_alert(self, alert_id: int):
        """Mark an alert as resolved"""
        conn = self.db.connect()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE alerts
            SET is_resolved = 1, resolved_at = ?
            WHERE id = ?
        """, (datetime.now(), alert_id))
        conn.commit()
    
    def get_dashboard_metrics(self, user_id: int = None) -> Dict:
        """Get all metrics for dashboard"""
        return {
            'queue_depth': self.get_queue_depth(user_id),
            'worker_error_rate': self.get_worker_error_rate(user_id),
            'send_rate': self.get_send_rate(user_id),
            'bounce_rate': self.get_bounce_rate(user_id),
            'llm_cost': self.get_llm_cost(user_id),
            'active_alerts': self.get_active_alerts(user_id),
            'timestamp': datetime.now().isoformat()
        }


