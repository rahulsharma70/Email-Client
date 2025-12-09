"""
Email Verification Module for ANAGHA SOLUTION
Uses SMTP handshake to verify email addresses
"""

import smtplib
import socket
import dns.resolver
from typing import Dict, Optional, List
from database.db_manager import DatabaseManager

class EmailVerifier:
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize email verifier
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
    
    def verify_email_smtp(self, email: str, timeout: int = 10) -> Dict:
        """
        Two-layer email verification:
        Layer 1: MX lookup to check if domain has mail servers
        Layer 2: SMTP handshake (MAIL FROM, RCPT TO) on port 25
        
        Args:
            email: Email address to verify
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with verification status
        """
        if not email or '@' not in email:
            return {
                'is_valid': False,
                'status': 'invalid_format',
                'message': 'Invalid email format',
                'verification_stage': 'format_check'
            }
        
        try:
            # Extract domain
            domain = email.split('@')[1]
            
            # ============================================
            # LAYER 1: MX Record Lookup
            # ============================================
            mx_host = None
            try:
                mx_records = dns.resolver.resolve(domain, 'MX', lifetime=timeout)
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
                return {
                    'is_valid': False,
                    'status': 'dns_timeout',
                    'message': 'DNS lookup timeout',
                    'verification_stage': 'mx_lookup',
                    'domain': domain
                }
            except Exception as e:
                return {
                    'is_valid': False,
                    'status': 'dns_error',
                    'message': f'DNS lookup error: {str(e)}',
                    'verification_stage': 'mx_lookup',
                    'domain': domain
                }
            
            # ============================================
            # LAYER 2: SMTP Handshake
            # ============================================
            try:
                # Connect to SMTP server on port 25
                server = smtplib.SMTP(timeout=timeout)
                server.set_debuglevel(0)  # Disable debug output
                
                # Connect to MX server
                server.connect(mx_host, 25)
                
                # Send EHLO (Extended Hello)
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
                    return {
                        'is_valid': False,
                        'status': 'mailbox_unavailable',
                        'message': f'Mailbox rejected: {message.decode("utf-8", errors="ignore") if isinstance(message, bytes) else str(message)}',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host,
                        'smtp_code': code
                    }
                # Other codes = Unknown/indeterminate
                else:
                    return {
                        'is_valid': False,
                        'status': 'unknown',
                        'message': f'SMTP server returned code {code}: {message.decode("utf-8", errors="ignore") if isinstance(message, bytes) else str(message)}',
                        'verification_stage': 'smtp_handshake',
                        'mx_host': mx_host,
                        'smtp_code': code
                    }
                    
            except smtplib.SMTPConnectError as e:
                return {
                    'is_valid': False,
                    'status': 'connection_error',
                    'message': f'Could not connect to MX server {mx_host}: {str(e)}',
                    'verification_stage': 'smtp_handshake',
                    'mx_host': mx_host
                }
            except smtplib.SMTPException as e:
                return {
                    'is_valid': False,
                    'status': 'smtp_error',
                    'message': f'SMTP error: {str(e)}',
                    'verification_stage': 'smtp_handshake',
                    'mx_host': mx_host
                }
            except socket.timeout:
                return {
                    'is_valid': False,
                    'status': 'timeout',
                    'message': 'SMTP connection timeout',
                    'verification_stage': 'smtp_handshake',
                    'mx_host': mx_host
                }
            except socket.gaierror:
                return {
                    'is_valid': False,
                    'status': 'connection_error',
                    'message': f'Could not resolve MX hostname {mx_host}',
                    'verification_stage': 'smtp_handshake',
                    'mx_host': mx_host
                }
            except Exception as e:
                return {
                    'is_valid': False,
                    'status': 'error',
                    'message': f'SMTP handshake error: {str(e)}',
                    'verification_stage': 'smtp_handshake',
                    'mx_host': mx_host
                }
                
        except Exception as e:
            return {
                'is_valid': False,
                'status': 'error',
                'message': f'Unexpected error: {str(e)}',
                'verification_stage': 'unknown'
            }
    
    def verify_lead_email(self, lead_id: int) -> Dict:
        """
        Verify email for a specific lead and update database
        
        Args:
            lead_id: Lead ID from database
            
        Returns:
            Verification result dictionary
        """
        conn = self.db.connect()
        cursor = conn.cursor()
        
        # Get lead
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

