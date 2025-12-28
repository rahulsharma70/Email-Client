"""
Billing Module for ANAGHA SOLUTION
Stripe integration for subscriptions and usage-based billing
"""

import stripe
from typing import Dict, Optional
from database.db_manager import DatabaseManager
from core.config import Config
import os

class BillingManager:
    """Manages billing and subscriptions via Stripe"""
    
    # Subscription plans
    PLANS = {
        'free': {
            'name': 'Free',
            'price': 0,
            'emails_per_month': 100,
            'features': ['Basic email sending', 'Lead scraping (limited)']
        },
        'start': {
            'name': 'Start',
            'price': 29,
            'stripe_price_id': os.getenv('STRIPE_START_PRICE_ID', ''),
            'emails_per_month': 1000,
            'features': ['1,000 emails/month', 'Lead scraping', 'Email verification']
        },
        'growth': {
            'name': 'Growth',
            'price': 79,
            'stripe_price_id': os.getenv('STRIPE_GROWTH_PRICE_ID', ''),
            'emails_per_month': 5000,
            'features': ['5,000 emails/month', 'Advanced lead scraping', 'AI personalization']
        },
        'pro': {
            'name': 'Pro',
            'price': 149,
            'stripe_price_id': os.getenv('STRIPE_PRO_PRICE_ID', ''),
            'emails_per_month': 20000,
            'features': ['20,000 emails/month', 'Priority support', 'Custom integrations']
        },
        'agency': {
            'name': 'Agency',
            'price': 399,
            'stripe_price_id': os.getenv('STRIPE_AGENCY_PRICE_ID', ''),
            'emails_per_month': 100000,
            'features': ['100,000 emails/month', 'White-label', 'Dedicated support']
        }
    }
    
    # Usage-based add-ons
    ADDONS = {
        'email_validation': {'price': 0.01, 'unit': 'per verification'},
        'lead_enrichment': {'price': 0.05, 'unit': 'per lead'},
        'ai_personalization': {'price': 0.02, 'unit': 'per email'},
        'website_scraping': {'price': 0.10, 'unit': 'per scrape'}
    }
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
    
    def create_customer(self, user_id: int, email: str, name: str = '') -> Dict:
        """Create Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'user_id': user_id}
            )
            
            # Save customer ID to database
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET stripe_customer_id = ?
                WHERE id = ?
            """, (customer.id, user_id))
            conn.commit()
            
            return {'success': True, 'customer_id': customer.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def create_subscription(self, user_id: int, plan_id: str, payment_method_id: str = None) -> Dict:
        """Create or update subscription"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT stripe_customer_id, email FROM users WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return {'success': False, 'error': 'User not found'}
            
            customer_id = row[0]
            email = row[1]
            
            # Create customer if doesn't exist
            if not customer_id:
                result = self.create_customer(user_id, email)
                if not result.get('success'):
                    return result
                customer_id = result['customer_id']
            
            plan = self.PLANS.get(plan_id)
            if not plan or not plan.get('stripe_price_id'):
                return {'success': False, 'error': 'Invalid plan'}
            
            # Create subscription
            subscription_data = {
                'customer': customer_id,
                'items': [{'price': plan['stripe_price_id']}],
                'payment_behavior': 'default_incomplete',
                'payment_settings': {'save_default_payment_method': 'on_subscription'},
                'expand': ['latest_invoice.payment_intent'],
            }
            
            if payment_method_id:
                subscription_data['default_payment_method'] = payment_method_id
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            # Save subscription ID
            cursor.execute("""
                UPDATE users 
                SET stripe_subscription_id = ?,
                    subscription_plan = ?,
                    subscription_status = ?
                WHERE id = ?
            """, (subscription.id, plan_id, subscription.status, user_id))
            conn.commit()
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'client_secret': subscription.latest_invoice.payment_intent.client_secret if subscription.latest_invoice.payment_intent else None
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def cancel_subscription(self, user_id: int) -> Dict:
        """Cancel subscription"""
        try:
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT stripe_subscription_id FROM users WHERE id = ?
            """, (user_id,))
            row = cursor.fetchone()
            
            if not row or not row[0]:
                return {'success': False, 'error': 'No active subscription'}
            
            subscription = stripe.Subscription.modify(
                row[0],
                cancel_at_period_end=True
            )
            
            cursor.execute("""
                UPDATE users 
                SET subscription_status = 'canceled'
                WHERE id = ?
            """, (user_id,))
            conn.commit()
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def record_usage(self, user_id: int, addon_type: str, quantity: int = 1) -> Dict:
        """Record usage for billing"""
        try:
            addon = self.ADDONS.get(addon_type)
            if not addon:
                return {'success': False, 'error': 'Invalid addon type'}
            
            # In production, create Stripe usage record
            # For now, just log it
            amount = addon['price'] * quantity
            
            # Store usage in database for invoicing
            conn = self.db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    addon_type TEXT,
                    quantity INTEGER,
                    amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            cursor.execute("""
                INSERT INTO usage_records (user_id, addon_type, quantity, amount)
                VALUES (?, ?, ?, ?)
            """, (user_id, addon_type, quantity, amount))
            conn.commit()
            
            return {'success': True, 'amount': amount}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_subscription_info(self, user_id: int) -> Dict:
        """Get subscription information"""
        conn = self.db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subscription_plan, subscription_status, stripe_customer_id, stripe_subscription_id
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        
        if not row:
            return {'error': 'User not found'}
        
        plan_id = row[0] or 'free'
        plan = self.PLANS.get(plan_id, self.PLANS['free'])
        
        return {
            'plan': plan_id,
            'plan_name': plan['name'],
            'status': row[1] or 'active',
            'features': plan.get('features', []),
            'emails_per_month': plan.get('emails_per_month', 0)
        }

    def create_checkout_session(self, user_id: int, plan_id: str, success_url: str, cancel_url: str) -> Dict:
        """
        Create Stripe Checkout Session for subscription
        
        Args:
            user_id: User ID
            plan_id: Plan identifier (start, growth, pro, agency)
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if user cancels
            
        Returns:
            Dictionary with checkout session URL or error
        """
        try:
            # Get user info
            conn = self.db.connect()
            cursor = conn.cursor()
            
            if hasattr(self.db, 'use_supabase') and self.db.use_supabase:
                result = self.db.supabase.client.table('users').select(
                    'id, email, first_name, last_name, stripe_customer_id'
                ).eq('id', user_id).execute()
                
                if not result.data or len(result.data) == 0:
                    return {'success': False, 'error': 'User not found'}
                
                user = result.data[0]
                email = user['email']
                customer_id = user.get('stripe_customer_id')
            else:
                cursor.execute("""
                    SELECT email, first_name, last_name, stripe_customer_id
                    FROM users WHERE id = ?
                """, (user_id,))
                row = cursor.fetchone()
                
                if not row:
                    return {'success': False, 'error': 'User not found'}
                
                email = row[0]
                customer_id = row[3]
            
            # Get plan
            plan = self.PLANS.get(plan_id)
            if not plan:
                return {'success': False, 'error': 'Invalid plan'}
            
            stripe_price_id = plan.get('stripe_price_id')
            if not stripe_price_id:
                return {'success': False, 'error': 'Plan not configured with Stripe price ID'}
            
            # Create or get Stripe customer
            if not customer_id:
                result = self.create_customer(user_id, email)
                if not result.get('success'):
                    return result
                customer_id = result['customer_id']
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user_id),
                    'plan_id': plan_id
                },
                subscription_data={
                    'metadata': {
                        'user_id': str(user_id),
                        'plan_id': plan_id
                    }
                },
                allow_promotion_codes=True,
            )
            
            return {
                'success': True,
                'checkout_url': checkout_session.url,
                'session_id': checkout_session.id
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

