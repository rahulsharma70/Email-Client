"""
Email Personalization Module for ANAGHA SOLUTION
Uses OpenRouter API for LLM-based personalization with cost controls
"""

import requests
import json
import hashlib
from typing import Dict, Optional, List
from database.db_manager import DatabaseManager

class EmailPersonalizer:
    def __init__(self, openrouter_api_key: str = None, model: str = None, db_manager: DatabaseManager = None, user_id: int = None):
        """
        Initialize email personalizer with quota management
        
        Args:
            openrouter_api_key: OpenRouter API key (can be set via environment variable OPENROUTER_API_KEY)
            model: Model to use for personalization (default: from config)
            db_manager: Database manager for quota tracking
            user_id: User ID for quota enforcement
        """
        from core.config import Config
        self.api_key = openrouter_api_key or self._get_api_key()
        self.model = model or Config.OPENROUTER_MODEL
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.db = db_manager
        self.user_id = user_id
        self._cache = {}  # Simple in-memory cache
        
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variable"""
        from core.config import Config
        return Config.get_openrouter_key()
    
    def _get_cache_key(self, template: str, name: str, company: str, context: str) -> str:
        """Generate cache key for personalization"""
        content = f"{template}|{name}|{company}|{context}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _check_quota(self) -> Dict:
        """Check LLM quota before making API call"""
        if not self.db or not self.user_id:
            return {'allowed': True}
        
        from core.quota_manager import QuotaManager
        quota_mgr = QuotaManager(self.db)
        
        # Estimate tokens (rough: 1 token ≈ 4 characters)
        estimated_tokens = 500  # Conservative estimate per personalization
        return quota_mgr.check_llm_quota(self.user_id, estimated_tokens)
    
    def personalize_email(self, template: str, name: str, company: str, context: str = "", use_cache: bool = True, custom_prompt: str = None) -> str:
        """
        Personalize email template using LLM with quota and caching
        
        Args:
            template: Base email template (can include {name}, {company} placeholders)
            name: Recipient name
            company: Company name
            context: Additional context about the recipient/company
            use_cache: Whether to use cached results
            custom_prompt: Custom personalization prompt from campaign (optional)
            
        Returns:
            Personalized email content
        """
        if not self.api_key:
            # Fallback to simple replacement if no API key
            personalized = template.replace('{name}', name)
            personalized = personalized.replace('{company}', company)
            return personalized
        
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(template, name, company, context)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # Check quota (both tokens and cost)
        quota_check = self._check_quota()
        if not quota_check.get('allowed', True):
            # Quota exceeded - use fallback
            print(f"LLM quota exceeded for user {self.user_id}, using fallback")
            personalized = template.replace('{name}', name)
            personalized = personalized.replace('{company}', company)
            return personalized
        
        # Check cost quota (estimate: 500 tokens per personalization)
        estimated_tokens = 500
        if self.db and self.user_id:
            from core.quota_manager import QuotaManager
            quota_mgr = QuotaManager(self.db)
            cost_check = quota_mgr.check_llm_cost_quota(self.user_id, estimated_tokens)
            if not cost_check.get('allowed', True):
                print(f"LLM cost quota exceeded for user {self.user_id}, using fallback")
                personalized = template.replace('{name}', name)
                personalized = personalized.replace('{company}', company)
                return personalized
        
        # Use custom prompt if provided, otherwise use default
        if custom_prompt:
            # Replace placeholders in custom prompt
            prompt = custom_prompt.replace('{template}', template)
            prompt = prompt.replace('{name}', name)
            prompt = prompt.replace('{company}', company)
            prompt = prompt.replace('{context}', context if context else 'No additional context provided')
        else:
            # Default prompt
            prompt = f"""Personalize this email template for a specific recipient.

Email Template:
{template}

Recipient Information:
- Name: {name}
- Company: {company}
- Context: {context if context else 'No additional context provided'}

Please personalize this email to:
1. Make it feel natural and conversational
2. Reference the recipient's name and company naturally
3. Incorporate the context if provided
4. Maintain the original intent and key messages
5. Keep it professional but warm

Return ONLY the personalized email content, no additional text or explanations."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://anaghasolution.com",
                "X-Title": "ANAGHA SOLUTION Email Client"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert email copywriter who personalizes emails to make them feel authentic and engaging."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            personalized_content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            # Track token usage and cost
            usage = data.get('usage', {})
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
            
            # Calculate cost
            cost_per_1k_tokens = 0.002
            cost = (total_tokens / 1000) * cost_per_1k_tokens
            
            # Record usage
            if self.db and self.user_id:
                from core.quota_manager import QuotaManager
                from core.observability import ObservabilityManager
                from database.settings_manager import SettingsManager
                
                quota_mgr = QuotaManager(self.db)
                obs_mgr = ObservabilityManager(self.db)
                settings = SettingsManager(self.db)
                
                # Record token usage
                quota_mgr.record_llm_usage(self.user_id, total_tokens)
                
                # Record cost
                current_cost = settings.get_setting('llm_cost_this_month', user_id=self.user_id) or '0'
                try:
                    new_cost = float(current_cost) + cost
                    settings.set_setting('llm_cost_this_month', str(new_cost), user_id=self.user_id)
                except:
                    pass
                
                # Record metric for observability
                obs_mgr.record_metric(self.user_id, 'llm', 'tokens_used', float(total_tokens), {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'cost': cost,
                    'model': self.model
                })
                
                # Record LLM usage metrics (aggregated by date)
                try:
                    from datetime import date
                    today = date.today()
                    
                    use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
                    if use_supabase:
                        # Check if record exists for today
                        result = self.db.supabase.client.table('llm_usage_metrics').select('*').eq('user_id', self.user_id).eq('metric_date', today.isoformat()).execute()
                        if result.data and len(result.data) > 0:
                            # Update existing
                            existing = result.data[0]
                            self.db.supabase.client.table('llm_usage_metrics').update({
                                'tokens_used': (existing.get('tokens_used', 0) or 0) + total_tokens,
                                'api_calls': (existing.get('api_calls', 0) or 0) + 1,
                                'cost': (existing.get('cost', 0) or 0) + cost
                            }).eq('id', existing['id']).execute()
                        else:
                            # Create new
                            self.db.supabase.client.table('llm_usage_metrics').insert({
                                'user_id': self.user_id,
                                'metric_date': today.isoformat(),
                                'tokens_used': total_tokens,
                                'api_calls': 1,
                                'cost': cost
                            }).execute()
                    else:
                        conn = self.db.connect()
                        cursor = conn.cursor()
                        # Ensure table exists
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS llm_usage_metrics (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER,
                                metric_date DATE NOT NULL,
                                tokens_used INTEGER DEFAULT 0,
                                api_calls INTEGER DEFAULT 0,
                                cost REAL DEFAULT 0.0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(user_id, metric_date),
                                FOREIGN KEY (user_id) REFERENCES users(id)
                            )
                        """)
                        # Check if record exists
                        cursor.execute("SELECT id, tokens_used, api_calls, cost FROM llm_usage_metrics WHERE user_id = ? AND metric_date = ?", (self.user_id, today))
                        row = cursor.fetchone()
                        if row:
                            # Update existing
                            cursor.execute("""
                                UPDATE llm_usage_metrics
                                SET tokens_used = tokens_used + ?,
                                    api_calls = api_calls + 1,
                                    cost = cost + ?
                                WHERE id = ?
                            """, (total_tokens, cost, row[0]))
                        else:
                            # Create new
                            cursor.execute("""
                                INSERT INTO llm_usage_metrics (user_id, metric_date, tokens_used, api_calls, cost, created_at)
                                VALUES (?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                            """, (self.user_id, today, total_tokens, cost))
                        conn.commit()
                except Exception as e:
                    # Table might not exist, that's okay
                    print(f"Note: Could not record LLM metrics: {e}")
            
            # Clean up the response (remove markdown code blocks if present)
            personalized_content = personalized_content.strip()
            if personalized_content.startswith('```'):
                # Remove markdown code blocks
                lines = personalized_content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines[-1].strip() == '```':
                    lines = lines[:-1]
                personalized_content = '\n'.join(lines)
            
            result = personalized_content.strip()
            
            # Cache result
            if use_cache:
                cache_key = self._get_cache_key(template, name, company, context)
                self._cache[cache_key] = result
            
            return result
            
        except requests.RequestException as e:
            print(f"Error calling OpenRouter API: {e}")
            # Fallback to simple replacement
            personalized = template.replace('{name}', name)
            personalized = personalized.replace('{company}', company)
            return personalized
        except Exception as e:
            print(f"Unexpected error in personalization: {e}")
            # Fallback to simple replacement
            personalized = template.replace('{name}', name)
            personalized = personalized.replace('{company}', company)
            return personalized
    
    def personalize_batch(self, template: str, recipients: List[Dict], delay: float = 0.5) -> Dict[str, str]:
        """
        Personalize email for multiple recipients
        
        Args:
            template: Base email template
            recipients: List of recipient dictionaries with 'name', 'company', and optional 'context'
            delay: Delay between API calls (seconds)
            
        Returns:
            Dictionary mapping recipient email/ID to personalized content
        """
        import time
        
        personalized_emails = {}
        
        for recipient in recipients:
            name = recipient.get('name', '')
            company = recipient.get('company', '')
            context = recipient.get('context', '')
            recipient_id = recipient.get('email') or recipient.get('id', '')
            
            try:
                personalized = self.personalize_email(template, name, company, context)
                personalized_emails[recipient_id] = personalized
            except Exception as e:
                print(f"Error personalizing for {name}: {e}")
                # Use fallback
                personalized = template.replace('{name}', name)
                personalized = personalized.replace('{company}', company)
                personalized_emails[recipient_id] = personalized
            
            # Add delay to avoid rate limiting
            time.sleep(delay)
        
        return personalized_emails

