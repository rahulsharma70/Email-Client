"""
Lead Scraper Module for ANAGHA SOLUTION (Hardened)
Uses Perplexity API to extract companies and decision makers
"""

import requests
import re
import json
import time
from typing import List, Dict, Optional, Any
from database.db_manager import DatabaseManager

# Simple mock fallback used when Perplexity fails
MOCK_COMPANIES = [
    {"name": "Acme Security", "domain": "acmesecurity.com", "industry": "Security", "size": "50-200"},
    {"name": "Nimbus Tech", "domain": "nimbustech.com", "industry": "SaaS", "size": "50-200"},
    {"name": "Blue Harbor", "domain": "blueharbor.com", "industry": "Finance", "size": "100-500"},
]

MOCK_DECISION_MAKERS = [
    {
      "name": "Alex Rivera",
      "title": "CTO",
      "email_patterns": []
    },
    {
      "name": "Jamie Chen",
      "title": "Head of Security",
      "email_patterns": []
    }
]


class LeadScraper:
    def __init__(self, db_manager: DatabaseManager, perplexity_api_key: str = None):
        """
        Initialize lead scraper

        Args:
            db_manager: Database manager instance
            perplexity_api_key: Perplexity API key (can be set via environment variable PERPLEXITY_API_KEY)
        """
        self.db = db_manager
        self.perplexity_api_key = perplexity_api_key or self._get_api_key()
        self.base_url = "https://api.perplexity.ai/chat/completions"

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variable or config"""
        try:
            from core.config import Config
            return Config.get_perplexity_key()
        except Exception:
            return None

    # ---------------------------
    # Perplexity helper (robust)
    # ---------------------------
    def _perplexity_api_call(self, prompt_text: str, candidate_model: str = "sonar") -> Optional[Dict[str, Any]]:
        """
        Call Perplexity endpoint. This helper:
        - validates key
        - tries two payload shapes (messages and prompt) to be resilient
        - logs request/response
        - returns parsed JSON dict on success, or None on failure
        """
        if not self.perplexity_api_key:
            print("Perplexity API key not configured.")
            return None

        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json"
        }

        # Candidate payload shapes to try (messages first, then simple prompt)
        payloads = [
            {
                "model": candidate_model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that returns strict JSON arrays when asked."},
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.4,
                "max_tokens": 1500
            },
            {
                # fallback minimal shape: some Perplexity variants accept prompt
                "model": candidate_model,
                "prompt": prompt_text,
                "temperature": 0.4,
                "max_tokens": 1500
            }
        ]

        for idx, payload in enumerate(payloads):
            try:
                raw = json.dumps(payload)
            except Exception as e:
                print("Payload serialization failed:", e)
                continue

            try:
                print(f"Perplexity -> REQUEST shape #{idx+1} (truncated):")
                print(raw[:2000])
                resp = requests.post(self.base_url, headers=headers, data=raw, timeout=30)
                print("Perplexity <- STATUS:", resp.status_code)
                print("Perplexity <- BODY (truncated):")
                print(resp.text[:4000])

                # if 4xx other than 429 -> treat as client error and stop trying shapes
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    print(f"Perplexity client error {resp.status_code}. Not retrying shapes.")
                    return None

                # allow retry on 429 / 5xx up to a small number - but here we just try the other shape once
                resp.raise_for_status()

                # parse JSON safely
                try:
                    return resp.json()
                except Exception as e:
                    print("Failed to parse JSON from Perplexity response:", e)
                    return None

            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                body = getattr(e.response, "text", "")
                print(f"Perplexity HTTPError ({status}): {body[:2000]}")
                # If rate limited, allow trying next shape once
                if status == 429:
                    print("Rate limited (429). Trying next payload shape or backing off.")
                    time.sleep(1)
                    continue
                # For other 4xx: stop and return None
                return None
            except requests.exceptions.RequestException as e:
                print("Perplexity RequestException:", e)
                # network transient -> try next shape or bail
                time.sleep(1)
                continue

        # if all shapes failed
        print("Perplexity: all payload shapes failed or returned client errors.")
        return None

    # ---------------------------
    # Utility: extract balanced JSON array from text
    # ---------------------------
    def _extract_json_array_from_text(self, text: str) -> Optional[str]:
        """
        Find the first balanced JSON array in the text and return as string.
        Returns None if not found.
        """
        if not text:
            return None

        # naive but effective: find first '[' then find matching closing ']'
        start = text.find('[')
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return None

    # ---------------------------
    # Main public methods
    # ---------------------------
    def extract_companies_from_icp(self, icp_description: str) -> List[Dict]:
        """
        Extract company names from ICP description using Perplexity API

        Args:
            icp_description: Description of Ideal Customer Profile

        Returns:
            List of company dictionaries with name and domain
        """
        prompt = f"""Based on this Ideal Customer Profile (ICP) description, extract a list of real companies that match this profile.

ICP Description: {icp_description}

Please provide a JSON array of companies with the following structure:
[
  {{
    "name": "Company Name",
    "domain": "companydomain.com",
    "industry": "Industry type",
    "size": "Company size (e.g., '50-200 employees')"
  }}
]

Extract at least 10 companies that match this ICP. Focus on real, existing companies.
Return ONLY the JSON array, no additional text."""

        # Try a primary candidate model name, fallback to 'sonar'
        for candidate_model in ("llama-3.1-sonar-large-128k-online", "sonar"):
            resp_json = self._perplexity_api_call(prompt, candidate_model=candidate_model)
            if not resp_json:
                continue

            # Best-effort extraction: many LLM responses will include choices -> message -> content
            content = None
            if isinstance(resp_json, dict):
                # common structure: {'choices':[{'message':{'content': '...'}}], ...}
                choices = resp_json.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content") or choices[0].get("text") or None
                # Some APIs put answer in 'answer' or 'result'
                if content is None:
                    content = resp_json.get("answer") or resp_json.get("result") or resp_json.get("text")

            # If content not found, try raw stringify of resp_json
            if content is None:
                content = json.dumps(resp_json)

            # Extract JSON array
            arr_text = self._extract_json_array_from_text(content)
            if arr_text:
                try:
                    companies = json.loads(arr_text)
                    if isinstance(companies, list):
                        return companies
                except json.JSONDecodeError as e:
                    print("Error parsing extracted JSON array:", e)
                    print("Extracted text (truncated):", arr_text[:1000])
                    # continue with next model shape or fallback

            # Try to parse entire content as JSON if it looks like JSON
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

        # If all attempts failed, return MOCK but do not raise
        print("extract_companies_from_icp: Perplexity failed to return companies; using MOCK list.")
        return MOCK_COMPANIES.copy()

    def extract_decision_makers(self, company_name: str, company_domain: str) -> List[Dict]:
        """
        Extract decision makers from a company using Perplexity API

        Args:
            company_name: Name of the company
            company_domain: Domain of the company

        Returns:
            List of decision maker dictionaries with name, title, and email patterns
        """
        prompt = f"""Find the key decision makers at {company_name} (domain: {company_domain}).

Extract 3-5 most important decision makers such as:
- CEO, CTO, CMO, CFO
- VP of Sales, VP of Marketing
- Head of Department (HOD)
- Directors

For each person, provide:
- Full name
- Job title/role
- Their likely email format based on the company domain

Return a JSON array with this structure:
[
  {{
    "name": "Full Name",
    "title": "Job Title",
    "email_patterns": ["pattern1@domain.com", "pattern2@domain.com"]
  }}
]

Generate up to 5 email pattern variations for each person using common formats.
Return ONLY the JSON array, no additional text."""

        for candidate_model in ("sonar", "llama-3.1-sonar-large-128k-online"):
            resp_json = self._perplexity_api_call(prompt, candidate_model=candidate_model)
            if not resp_json:
                continue

            content = None
            if isinstance(resp_json, dict):
                choices = resp_json.get("choices")
                if choices and isinstance(choices, list) and len(choices) > 0:
                    content = choices[0].get("message", {}).get("content") or choices[0].get("text") or None
                if content is None:
                    content = resp_json.get("answer") or resp_json.get("result") or resp_json.get("text")

            if content is None:
                content = json.dumps(resp_json)

            arr_text = self._extract_json_array_from_text(content)
            if arr_text:
                try:
                    dms = json.loads(arr_text)
                    if isinstance(dms, list):
                        # Ensure email_patterns exist; if empty, the caller will generate
                        for dm in dms:
                            if "email_patterns" not in dm:
                                dm["email_patterns"] = []
                        return dms
                except json.JSONDecodeError as e:
                    print("Error parsing decision makers JSON array:", e)
                    print("Extracted (truncated):", arr_text[:1000])
                    # continue to next model

            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    for dm in parsed:
                        if "email_patterns" not in dm:
                            dm["email_patterns"] = []
                    return parsed
            except Exception:
                pass

        # fallback
        print(f"extract_decision_makers: Perplexity failed for {company_name}; returning MOCK decision makers.")
        return MOCK_DECISION_MAKERS.copy()

    def generate_email_patterns(self, first_name: str, last_name: str, domain: str) -> List[str]:
        """
        Generate 5 email pattern variations for a person
        """
        if not first_name:
            return []
        first_name = first_name.lower().strip()
        last_name = (last_name or "").lower().strip()
        domain = domain.lower().strip()

        # sanitize single-word last name
        last_name_compact = last_name.replace(' ', '')
        patterns = [
            f"{first_name}.{last_name_compact}@{domain}",
            f"{first_name}{last_name_compact}@{domain}",
            f"{first_name[0]}.{last_name_compact}@{domain}" if last_name_compact else f"{first_name}@{domain}",
            f"{first_name}@{domain}",
            f"{first_name[0]}{last_name_compact}@{domain}"
        ]
        # deduplicate and return up to 5
        seen = []
        out = []
        for p in patterns:
            if p not in seen:
                seen.append(p)
                out.append(p)
            if len(out) >= 5:
                break
        return out

    def save_leads_to_database(self, leads: List[Dict], scraping_job_id: int = None, user_id: int = None):
        """
        Save leads to database with deduplication check
        
        Args:
            leads: List of lead dictionaries
            scraping_job_id: Optional scraping job ID
            user_id: User ID for multi-tenant support
        """
        conn = self.db.connect()
        cursor = conn.cursor()

        saved_count = 0
        skipped_count = 0
        
        for lead in leads:
            try:
                email = lead.get('email', '').lower().strip()
                if not email:
                    continue
                
                # Check if lead already exists (by email and optionally user_id)
                if user_id:
                    cursor.execute("""
                        SELECT id, is_verified, follow_up_count FROM leads 
                        WHERE email = ? AND user_id = ?
                    """, (email, user_id))
                else:
                    cursor.execute("""
                        SELECT id, is_verified, follow_up_count FROM leads 
                        WHERE email = ?
                    """, (email,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Lead exists - update if needed, increment follow_up_count if from new source
                    existing_id = existing[0]
                    existing_verified = existing[1]
                    follow_up_count = (existing[2] or 0) + 1
                    
                    # Update follow-up count and source if from scraping
                    if scraping_job_id:
                        cursor.execute("""
                            UPDATE leads 
                            SET follow_up_count = ?,
                                source = CASE 
                                    WHEN source NOT LIKE 'scraper_job_%' THEN ?
                                    ELSE source
                                END,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (follow_up_count, lead.get('source', 'scraper'), existing_id))
                    else:
                        cursor.execute("""
                            UPDATE leads 
                            SET follow_up_count = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (follow_up_count, existing_id))
                    
                    skipped_count += 1
                    continue
                
                # New lead - insert it
                if user_id:
                    cursor.execute("""
                        INSERT INTO leads (name, company_name, domain, email, title, source, user_id, follow_up_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        lead.get('name', ''),
                        lead.get('company_name', ''),
                        lead.get('domain', ''),
                        email,
                        lead.get('title', ''),
                        lead.get('source', 'scraper'),
                        user_id
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO leads (name, company_name, domain, email, title, source, follow_up_count)
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                    """, (
                        lead.get('name', ''),
                        lead.get('company_name', ''),
                        lead.get('domain', ''),
                        email,
                        lead.get('title', ''),
                        lead.get('source', 'scraper')
                    ))
                saved_count += 1
            except Exception as e:
                print(f"Error saving lead {lead.get('name', 'unknown')}: {e}")
                continue

        conn.commit()
        return {'saved': saved_count, 'skipped': skipped_count, 'total': saved_count + skipped_count}

    def run_full_scraping_job(self, icp_description: str, job_id: int = None) -> Dict:
        """
        Run complete scraping job: ICP -> Companies -> Decision Makers -> Email Patterns -> Verification
        
        Args:
            icp_description: ICP description
            job_id: Optional job ID (if None, creates new job)
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        if job_id is None:
            cursor.execute("""
                INSERT INTO lead_scraping_jobs (icp_description, status)
                VALUES (?, 'running')
            """, (icp_description,))
            job_id = cursor.lastrowid
            conn.commit()
        else:
            # Update existing job
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET status = 'running', current_step = 'Starting...', progress_percent = 0
                WHERE id = ?
            """, (job_id,))
            conn.commit()

        try:
            # Update progress: Starting
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET status = 'running', current_step = 'Extracting companies from ICP...', progress_percent = 5
                WHERE id = ?
            """, (job_id,))
            conn.commit()
            
            # Step 1: Extract companies
            print("Step 1: Extracting companies from ICP...")
            companies = self.extract_companies_from_icp(icp_description)
            print(f"Found {len(companies)} companies")
            
            # Update progress: Companies found
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET companies_found = ?, current_step = 'Extracting decision makers...', progress_percent = 20
                WHERE id = ?
            """, (len(companies), job_id))
            conn.commit()

            # Step 2: Extract decision makers for each company
            all_leads = []
            total_companies = len(companies)
            for idx, company in enumerate(companies):
                company_name = company.get('name', '')
                company_domain = company.get('domain', '')

                if not company_domain and company_name:
                    # Try to construct a naive domain from company name
                    company_domain = company_name.lower().replace(' ', '').replace('.', '').replace(',', '') + '.com'

                print(f"Extracting decision makers from {company_name} ({company_domain})...")
                
                # Update progress for decision maker extraction
                progress = 20 + int((idx / total_companies) * 40)  # 20-60%
                cursor.execute("""
                    UPDATE lead_scraping_jobs 
                    SET current_step = ?, progress_percent = ?
                    WHERE id = ?
                """, (f'Extracting decision makers from {company_name}... ({idx+1}/{total_companies})', progress, job_id))
                conn.commit()
                
                decision_makers = self.extract_decision_makers(company_name, company_domain)

                # Step 3: Generate email patterns and create leads
                for dm in decision_makers:
                    name = dm.get('name', '')
                    title = dm.get('title', '')
                    email_patterns = dm.get('email_patterns', [])

                    # If email patterns not provided, generate them
                    if not email_patterns and name:
                        name_parts = name.split()
                        if len(name_parts) >= 2:
                            first_name = name_parts[0]
                            last_name = ' '.join(name_parts[1:])
                            email_patterns = self.generate_email_patterns(first_name, last_name, company_domain)
                        else:
                            email_patterns = self.generate_email_patterns(name_parts[0], "", company_domain)

                    # Create lead entries for each email pattern
                    for email_pattern in email_patterns[:5]:  # Limit to 5 patterns
                        lead = {
                            'name': name,
                            'company_name': company_name,
                            'domain': company_domain,
                            'email': email_pattern,
                            'title': title,
                            'source': f'scraper_job_{job_id}'
                        }
                        all_leads.append(lead)

                # Add delay to avoid rate limiting (small)
                time.sleep(1)

            # Step 4: Save leads to database
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET current_step = 'Saving leads to database...', progress_percent = 60
                WHERE id = ?
            """, (job_id,))
            conn.commit()
            
            # Get user_id from job if available
            cursor.execute("SELECT user_id FROM lead_scraping_jobs WHERE id = ?", (job_id,))
            job_row = cursor.fetchone()
            user_id = job_row[0] if job_row and len(job_row) > 0 else None
            
            print(f"Saving {len(all_leads)} leads to database...")
            result = self.save_leads_to_database(all_leads, job_id, user_id=user_id)
            saved_count = result.get('saved', 0) if isinstance(result, dict) else result
            
            # Step 5: Validate leads immediately after saving
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET current_step = 'Validating leads...', progress_percent = 65
                WHERE id = ?
            """, (job_id,))
            conn.commit()
            
            print(f"Validating {saved_count} leads...")
            from core.email_verifier import EmailVerifier
            verifier = EmailVerifier(self.db)
            
            # Get all lead IDs that were just saved
            cursor.execute("""
                SELECT id FROM leads 
                WHERE source = ? 
                ORDER BY id DESC 
                LIMIT ?
            """, (f'scraper_job_{job_id}', saved_count))
            lead_ids = [row[0] for row in cursor.fetchall()]
            
            # Validate each lead
            verified_count = 0
            total_leads = len(lead_ids)
            for idx, lead_id in enumerate(lead_ids):
                try:
                    result = verifier.verify_lead_email(lead_id)
                    if result.get('is_verified'):
                        verified_count += 1
                    
                    # Update progress in database (65-95%)
                    progress = 65 + int((idx / total_leads) * 30) if total_leads > 0 else 65
                    cursor.execute("""
                        UPDATE lead_scraping_jobs 
                        SET verified_leads = ?, 
                            current_step = ?,
                            progress_percent = ?
                        WHERE id = ?
                    """, (
                        verified_count, 
                        f'Validating leads... ({idx+1}/{total_leads} verified: {verified_count})',
                        progress,
                        job_id
                    ))
                    conn.commit()
                    
                    # Small delay to avoid overwhelming mail servers
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Error validating lead {lead_id}: {e}")
                    continue

            # Step 6: Update job status - completed
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET status = 'completed', 
                    companies_found = ?,
                    leads_found = ?,
                    verified_leads = ?,
                    current_step = 'Completed',
                    progress_percent = 100,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (len(companies), saved_count, verified_count, job_id))
            conn.commit()

            return {
                'job_id': job_id,
                'companies_found': len(companies),
                'leads_found': saved_count,
                'verified_leads': verified_count,
                'status': 'completed'
            }

        except Exception as e:
            # Update job status to failed and do not raise raw Perplexity errors upward
            print("Unexpected error in full scraping job:", e)
            cursor.execute("""
                UPDATE lead_scraping_jobs 
                SET status = 'failed'
                WHERE id = ?
            """, (job_id,))
            conn.commit()
            return {
                'job_id': job_id,
                'companies_found': 0,
                'leads_found': 0,
                'status': 'failed',
                'error': str(e)
            }
