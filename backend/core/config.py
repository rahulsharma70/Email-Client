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
    OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')
    
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
    def _update_env_file(key: str, value: str):
        """Update .env file with new key-value pair"""
        env_file = Path(__file__).parent.parent / '.env'
        
        # Read existing .env file
        env_vars = {}
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip()
        
        # Update the key
        env_vars[key] = value
        
        # Write back to .env file
        with open(env_file, 'w') as f:
            f.write("# API Keys Configuration\n")
            f.write("# Auto-generated - do not edit manually\n\n")
            f.write(f"# Perplexity API Key (for lead scraping)\n")
            f.write(f"PERPLEXITY_API_KEY={env_vars.get('PERPLEXITY_API_KEY', '')}\n\n")
            f.write(f"# OpenRouter API Key (for email personalization)\n")
            f.write(f"OPENROUTER_API_KEY={env_vars.get('OPENROUTER_API_KEY', '')}\n")
            
            # Write model
            f.write(f"\n# OpenRouter Model\n")
            f.write(f"OPENROUTER_MODEL={env_vars.get('OPENROUTER_MODEL', 'openai/gpt-4o-mini')}\n")

