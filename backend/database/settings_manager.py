"""
Settings Manager for ANAGHA SOLUTION
Persistent settings storage in database
"""

from typing import Dict, Optional, Any
import os
from core.config import Config

# Import database manager based on type
def get_db_manager():
    """Get appropriate database manager"""
    database_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    if database_type == 'supabase':
        try:
            from database.supabase_manager import SupabaseDatabaseManager
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            if supabase_url and supabase_key:
                return SupabaseDatabaseManager(supabase_url, supabase_key)
        except:
            pass
    # Fallback to SQLite
    from database.db_manager import DatabaseManager
    return DatabaseManager()

class SettingsManager:
    """Manages persistent application settings"""
    
    def __init__(self, db_manager=None):
        self.db = db_manager or get_db_manager()
        self._ensure_settings_table()
    
    def _ensure_settings_table(self):
        """Ensure settings table exists"""
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            # Supabase tables are created via schema migration
            return
        
        # SQLite - create table
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, setting_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    
    def get_setting(self, key: str, user_id: int = None, default: Any = None) -> Any:
        """Get setting value"""
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            filters = {'setting_key': key}
            if user_id:
                filters['user_id'] = user_id
            else:
                filters['user_id'] = None
            result = self.db.supabase.select('app_settings', filters=filters, limit=1)
            if result and result[0].get('setting_value'):
                return result[0]['setting_value']
            return default
        
        # SQLite
        conn = self.db.connect()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT setting_value FROM app_settings 
                WHERE setting_key = ? AND user_id = ?
            """, (key, user_id))
        else:
            cursor.execute("""
                SELECT setting_value FROM app_settings 
                WHERE setting_key = ? AND user_id IS NULL
            """, (key,))
        
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        return default
    
    def set_setting(self, key: str, value: Any, user_id: int = None):
        """Set setting value"""
        # Convert value to string
        value_str = str(value) if value is not None else None
        
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            data = {
                'setting_key': key,
                'setting_value': value_str,
                'user_id': user_id
            }
            # Check if setting exists
            filters = {'setting_key': key}
            if user_id:
                filters['user_id'] = user_id
            else:
                filters['user_id'] = None
            existing = self.db.supabase.select('app_settings', filters=filters, limit=1)
            if existing:
                self.db.supabase.update('app_settings', filters, data)
            else:
                self.db.supabase.insert('app_settings', data)
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute("""
                    INSERT OR REPLACE INTO app_settings (user_id, setting_key, setting_value, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, key, value_str))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO app_settings (setting_key, setting_value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value_str))
            
            conn.commit()
        
        # Also update .env file for critical settings
        self._update_env_if_needed(key, value_str)
    
    def _update_env_if_needed(self, key: str, value: str):
        """Update .env file for critical settings"""
        critical_keys = [
            'SUPABASE_URL', 'SUPABASE_KEY', 'DATABASE_TYPE',
            'JWT_SECRET_KEY', 'STRIPE_SECRET_KEY', 'REDIS_URL',
            'PERPLEXITY_API_KEY', 'OPENROUTER_API_KEY', 'OPENROUTER_MODEL'
        ]
        
        if key.upper() in critical_keys:
            try:
                from core.config import Config
                Config._update_env_file(key.upper(), value)
            except:
                pass
    
    def get_all_settings(self, user_id: int = None) -> Dict[str, Any]:
        """Get all settings"""
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            filters = {}
            if user_id:
                # Get both user-specific and global settings
                result = self.db.supabase.select('app_settings', 
                                                filters={'user_id': user_id}, 
                                                order_by='user_id.desc')
                global_result = self.db.supabase.select('app_settings',
                                                       filters={'user_id': None})
                result = result + global_result
            else:
                result = self.db.supabase.select('app_settings',
                                                filters={'user_id': None})
            
            settings = {}
            for row in result:
                key = row.get('setting_key')
                value = row.get('setting_value')
                # Don't override user-specific settings with global ones
                if key and key not in settings:
                    settings[key] = value
            return settings
        
        # SQLite
        conn = self.db.connect()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT setting_key, setting_value FROM app_settings 
                WHERE user_id = ? OR user_id IS NULL
                ORDER BY user_id DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT setting_key, setting_value FROM app_settings 
                WHERE user_id IS NULL
            """)
        
        settings = {}
        for row in cursor.fetchall():
            key = row[0]
            value = row[1]
            # Don't override user-specific settings with global ones
            if key not in settings:
                settings[key] = value
        
        return settings
    
    def delete_setting(self, key: str, user_id: int = None):
        """Delete setting"""
        # Check if using Supabase
        if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
            filters = {'setting_key': key}
            if user_id:
                filters['user_id'] = user_id
            else:
                filters['user_id'] = None
            self.db.supabase.delete('app_settings', filters)
            return
        
        # SQLite
        conn = self.db.connect()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                DELETE FROM app_settings 
                WHERE setting_key = ? AND user_id = ?
            """, (key, user_id))
        else:
            cursor.execute("""
                DELETE FROM app_settings 
                WHERE setting_key = ? AND user_id IS NULL
            """, (key,))
        
        conn.commit()

