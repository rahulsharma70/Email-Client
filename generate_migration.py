#!/usr/bin/env python3
"""
Generate Supabase Migration File
Creates supabase_migration.sql with all table definitions
"""

import sys
import os
sys.path.insert(0, 'backend')

from database.supabase_schema import SupabaseSchema
from unittest.mock import Mock

# Create mock client for migration file generation
class MockClient:
    def __init__(self):
        self.client = Mock()

client = MockClient()
schema = SupabaseSchema(client)

# Generate migration file
schema._save_migration_file(schema._get_sql_statements())

# Verify file was created
if os.path.exists('supabase_migration.sql'):
    with open('supabase_migration.sql', 'r') as f:
        content = f.read()
        lines = content.split('\n')
        print(f'✓ Migration file generated: supabase_migration.sql')
        print(f'✓ File has {len(lines)} lines')
        print(f'✓ File size: {len(content)} bytes')
        print('')
        print('Next steps:')
        print('1. Go to Supabase Dashboard → SQL Editor')
        print('2. Copy contents of supabase_migration.sql')
        print('3. Paste and run in SQL Editor')
else:
    print('✗ Failed to generate migration file')


