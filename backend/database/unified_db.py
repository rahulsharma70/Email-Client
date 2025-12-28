"""
Unified Database Interface
Provides a simple, transparent database interface that works with both SQLite and Supabase
"""

from typing import Optional, Dict, List, Any
from datetime import datetime

class UnifiedDatabase:
    """Unified database interface that works with both SQLite and Supabase"""
    
    def __init__(self, db_manager):
        """Initialize with a database manager (SQLite or Supabase)"""
        self.db = db_manager
        self.use_supabase = hasattr(db_manager, 'use_supabase') and db_manager.use_supabase
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> List[Dict]:
        """
        Execute a SELECT query and return results
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results
            
        Returns:
            List of dictionaries (rows)
        """
        if self.use_supabase:
            # For Supabase, queries should use table methods directly
            # This is a fallback for simple queries
            raise NotImplementedError("Use Supabase table methods directly for queries")
        else:
            conn = self.db.connect()
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch:
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            return []
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """
        Execute INSERT/UPDATE/DELETE query
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        if self.use_supabase:
            raise NotImplementedError("Use Supabase table methods directly for updates")
        else:
            conn = self.db.connect()
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        if self.use_supabase:
            return self.db.get_user(user_id)
        else:
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def table(self, table_name: str):
        """Get a table interface (Supabase style)"""
        if self.use_supabase:
            return self.db.supabase.client.table(table_name)
        else:
            # Return a SQLite table wrapper
            return SQLiteTableWrapper(self.db, table_name)

class SQLiteTableWrapper:
    """Wrapper to make SQLite look like Supabase table API"""
    
    def __init__(self, db_manager, table_name: str):
        self.db = db_manager
        self.table_name = table_name
    
    def select(self, columns: str = "*"):
        """Start a SELECT query"""
        self._columns = columns
        return self
    
    def eq(self, column: str, value: Any):
        """Add WHERE clause"""
        if not hasattr(self, '_conditions'):
            self._conditions = []
        self._conditions.append((column, value))
        return self
    
    def execute(self):
        """Execute the query"""
        query = f"SELECT {self._columns} FROM {self.table_name}"
        params = []
        if hasattr(self, '_conditions'):
            conditions = []
            for col, val in self._conditions:
                conditions.append(f"{col} = ?")
                params.append(val)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        # Return result in Supabase-like format
        class Result:
            def __init__(self, rows):
                self.data = [dict(row) for row in rows] if rows else []
        
        return Result(rows)
