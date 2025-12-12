"""
Policy Enforcement Module for ANAGHA SOLUTION
Enforces daily limits, warmup speed, domain rotation, and bounce thresholds
"""

from typing import Dict, Optional
from datetime import datetime, timedelta, date
from database.db_manager import DatabaseManager
from core.quota_manager import QuotaManager
from core.billing import BillingManager

class PolicyEnforcer:
    """Enforces platform policies for email sending"""
    
    # Bounce thresholds
    BOUNCE_THRESHOLD_WARNING = 0.02  # 2% bounce rate
    BOUNCE_THRESHOLD_PAUSE = 0.05    # 5% bounce rate
    
    # Daily send limits per plan
    DAILY_SEND_LIMITS = {
        'free': 10,
        'start': 300,
        'growth': 1500,
        'pro': 6000,
        'agency': 30000
    }
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.quota_manager = QuotaManager(db_manager)
        self.billing_manager = BillingManager(db_manager)
    
    def enforce_daily_send_limit(self, user_id: int, email_count: int) -> Dict:
        """
        Enforce daily send limit per plan
        
        Returns:
            Dictionary with allowed status and reason
        """
        try:
            # Get user plan
            plan = self.quota_manager.get_user_plan(user_id)
            daily_limit = self.DAILY_SEND_LIMITS.get(plan, self.DAILY_SEND_LIMITS['start'])
            
            # Get today's sent count
            today = date.today()
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                # Supabase: count sent emails today for campaigns owned by the user
                campaigns = self.db.supabase.client.table('campaigns').select('id').eq('user_id', user_id).execute()
                campaign_ids = [c['id'] for c in (campaigns.data or [])]
                if campaign_ids:
                    result = self.db.supabase.client.table('email_queue').select('id', count='exact') \
                        .in_('campaign_id', campaign_ids) \
                        .eq('status', 'sent') \
                        .gte('sent_at', today.isoformat()) \
                        .execute()
                    sent_today = result.count if result.count else 0
                else:
                    sent_today = 0
            else:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM email_queue eq
                    JOIN campaigns c ON eq.campaign_id = c.id
                    WHERE c.user_id = ? AND eq.status = 'sent' AND DATE(eq.sent_at) = ?
                """, (user_id, today))
                sent_today = cursor.fetchone()[0] or 0
            
            remaining = daily_limit - sent_today
            
            if sent_today + email_count > daily_limit:
                return {
                    'allowed': False,
                    'reason': f'Daily send limit ({daily_limit}) exceeded. Sent today: {sent_today}, Requested: {email_count}',
                    'limit': daily_limit,
                    'sent_today': sent_today,
                    'remaining': max(0, remaining)
                }
            
            return {
                'allowed': True,
                'limit': daily_limit,
                'sent_today': sent_today,
                'remaining': remaining - email_count
            }
            
        except Exception as e:
            print(f"Error enforcing daily send limit: {e}")
            import traceback
            traceback.print_exc()
            return {
                'allowed': True,  # Allow on error to prevent blocking
                'error': str(e)
            }
    
    def enforce_warmup_speed(self, smtp_server_id: int, requested_count: int) -> Dict:
        """
        Enforce warmup speed - prevent manual override
        
        Returns:
            Dictionary with allowed status
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('smtp_servers').select(
                    'warmup_stage, warmup_emails_sent, warmup_start_date'
                ).eq('id', smtp_server_id).execute()
                
                if not result.data or len(result.data) == 0:
                    return {'allowed': True}  # No warmup data, allow
                
                server = result.data[0]
                warmup_stage = server.get('warmup_stage', 0)
            else:
                cursor.execute("""
                    SELECT warmup_stage, warmup_emails_sent, warmup_start_date
                    FROM smtp_servers WHERE id = ?
                """, (smtp_server_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {'allowed': True}
                
                server = dict(row)
                warmup_stage = server.get('warmup_stage', 0)
            
            # If warmup is active (stage > 0), enforce limits
            if warmup_stage > 0:
                from core.warmup_manager import WarmupManager
                warmup_mgr = WarmupManager(self.db)
                
                # Get warmup stage info
                stage_info = warmup_mgr.get_warmup_stage_info(smtp_server_id)
                
                if stage_info and stage_info.get('emails_per_day'):
                    max_allowed = stage_info['emails_per_day']
                    
                    if requested_count > max_allowed:
                        return {
                            'allowed': False,
                            'reason': f'Warmup limit: {max_allowed} emails/day. Requested: {requested_count}',
                            'max_allowed': max_allowed
                        }
            
            return {'allowed': True}
            
        except Exception as e:
            print(f"Error enforcing warmup speed: {e}")
            return {'allowed': True}  # Allow on error
    
    def enforce_domain_rotation(self, user_id: int, domain: str, email_count: int) -> Dict:
        """
        Enforce domain rotation if user has multiple domains
        
        Returns:
            Dictionary with allowed status
        """
        try:
            # Check if using Supabase FIRST before trying to use SQLite methods
            use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
            
            # Get user's domains
            domains = []
            if use_supabase:
                try:
                    result = self.db.supabase.client.table('domains').select('domain').eq('user_id', user_id).execute()
                    domains = [d['domain'] for d in (result.data or [])]
                except Exception as table_error:
                    # Table doesn't exist or error accessing it - skip domain rotation silently
                    # This is expected if the domains table hasn't been created yet
                    error_msg = str(table_error)
                    if 'PGRST205' in error_msg or 'schema cache' in error_msg.lower():
                        # Table doesn't exist - this is fine, domain rotation is optional
                        pass
                    else:
                        # Other error - log it
                        print(f"Domain rotation check failed: {table_error}")
                    return {'allowed': True}
            else:
                try:
                    conn = self.db.connect()
                    cursor = conn.cursor()
                    cursor.execute("SELECT domain FROM domains WHERE user_id = ?", (user_id,))
                    domains = [row[0] for row in cursor.fetchall()]
                except Exception as table_error:
                    # Table doesn't exist - skip domain rotation silently
                    # This is expected if the domains table hasn't been created yet
                    return {'allowed': True}
            
            # If user has multiple domains, enforce rotation
            if len(domains) > 1:
                # Get today's sends per domain
                today = date.today()
                
                domain_sends = {}
                for d in domains:
                    if use_supabase:
                        try:
                            # Count sends for this domain today via campaigns
                            # Note: email_queue might not have sender_email directly, so we check campaigns
                            camp_result = self.db.supabase.client.table('campaigns').select('id, sender_email').eq('user_id', user_id).like('sender_email', f'%@{d}').execute()
                            campaign_ids = [c['id'] for c in (camp_result.data or [])]
                            
                            if campaign_ids:
                                # Count sent emails from these campaigns today
                                queue_result = self.db.supabase.client.table('email_queue').select('id', count='exact').in_('campaign_id', campaign_ids).eq('status', 'sent').gte('sent_at', today.isoformat()).execute()
                                domain_sends[d] = queue_result.count if queue_result.count else 0
                            else:
                                domain_sends[d] = 0
                        except Exception as e:
                            print(f"Error counting domain sends for {d}: {e}")
                            domain_sends[d] = 0
                    else:
                        try:
                            conn = self.db.connect()
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT COUNT(*) FROM email_queue eq
                                JOIN campaigns c ON eq.campaign_id = c.id
                                WHERE c.user_id = ? AND eq.status = 'sent' 
                                AND DATE(eq.sent_at) = ? AND c.sender_email LIKE ?
                            """, (user_id, today, f'%@{d}'))
                            domain_sends[d] = cursor.fetchone()[0] or 0
                        except Exception as e:
                            print(f"Error counting domain sends for {d}: {e}")
                            domain_sends[d] = 0
                
                # Check if current domain is overused
                current_domain_sends = domain_sends.get(domain, 0)
                avg_sends = sum(domain_sends.values()) / len(domains) if domains else 0
                
                # If current domain has sent 50% more than average, suggest rotation
                if current_domain_sends > avg_sends * 1.5 and email_count > 0:
                    return {
                        'allowed': True,  # Allow but warn
                        'warning': f'Domain {domain} is being overused. Consider rotating to other domains.',
                        'suggest_rotation': True
                    }
            
            return {'allowed': True}
            
        except Exception as e:
            print(f"Error enforcing domain rotation: {e}")
            import traceback
            traceback.print_exc()
            # Always allow on error - don't block sends
            return {'allowed': True}
    
    def check_bounce_threshold(self, user_id: int, smtp_server_id: int = None) -> Dict:
        """
        Check bounce rate and enforce thresholds
        
        Returns:
            Dictionary with bounce status and actions
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Get bounce rate for last 24 hours
            yesterday = datetime.now() - timedelta(days=1)
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                # Supabase: filter by campaigns owned by the user
                campaigns = self.db.supabase.client.table('campaigns').select('id').eq('user_id', user_id).execute()
                campaign_ids = [c['id'] for c in (campaigns.data or [])]
                
                if campaign_ids:
                    sent_result = self.db.supabase.client.table('email_queue').select('id', count='exact') \
                        .in_('campaign_id', campaign_ids) \
                        .eq('status', 'sent') \
                        .gte('sent_at', yesterday.isoformat()) \
                        .execute()
                    total_sent = sent_result.count if sent_result.count else 0
                else:
                    total_sent = 0
                
                # Count bounces - check both event_type='bounce' and bounced=1 for compatibility
                bounce_result = self.db.supabase.client.table('email_tracking').select(
                    'id', count='exact'
                ).eq('user_id', user_id).or_('event_type.eq.bounce,bounced.eq.1').gte('created_at', yesterday.isoformat()).execute()
                total_bounces = bounce_result.count if bounce_result.count else 0
            else:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM email_queue eq
                    JOIN campaigns c ON eq.campaign_id = c.id
                    WHERE c.user_id = ? AND eq.status = 'sent' AND eq.sent_at >= ?
                """, (user_id, yesterday))
                total_sent = cursor.fetchone()[0] or 0
                
                # Try to query email_tracking table, fallback to tracking table if it doesn't exist
                try:
                    cursor.execute("""
                        SELECT COUNT(*) FROM email_tracking
                        WHERE user_id = ? AND (event_type = 'bounce' OR bounced = 1) AND created_at >= ?
                    """, (user_id, yesterday))
                    total_bounces = cursor.fetchone()[0] or 0
                except sqlite3.OperationalError:
                    # Fallback to tracking table if email_tracking doesn't exist
                    try:
                        cursor.execute("""
                            SELECT COUNT(*) FROM tracking
                            WHERE event_type = 'bounce' AND created_at >= ?
                        """, (yesterday,))
                        total_bounces = cursor.fetchone()[0] or 0
                    except sqlite3.OperationalError:
                        total_bounces = 0
            
            if total_sent == 0:
                return {
                    'bounce_rate': 0,
                    'status': 'ok',
                    'action': None
                }
            
            bounce_rate = total_bounces / total_sent
            
            action = None
            status = 'ok'
            
            if bounce_rate >= self.BOUNCE_THRESHOLD_PAUSE:
                status = 'critical'
                action = 'pause'
                # Auto-pause sending
                self._pause_sending(user_id, smtp_server_id)
            elif bounce_rate >= self.BOUNCE_THRESHOLD_WARNING:
                status = 'warning'
                action = 'alert'
            
            return {
                'bounce_rate': bounce_rate,
                'bounce_percentage': bounce_rate * 100,
                'total_sent': total_sent,
                'total_bounces': total_bounces,
                'status': status,
                'action': action,
                'threshold_warning': self.BOUNCE_THRESHOLD_WARNING * 100,
                'threshold_pause': self.BOUNCE_THRESHOLD_PAUSE * 100
            }
            
        except Exception as e:
            print(f"Error checking bounce threshold: {e}")
            import traceback
            traceback.print_exc()
            return {
                'bounce_rate': 0,
                'status': 'error',
                'error': str(e)
            }
    
    def _pause_sending(self, user_id: int, smtp_server_id: int = None):
        """Pause sending for user or specific SMTP server"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if smtp_server_id:
                # Pause specific SMTP server
                if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                    self.db.supabase.client.table('smtp_servers').update({
                        'is_active': 0
                    }).eq('id', smtp_server_id).execute()
                else:
                    cursor.execute("""
                        UPDATE smtp_servers
                        SET is_active = 0
                        WHERE id = ?
                    """, (smtp_server_id,))
                    conn.commit()
                
                print(f"⚠️ Paused SMTP server {smtp_server_id} due to high bounce rate")
            else:
                # Pause all SMTP servers for user
                if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                    self.db.supabase.client.table('smtp_servers').update({
                        'is_active': 0
                    }).eq('user_id', user_id).execute()
                else:
                    cursor.execute("""
                        UPDATE smtp_servers
                        SET is_active = 0
                        WHERE user_id = ?
                    """, (user_id,))
                    conn.commit()
                
                print(f"⚠️ Paused all SMTP servers for user {user_id} due to high bounce rate")
            
            # Create alert
            from core.observability import ObservabilityManager
            obs_mgr = ObservabilityManager(self.db)
            obs_mgr.create_alert(
                user_id,
                'bounce_threshold',
                f'Sending paused due to high bounce rate ({self.BOUNCE_THRESHOLD_PAUSE * 100}%)',
                'critical'
            )
            
        except Exception as e:
            print(f"Error pausing sending: {e}")
            import traceback
            traceback.print_exc()
    
    def enforce_all_policies(self, user_id: int, smtp_server_id: int, email_count: int, domain: str = None) -> Dict:
        """
        Enforce all policies before sending
        
        Returns:
            Dictionary with overall allowed status and details
        """
        results = {
            'allowed': True,
            'policies': {}
        }
        
        # Daily send limit
        daily_check = self.enforce_daily_send_limit(user_id, email_count)
        results['policies']['daily_limit'] = daily_check
        if not daily_check.get('allowed'):
            results['allowed'] = False
            results['reason'] = daily_check.get('reason')
        
        # Warmup speed
        warmup_check = self.enforce_warmup_speed(smtp_server_id, email_count)
        results['policies']['warmup'] = warmup_check
        if not warmup_check.get('allowed'):
            results['allowed'] = False
            results['reason'] = warmup_check.get('reason')
        
        # Domain rotation
        if domain:
            rotation_check = self.enforce_domain_rotation(user_id, domain, email_count)
            results['policies']['domain_rotation'] = rotation_check
            if rotation_check.get('warning'):
                results['warning'] = rotation_check.get('warning')
        
        # Bounce threshold
        bounce_check = self.check_bounce_threshold(user_id, smtp_server_id)
        results['policies']['bounce'] = bounce_check
        if bounce_check.get('action') == 'pause':
            results['allowed'] = False
            results['reason'] = f'High bounce rate ({bounce_check.get("bounce_percentage", 0):.2f}%). Sending paused.'
        
        return results
