"""
DNS Verification Module for ANAGHA SOLUTION
Handles SPF, DKIM, and DMARC record validation
"""

import dns.resolver
import dns.exception
from typing import Dict, Optional, List
from datetime import datetime
import secrets
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

class DNSVerifier:
    """Manages DNS record verification for email domains"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def generate_dkim_keys(self) -> Dict:
        """
        Generate DKIM public and private keys
        
        Returns:
            Dictionary with public_key, private_key, selector
        """
        try:
            # Generate RSA key pair (2048 bits)
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            public_key = private_key.public_key()
            
            # Serialize keys
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Extract public key for DNS record (remove headers and newlines)
            public_key_str = public_pem.decode('utf-8')
            public_key_str = public_key_str.replace('-----BEGIN PUBLIC KEY-----\n', '')
            public_key_str = public_key_str.replace('-----END PUBLIC KEY-----\n', '')
            public_key_str = public_key_str.replace('\n', '')
            
            # Generate selector (random string)
            selector = secrets.token_hex(8)
            
            return {
                'public_key': public_key_str,
                'private_key': private_pem.decode('utf-8'),
                'selector': selector,
                'dns_record': f"{selector}._domainkey"
            }
        except Exception as e:
            print(f"Error generating DKIM keys: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def verify_spf(self, domain: str) -> Dict:
        """
        Verify SPF record for domain
        
        Returns:
            Dictionary with is_valid, record, message
        """
        try:
            try:
                records = dns.resolver.resolve(domain, 'TXT', lifetime=10)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'No TXT records found for {domain}',
                    'status': 'not_found'
                }
            except dns.resolver.Timeout:
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'DNS lookup timeout for {domain}',
                    'status': 'timeout'
                }
            
            # Look for SPF record
            spf_record = None
            for record in records:
                txt_data = str(record).strip('"')
                if txt_data.startswith('v=spf1'):
                    spf_record = txt_data
                    break
            
            if not spf_record:
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'No SPF record found for {domain}',
                    'status': 'not_found',
                    'instructions': f'Add this TXT record to {domain}:\nv=spf1 include:_spf.google.com ~all'
                }
            
            # Basic SPF validation
            if 'include:' in spf_record or 'a' in spf_record or 'mx' in spf_record:
                return {
                    'is_valid': True,
                    'record': spf_record,
                    'message': 'SPF record is valid',
                    'status': 'valid'
                }
            else:
                return {
                    'is_valid': False,
                    'record': spf_record,
                    'message': 'SPF record exists but may be incomplete',
                    'status': 'incomplete'
                }
                
        except Exception as e:
            print(f"Error verifying SPF: {e}")
            return {
                'is_valid': False,
                'record': None,
                'message': f'Error verifying SPF: {str(e)}',
                'status': 'error'
            }
    
    def verify_dkim(self, domain: str, selector: str) -> Dict:
        """
        Verify DKIM record for domain
        
        Args:
            domain: Domain name
            selector: DKIM selector
            
        Returns:
            Dictionary with is_valid, record, message
        """
        try:
            dkim_domain = f"{selector}._domainkey.{domain}"
            
            try:
                records = dns.resolver.resolve(dkim_domain, 'TXT', lifetime=10)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'No DKIM record found at {dkim_domain}',
                    'status': 'not_found',
                    'dns_name': dkim_domain
                }
            except dns.resolver.Timeout:
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'DNS lookup timeout for {dkim_domain}',
                    'status': 'timeout',
                    'dns_name': dkim_domain
                }
            
            # Get DKIM record
            dkim_record = None
            for record in records:
                txt_data = str(record).strip('"')
                if 'v=DKIM1' in txt_data or 'k=rsa' in txt_data:
                    dkim_record = txt_data
                    break
            
            if not dkim_record:
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'DKIM record found but invalid format',
                    'status': 'invalid',
                    'dns_name': dkim_domain
                }
            
            # Validate DKIM record format
            if 'v=DKIM1' in dkim_record and 'k=rsa' in dkim_record and 'p=' in dkim_record:
                return {
                    'is_valid': True,
                    'record': dkim_record,
                    'message': 'DKIM record is valid',
                    'status': 'valid',
                    'dns_name': dkim_domain
                }
            else:
                return {
                    'is_valid': False,
                    'record': dkim_record,
                    'message': 'DKIM record format is invalid',
                    'status': 'invalid',
                    'dns_name': dkim_domain
                }
                
        except Exception as e:
            print(f"Error verifying DKIM: {e}")
            return {
                'is_valid': False,
                'record': None,
                'message': f'Error verifying DKIM: {str(e)}',
                'status': 'error'
            }
    
    def verify_dmarc(self, domain: str) -> Dict:
        """
        Verify DMARC record for domain
        
        Returns:
            Dictionary with is_valid, record, message
        """
        try:
            dmarc_domain = f"_dmarc.{domain}"
            
            try:
                records = dns.resolver.resolve(dmarc_domain, 'TXT', lifetime=10)
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'No DMARC record found at {dmarc_domain}',
                    'status': 'not_found',
                    'dns_name': dmarc_domain
                }
            except dns.resolver.Timeout:
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'DNS lookup timeout for {dmarc_domain}',
                    'status': 'timeout',
                    'dns_name': dmarc_domain
                }
            
            # Get DMARC record
            dmarc_record = None
            for record in records:
                txt_data = str(record).strip('"')
                if txt_data.startswith('v=DMARC1'):
                    dmarc_record = txt_data
                    break
            
            if not dmarc_record:
                return {
                    'is_valid': False,
                    'record': None,
                    'message': f'DMARC record found but invalid format',
                    'status': 'invalid',
                    'dns_name': dmarc_domain
                }
            
            # Validate DMARC record
            if 'v=DMARC1' in dmarc_record:
                # Check for policy
                policy = 'none'
                if 'p=quarantine' in dmarc_record:
                    policy = 'quarantine'
                elif 'p=reject' in dmarc_record:
                    policy = 'reject'
                
                return {
                    'is_valid': True,
                    'record': dmarc_record,
                    'message': f'DMARC record is valid (policy: {policy})',
                    'status': 'valid',
                    'policy': policy,
                    'dns_name': dmarc_domain
                }
            else:
                return {
                    'is_valid': False,
                    'record': dmarc_record,
                    'message': 'DMARC record format is invalid',
                    'status': 'invalid',
                    'dns_name': dmarc_domain
                }
                
        except Exception as e:
            print(f"Error verifying DMARC: {e}")
            return {
                'is_valid': False,
                'record': None,
                'message': f'Error verifying DMARC: {str(e)}',
                'status': 'error'
            }
    
    def verify_all_records(self, domain: str, dkim_selector: str = None) -> Dict:
        """
        Verify all DNS records (SPF, DKIM, DMARC) for a domain
        
        Args:
            domain: Domain name
            dkim_selector: Optional DKIM selector (if None, will try to get from database)
            
        Returns:
            Dictionary with verification results for all records
        """
        results = {
            'domain': domain,
            'spf': self.verify_spf(domain),
            'dmarc': self.verify_dmarc(domain)
        }
        
        # Get DKIM selector from database if not provided
        if not dkim_selector:
            try:
                conn = self.db.connect()
                cursor = conn.cursor()
                
                if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                    result = self.db.supabase.client.table('domains').select(
                        'dkim_selector'
                    ).eq('domain', domain).execute()
                    
                    if result.data and len(result.data) > 0:
                        dkim_selector = result.data[0].get('dkim_selector')
                else:
                    cursor.execute("SELECT dkim_selector FROM domains WHERE domain = ?", (domain,))
                    row = cursor.fetchone()
                    if row:
                        dkim_selector = row[0]
            except Exception as e:
                print(f"Error getting DKIM selector: {e}")
        
        if dkim_selector:
            results['dkim'] = self.verify_dkim(domain, dkim_selector)
        else:
            results['dkim'] = {
                'is_valid': False,
                'message': 'DKIM selector not found. Please generate DKIM keys first.',
                'status': 'not_configured'
            }
        
        # Overall status
        all_valid = (
            results['spf'].get('is_valid', False) and
            results['dkim'].get('is_valid', False) and
            results['dmarc'].get('is_valid', False)
        )
        
        results['all_valid'] = all_valid
        results['verified_at'] = datetime.now().isoformat()
        
        return results
    
    def get_dns_setup_instructions(self, domain: str, dkim_public_key: str, dkim_selector: str) -> Dict:
        """
        Get DNS setup instructions for a domain
        
        Args:
            domain: Domain name
            dkim_public_key: DKIM public key
            dkim_selector: DKIM selector
            
        Returns:
            Dictionary with DNS setup instructions
        """
        instructions = {
            'domain': domain,
            'records': []
        }
        
        # SPF record
        instructions['records'].append({
            'type': 'TXT',
            'name': '@',
            'value': 'v=spf1 include:_spf.google.com ~all',
            'description': 'SPF record to authorize email sending'
        })
        
        # DKIM record
        dkim_value = f"v=DKIM1; k=rsa; p={dkim_public_key}"
        instructions['records'].append({
            'type': 'TXT',
            'name': f'{dkim_selector}._domainkey',
            'value': dkim_value,
            'description': 'DKIM record for email authentication'
        })
        
        # DMARC record
        instructions['records'].append({
            'type': 'TXT',
            'name': '_dmarc',
            'value': 'v=DMARC1; p=none; rua=mailto:dmarc@' + domain,
            'description': 'DMARC record for email policy'
        })
        
        return instructions
