"""
Onboarding Manager for ANAGHA SOLUTION
Handles multi-step onboarding flow for new users
"""

import json
from typing import Dict, Optional, List
from datetime import datetime
from database.db_manager import DatabaseManager

class OnboardingManager:
    """Manages user onboarding process"""
    
    ONBOARDING_STEPS = [
        {
            'id': 'welcome',
            'title': 'Welcome to ANAGHA SOLUTION',
            'description': 'Let\'s get you set up in a few simple steps',
            'required': True
        },
        {
            'id': 'domain',
            'title': 'Add Sending Domain',
            'description': 'Add your domain or connect Gmail/OAuth',
            'required': True
        },
        {
            'id': 'dns',
            'title': 'Verify DNS Records',
            'description': 'Verify SPF, DKIM, and DMARC records',
            'required': True
        },
        {
            'id': 'inbox',
            'title': 'Add Inbox',
            'description': 'Add your inbox - warmup will begin automatically',
            'required': True
        },
        {
            'id': 'tracking',
            'title': 'Custom Tracking Domain',
            'description': 'Add custom tracking domain (optional)',
            'required': False
        },
        {
            'id': 'leads',
            'title': 'Import Leads',
            'description': 'Import your leads or scrape new ones (optional)',
            'required': False
        },
        {
            'id': 'complete',
            'title': 'You\'re All Set!',
            'description': 'Start sending your first campaign',
            'required': True
        }
    ]
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def get_onboarding_status(self, user_id: int) -> Dict:
        """
        Get onboarding status for user
        
        Returns:
            Dictionary with onboarding status and progress
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('users').select(
                    'onboarding_completed, onboarding_step, onboarding_data'
                ).eq('id', user_id).execute()
                
                if not result.data or len(result.data) == 0:
                    return {
                        'completed': False,
                        'current_step': 0,
                        'steps': self.ONBOARDING_STEPS,
                        'progress': 0
                    }
                
                user = result.data[0]
                onboarding_completed = user.get('onboarding_completed', 0)
                current_step = user.get('onboarding_step', 0)
                onboarding_data = user.get('onboarding_data', {})
                
                if isinstance(onboarding_data, str):
                    import json
                    try:
                        onboarding_data = json.loads(onboarding_data)
                    except:
                        onboarding_data = {}
            else:
                cursor.execute("""
                    SELECT onboarding_completed, onboarding_step, onboarding_data
                    FROM users WHERE id = ?
                """, (user_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {
                        'completed': False,
                        'current_step': 0,
                        'steps': self.ONBOARDING_STEPS,
                        'progress': 0
                    }
                
                onboarding_completed, current_step, onboarding_data_str = row
                onboarding_data = {}
                if onboarding_data_str:
                    import json
                    try:
                        onboarding_data = json.loads(onboarding_data_str)
                    except:
                        onboarding_data = {}
            
            # Calculate progress
            total_steps = len(self.ONBOARDING_STEPS)
            progress = int((current_step / total_steps) * 100) if current_step > 0 else 0
            
            return {
                'completed': bool(onboarding_completed),
                'current_step': current_step,
                'steps': self.ONBOARDING_STEPS,
                'progress': progress,
                'data': onboarding_data
            }
            
        except Exception as e:
            print(f"Error getting onboarding status: {e}")
            import traceback
            traceback.print_exc()
            return {
                'completed': False,
                'current_step': 0,
                'steps': self.ONBOARDING_STEPS,
                'progress': 0
            }
    
    def update_onboarding_step(self, user_id: int, step: int, data: Dict = None) -> Dict:
        """
        Update onboarding step for user
        
        Args:
            user_id: User ID
            step: Step number (0-indexed)
            data: Optional data to store for this step
            
        Returns:
            Dictionary with success status
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            # Get existing onboarding data
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('users').select('onboarding_data').eq('id', user_id).execute()
                existing_data = {}
                if result.data and len(result.data) > 0:
                    existing_data_str = result.data[0].get('onboarding_data', '{}')
                    if existing_data_str:
                        import json
                        try:
                            existing_data = json.loads(existing_data_str) if isinstance(existing_data_str, str) else existing_data_str
                        except:
                            existing_data = {}
                
                # Merge new data
                if data:
                    existing_data.update(data)
                
                # Update step
                update_data = {
                    'onboarding_step': step,
                    'onboarding_data': json.dumps(existing_data) if existing_data else None
                }
                
                # Mark as completed if last step
                if step >= len(self.ONBOARDING_STEPS) - 1:
                    update_data['onboarding_completed'] = 1
                
                self.db.supabase.client.table('users').update(update_data).eq('id', user_id).execute()
            else:
                cursor.execute("SELECT onboarding_data FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                existing_data = {}
                if row and row[0]:
                    import json
                    try:
                        existing_data = json.loads(row[0])
                    except:
                        existing_data = {}
                
                # Merge new data
                if data:
                    existing_data.update(data)
                
                # Update step
                onboarding_completed = 1 if step >= len(self.ONBOARDING_STEPS) - 1 else 0
                
                cursor.execute("""
                    UPDATE users
                    SET onboarding_step = ?,
                        onboarding_data = ?,
                        onboarding_completed = ?
                    WHERE id = ?
                """, (step, json.dumps(existing_data) if existing_data else None, onboarding_completed, user_id))
                conn.commit()
            
            return {'success': True}
            
        except Exception as e:
            print(f"Error updating onboarding step: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def complete_onboarding(self, user_id: int) -> Dict:
        """
        Mark onboarding as completed
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with success status
        """
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                self.db.supabase.client.table('users').update({
                    'onboarding_completed': 1,
                    'onboarding_step': len(self.ONBOARDING_STEPS) - 1
                }).eq('id', user_id).execute()
            else:
                cursor.execute("""
                    UPDATE users
                    SET onboarding_completed = 1,
                        onboarding_step = ?
                    WHERE id = ?
                """, (len(self.ONBOARDING_STEPS) - 1, user_id))
                conn.commit()
            
            return {'success': True}
            
        except Exception as e:
            print(f"Error completing onboarding: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
    
    def should_show_onboarding(self, user_id: int) -> bool:
        """
        Check if user should see onboarding
        
        Args:
            user_id: User ID
            
        Returns:
            True if onboarding should be shown
        """
        status = self.get_onboarding_status(user_id)
        return not status.get('completed', False)
    
    def get_next_step(self, user_id: int) -> Optional[Dict]:
        """
        Get next onboarding step
        
        Args:
            user_id: User ID
            
        Returns:
            Next step dictionary or None if completed
        """
        status = self.get_onboarding_status(user_id)
        
        if status.get('completed'):
            return None
        
        current_step = status.get('current_step', 0)
        if current_step < len(self.ONBOARDING_STEPS):
            return self.ONBOARDING_STEPS[current_step]
        
        return None
