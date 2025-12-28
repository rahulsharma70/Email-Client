"""
Configuration Manager for ANAGHA SOLUTION
Handles environment variables and API keys
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    """Application configuration"""
    
    # API Keys
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '')
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    
    # Default model for OpenRouter
    OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-7b-instruct')
    
    @staticmethod
    def get_perplexity_key():
        """Get Perplexity API key"""
        return Config.PERPLEXITY_API_KEY
    
    @staticmethod
    def get_openrouter_key():
        """Get OpenRouter API key"""
        return Config.OPENROUTER_API_KEY
    
    @staticmethod
    def set_perplexity_key(key: str):
        """Set Perplexity API key (updates .env file)"""
        Config._update_env_file('PERPLEXITY_API_KEY', key)
        Config.PERPLEXITY_API_KEY = key
    
    @staticmethod
    def set_openrouter_key(key: str):
        """Set OpenRouter API key (updates .env file)"""
        Config._update_env_file('OPENROUTER_API_KEY', key)
        Config.OPENROUTER_API_KEY = key
    
    @staticmethod
    def get(key: str, default: str = None):
        """Get environment variable"""
        return os.getenv(key, default)
    
    @staticmethod
    def _update_env_file(key: str, value: str):
        """Update .env file with new key-value pair - IMMEDIATELY PERSISTENT"""
        # Get project root (two levels up from backend/core)
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / '.env'
        
        # Read existing .env file
        env_vars = {}
        comments = {}  # Store comments for each key
        other_lines = []  # Store other lines (comments, blank lines)
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        other_lines.append(line)
                        continue
                    if '=' in stripped:
                        k, v = stripped.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        env_vars[k] = v
                        # Store comment if previous line was a comment
                        if other_lines and other_lines[-1].strip().startswith('#'):
                            comments[k] = other_lines[-1].strip()
                    else:
                        other_lines.append(line)
        
        # Update the key
        env_vars[key] = value
        
        # Write back to .env file preserving structure
        with open(env_file, 'w') as f:
            # Write header if file is new
            if not env_file.exists() or not other_lines:
                f.write("# ANAGHA SOLUTION - Environment Configuration\n")
                f.write("# Auto-generated - do not edit manually\n\n")
            
            # Write all environment variables
            all_keys = sorted(set(list(env_vars.keys()) + [key]))
            
            # Group by category
            categories = {
                'Database': ['DATABASE_TYPE', 'SUPABASE_URL', 'SUPABASE_KEY', 'SUPABASE_SERVICE_KEY'],
                'Authentication': ['JWT_SECRET_KEY'],
                'Billing': ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY'],
                'Redis': ['REDIS_URL'],
                'API Keys': ['PERPLEXITY_API_KEY', 'OPENROUTER_API_KEY', 'OPENROUTER_MODEL'],
                'Deployment': ['DEPLOYMENT_URL', 'DEPLOYMENT_ENV_VARS'],
                'Email Verification': ['EMAIL_VERIFICATION_API_KEY', 'EMAIL_VERIFICATION_PROVIDER']
            }
            
            written_keys = set()
            
            # Write categorized keys
            for category, keys in categories.items():
                category_keys = [k for k in keys if k in env_vars]
                if category_keys:
                    f.write(f"\n# {category}\n")
                    for k in category_keys:
                        comment = comments.get(k, '')
                        if comment:
                            f.write(f"{comment}\n")
                        f.write(f"{k}={env_vars[k]}\n")
                        written_keys.add(k)
            
            # Write remaining keys
            remaining = [k for k in all_keys if k not in written_keys and k in env_vars]
            if remaining:
                f.write("\n# Other Configuration\n")
                for k in remaining:
                    comment = comments.get(k, '')
                    if comment:
                        f.write(f"{comment}\n")
                    f.write(f"{k}={env_vars[k]}\n")
        
        # Reload environment variables
        load_dotenv(dotenv_path=env_file, override=True)

