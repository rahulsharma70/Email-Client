"""
Supabase Database Initialization Script
Creates all tables in Supabase if they don't exist
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.config import Config
from core.supabase_client import SupabaseClient
from database.supabase_schema import SupabaseSchema

def initialize_supabase_tables():
    """Initialize Supabase tables"""
    try:
        supabase_url = Config.get('SUPABASE_URL') or os.getenv('SUPABASE_URL')
        supabase_key = Config.get('SUPABASE_KEY') or os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            print("⚠️  Supabase URL or Key not found in environment")
            print("   Set SUPABASE_URL and SUPABASE_KEY in .env file")
            return False
        
        print(f"Connecting to Supabase: {supabase_url[:30]}...")
        client = SupabaseClient(supabase_url, supabase_key)
        schema = SupabaseSchema(client)
        
        print("Initializing Supabase schema...")
        result = schema.initialize_schema()
        
        if result:
            print("✓ Supabase tables initialized successfully")
            return True
        else:
            print("⚠️  Could not auto-create tables")
            print("   Please run supabase_migration.sql in Supabase SQL Editor")
            return False
            
    except Exception as e:
        print(f"✗ Error initializing Supabase: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    initialize_supabase_tables()


