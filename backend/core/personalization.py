"""
Email Personalization Module for ANAGHA SOLUTION
Uses OpenRouter API for LLM-based personalization
"""

import requests
import json
from typing import Dict, Optional, List

class EmailPersonalizer:
    def __init__(self, openrouter_api_key: str = None, model: str = None):
        """
        Initialize email personalizer
        
        Args:
            openrouter_api_key: OpenRouter API key (can be set via environment variable OPENROUTER_API_KEY)
            model: Model to use for personalization (default: from config)
        """
        from core.config import Config
        self.api_key = openrouter_api_key or self._get_api_key()
        self.model = model or Config.OPENROUTER_MODEL
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variable"""
        from core.config import Config
        return Config.get_openrouter_key()
    
    def personalize_email(self, template: str, name: str, company: str, context: str = "") -> str:
        """
        Personalize email template using LLM
        
        Args:
            template: Base email template (can include {name}, {company} placeholders)
            name: Recipient name
            company: Company name
            context: Additional context about the recipient/company
            
        Returns:
            Personalized email content
        """
        if not self.api_key:
            # Fallback to simple replacement if no API key
            personalized = template.replace('{name}', name)
            personalized = personalized.replace('{company}', company)
            return personalized
        
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
            
            return personalized_content.strip()
            
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

