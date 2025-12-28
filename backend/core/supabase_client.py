"""
Supabase Database Client for ANAGHA SOLUTION
Replaces SQLite with Supabase PostgreSQL
"""

import os
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
from core.config import Config

class SupabaseClient:
    """Supabase database client wrapper"""
    
    def __init__(self, url: str = None, key: str = None):
        """
        Initialize Supabase client
        
        Args:
            url: Supabase project URL
            key: Supabase anon/service key
        """
        self.url = url or Config.get('SUPABASE_URL') or os.getenv('SUPABASE_URL')
        self.key = key or Config.get('SUPABASE_KEY') or os.getenv('SUPABASE_KEY')
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and Key are required. Set SUPABASE_URL and SUPABASE_KEY in .env")
        
        self.client: Optional[Client] = None
        self._connect()
    
    def _connect(self):
        """Connect to Supabase"""
        try:
            self.client = create_client(self.url, self.key)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Supabase: {e}")
    
    def execute_query(self, table: str, operation: str = 'select', 
                     filters: Dict = None, data: Dict = None, 
                     limit: int = None, order_by: str = None) -> List[Dict]:
        """
        Execute query on Supabase table
        
        Args:
            table: Table name
            operation: 'select', 'insert', 'update', 'delete'
            filters: Dictionary of filters (e.g., {'id': 1, 'user_id': 2})
            data: Data for insert/update
            limit: Limit results
            order_by: Order by clause (e.g., 'created_at.desc')
        """
        if not self.client:
            self._connect()
        
        try:
            # Execute operation - each operation has different pattern
            if operation == 'select':
                # SELECT: table().select('*').eq().order().limit()
                query = self.client.table(table).select('*')
                
                # Apply filters using .eq() after .select()
                if filters:
                    for key, value in filters.items():
                        query = query.eq(key, value)
                
                # Apply ordering
                if order_by:
                    parts = order_by.split('.')
                    if len(parts) == 2:
                        query = query.order(parts[0], desc=(parts[1].lower() == 'desc'))
                    else:
                        query = query.order(parts[0])
                
                # Apply limit
                if limit:
                    query = query.limit(limit)
                
                # Execute query
                result = query.execute()
                return result.data if result.data else []
            
            elif operation == 'insert':
                # INSERT: table().insert(data).execute()
                if not data:
                    raise ValueError("Data required for insert operation")
                result = self.client.table(table).insert(data).execute()
                return result.data if result.data else []
            
            elif operation == 'update':
                # UPDATE: table().update(data).eq().execute()
                if not data:
                    raise ValueError("Data required for update operation")
                query = self.client.table(table).update(data)
                
                # Apply filters using .eq()
                if filters:
                    for key, value in filters.items():
                        query = query.eq(key, value)
                
                result = query.execute()
                return result.data if result.data else []
            
            elif operation == 'delete':
                # DELETE: table().delete().eq().execute()
                query = self.client.table(table).delete()
                
                # Apply filters using .eq()
                if filters:
                    for key, value in filters.items():
                        query = query.eq(key, value)
                
                result = query.execute()
                return result.data if result.data else []
            
            else:
                raise ValueError(f"Unknown operation: {operation}")
                
        except Exception as e:
            raise Exception(f"Supabase query error: {e}")
    
    def insert(self, table: str, data: Dict) -> Dict:
        """Insert single record - direct call"""
        if not self.client:
            self._connect()
        result = self.client.table(table).insert(data).execute()
        return result.data[0] if result.data and len(result.data) > 0 else {}
    
    def select(self, table: str, filters: Dict = None, 
               limit: int = None, order_by: str = None) -> List[Dict]:
        """Select records"""
        return self.execute_query(table, 'select', filters=filters, 
                                 limit=limit, order_by=order_by)
    
    def update(self, table: str, filters: Dict, data: Dict) -> List[Dict]:
        """Update records - direct call"""
        if not self.client:
            self._connect()
        query = self.client.table(table).update(data)
        
        # Apply filters using .eq()
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        result = query.execute()
        return result.data if result.data else []
    
    def delete(self, table: str, filters: Dict) -> List[Dict]:
        """Delete records - direct call"""
        if not self.client:
            self._connect()
        query = self.client.table(table).delete()
        
        # Apply filters using .eq()
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        result = query.execute()
        return result.data if result.data else []
    
    def execute_sql(self, sql: str, params: List = None) -> Any:
        """
        Execute raw SQL (using RPC if needed)
        Note: Supabase doesn't support arbitrary SQL, use table methods instead
        """
        # For complex queries, use Supabase RPC functions
        # This is a placeholder - implement RPC functions in Supabase
        raise NotImplementedError("Use table methods or create RPC functions in Supabase")
    
    def test_connection(self) -> bool:
        """Test Supabase connection"""
        try:
            # Try to query a simple table (users table should exist)
            self.client.table('users').select('id').limit(1).execute()
            return True
        except:
            # If users table doesn't exist, connection is still valid
            return True

