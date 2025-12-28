"""
Email Verification Module for ANAGHA SOLUTION
Hardened SMTP verification with rate limits, exponential backoff, and paid API support
"""

import smtplib
import socket
import dns.resolver
import time
import random
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from core.config import Config
import requests

class EmailVerifier:
    """Hardened email verifier with rate limiting and exponential backoff"""
    
    # Rate limiting
    MAX_PROBES_PER_DOMAIN_PER_HOUR = 10
    MAX_PROBES_PER_IP_PER_HOUR = 50
    MIN_DELAY_BETWEEN_PROBES = 5  # seconds
    
    # Exponential backoff
    INITIAL_BACKOFF = 1  # seconds
    MAX_BACKOFF = 60  # seconds
    BACKOFF_MULTIPLIER = 2
    
    # Timeouts
    MX_LOOKUP_TIMEOUT = 5  # seconds
    SMTP_CONNECT_TIMEOUT = 10  # seconds
    SMTP_COMMAND_TIMEOUT = 5  # seconds
    
    # Probe tracking
    _domain_probe_counts = {}  # domain -> {count, reset_time}
    _ip_probe_counts = {}  # ip -> {count, reset_time}
    _last_probe_time = {}  # domain -> timestamp
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize email verifier
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.use_paid_api = Config.get('EMAIL_VERIFICATION_PROVIDER') == 'paid'
        self.paid_api_key = Config.get('EMAIL_VERIFICATION_API_KEY', '')
    
    def _check_rate_limit(self, domain: str) -> bool:
        """Check if we can probe this domain (rate limiting)"""
        now = datetime.now()
        
        # Check domain rate limit
        if domain in self._domain_probe_counts:
            count_info = self._domain_probe_counts[domain]
            if now < count_info['reset_time']:
                if count_info['count'] >= self.MAX_PROBES_PER_DOMAIN_PER_HOUR:
                    return False
            else:
                # Reset counter
                count_info['count'] = 0
                count_info['reset_time'] = now + timedelta(hours=1)
        
        # Check minimum delay
        if domain in self._last_probe_time:
            time_since_last = (now - self._last_probe_time[domain]).total_seconds()
            if time_since_last < self.MIN_DELAY_BETWEEN_PROBES:
                return False
        
        return True
    
    def _record_probe(self, domain: str):
        """Record that we probed this domain"""
        now = datetime.now()
        
        if domain not in self._domain_probe_counts:
            self._domain_probe_counts[domain] = {
                'count': 0,
                'reset_time': now + timedelta(hours=1)
            }
        
        self._domain_probe_counts[domain]['count'] += 1
        self._last_probe_time[domain] = now
    
    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay"""
        delay = min(
            self.INITIAL_BACKOFF * (self.BACKOFF_MULTIPLIER ** attempt),
            self.MAX_BACKOFF
        )
        # Add jitter
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
    
    def verify_email_paid_api(self, email: str) -> Dict:
        """Verify email using paid API (ZeroBounce, NeverBounce, etc.)"""
        if not self.paid_api_key:
            return {'error': 'Paid API key not configured'}
        
        provider = Config.get('EMAIL_VERIFICATION_PROVIDER', 'zerobounce')
        
        try:
            if provider.lower() == 'zerobounce':
                # ZeroBounce API
                url = 'https://api.zerobounce.net/v2/validate'
                params = {
                    'api_key': self.paid_api_key,
                    'email': email
                }
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                
                status = data.get('status', 'unknown')
                if status in ['valid', 'catch-all']:
                    return {
                        'is_valid': True,
                        'status': 'verified',
                        'message': 'Email verified via ZeroBounce',
                        'verification_stage': 'paid_api',
                        'provider': 'zerobounce'
                    }
                elif status in ['invalid', 'spamtrap', 'abuse', 'do_not_mail']:
                    return {
                        'is_valid': False,
                        'status': 'invalid',
                        'message': f'Email invalid: {status}',
                        'verification_stage': 'paid_api',
                        'provider': 'zerobounce'
                    }
                else:
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'Unknown status: {status}',
                        'verification_stage': 'paid_api',
                        'provider': 'zerobounce'
                    }
            else:
                return {'error': f'Unknown provider: {provider}'}
        except Exception as e:
            return {
                'is_valid': False,
                'status': 'error',
                'message': f'Paid API error: {str(e)}',
                'verification_stage': 'paid_api'
            }
    
    def verify_email_smtp(self, email: str, timeout: int = None, max_attempts: int = 3) -> Dict:
        """
        Hardened two-layer email verification with rate limiting and exponential backoff:
        Layer 1: MX lookup to check if domain has mail servers
        Layer 2: SMTP handshake (MAIL FROM, RCPT TO) on port 25
        
        Args:
            email: Email address to verify
            timeout: Connection timeout in seconds (defaults to SMTP_CONNECT_TIMEOUT)
            max_attempts: Maximum retry attempts with exponential backoff
            
        Returns:
            Dictionary with verification status
        """
        # Use paid API if configured
        if self.use_paid_api and self.paid_api_key:
            return self.verify_email_paid_api(email)
        
        if not email or '@' not in email:
            return {
                'is_valid': False,
                'status': 'invalid_format',
                'message': 'Invalid email format',
                'verification_stage': 'format_check'
            }
        
        # Extract domain
        domain = email.split('@')[1].lower()
        
        # Check rate limits
        if not self._check_rate_limit(domain):
            return {
                'is_valid': False,
                'status': 'rate_limited',
                'message': 'Rate limit exceeded for this domain',
                'verification_stage': 'rate_limit_check'
            }
        
        timeout = timeout or self.SMTP_CONNECT_TIMEOUT
        
        # Retry with exponential backoff
        last_error = None
        for attempt in range(max_attempts):
            try:
                # ============================================
                # LAYER 1: MX Record Lookup
                # ============================================
                mx_host = None
                try:
                    mx_records = dns.resolver.resolve(domain, 'MX', lifetime=self.MX_LOOKUP_TIMEOUT)
                    if not mx_records or len(mx_records) == 0:
                        return {
                            'is_valid': False,
                            'status': 'no_mx_record',
                            'message': 'Domain has no MX records configured',
                            'verification_stage': 'mx_lookup',
                            'domain': domain
                        }
                    
                    # Get the highest priority (lowest preference value) MX record
                    mx_record = sorted(mx_records, key=lambda x: x.preference)[0]
                    mx_host = str(mx_record.exchange).rstrip('.')
                    
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    return {
                        'is_valid': False,
                        'status': 'dns_error',
                        'message': 'Domain does not exist or has no MX records',
                        'verification_stage': 'mx_lookup',
                        'domain': domain
                    }
                except dns.resolver.Timeout:
                    # Transient failure - mark as unknown
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': 'DNS lookup timeout (transient failure)',
                        'verification_stage': 'mx_lookup',
                        'domain': domain
                    }
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'DNS lookup error (transient): {str(e)}',
                        'verification_stage': 'mx_lookup',
                        'domain': domain
                    }
                
                # ============================================
                # LAYER 2: SMTP Handshake
                # ============================================
                try:
                    # Connect to SMTP server on port 25 with timeout
                    server = smtplib.SMTP(timeout=self.SMTP_CONNECT_TIMEOUT)
                    server.set_debuglevel(0)  # Disable debug output
                    
                    # Connect to MX server
                    server.connect(mx_host, 25)
                
                    # Send EHLO (Extended Hello) with timeout
                    try:
                        server.ehlo()
                    except:
                        server.helo()  # Fallback to HELO
                    
                    # MAIL FROM command (set sender)
                    server.mail('verify@example.com')
                    
                    # RCPT TO command (check recipient)
                    code, message = server.rcpt(email)
                    
                    # Close connection gracefully
                    try:
                        server.quit()
                    except:
                        try:
                            server.close()
                        except:
                            pass
                    
                    # Record successful probe
                    self._record_probe(domain)
                    
                    # Interpret response codes
                    # 250 = OK, 251 = User not local, will forward, 252 = Cannot verify but will attempt delivery
                    if code in (250, 251, 252):
                        return {
                            'is_valid': True,
                            'status': 'verified',
                            'message': 'Email verified successfully',
                            'verification_stage': 'smtp_handshake',
                            'mx_host': mx_host,
                            'smtp_code': code,
                            'smtp_message': message.decode('utf-8', errors='ignore') if isinstance(message, bytes) else str(message)
                        }
                    # 5xx codes = Permanent failure (mailbox doesn't exist, etc.)
                    elif 500 <= code < 600:
                        self._record_probe(domain)
                        return {
                            'is_valid': False,
                            'status': 'mailbox_unavailable',
                            'message': f'Mailbox rejected: {message.decode("utf-8", errors="ignore") if isinstance(message, bytes) else str(message)}',
                            'verification_stage': 'smtp_handshake',
                            'mx_host': mx_host,
                            'smtp_code': code
                        }
                    # Other codes = Unknown/indeterminate (transient failures)
                    else:
                        # Mark as unknown for transient failures
                        return {
                            'is_valid': False,
                            'status': 'unknown',
                            'message': f'SMTP server returned code {code} (transient): {message.decode("utf-8", errors="ignore") if isinstance(message, bytes) else str(message)}',
                            'verification_stage': 'smtp_handshake',
                            'mx_host': mx_host,
                            'smtp_code': code
                        }
                        
                except smtplib.SMTPConnectError as e:
                    last_error = e
                    # Transient failure - retry with backoff
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'Could not connect to MX server {mx_host} (transient): {str(e)}',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host
                    }
                except smtplib.SMTPException as e:
                    last_error = e
                    # Transient failure
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'SMTP error (transient): {str(e)}',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host
                    }
                except socket.timeout:
                    # Transient failure
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': 'SMTP connection timeout (transient failure)',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host
                    }
                except socket.gaierror:
                    # Transient failure
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'Could not resolve MX hostname {mx_host} (transient)',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host
                    }
                except Exception as e:
                    last_error = e
                    # Transient failure
                    if attempt < max_attempts - 1:
                        backoff = self._exponential_backoff(attempt)
                        time.sleep(backoff)
                        continue
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'SMTP handshake error (transient): {str(e)}',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host
                    }
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    backoff = self._exponential_backoff(attempt)
                    time.sleep(backoff)
                    continue
        
        # All attempts failed
        return {
            'is_valid': False,
            'status': 'unknown',
            'message': f'All verification attempts failed: {str(last_error) if last_error else "Unknown error"}',
            'verification_stage': 'max_attempts_exceeded'
        }
    
    def verify_lead_email(self, lead_id: int) -> Dict:
        """
        Verify email for a specific lead and update database
        
        Args:
            lead_id: Lead ID from database
            
        Returns:
            Verification result dictionary
        """
        # Check if using Supabase
        use_supabase = hasattr(self.db, 'use_supabase') and self.db.use_supabase
        
        if use_supabase:
            # Get lead using Supabase
            result = self.db.supabase.client.table('leads').select('id,email,name,company_name').eq('id', lead_id).execute()
            if not result.data or len(result.data) == 0:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
            lead = result.data[0]
        else:
            # SQLite
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, name, company_name FROM leads WHERE id = ?", (lead_id,))
            row = cursor.fetchone()
            
            if not row:
                return {
                    'success': False,
                    'message': 'Lead not found'
                }
            lead = dict(row)
        
        email = lead.get('email', '')
        
        if not email:
            return {
                'success': False,
                'message': 'Lead has no email address'
            }
        
        # Verify email
        verification_result = self.verify_email_smtp(email)
        
        # Update database
        is_verified = 1 if verification_result.get('is_valid', False) else 0
        verification_status = verification_result.get('status', 'pending')
        
        from datetime import datetime
        verification_date = datetime.now() if is_verified else None
        
        if use_supabase:
            # Update lead using Supabase
            update_data = {
                'is_verified': is_verified,
                'verification_status': verification_status,
                'updated_at': datetime.now().isoformat()
            }
            if verification_date:
                update_data['verification_date'] = verification_date.isoformat()
            
            self.db.supabase.client.table('leads').update(update_data).eq('id', lead_id).execute()
            
            # If verified, add to recipients table
            if is_verified:
                try:
                    # Extract first and last name
                    name = lead.get('name', '')
                    name_parts = name.split(maxsplit=1) if name else []
                    first_name = name_parts[0] if len(name_parts) > 0 else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    # Check if recipient already exists
                    existing = self.db.supabase.client.table('recipients').select('id').eq('email', email.lower().strip()).execute()
                    if not existing.data or len(existing.data) == 0:
                        # Add to recipients
                        self.db.supabase.client.table('recipients').insert({
                            'email': email.lower().strip(),
                            'first_name': first_name,
                            'last_name': last_name,
                            'company': lead.get('company_name', ''),
                            'list_name': 'verified_leads',
                            'is_verified': 1
                        }).execute()
                except Exception as e:
                    print(f"Error adding verified lead to recipients: {e}")
        else:
            # SQLite
            cursor.execute("""
                UPDATE leads 
                SET is_verified = ?,
                    verification_status = ?,
                    verification_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (is_verified, verification_status, verification_date, lead_id))
            
            # If verified, add to recipients table
            if is_verified:
                try:
                    # Extract first and last name
                    name = lead.get('name', '')
                    name_parts = name.split(maxsplit=1) if name else []
                    first_name = name_parts[0] if len(name_parts) > 0 else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    # Add to recipients (ignore if duplicate)
                    cursor.execute("""
                        INSERT OR IGNORE INTO recipients (email, first_name, last_name, company, list_name, is_verified)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (
                        email.lower().strip(),
                        first_name,
                        last_name,
                        lead.get('company_name', ''),
                        'verified_leads'
                    ))
                except Exception as e:
                    print(f"Error adding verified lead to recipients: {e}")
            
            conn.commit()
        
        return {
            'success': True,
            'lead_id': lead_id,
            'email': email,
            'is_verified': is_verified,
            'verification_result': verification_result
        }
    
    def verify_batch_leads(self, lead_ids: List[int], delay: float = 1.0) -> Dict:
        """
        Verify multiple leads in batch
        
        Args:
            lead_ids: List of lead IDs to verify
            delay: Delay between verifications (seconds)
            
        Returns:
            Summary dictionary
        """
        import time
        
        results = {
            'total': len(lead_ids),
            'verified': 0,
            'failed': 0,
            'errors': []
        }
        
        for lead_id in lead_ids:
            try:
                result = self.verify_lead_email(lead_id)
                if result.get('success') and result.get('verification_result', {}).get('is_valid'):
                    results['verified'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'lead_id': lead_id,
                        'error': result.get('message', 'Unknown error')
                    })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'lead_id': lead_id,
                    'error': str(e)
                })
            
            # Add delay to avoid rate limiting
            time.sleep(delay)
        
        return results

