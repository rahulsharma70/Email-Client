"""
Domain Reputation Engine for ANAGHA SOLUTION
Tracks and enforces domain reputation scores
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from database.db_manager import DatabaseManager

class DomainReputationEngine:
    """Manages domain reputation tracking and enforcement"""
    
    # Reputation thresholds
    REPUTATION_EXCELLENT = 90
    REPUTATION_GOOD = 70
    REPUTATION_FAIR = 50
    REPUTATION_POOR = 30
    REPUTATION_BLOCKED = 0
    
    # Reputation factors and weights
    FACTOR_WEIGHTS = {
        'open_rate': 0.25,
        'reply_rate': 0.30,
        'bounce_rate': 0.20,
        'spam_rate': 0.15,
        'engagement_rate': 0.10
    }
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def calculate_reputation(self, domain: str, user_id: int, days: int = 30) -> Dict:
        """
        Calculate domain reputation score
        
        Args:
            domain: Domain name
            user_id: User ID
            days: Number of days to look back
            
        Returns:
            Dictionary with reputation score and details
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Get email metrics for this domain
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                # Count total sent
                sent_result = self.db.supabase.client.table('email_queue').select(
                    'id', count='exact'
                ).eq('user_id', user_id).eq('status', 'sent').like('sender_email', f'%@{domain}').gte('sent_at', start_date.isoformat()).execute()
                total_sent = sent_result.count if sent_result.count else 0
                
                # Count opens
                open_result = self.db.supabase.client.table('email_tracking').select(
                    'id', count='exact'
                ).eq('user_id', user_id).eq('event_type', 'open').like('sender_email', f'%@{domain}').gte('created_at', start_date.isoformat()).execute()
                total_opens = open_result.count if open_result.count else 0
                
                # Count replies
                reply_result = self.db.supabase.client.table('email_tracking').select(
                    'id', count='exact'
                ).eq('user_id', user_id).eq('event_type', 'reply').like('sender_email', f'%@{domain}').gte('created_at', start_date.isoformat()).execute()
                total_replies = reply_result.count if reply_result.count else 0
                
                # Count bounces
                bounce_result = self.db.supabase.client.table('email_tracking').select(
                    'id', count='exact'
                ).eq('user_id', user_id).eq('event_type', 'bounce').like('sender_email', f'%@{domain}').gte('created_at', start_date.isoformat()).execute()
                total_bounces = bounce_result.count if bounce_result.count else 0
                
                # Count spam reports
                spam_result = self.db.supabase.client.table('email_tracking').select(
                    'id', count='exact'
                ).eq('user_id', user_id).eq('event_type', 'spam').like('sender_email', f'%@{domain}').gte('created_at', start_date.isoformat()).execute()
                total_spam = spam_result.count if spam_result.count else 0
            else:
                # SQLite queries
                cursor.execute("""
                    SELECT COUNT(*) FROM email_queue
                    WHERE user_id = ? AND status = 'sent' 
                    AND sender_email LIKE ? AND sent_at >= ?
                """, (user_id, f'%@{domain}', start_date))
                total_sent = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COUNT(*) FROM email_tracking
                    WHERE user_id = ? AND event_type = 'open'
                    AND sender_email LIKE ? AND created_at >= ?
                """, (user_id, f'%@{domain}', start_date))
                total_opens = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COUNT(*) FROM email_tracking
                    WHERE user_id = ? AND event_type = 'reply'
                    AND sender_email LIKE ? AND created_at >= ?
                """, (user_id, f'%@{domain}', start_date))
                total_replies = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COUNT(*) FROM email_tracking
                    WHERE user_id = ? AND event_type = 'bounce'
                    AND sender_email LIKE ? AND created_at >= ?
                """, (user_id, f'%@{domain}', start_date))
                total_bounces = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COUNT(*) FROM email_tracking
                    WHERE user_id = ? AND event_type = 'spam'
                    AND sender_email LIKE ? AND created_at >= ?
                """, (user_id, f'%@{domain}', start_date))
                total_spam = cursor.fetchone()[0] or 0
            
            if total_sent == 0:
                return {
                    'reputation_score': 50,  # Neutral score for new domains
                    'status': 'new',
                    'message': 'Domain has no sending history',
                    'factors': {}
                }
            
            # Calculate rates
            open_rate = (total_opens / total_sent) * 100 if total_sent > 0 else 0
            reply_rate = (total_replies / total_sent) * 100 if total_sent > 0 else 0
            bounce_rate = (total_bounces / total_sent) * 100 if total_sent > 0 else 0
            spam_rate = (total_spam / total_sent) * 100 if total_sent > 0 else 0
            engagement_rate = ((total_opens + total_replies) / total_sent) * 100 if total_sent > 0 else 0
            
            # Calculate factor scores (0-100)
            open_score = min(100, open_rate * 2)  # 50% open rate = 100 score
            reply_score = min(100, reply_rate * 10)  # 10% reply rate = 100 score
            bounce_score = max(0, 100 - (bounce_rate * 20))  # 5% bounce = 0 score
            spam_score = max(0, 100 - (spam_rate * 50))  # 2% spam = 0 score
            engagement_score = min(100, engagement_rate * 1.5)  # 66% engagement = 100 score
            
            # Calculate weighted reputation score
            reputation_score = (
                open_score * self.FACTOR_WEIGHTS['open_rate'] +
                reply_score * self.FACTOR_WEIGHTS['reply_rate'] +
                bounce_score * self.FACTOR_WEIGHTS['bounce_rate'] +
                spam_score * self.FACTOR_WEIGHTS['spam_rate'] +
                engagement_score * self.FACTOR_WEIGHTS['engagement_rate']
            )
            
            # Determine status
            if reputation_score >= self.REPUTATION_EXCELLENT:
                status = 'excellent'
            elif reputation_score >= self.REPUTATION_GOOD:
                status = 'good'
            elif reputation_score >= self.REPUTATION_FAIR:
                status = 'fair'
            elif reputation_score >= self.REPUTATION_POOR:
                status = 'poor'
            else:
                status = 'blocked'
            
            return {
                'reputation_score': round(reputation_score, 2),
                'status': status,
                'message': f'Domain reputation: {status}',
                'factors': {
                    'open_rate': round(open_rate, 2),
                    'reply_rate': round(reply_rate, 2),
                    'bounce_rate': round(bounce_rate, 2),
                    'spam_rate': round(spam_rate, 2),
                    'engagement_rate': round(engagement_rate, 2)
                },
                'metrics': {
                    'total_sent': total_sent,
                    'total_opens': total_opens,
                    'total_replies': total_replies,
                    'total_bounces': total_bounces,
                    'total_spam': total_spam
                }
            }
            
        except Exception as e:
            print(f"Error calculating domain reputation: {e}")
            import traceback
            traceback.print_exc()
            return {
                'reputation_score': 50,
                'status': 'error',
                'error': str(e)
            }
    
    def enforce_reputation_threshold(self, domain: str, user_id: int) -> Dict:
        """
        Enforce reputation threshold - block sending if reputation too low
        
        Returns:
            Dictionary with allowed status
        """
        try:
            reputation = self.calculate_reputation(domain, user_id)
            score = reputation.get('reputation_score', 50)
            status = reputation.get('status', 'fair')
            
            # Block if reputation is poor or blocked
            if status in ['poor', 'blocked'] or score < self.REPUTATION_POOR:
                return {
                    'allowed': False,
                    'reason': f'Domain reputation too low ({score:.1f}/100). Status: {status}',
                    'reputation': reputation,
                    'action': 'block_sending'
                }
            
            # Throttle if reputation is fair
            if status == 'fair' or score < self.REPUTATION_GOOD:
                return {
                    'allowed': True,
                    'throttle': True,
                    'reason': f'Domain reputation is fair ({score:.1f}/100). Sending will be throttled.',
                    'reputation': reputation,
                    'throttle_factor': 0.5  # Send at 50% speed
                }
            
            return {
                'allowed': True,
                'reputation': reputation
            }
            
        except Exception as e:
            print(f"Error enforcing reputation threshold: {e}")
            return {'allowed': True}  # Allow on error
    
    def update_reputation(self, domain: str, user_id: int) -> Dict:
        """
        Update and store domain reputation
        
        Returns:
            Dictionary with updated reputation
        """
        try:
            reputation = self.calculate_reputation(domain, user_id)
            
            # Store in database
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                # Update domains table
                self.db.supabase.client.table('domains').update({
                    'reputation_score': reputation['reputation_score'],
                    'reputation_status': reputation['status'],
                    'reputation_updated_at': datetime.now().isoformat()
                }).eq('user_id', user_id).eq('domain', domain).execute()
            else:
                # Add reputation columns if they don't exist
                try:
                    cursor.execute("ALTER TABLE domains ADD COLUMN reputation_score REAL")
                    cursor.execute("ALTER TABLE domains ADD COLUMN reputation_status TEXT")
                    cursor.execute("ALTER TABLE domains ADD COLUMN reputation_updated_at TIMESTAMP")
                except:
                    pass  # Columns may already exist
                
                cursor.execute("""
                    UPDATE domains
                    SET reputation_score = ?,
                        reputation_status = ?,
                        reputation_updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND domain = ?
                """, (reputation['reputation_score'], reputation['status'], user_id, domain))
                conn.commit()
            
            return reputation
            
        except Exception as e:
            print(f"Error updating reputation: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
