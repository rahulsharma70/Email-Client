"""
ANAGHA SOLUTION - Web Application
Flask-based web interface for bulk email software
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_cors import CORS
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from database.db_manager import DatabaseManager
from core.email_sender import EmailSender
from core.auth import AuthManager
from core.middleware import require_auth, optional_auth, get_current_user, set_auth_manager
from core.rate_limiter import RateLimiter
from core.warmup import WarmupManager
from core.billing import BillingManager
from core.warmup_manager import WarmupManager
from core.observability import ObservabilityManager
from database.migrations import MigrationManager
import pandas as pd
from datetime import datetime
import json

# Get paths relative to backend directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_root, 'frontend')

app = Flask(__name__, 
            template_folder=os.path.join(frontend_dir, 'templates'),
            static_folder=os.path.join(frontend_dir, 'static'))
app.secret_key = 'anagha_solution_secret_key_2024'
CORS(app, resources={r"/*": {"origins": "*"}})

# Disable strict slashes to avoid 403 errors
app.url_map.strict_slashes = False

# Add error handlers
@app.errorhandler(403)
def forbidden(error):
    return jsonify({'error': 'Access forbidden. Please check server configuration.'}), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Page not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Initialize database - check if Supabase is configured
database_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
if database_type == 'supabase':
    try:
        from database.supabase_manager import SupabaseDatabaseManager
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        if supabase_url and supabase_key:
            print("Initializing Supabase database...")
            db = SupabaseDatabaseManager(supabase_url, supabase_key)
            print("✓ Using Supabase database")
            # Ensure tables are created
            db.initialize_database()
        else:
            print("⚠️  Supabase URL/Key not found, falling back to SQLite")
            db = DatabaseManager()
            db.initialize_database()
    except Exception as e:
        import traceback
        print(f"⚠️  Error initializing Supabase: {e}")
        traceback.print_exc()
        print("Falling back to SQLite...")
        db = DatabaseManager()
        db.initialize_database()
else:
    print("Initializing SQLite database...")
    db = DatabaseManager()
    db.initialize_database()
    print("✓ SQLite database initialized")

# Initialize managers
from database.settings_manager import SettingsManager
from database.migrations import MigrationManager
from core.warmup_manager import WarmupManager as EnhancedWarmupManager
from core.observability import ObservabilityManager

settings_manager = SettingsManager(db)
auth_manager = AuthManager(db)
# Set auth manager in middleware so it uses the same instance
set_auth_manager(auth_manager)
rate_limiter = RateLimiter(db)
warmup_manager = WarmupManager(db)  # Keep old one for compatibility
enhanced_warmup_manager = EnhancedWarmupManager(db)
billing_manager = BillingManager(db)
observability_manager = ObservabilityManager(db)

# Run migrations and create indexes
migration_manager = MigrationManager(db)
migration_manager.migrate_schema()
migration_manager.create_indexes()
print("✓ Database migrations and indexes created")

# Global email sender instance
email_sender = None

# Authentication Routes
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """Register new user"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        company_name = data.get('company_name', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_manager.register_user(email, password, first_name, last_name, company_name)
        
        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Login user"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        result = auth_manager.login_user(email, password)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'token': result['token'],
                'user': {
                    'id': result['user_id'],
                    'email': result['email'],
                    'first_name': result.get('first_name', ''),
                    'last_name': result.get('last_name', '')
                }
            })
        else:
            # Check if it's an email verification error
            if result.get('email_verified') == False:
                return jsonify({
                    'error': result.get('error', 'Email not verified'),
                    'email_verified': False,
                    'message': 'Please verify your email before logging in.',
                    'email': email  # Include email for resend functionality
                }), 403
            return jsonify({'error': result.get('error', 'Login failed')}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/me', methods=['GET'])
@optional_auth
def api_get_current_user(user_id):
    """Get current user info - validates token"""
    try:
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        user = auth_manager.get_user(user_id)
        if user:
            # Don't return sensitive info
            user.pop('password_hash', None)
            
            # Add onboarding status
            from core.onboarding import OnboardingManager
            onboarding_mgr = OnboardingManager(db)
            onboarding_status = onboarding_mgr.get_onboarding_status(user_id)
            user['onboarding'] = onboarding_status
            
            return jsonify({'success': True, 'user': user})
        else:
            return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        import traceback
        print(f"Error in /api/auth/me: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/change-password', methods=['POST'])
@require_auth
def api_change_password(user_id):
    """Change user password"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return jsonify({'error': 'Old and new passwords are required'}), 400
        
        result = auth_manager.change_password(user_id, old_password, new_password)
        return jsonify(result) if result.get('success') else jsonify(result), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/verify-email', methods=['GET', 'POST'])
def api_verify_email():
    """Verify email using token"""
    try:
        from core.email_verification import EmailVerificationManager
        
        email_verification = EmailVerificationManager(db)
        
        if request.method == 'GET':
            # GET request - show verification page
            token = request.args.get('token', '')
            if not token:
                return render_template('verify_email.html', 
                                     success=False, 
                                     error='No verification token provided')
            
            result = email_verification.verify_email_token(token)
            
            if result.get('success'):
                return render_template('verify_email.html', 
                                     success=True, 
                                     message='Email verified successfully! You can now log in.')
            else:
                return render_template('verify_email.html', 
                                     success=False, 
                                     error=result.get('error', 'Verification failed'))
        else:
            # POST request - API endpoint
            data = request.json if request.is_json else request.form.to_dict()
            token = data.get('token', '')
            
            if not token:
                return jsonify({'success': False, 'error': 'Token is required'}), 400
            
            result = email_verification.verify_email_token(token)
            
            if result.get('success'):
                return jsonify({
                    'success': True,
                    'message': 'Email verified successfully',
                    'user_id': result.get('user_id')
                })
            else:
                return jsonify(result), 400
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/resend-verification', methods=['POST'])
def api_resend_verification():
    """Resend verification email"""
    try:
        from core.email_verification import EmailVerificationManager
        
        data = request.json if request.is_json else request.form.to_dict()
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        email_verification = EmailVerificationManager(db)
        result = email_verification.resend_verification_email(email)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Verification email sent. Please check your inbox.'
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/verify-email')
def verify_email_page():
    """Email verification page"""
    token = request.args.get('token', '')
    return render_template('verify_email.html', token=token)

# Billing & Stripe Routes
@app.route('/api/billing/create-checkout-session', methods=['POST'])
@require_auth
def api_create_checkout_session(user_id):
    """Create Stripe Checkout Session"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        plan_id = data.get('plan_id', '').strip()
        
        if not plan_id:
            return jsonify({'success': False, 'error': 'Plan ID is required'}), 400
        
        # Validate plan
        if plan_id not in billing_manager.PLANS:
            return jsonify({'success': False, 'error': 'Invalid plan'}), 400
        
        # Get app URL for redirects
        from core.config import Config
        app_url = Config.get('APP_URL', request.host_url.rstrip('/'))
        success_url = f"{app_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{app_url}/checkout/cancel"
        
        result = billing_manager.create_checkout_session(user_id, plan_id, success_url, cancel_url)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'checkout_url': result['checkout_url'],
                'session_id': result['session_id']
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/checkout/success')
def checkout_success():
    """Stripe checkout success page"""
    session_id = request.args.get('session_id', '')
    return render_template('checkout_success.html', session_id=session_id)

@app.route('/checkout/cancel')
def checkout_cancel():
    """Stripe checkout cancel page"""
    return render_template('checkout_cancel.html')

@app.route('/api/webhooks/stripe', methods=['POST'])
def api_stripe_webhook():
    """
    Stripe webhook handler
    Verifies webhook signature and handles events
    """
    import stripe
    from core.config import Config
    
    # Ensure Stripe is initialized
    if not stripe.api_key:
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
    
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        print("⚠️ STRIPE_WEBHOOK_SECRET not configured")
        return jsonify({'error': 'Webhook secret not configured'}), 500
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        print(f"⚠️ Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        print(f"⚠️ Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    event_type = event['type']
    event_data = event['data']['object']
    
    print(f"📥 Stripe webhook received: {event_type}")
    
    try:
        if event_type == 'checkout.session.completed':
            handle_checkout_session_completed(event_data)
        elif event_type == 'customer.subscription.created':
            handle_subscription_created(event_data)
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(event_data)
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(event_data)
        elif event_type == 'invoice.payment_succeeded':
            handle_invoice_payment_succeeded(event_data)
        elif event_type == 'invoice.payment_failed':
            handle_invoice_payment_failed(event_data)
        else:
            print(f"ℹ️ Unhandled event type: {event_type}")
        
        return jsonify({'success': True})
    except Exception as e:
        import traceback
        print(f"❌ Error handling webhook event {event_type}: {e}")
        traceback.print_exc()
        # Return 200 to prevent Stripe from retrying (we'll handle retries manually)
        return jsonify({'error': str(e)}), 200

def handle_checkout_session_completed(session):
    """Handle checkout.session.completed event"""
    try:
        user_id = int(session['metadata'].get('user_id', 0))
        plan_id = session['metadata'].get('plan_id', '')
        
        if not user_id or not plan_id:
            print(f"⚠️ Missing metadata in checkout session: {session.get('id')}")
            return
        
        print(f"✅ Checkout completed for user {user_id}, plan {plan_id}")
        
        # Update user subscription
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            db.supabase.client.table('users').update({
                'subscription_plan': plan_id,
                'subscription_status': 'active',
                'stripe_subscription_id': session.get('subscription')
            }).eq('id', user_id).execute()
        else:
            cursor.execute("""
                UPDATE users
                SET subscription_plan = ?,
                    subscription_status = 'active',
                    stripe_subscription_id = ?
                WHERE id = ?
            """, (plan_id, session.get('subscription'), user_id))
            conn.commit()
        
        # Activate account
        activate_account_after_payment(user_id, plan_id)
        
    except Exception as e:
        import traceback
        print(f"❌ Error in handle_checkout_session_completed: {e}")
        traceback.print_exc()
        raise

def handle_subscription_created(subscription):
    """Handle customer.subscription.created event"""
    try:
        customer_id = subscription['customer']
        plan_id = subscription['metadata'].get('plan_id', '')
        user_id = subscription['metadata'].get('user_id', '')
        
        if not user_id:
            # Try to get user_id from customer metadata
            import stripe
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get('user_id', '')
        
        if not user_id:
            print(f"⚠️ Could not find user_id for subscription: {subscription.get('id')}")
            return
        
        user_id = int(user_id)
        
        print(f"✅ Subscription created for user {user_id}, plan {plan_id}")
        
        # Update user subscription
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            db.supabase.client.table('users').update({
                'subscription_plan': plan_id,
                'subscription_status': subscription['status'],
                'stripe_subscription_id': subscription['id']
            }).eq('id', user_id).execute()
        else:
            cursor.execute("""
                UPDATE users
                SET subscription_plan = ?,
                    subscription_status = ?,
                    stripe_subscription_id = ?
                WHERE id = ?
            """, (plan_id, subscription['status'], subscription['id'], user_id))
            conn.commit()
        
        # Activate account if status is active
        if subscription['status'] == 'active':
            activate_account_after_payment(user_id, plan_id)
        
    except Exception as e:
        import traceback
        print(f"❌ Error in handle_subscription_created: {e}")
        traceback.print_exc()
        raise

def handle_subscription_updated(subscription):
    """Handle customer.subscription.updated event"""
    try:
        customer_id = subscription['customer']
        plan_id = subscription['metadata'].get('plan_id', '')
        user_id = subscription['metadata'].get('user_id', '')
        
        if not user_id:
            import stripe
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get('user_id', '')
        
        if not user_id:
            # Try to find by subscription_id
            conn = db.connect()
            cursor = conn.cursor()
            
            if hasattr(db, 'use_supabase') and db.use_supabase:
                result = db.supabase.client.table('users').select('id').eq('stripe_subscription_id', subscription['id']).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]['id']
            else:
                cursor.execute("SELECT id FROM users WHERE stripe_subscription_id = ?", (subscription['id'],))
                row = cursor.fetchone()
                if row:
                    user_id = row[0]
        
        if not user_id:
            print(f"⚠️ Could not find user_id for subscription: {subscription.get('id')}")
            return
        
        user_id = int(user_id)
        
        # Get plan from subscription items if not in metadata
        if not plan_id:
            items = subscription.get('items', {}).get('data', [])
            if items and len(items) > 0:
                price_id = items[0].get('price', {}).get('id', '')
                # Map price_id to plan_id (you may need to adjust this)
                for p_id, plan in billing_manager.PLANS.items():
                    if plan.get('stripe_price_id') == price_id:
                        plan_id = p_id
                        break
        
        print(f"✅ Subscription updated for user {user_id}, status: {subscription['status']}")
        
        # Update user subscription
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            update_data = {
                'subscription_status': subscription['status']
            }
            if plan_id:
                update_data['subscription_plan'] = plan_id
            
            db.supabase.client.table('users').update(update_data).eq('id', user_id).execute()
        else:
            if plan_id:
                cursor.execute("""
                    UPDATE users
                    SET subscription_plan = ?,
                        subscription_status = ?
                    WHERE id = ?
                """, (plan_id, subscription['status'], user_id))
            else:
                cursor.execute("""
                    UPDATE users
                    SET subscription_status = ?
                    WHERE id = ?
                """, (subscription['status'], user_id))
            conn.commit()
        
        # Handle status changes
        if subscription['status'] == 'active':
            # Ensure account is activated
            activate_account_after_payment(user_id, plan_id or 'free')
        elif subscription['status'] in ['canceled', 'unpaid', 'past_due']:
            # Deactivate or downgrade
            deactivate_account(user_id)
        
    except Exception as e:
        import traceback
        print(f"❌ Error in handle_subscription_updated: {e}")
        traceback.print_exc()
        raise

def handle_subscription_deleted(subscription):
    """Handle customer.subscription.deleted event"""
    try:
        customer_id = subscription['customer']
        user_id = subscription['metadata'].get('user_id', '')
        
        if not user_id:
            import stripe
            customer = stripe.Customer.retrieve(customer_id)
            user_id = customer.metadata.get('user_id', '')
        
        if not user_id:
            # Find by subscription_id
            conn = db.connect()
            cursor = conn.cursor()
            
            if hasattr(db, 'use_supabase') and db.use_supabase:
                result = db.supabase.client.table('users').select('id').eq('stripe_subscription_id', subscription['id']).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]['id']
            else:
                cursor.execute("SELECT id FROM users WHERE stripe_subscription_id = ?", (subscription['id'],))
                row = cursor.fetchone()
                if row:
                    user_id = row[0]
        
        if not user_id:
            print(f"⚠️ Could not find user_id for deleted subscription: {subscription.get('id')}")
            return
        
        user_id = int(user_id)
        
        print(f"✅ Subscription deleted for user {user_id}")
        
        # Deactivate account
        deactivate_account(user_id)
        
    except Exception as e:
        import traceback
        print(f"❌ Error in handle_subscription_deleted: {e}")
        traceback.print_exc()
        raise

def handle_invoice_payment_succeeded(invoice):
    """Handle invoice.payment_succeeded event"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        # Find user by subscription_id
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('users').select('id').eq('stripe_subscription_id', subscription_id).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]['id']
            else:
                return
        else:
            cursor.execute("SELECT id FROM users WHERE stripe_subscription_id = ?", (subscription_id,))
            row = cursor.fetchone()
            if not row:
                return
            user_id = row[0]
        
        print(f"✅ Invoice payment succeeded for user {user_id}")
        
        # Ensure subscription is active
        if hasattr(db, 'use_supabase') and db.use_supabase:
            db.supabase.client.table('users').update({
                'subscription_status': 'active'
            }).eq('id', user_id).execute()
        else:
            cursor.execute("""
                UPDATE users
                SET subscription_status = 'active'
                WHERE id = ?
            """, (user_id,))
            conn.commit()
        
    except Exception as e:
        import traceback
        print(f"❌ Error in handle_invoice_payment_succeeded: {e}")
        traceback.print_exc()
        raise

def handle_invoice_payment_failed(invoice):
    """Handle invoice.payment_failed event"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        # Find user by subscription_id
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('users').select('id').eq('stripe_subscription_id', subscription_id).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]['id']
            else:
                return
        else:
            cursor.execute("SELECT id FROM users WHERE stripe_subscription_id = ?", (subscription_id,))
            row = cursor.fetchone()
            if not row:
                return
            user_id = row[0]
        
        print(f"⚠️ Invoice payment failed for user {user_id}")
        
        # Update subscription status
        if hasattr(db, 'use_supabase') and db.use_supabase:
            db.supabase.client.table('users').update({
                'subscription_status': 'past_due'
            }).eq('id', user_id).execute()
        else:
            cursor.execute("""
                UPDATE users
                SET subscription_status = 'past_due'
                WHERE id = ?
            """, (user_id,))
            conn.commit()
        
        # TODO: Send notification email to user
        
    except Exception as e:
        import traceback
        print(f"❌ Error in handle_invoice_payment_failed: {e}")
        traceback.print_exc()
        raise

def activate_account_after_payment(user_id, plan_id):
    """
    Activate account after successful payment
    Creates tenant, assigns plan, records quotas, enables dashboard access
    """
    try:
        from core.quota_manager import QuotaManager
        from core.email_verification import EmailVerificationManager
        import secrets
        
        quota_manager = QuotaManager(db)
        email_verification = EmailVerificationManager(db)
        
        print(f"🔧 Activating account for user {user_id}, plan {plan_id}")
        
        # Get user info
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('users').select(
                'id, email, first_name, last_name'
            ).eq('id', user_id).execute()
            
            if not result.data or len(result.data) == 0:
                print(f"⚠️ User {user_id} not found")
                return
            
            user = result.data[0]
            email = user['email']
        else:
            cursor.execute("SELECT email, first_name, last_name FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                print(f"⚠️ User {user_id} not found")
                return
            email = row[0]
        
        # Generate one-time password
        one_time_password = secrets.token_urlsafe(12)
        
        # Initialize usage counters
        usage_counters = [
            ('emails_sent_this_month', 0),
            ('leads_scraped_this_month', 0),
            ('llm_tokens_used_this_month', 0),
            ('campaigns_created_this_month', 0),
        ]
        
        # Get plan limits
        plan_limits = quota_manager.PLAN_LIMITS.get(plan_id, quota_manager.PLAN_LIMITS['start'])
        
        # Update user account
        if hasattr(db, 'use_supabase') and db.use_supabase:
            db.supabase.client.table('users').update({
                'is_active': 1,
                'subscription_plan': plan_id,
                'subscription_status': 'active',
                'one_time_password': one_time_password
            }).eq('id', user_id).execute()
        else:
            cursor.execute("""
                UPDATE users
                SET is_active = 1,
                    subscription_plan = ?,
                    subscription_status = 'active',
                    one_time_password = ?,
                    account_activated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (plan_id, one_time_password, user_id))
            conn.commit()
        
        # Create usage counter records
        for counter_type, initial_value in usage_counters:
            try:
                if hasattr(db, 'use_supabase') and db.use_supabase:
                    # Check if counter exists
                    result = db.supabase.client.table('usage_counters').select('id').eq('user_id', user_id).eq('counter_type', counter_type).execute()
                    if not result.data or len(result.data) == 0:
                        db.supabase.client.table('usage_counters').insert({
                            'user_id': user_id,
                            'counter_type': counter_type,
                            'current_value': initial_value,
                            'reset_date': datetime.now().date().isoformat()
                        }).execute()
                else:
                    cursor.execute("""
                        INSERT OR IGNORE INTO usage_counters (user_id, counter_type, current_value, reset_date)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, counter_type, initial_value, datetime.now().date()))
                    conn.commit()
            except Exception as e:
                print(f"⚠️ Error creating usage counter {counter_type}: {e}")
        
        print(f"✅ Account activated for user {user_id}")
        
        # TODO: Send access email with credentials
        # email_verification.send_access_email(email, one_time_password, user_id)
        
    except Exception as e:
        import traceback
        print(f"❌ Error in activate_account_after_payment: {e}")
        traceback.print_exc()
        raise

def deactivate_account(user_id):
    """Deactivate account and downgrade to free plan"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            db.supabase.client.table('users').update({
                'subscription_plan': 'free',
                'subscription_status': 'canceled'
            }).eq('id', user_id).execute()
        else:
            cursor.execute("""
                UPDATE users
                SET subscription_plan = 'free',
                    subscription_status = 'canceled'
                WHERE id = ?
            """, (user_id,))
            conn.commit()
        
        print(f"✅ Account deactivated for user {user_id}")
        
    except Exception as e:
        import traceback
        print(f"❌ Error in deactivate_account: {e}")
        traceback.print_exc()
        raise

@app.route('/')
@optional_auth
def index(user_id):
    """Dashboard page - redirects to onboarding if needed"""
    try:
        if user_id:
            from core.onboarding import OnboardingManager
            onboarding_mgr = OnboardingManager(db)
            
            if onboarding_mgr.should_show_onboarding(user_id):
                return redirect('/onboarding')
        
        return render_template('dashboard.html')
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'ANAGHA SOLUTION Web Server is running'})

@app.route('/campaign-builder')
def campaign_builder():
    """Campaign builder page"""
    templates = db.get_templates()
    return render_template('campaign_builder.html', templates=templates)

@app.route('/recipients')
def recipients():
    """Recipients management page"""
    recipients_list = db.get_recipients()
    # Make sure recipients are not deleted - this was the bug
    return render_template('recipients.html', recipients=recipients_list)

@app.route('/leads')
def leads():
    """Leads management page"""
    return render_template('leads.html')

@app.route('/smtp-config')
def smtp_config():
    """SMTP configuration page"""
    servers = db.get_smtp_servers(active_only=False)
    return render_template('smtp_config.html', servers=servers)

@app.route('/templates')
def templates():
    """Template library page"""
    templates_list = db.get_templates()
    return render_template('templates.html', templates=templates_list)

@app.route('/analytics')
def analytics():
    """Analytics page"""
    campaigns = db.get_campaigns()
    return render_template('analytics.html', campaigns=campaigns)

@app.route('/sent-items')
def sent_items_page():
    """Sent Items page"""
    return render_template('sent_items.html')

@app.route('/inbox')
def inbox():
    """Inbox page for viewing incoming emails"""
    return render_template('inbox.html')

@app.route('/login')
def login_page():
    """Login page"""
    return render_template('login.html')

@app.route('/register')
def register_page():
    """Register page"""
    return render_template('register.html')

@app.route('/terms')
def terms_page():
    """Terms of Service page"""
    return render_template('terms.html')

@app.route('/privacy')
def privacy_page():
    """Privacy Policy page"""
    return render_template('privacy.html')

@app.route('/gdpr')
def gdpr_page():
    """GDPR Compliance page"""
    return render_template('gdpr.html')

# Inbox API Routes
import imaplib
import email
from email.header import decode_header

@app.route('/api/inbox/fetch/<int:account_id>')
def api_fetch_inbox(account_id):
    """Fetch emails from IMAP server - optimized to fetch only headers first"""
    try:
        folder = request.args.get('folder', 'INBOX')
        limit = request.args.get('limit', 100, type=int)  # Increased limit to fetch more emails
        
        # Get SMTP/IMAP config for this account
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        # Get IMAP settings - try imap_host first, then construct from smtp host
        imap_host = account.get('imap_host')
        if not imap_host:
            # Try to construct IMAP host from SMTP host
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        password = account.get('password', '')
        
        # Decrypt password if encrypted
        if password:
            try:
                from core.encryption import get_encryption_manager
                encryptor = get_encryption_manager()
                password = encryptor.decrypt(password)
            except:
                # If decryption fails, might be plaintext from old data
                pass
        
        if not imap_host or not username or not password:
            return jsonify({'error': 'IMAP settings not configured for this account'}), 400
        
        # Connect to IMAP server
        try:
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass
            
            imap.login(username, password)
        except Exception as conn_error:
            return jsonify({'error': f'Failed to connect to IMAP server: {str(conn_error)}'}), 500
        
        # Try to select the folder (handle different naming conventions)
        folder_variants = [folder]
        if folder == 'INBOX':
            folder_variants = ['INBOX']
        elif folder == 'Sent':
            folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent', '"Sent"', '"Sent Items"']
        elif folder == 'Drafts':
            folder_variants = ['Drafts', 'Draft', 'INBOX.Drafts']
        elif folder == 'Trash':
            folder_variants = ['Trash', 'Deleted', 'Deleted Items', 'INBOX.Trash']
        elif folder == 'Spam':
            folder_variants = ['Spam', 'Junk', 'Junk E-mail', 'INBOX.Spam', 'INBOX.Junk']
        
        selected = False
        for f in folder_variants:
            try:
                status, _ = imap.select(f, readonly=True)
                if status == 'OK':
                    selected = True
                    break
            except:
                continue
        
        if not selected:
            imap.logout()
            return jsonify({'error': f'Could not access folder: {folder}'}), 400
        
        # Search for all emails
        status, messages = imap.search(None, 'ALL')
        if status != 'OK':
            imap.logout()
            return jsonify({'error': 'Failed to search emails'}), 500
        
        if not messages or not messages[0]:
            imap.logout()
            return jsonify({
                'success': True,
                'emails': [],
                'total': 0,
                'folder': folder,
                'message': 'No emails found in this folder'
            })
        
        email_ids = messages[0].split()
        
        if not email_ids:
            imap.logout()
            return jsonify({
                'success': True,
                'emails': [],
                'total': 0,
                'folder': folder,
                'message': 'No emails found in this folder'
            })
        
        print(f"Found {len(email_ids)} emails in {folder}, fetching last {limit}")
        
        # Get last N emails (most recent)
        email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
        email_ids = email_ids[::-1]  # Reverse to show newest first
        
        # OPTIMIZATION: Fetch only headers and flags first (much faster)
        # Use batch fetch for better performance
        if not email_ids:
            imap.logout()
            return jsonify({
                'success': True,
                'emails': [],
                'total': 0,
                'folder': folder
            })
        
        # OPTIMIZATION: Fetch headers and flags individually (more reliable than batch)
        emails = []
        successful_fetches = 0
        failed_fetches = 0
        
        for email_id in email_ids:
            try:
                # Fetch flags first
                unread = True  # Default to unread
                try:
                    status_flags, flags_data = imap.fetch(email_id, '(FLAGS)')
                    if status_flags == 'OK' and flags_data:
                        for flag_part in flags_data:
                            if isinstance(flag_part, tuple):
                                flag_str = str(flag_part)
                                if 'FLAGS' in flag_str:
                                    unread = '\\Seen' not in flag_str
                except:
                    pass  # Use default unread if flags fetch fails
                
                # Fetch headers
                status, msg_data = imap.fetch(email_id, '(BODY.PEEK[HEADER])')
                if status != 'OK' or not msg_data:
                    failed_fetches += 1
                    print(f"Failed to fetch headers for email {email_id}")
                    continue
                
                msg = None
                
                # Parse the response - handle different response formats
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        if len(response_part) >= 2:
                            part_header, part_data = response_part[0], response_part[1]
                            
                            # Get header data
                            if isinstance(part_data, bytes):
                                try:
                                    msg = email.message_from_bytes(part_data)
                                    break  # Found the message, exit loop
                                except Exception as parse_error:
                                    # Try alternative parsing methods
                                    try:
                                        # Try decoding first
                                        decoded = part_data.decode('utf-8', errors='ignore')
                                        msg = email.message_from_string(decoded)
                                        break
                                    except:
                                        try:
                                            # Try with latin-1 encoding
                                            decoded = part_data.decode('latin-1', errors='ignore')
                                            msg = email.message_from_string(decoded)
                                            break
                                        except:
                                            continue
                            elif isinstance(part_data, str):
                                try:
                                    msg = email.message_from_string(part_data)
                                    break
                                except:
                                    continue
                    elif isinstance(response_part, bytes):
                        # Sometimes response comes as bytes directly
                        try:
                            msg = email.message_from_bytes(response_part)
                            break
                        except:
                            try:
                                msg = email.message_from_string(response_part.decode('utf-8', errors='ignore'))
                                break
                            except:
                                continue
                
                if not msg:
                    failed_fetches += 1
                    print(f"Could not parse message for email {email_id}")
                    continue
                
                # Decode subject
                subject = msg.get('Subject', '')
                if subject:
                    try:
                        decoded_parts = decode_header(subject)
                        subject = ''
                        for part, encoding in decoded_parts:
                            if isinstance(part, bytes):
                                subject += part.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                subject += str(part)
                    except:
                        subject = str(subject)
                
                # Decode from
                from_addr = msg.get('From', '')
                if from_addr:
                    try:
                        decoded_parts = decode_header(from_addr)
                        from_decoded = ''
                        for part, encoding in decoded_parts:
                            if isinstance(part, bytes):
                                from_decoded += part.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                from_decoded += str(part)
                        from_addr = from_decoded
                    except:
                        from_addr = str(from_addr)
                
                email_uid = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                
                emails.append({
                    'uid': email_uid,
                    'subject': subject or '(No Subject)',
                    'from': from_addr or 'Unknown',
                    'to': msg.get('To', ''),
                    'date': msg.get('Date', ''),
                    'body': '',  # Will be loaded on demand
                    'html': '',  # Will be loaded on demand
                    'unread': unread
                })
                successful_fetches += 1
                
            except Exception as email_error:
                failed_fetches += 1
                import traceback
                error_details = traceback.format_exc()
                print(f"Error processing email {email_id}: {email_error}")
                print(f"Error details: {error_details}")
                # Continue processing other emails even if one fails
                continue
        
        print(f"Email fetch summary: {successful_fetches} successful, {failed_fetches} failed out of {len(email_ids)} total")
        
        # If we got some emails but not all, log it
        if successful_fetches > 0 and successful_fetches < len(email_ids):
            print(f"Warning: Only fetched {successful_fetches} out of {len(email_ids)} emails")
        
        # If no emails were fetched, try fallback method with full RFC822 (slower but more reliable)
        if len(emails) == 0 and len(email_ids) > 0:
            print("Trying fallback method with RFC822...")
            emails = []
            for email_id in email_ids[:10]:  # Limit to 10 for fallback
                try:
                    status, msg_data = imap.fetch(email_id, '(RFC822 FLAGS)')
                    if status != 'OK' or not msg_data:
                        continue
                    
                    msg = None
                    unread = True
                    
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            part_header, part_data = response_part
                            
                            # Check flags
                            if isinstance(part_header, bytes):
                                header_str = part_header.decode('utf-8', errors='ignore')
                            else:
                                header_str = str(part_header)
                            
                            if 'FLAGS' in header_str:
                                unread = '\\Seen' not in header_str
                            
                            # Get message
                            if isinstance(part_data, bytes):
                                try:
                                    msg = email.message_from_bytes(part_data)
                                except:
                                    continue
                    
                    if not msg:
                        continue
                    
                    # Extract headers only (ignore body for now)
                    subject = msg.get('Subject', '') or '(No Subject)'
                    from_addr = msg.get('From', '') or 'Unknown'
                    
                    # Decode if needed
                    try:
                        decoded_parts = decode_header(subject)
                        subject = ''.join([p.decode(e or 'utf-8', errors='ignore') if isinstance(p, bytes) else str(p) 
                                         for p, e in decoded_parts])
                    except:
                        pass
                    
                    try:
                        decoded_parts = decode_header(from_addr)
                        from_addr = ''.join([p.decode(e or 'utf-8', errors='ignore') if isinstance(p, bytes) else str(p) 
                                           for p, e in decoded_parts])
                    except:
                        pass
                    
                    emails.append({
                        'uid': email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                        'subject': subject,
                        'from': from_addr,
                        'to': msg.get('To', ''),
                        'date': msg.get('Date', ''),
                        'body': '',
                        'html': '',
                        'unread': unread
                    })
                except Exception as e:
                    print(f"Fallback error for {email_id}: {e}")
                    continue
        
        imap.logout()
        
        return jsonify({
            'success': True,
            'emails': emails,
            'total': len(emails),
            'folder': folder
        })
        
    except Exception as e:
        import traceback
        print(f"Error fetching inbox: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/fetch-body/<int:account_id>/<email_uid>')
def api_fetch_email_body(account_id, email_uid):
    """Fetch full email body on demand (optimized - only when user views email)"""
    try:
        folder = request.args.get('folder', 'INBOX')
        
        # Get account config
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        imap_host = account.get('imap_host')
        if not imap_host:
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        password = account.get('password', '')
        
        # Decrypt password if encrypted
        if password:
            try:
                from core.encryption import get_encryption_manager
                encryptor = get_encryption_manager()
                password = encryptor.decrypt(password)
            except Exception as decrypt_error:
                # If decryption fails, might be plaintext from old data
                print(f"Password decryption failed (may be plaintext): {decrypt_error}")
                pass
        
        if not imap_host or not username or not password:
            return jsonify({'error': 'IMAP settings not properly configured'}), 400
        
        # Connect to IMAP
        imap = None
        try:
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass
            imap.login(username, password)
        except Exception as conn_error:
            if imap:
                try:
                    imap.logout()
                except:
                    pass
            return jsonify({'error': f'Failed to connect to IMAP server: {str(conn_error)}'}), 500
        
        # Select folder
        folder_variants = [folder]
        if folder == 'Sent':
            folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent']
        elif folder == 'Drafts':
            folder_variants = ['Drafts', 'Draft', 'INBOX.Drafts']
        elif folder == 'Trash':
            folder_variants = ['Trash', 'Deleted', 'Deleted Items', 'INBOX.Trash']
        elif folder == 'Spam':
            folder_variants = ['Spam', 'Junk', 'Junk E-mail', 'INBOX.Spam']
        
        selected = False
        for f in folder_variants:
            try:
                status, _ = imap.select(f, readonly=True)
                if status == 'OK':
                    selected = True
                    break
            except:
                continue
        
        if not selected:
            if imap:
                try:
                    imap.logout()
                except:
                    pass
            return jsonify({'error': f'Could not access folder: {folder}'}), 400
        
        # Fetch full email body
        try:
            email_id = email_uid.encode() if isinstance(email_uid, str) else email_uid
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            
            if status != 'OK' or not msg_data:
                if imap:
                    try:
                        imap.logout()
                    except:
                        pass
                return jsonify({'error': 'Failed to fetch email body. Email may have been deleted or moved.'}), 500
        except Exception as fetch_error:
            if imap:
                try:
                    imap.logout()
                except:
                    pass
            return jsonify({'error': f'Failed to fetch email: {str(fetch_error)}'}), 500
        
        body = ''
        html_body = ''
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Get body
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain' and not body:
                            try:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                body = str(part.get_payload())
                        elif content_type == 'text/html' and not html_body:
                            try:
                                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                html_body = str(part.get_payload())
                else:
                    content_type = msg.get_content_type()
                    payload = msg.get_payload(decode=True)
                    if payload:
                        try:
                            content = payload.decode('utf-8', errors='ignore')
                            if content_type == 'text/html':
                                html_body = content
                            else:
                                body = content
                        except:
                            body = str(msg.get_payload())
                break
        
        if imap:
            try:
                imap.logout()
            except:
                pass
        
        return jsonify({
            'success': True,
            'body': body,
            'html': html_body
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error fetching email body: {error_details}")
        
        # Ensure IMAP connection is closed
        if 'imap' in locals() and imap:
            try:
                imap.logout()
            except:
                pass
        
        return jsonify({'error': f'Failed to fetch email content: {str(e)}'}), 500

@app.route('/api/inbox/delete', methods=['POST'])
def api_delete_emails():
    """Delete emails from IMAP server"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        account_id = data.get('account_id')
        folder = data.get('folder', 'INBOX')
        uids = data.get('uids', [])
        
        if not account_id:
            return jsonify({'error': 'Account ID required'}), 400
        
        if not uids:
            return jsonify({'error': 'No email UIDs provided'}), 400
        
        # Get account config
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        # Get IMAP settings
        imap_host = account.get('imap_host')
        if not imap_host:
            smtp_host = account.get('host', '')
            if 'smtp' in smtp_host.lower():
                imap_host = smtp_host.replace('smtp', 'imap').replace('smtpout', 'imap')
            else:
                imap_host = 'imap.' + smtp_host.split('.', 1)[-1] if '.' in smtp_host else smtp_host
        
        imap_port = int(account.get('imap_port', 993))
        username = account.get('username', '')
        password = account.get('password', '')
        
        # Connect to IMAP
        if imap_port == 993:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
        else:
            imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
            try:
                imap.starttls()
            except:
                pass
        
        imap.login(username, password)
        
        # Select folder
        folder_variants = [folder]
        if folder == 'Sent':
            folder_variants = ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent']
        elif folder == 'Drafts':
            folder_variants = ['Drafts', 'Draft', 'INBOX.Drafts']
        elif folder == 'Trash':
            folder_variants = ['Trash', 'Deleted', 'Deleted Items', 'INBOX.Trash']
        elif folder == 'Spam':
            folder_variants = ['Spam', 'Junk', 'Junk E-mail', 'INBOX.Spam']
        
        selected = False
        for f in folder_variants:
            try:
                status, _ = imap.select(f)
                if status == 'OK':
                    selected = True
                    break
            except:
                continue
        
        if not selected:
            imap.logout()
            return jsonify({'error': f'Could not access folder: {folder}'}), 400
        
        # Delete emails by marking as deleted
        deleted_count = 0
        for uid in uids:
            try:
                # Mark for deletion
                imap.store(uid.encode() if isinstance(uid, str) else uid, '+FLAGS', '\\Deleted')
                deleted_count += 1
            except Exception as del_error:
                print(f"Error deleting email {uid}: {del_error}")
                continue
        
        # Expunge to permanently remove
        imap.expunge()
        imap.logout()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        import traceback
        print(f"Error deleting emails: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sent-emails')
def api_get_sent_emails():
    """Get sent emails"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase methods with retry logic for network errors
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)
            search = request.args.get('search', '')
            
            # Retry logic for Supabase queries
            import time
            max_retries = 3
            retry_delay = 0.5
            
            # Get sent emails with joins (Supabase doesn't support complex JOINs easily)
            # For now, get sent_emails and enrich with campaign/recipient data separately
            sent_emails = []
            for attempt in range(max_retries):
                try:
                    query = db.supabase.client.table('sent_emails').select('*')
                    query = query.order('sent_at', desc=True).range(offset, offset + limit - 1)
                    result = query.execute()
                    sent_emails = result.data if result.data else []
                    break
                except Exception as e:
                    error_msg = str(e)
                    error_type = str(type(e).__name__)
                    # Retry on network errors
                    if 'Resource temporarily unavailable' in error_msg or 'ReadError' in error_type or 'ConnectionError' in error_type or 'OSError' in error_type or attempt < max_retries - 1:
                        if attempt < max_retries - 1:
                            print(f"Supabase query error (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                            time.sleep(retry_delay * (attempt + 1))
                        else:
                            print(f"Failed to fetch sent emails after {max_retries} attempts: {e}")
                            # Return empty result instead of crashing
                            return jsonify({
                                'success': True,
                                'sent_emails': [],
                                'total': 0,
                                'error': 'Network error, please try again'
                            })
                    else:
                        # Non-network error, don't retry
                        print(f"Supabase query error: {e}")
                        return jsonify({
                            'success': False,
                            'error': str(e),
                            'sent_emails': [],
                            'total': 0
                        })
            
            # Filter by search term if provided
            if search:
                search_lower = search.lower()
                sent_emails = [e for e in sent_emails if 
                              search_lower in (e.get('recipient_email', '') or '').lower() or
                              search_lower in (e.get('subject', '') or '').lower() or
                              search_lower in (e.get('sender_email', '') or '').lower()]
            
            # Enrich with campaign and recipient data (with retry logic)
            for email in sent_emails:
                if email.get('campaign_id'):
                    for attempt in range(max_retries):
                        try:
                            campaign = db.supabase.client.table('campaigns').select('name').eq('id', email['campaign_id']).execute()
                            email['campaign_name'] = campaign.data[0]['name'] if campaign.data else None
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (attempt + 1))
                            else:
                                email['campaign_name'] = None
                                
                if email.get('recipient_id'):
                    for attempt in range(max_retries):
                        try:
                            recipient = db.supabase.client.table('recipients').select('first_name,last_name').eq('id', email['recipient_id']).execute()
                            if recipient.data:
                                email['first_name'] = recipient.data[0].get('first_name')
                                email['last_name'] = recipient.data[0].get('last_name')
                            break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay * (attempt + 1))
                            else:
                                email['first_name'] = None
                                email['last_name'] = None
            
            # Get total count
            if search:
                # For search, count filtered results
                total = len(sent_emails)
            else:
                total = len(sent_emails)  # Use length as fallback
                for attempt in range(max_retries):
                    try:
                        count_query = db.supabase.client.table('sent_emails').select('id', count='exact')
                        count_result = count_query.execute()
                        total = count_result.count if hasattr(count_result, 'count') else len(sent_emails)
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))
                        else:
                            # Use length as fallback
                            total = len(sent_emails)
            
            return jsonify({
                'success': True,
                'sent_emails': sent_emails,
                'total': total
            })
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Get query parameters
            limit = request.args.get('limit', 100, type=int)
            offset = request.args.get('offset', 0, type=int)
            search = request.args.get('search', '')
            
            query = """
                SELECT se.*, c.name as campaign_name, r.first_name, r.last_name
                FROM sent_emails se
                LEFT JOIN campaigns c ON se.campaign_id = c.id
                LEFT JOIN recipients r ON se.recipient_id = r.id
                WHERE 1=1
            """
            params = []
            
            if search:
                query += " AND (se.recipient_email LIKE ? OR se.subject LIKE ? OR se.sender_email LIKE ?)"
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])
            
            query += " ORDER BY se.sent_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            sent_emails = [dict(row) for row in cursor.fetchall()]
            
            # Get total count
            count_query = "SELECT COUNT(*) FROM sent_emails se WHERE 1=1"
            count_params = []
            if search:
                count_query += " AND (se.recipient_email LIKE ? OR se.subject LIKE ? OR se.sender_email LIKE ?)"
                search_term = f"%{search}%"
                count_params.extend([search_term, search_term, search_term])
            cursor.execute(count_query, count_params)
            total = cursor.fetchone()[0]
            
            return jsonify({
                'success': True,
                'sent_emails': sent_emails,
                'total': total
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sent-emails/<int:email_id>')
def api_get_sent_email(email_id):
    """Get a single sent email"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase methods
            result = db.supabase.client.table('sent_emails').select('*').eq('id', email_id).execute()
            
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Email not found'}), 404
            
            email = result.data[0]
            
            # Enrich with campaign and recipient data
            if email.get('campaign_id'):
                campaign = db.supabase.client.table('campaigns').select('name').eq('id', email['campaign_id']).execute()
                email['campaign_name'] = campaign.data[0]['name'] if campaign.data else None
            if email.get('recipient_id'):
                recipient = db.supabase.client.table('recipients').select('first_name,last_name').eq('id', email['recipient_id']).execute()
                if recipient.data:
                    email['first_name'] = recipient.data[0].get('first_name')
                    email['last_name'] = recipient.data[0].get('last_name')
            
            return jsonify({'success': True, 'email': email})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT se.*, c.name as campaign_name, r.first_name, r.last_name
                FROM sent_emails se
                LEFT JOIN campaigns c ON se.campaign_id = c.id
                LEFT JOIN recipients r ON se.recipient_id = r.id
                WHERE se.id = ?
            """, (email_id,))
            row = cursor.fetchone()
            
            if row:
                return jsonify({'success': True, 'email': dict(row)})
            else:
                return jsonify({'error': 'Email not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/sent-items')
def sent_items():
    """Sent Items page"""
    return render_template('sent_items.html')

@app.route('/settings')
def settings_page():
    """Settings page"""
    return render_template('settings.html')

# Settings API Routes

@app.route('/api/settings')
@optional_auth
def api_get_settings(user_id):
    """Get all settings"""
    try:
        # Get from persistent storage
        settings = settings_manager.get_all_settings(user_id=user_id)
        
        # Convert string values to appropriate types
        result = {
            'email_delay': int(settings.get('email_delay', 30)),
            'max_per_hour': int(settings.get('max_per_hour', 100)),
            'email_priority': int(settings.get('email_priority', 5)),
            'emails_per_server': int(settings.get('emails_per_server', 20)),
            'use_threading': settings.get('use_threading', 'false').lower() == 'true'
        }
        return jsonify({'success': True, 'settings': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/delay', methods=['POST'])
@optional_auth
def api_set_delay(user_id):
    """Set email delay setting"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        delay = data.get('email_delay', 30)
        
        # Validate delay value
        delay = int(delay)
        if delay < 1:
            delay = 1
        if delay > 600:
            delay = 600
        
        # Save to persistent storage
        settings_manager.set_setting('email_delay', str(delay), user_id=user_id)
        
        # Update the global email sender if it exists
        global email_sender
        if email_sender:
            email_sender.interval = float(delay)
            print(f"✓ Email delay updated to {delay} seconds")
        
        return jsonify({'success': True, 'email_delay': delay})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/other', methods=['POST'])
@optional_auth
def api_set_other_settings(user_id):
    """Set other settings"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        if 'max_per_hour' in data:
            settings_manager.set_setting('max_per_hour', data['max_per_hour'], user_id=user_id)
        
        if 'email_priority' in data:
            settings_manager.set_setting('email_priority', data['email_priority'], user_id=user_id)
        
        if 'emails_per_server' in data:
            settings_manager.set_setting('emails_per_server', data['emails_per_server'], user_id=user_id)
        
        if 'use_threading' in data:
            settings_manager.set_setting('use_threading', data['use_threading'], user_id=user_id)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/emails-per-server', methods=['POST'])
@optional_auth
def api_set_emails_per_server(user_id):
    """Set emails per server setting"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        emails_per_server = int(data.get('emails_per_server', 20))
        
        if emails_per_server < 1:
            emails_per_server = 1
        if emails_per_server > 100:
            emails_per_server = 100
        
        # Save to persistent storage
        settings_manager.set_setting('emails_per_server', str(emails_per_server), user_id=user_id)
        return jsonify({'success': True, 'emails_per_server': emails_per_server})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/api-keys', methods=['GET'])
@optional_auth
def api_get_api_keys(user_id):
    """Get API keys (masked)"""
    try:
        from core.config import Config
        
        # Get from persistent storage first
        perplexity_key = settings_manager.get_setting('PERPLEXITY_API_KEY', user_id=user_id) or Config.get_perplexity_key()
        openrouter_key = settings_manager.get_setting('OPENROUTER_API_KEY', user_id=user_id) or Config.get_openrouter_key()
        openrouter_model = settings_manager.get_setting('OPENROUTER_MODEL', user_id=user_id) or Config.OPENROUTER_MODEL
        
        def mask_key(key):
            if not key or len(key) < 8:
                return ''
            return key[:4] + '*' * (len(key) - 8) + key[-4:]
        
        return jsonify({
            'success': True,
            'keys': {
                'perplexity_api_key': mask_key(perplexity_key) if perplexity_key else '',
                'openrouter_api_key': mask_key(openrouter_key) if openrouter_key else '',
                'openrouter_model': openrouter_model
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/api-keys', methods=['POST'])
@optional_auth
def api_set_api_keys(user_id):
    """Set API keys"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        from core.config import Config
        
        if data.get('perplexity_api_key'):
            settings_manager.set_setting('PERPLEXITY_API_KEY', data['perplexity_api_key'], user_id=user_id)
            Config.set_perplexity_key(data['perplexity_api_key'])
        
        if data.get('openrouter_api_key'):
            settings_manager.set_setting('OPENROUTER_API_KEY', data['openrouter_api_key'], user_id=user_id)
            Config.set_openrouter_key(data['openrouter_api_key'])
        
        if data.get('openrouter_model'):
            settings_manager.set_setting('OPENROUTER_MODEL', data['openrouter_model'], user_id=user_id)
            Config._update_env_file('OPENROUTER_MODEL', data['openrouter_model'])
            Config.OPENROUTER_MODEL = data['openrouter_model']
        
        return jsonify({'success': True, 'message': 'API keys saved successfully'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Database Configuration API
@app.route('/api/settings/database', methods=['GET'])
@optional_auth
def api_get_database_config(user_id):
    """Get database configuration"""
    try:
        from core.config import Config
        
        # Get from persistent storage first, then env
        config = {
            'database_type': settings_manager.get_setting('DATABASE_TYPE', user_id=user_id) or os.getenv('DATABASE_TYPE', 'sqlite'),
            'supabase_url': settings_manager.get_setting('SUPABASE_URL', user_id=user_id) or Config.get('SUPABASE_URL') or os.getenv('SUPABASE_URL', ''),
            'supabase_key': settings_manager.get_setting('SUPABASE_KEY', user_id=user_id) or Config.get('SUPABASE_KEY') or os.getenv('SUPABASE_KEY', '')
        }
        
        # Mask key if present
        if config['supabase_key'] and len(config['supabase_key']) > 8:
            key = config['supabase_key']
            config['supabase_key'] = key[:4] + '*' * (len(key) - 8) + key[-4:]
        
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/database', methods=['POST'])
@optional_auth
def api_set_database_config(user_id):
    """Set database configuration"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        from core.config import Config
        
        if data.get('database_type'):
            settings_manager.set_setting('DATABASE_TYPE', data['database_type'], user_id=user_id)
            Config._update_env_file('DATABASE_TYPE', data['database_type'])
        
        if data.get('supabase_url'):
            settings_manager.set_setting('SUPABASE_URL', data['supabase_url'], user_id=user_id)
            Config._update_env_file('SUPABASE_URL', data['supabase_url'])
        
        if data.get('supabase_key'):
            settings_manager.set_setting('SUPABASE_KEY', data['supabase_key'], user_id=user_id)
            Config._update_env_file('SUPABASE_KEY', data['supabase_key'])
        
        return jsonify({'success': True, 'message': 'Database configuration saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/test-supabase', methods=['POST'])
def api_test_supabase():
    """Test Supabase connection - DYNAMIC"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        url = data.get('url')
        key = data.get('key')
        
        if not url or not key:
            return jsonify({'error': 'URL and Key are required'}), 400
        
        try:
            from core.supabase_client import SupabaseClient
            client = SupabaseClient(url, key)
            connected = client.test_connection()
            
            if connected:
                # Test a simple query
                try:
                    result = client.client.table('users').select('id').limit(1).execute()
                    return jsonify({
                        'success': True, 
                        'message': 'Supabase connection successful',
                        'details': {
                            'url': url.split('//')[1].split('.')[0] if '//' in url else url,
                            'query_test': 'passed',
                            'timestamp': datetime.now().isoformat()
                        }
                    })
                except:
                    return jsonify({
                        'success': True,
                        'message': 'Supabase connection successful (tables may need migration)',
                        'details': {
                            'url': url.split('//')[1].split('.')[0] if '//' in url else url,
                            'timestamp': datetime.now().isoformat()
                        }
                    })
            else:
                return jsonify({'success': False, 'error': 'Connection test failed'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Connection error: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/database-status', methods=['GET'])
def api_get_database_status():
    """Get database connection status - DYNAMIC"""
    try:
        # Get from settings (persistent) or env
        database_type = settings_manager.get_setting('DATABASE_TYPE') or os.getenv('DATABASE_TYPE', 'sqlite')
        connected = False
        error_message = None
        
        if database_type == 'supabase':
            try:
                supabase_url = settings_manager.get_setting('SUPABASE_URL') or os.getenv('SUPABASE_URL')
                supabase_key = settings_manager.get_setting('SUPABASE_KEY') or os.getenv('SUPABASE_KEY')
                
                if supabase_url and supabase_key:
                    from core.supabase_client import SupabaseClient
                    client = SupabaseClient(supabase_url, supabase_key)
                    connected = client.test_connection()
                else:
                    error_message = 'Supabase URL or Key not configured'
            except Exception as e:
                connected = False
                error_message = str(e)
        else:
            # SQLite - always connected if file exists
            try:
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(backend_dir, 'anagha_solution.db')
                connected = os.path.exists(db_path)
            except Exception as e:
                connected = False
                error_message = str(e)
        
        return jsonify({
            'success': True,
            'status': {
                'connected': connected,
                'database_type': database_type,
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Deployment Configuration API
@app.route('/api/settings/deployment', methods=['GET'])
@optional_auth
def api_get_deployment_config(user_id):
    """Get deployment configuration"""
    try:
        from core.config import Config
        
        # Get from persistent storage first
        config = {
            'env_vars': settings_manager.get_setting('DEPLOYMENT_ENV_VARS', user_id=user_id) or Config.get('DEPLOYMENT_ENV_VARS') or '',
            'deployment_url': settings_manager.get_setting('DEPLOYMENT_URL', user_id=user_id) or Config.get('DEPLOYMENT_URL') or ''
        }
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/deployment', methods=['POST'])
@optional_auth
def api_set_deployment_config(user_id):
    """Set deployment configuration"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        from core.config import Config
        
        if data.get('env_vars'):
            settings_manager.set_setting('DEPLOYMENT_ENV_VARS', data['env_vars'], user_id=user_id)
            Config._update_env_file('DEPLOYMENT_ENV_VARS', data['env_vars'])
        
        if data.get('deployment_url'):
            settings_manager.set_setting('DEPLOYMENT_URL', data['deployment_url'], user_id=user_id)
            Config._update_env_file('DEPLOYMENT_URL', data['deployment_url'])
        
        return jsonify({'success': True, 'message': 'Deployment settings saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

# Email Sending Control API
@app.route('/api/email-sender/status', methods=['GET'])
def api_get_sender_status():
    """Get email sender status"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({
                'status': 'stopped',
                'is_sending': False,
                'is_paused': False,
                'message': 'Email sender not initialized'
            })
        
        status = email_sender.get_status()
        return jsonify({
            'status': status,
            'is_sending': email_sender.is_sending,
            'is_paused': getattr(email_sender, 'is_paused', False),
            'message': f'Email sender is {status}'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/email-sender/stop', methods=['POST'])
def api_stop_sender():
    """Stop email sending"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({'error': 'Email sender not initialized'}), 400
        
        email_sender.stop_sending()
        return jsonify({
            'success': True,
            'message': 'Email sending stopped',
            'status': 'stopped'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/email-sender/pause', methods=['POST'])
def api_pause_sender():
    """Pause email sending"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({'error': 'Email sender not initialized'}), 400
        
        if not email_sender.is_sending:
            return jsonify({'error': 'Email sender is not running'}), 400
        
        email_sender.pause_sending()
        return jsonify({
            'success': True,
            'message': 'Email sending paused',
            'status': 'paused'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/email-sender/resume', methods=['POST'])
def api_resume_sender():
    """Resume email sending"""
    try:
        global email_sender
        if not email_sender:
            return jsonify({'error': 'Email sender not initialized'}), 400
        
        # Allow resume if sender is paused (even if is_sending is True)
        # Or if sender exists but is stopped, we can't resume - need to restart
        if not email_sender.is_sending:
            return jsonify({
                'error': 'Email sender is not running. Please start a campaign to begin sending.',
                'code': 'not_running'
            }), 400
        
        # Check if paused
        is_paused = getattr(email_sender, 'is_paused', False)
        if not is_paused:
            return jsonify({
                'error': 'Email sending is not paused',
                'code': 'not_paused'
            }), 400
        
        email_sender.resume_sending()
        return jsonify({
            'success': True,
            'message': 'Email sending resumed',
            'status': 'sending'
        })
    except Exception as e:
        import traceback
        print(f"Error resuming sender: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

# API Routes

@app.route('/api/dashboard/stats')
@optional_auth
def api_dashboard_stats(user_id):
    """Get dashboard statistics with observability metrics"""
    try:
        # Get queue stats (works for both Supabase and SQLite)
        queue_stats = db.get_queue_stats() if hasattr(db, 'get_queue_stats') else {'pending': 0, 'sent_today': 0}
        
        # Get daily stats (works for both Supabase and SQLite)
        daily_stats = db.get_daily_stats() if hasattr(db, 'get_daily_stats') else {
            'emails_sent': 0,
            'emails_delivered': 0,
            'emails_bounced': 0,
            'emails_opened': 0,
            'emails_clicked': 0,
            'spam_reports': 0,
            'unsubscribes': 0
        }
        
        total_sent = daily_stats.get('emails_sent', 0) or 0
        delivered = daily_stats.get('emails_delivered', 0) or 0
        bounced = daily_stats.get('emails_bounced', 0) or 0
        spam = daily_stats.get('spam_reports', 0) or 0
        
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
        spam_rate = (spam / total_sent * 100) if total_sent > 0 else 0
        
        # Get recipients count (filter by user_id if provided)
        recipients = db.get_recipients(user_id=user_id) if user_id else db.get_recipients()
        subscriber_count = len(recipients) if recipients else 0
        
        # Get observability metrics
        obs_metrics = {}
        try:
            if user_id:
                obs_metrics = observability_manager.get_dashboard_metrics(user_id)
        except Exception as obs_error:
            print(f"Error getting observability metrics: {obs_error}")
        
        return jsonify({
            'success': True,
            'sent_today': queue_stats.get('sent_today', 0),
            'pending': queue_stats.get('pending', 0),
            'delivery_rate': round(delivery_rate, 1),
            'bounce_rate': round(bounce_rate, 1),
            'spam_rate': round(spam_rate, 1),
            'subscribers': subscriber_count,
            'daily_stats': daily_stats,
            'observability': obs_metrics
        })
    except Exception as e:
        import traceback
        print(f"Error in api_dashboard_stats: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'sent_today': 0,
            'pending': 0,
            'delivery_rate': 0,
            'bounce_rate': 0,
            'spam_rate': 0,
            'subscribers': 0,
            'daily_stats': {}
        }), 500

@app.route('/api/campaign/create', methods=['POST'])
@require_auth
def api_create_campaign(user_id):
    """Create a new campaign"""
    try:
        # Handle both JSON and form data
        if request.content_type and 'application/json' in request.content_type:
            # JSON request
            data = request.get_json() if request.is_json else {}
            attachments = []
        else:
            # Form data (multipart/form-data for file uploads)
            attachments = request.files.getlist('attachments')
            
            # Convert form data to dict, preserving list values for selected_smtp_servers
            data = {}
            for key in request.form:
                values = request.form.getlist(key)
                if len(values) == 1:
                    data[key] = values[0]
                else:
                    data[key] = values
        
        # Determine message content based on type
        message_type = data.get('message_type', 'html')
        if message_type == 'text':
            # Convert text to HTML for storage
            text_content = data.get('text_content', '')
            html_content = text_content.replace('\n', '<br>')
        else:
            html_content = data.get('html_content', '')
        
        # Check if personalization is enabled
        use_personalization = data.get('use_personalization') == 'on' or data.get('use_personalization') == True
        personalization_prompt = data.get('personalization_prompt', '').strip() if use_personalization else None
        
        # Validate: if personalization is enabled, prompt is required
        if use_personalization and not personalization_prompt:
            return jsonify({'error': 'Personalization prompt is required when AI personalization is enabled'}), 400
        
        # Create campaign first to get ID
        campaign_id = db.create_campaign(
            name=data.get('name'),
            subject=data.get('subject'),
            sender_name=data.get('sender_name'),
            sender_email=data.get('sender_email'),
            reply_to=None,
            html_content=html_content,
            template_id=data.get('template_id'),
            use_personalization=use_personalization,
            user_id=user_id,
            personalization_prompt=personalization_prompt
        )
        
        # Save attachments if any
        attachment_paths = []
        if attachments:
            # Use absolute path for attachments directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            attachments_dir = os.path.join(script_dir, 'attachments')
            os.makedirs(attachments_dir, exist_ok=True)
            for attachment in attachments:
                if attachment and attachment.filename:
                    filename = f"{campaign_id}_{attachment.filename}"
                    filepath = os.path.join(attachments_dir, filename)
                    attachment.save(filepath)
                    attachment_paths.append(filepath)
        
        # Update campaign with attachment paths if any
        if attachment_paths:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE campaigns SET html_content = html_content || ? 
                WHERE id = ?
            """, (f"\n<!--ATTACHMENTS:{','.join(attachment_paths)}-->", campaign_id))
            conn.commit()
        
        # If sending immediately
        send_now = data.get('send_now')
        send_now_bool = (send_now == 'on' or send_now == True or send_now == 'true' or 
                        str(send_now).lower() == 'true' or send_now == '1')
        
        if send_now_bool:
            recipients = db.get_recipients(user_id=user_id)
            if not recipients:
                return jsonify({'success': True, 'campaign_id': campaign_id, 
                              'warning': 'Campaign created but no recipients found to send to'})
            
            recipient_ids = [r['id'] for r in recipients]
            
            # Get selected SMTP servers from form data
            # IMPORTANT: FormData with multiple values with same key needs special handling
            selected_smtp_servers = None
            
            # Try to get from request.form.getlist first (handles multiple values correctly)
            if request.method == 'POST' and not (request.content_type and 'application/json' in request.content_type):
                selected_servers_list = request.form.getlist('selected_smtp_servers')
                if selected_servers_list:
                    print(f"📋 Got selected_smtp_servers from request.form.getlist: {selected_servers_list}")
                    try:
                        selected_smtp_servers = [int(sid) for sid in selected_servers_list if sid and str(sid).strip()]
                        if len(selected_smtp_servers) > 0:
                            print(f"📧 Using {len(selected_smtp_servers)} selected SMTP servers: {selected_smtp_servers}")
                        else:
                            print("⚠ Warning: selected_servers_list is empty after filtering")
                            selected_smtp_servers = None
                    except (ValueError, TypeError) as e:
                        print(f"✗ Error parsing selected SMTP servers from getlist: {e}")
                        selected_smtp_servers = None
            
            # Fallback to data dict if not found in form
            if not selected_smtp_servers and 'selected_smtp_servers' in data:
                selected_servers = data.get('selected_smtp_servers', [])
                print(f"📋 Fallback: Got selected_smtp_servers from data dict: {selected_servers} (type: {type(selected_servers)})")
                
                # Handle both list and single value
                if isinstance(selected_servers, str):
                    selected_servers = [selected_servers]
                elif not isinstance(selected_servers, list):
                    selected_servers = [selected_servers] if selected_servers else []
                
                if selected_servers:
                    try:
                        selected_smtp_servers = [int(sid) for sid in selected_servers if sid and str(sid).strip()]
                        if len(selected_smtp_servers) > 0:
                            print(f"📧 Using {len(selected_smtp_servers)} selected SMTP servers: {selected_smtp_servers}")
                        else:
                            print("⚠ Warning: selected_servers list is empty after filtering")
                            selected_smtp_servers = None
                    except (ValueError, TypeError) as e:
                        print(f"✗ Error parsing selected SMTP servers: {e}")
                        print(f"   Raw selected_servers: {selected_servers}")
                        import traceback
                        traceback.print_exc()
                        selected_smtp_servers = None
                else:
                    print("⚠ Warning: selected_servers is empty or None")
                    selected_smtp_servers = None
            
            if not selected_smtp_servers:
                print("⚠ No selected SMTP servers found in request")
            
            # Validate selected servers
            # Allow any number of SMTP servers (minimum 1)
            if selected_smtp_servers and len(selected_smtp_servers) < 1:
                return jsonify({'error': 'Please select at least 1 SMTP server.'}), 400
            
            # Check if SMTP servers are configured
            if not selected_smtp_servers:
                smtp_servers = db.get_smtp_servers(user_id=user_id, active_only=True)
                if not smtp_servers or len(smtp_servers) == 0:
                    return jsonify({'error': 'No active SMTP server configured. Please add at least 1 SMTP server.'}), 400
            
            # Update campaign status to 'sending'
            # Check if using Supabase FIRST before trying to use SQLite methods
            use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
            if use_supabase:
                db.supabase.client.table('campaigns').update({'status': 'sending'}).eq('id', campaign_id).execute()
            else:
                conn = db.connect()
                cursor = conn.cursor()
                cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
                conn.commit()
            
            # Add to queue with round-robin distribution using selected servers
            emails_per_server = 20  # 20 emails per SMTP server
            db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, 
                          emails_per_server=emails_per_server, 
                          selected_smtp_servers=selected_smtp_servers)
            print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
            
            # Start sending in background thread
            import threading
            global email_sender
            
            def start_sender():
                try:
                    global email_sender
                    if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                        # Get delay from settings
                        email_delay = db.get_email_delay()
                        email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                        email_sender.start_sending()
                        print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients ({email_delay} sec delay)")
                    else:
                        print("ℹ Email sender already running, queue will be processed")
                except Exception as e:
                    print(f"✗ Error starting email sender: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start in background thread
            sender_thread = threading.Thread(target=start_sender, daemon=True)
            sender_thread.start()
            
            # Give it a moment to start
            import time
            time.sleep(0.5)
        
        return jsonify({'success': True, 'campaign_id': campaign_id})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error creating campaign: {error_details}")
        return jsonify({'error': str(e), 'details': error_details}), 500

@app.route('/api/recipients/import', methods=['POST'])
@require_auth
def api_import_recipients(user_id):
    """Import recipients from file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save file temporarily
        filename = file.filename
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(script_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, filename)
        file.save(filepath)
        
        # Read file
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Normalize columns
        df.columns = df.columns.str.lower().str.strip()
        
        column_mapping = {
            'email': 'email',
            'e-mail': 'email',
            'email address': 'email',
            'firstname': 'first_name',
            'first name': 'first_name',
            'fname': 'first_name',
            'lastname': 'last_name',
            'last name': 'last_name',
            'lname': 'last_name',
            'company': 'company',
            'city': 'city',
            'phone': 'phone',
            'list': 'list_name',
            'listname': 'list_name'
        }
        
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        if 'email' not in df.columns:
            return jsonify({'error': 'CSV/Excel file must contain an email column'}), 400
        
        recipients = df.to_dict('records')
        count = db.add_recipients(recipients, user_id=user_id)
        
        # Clean up
        os.remove(filepath)
        
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/add', methods=['POST'])
def api_add_recipient():
    """Add a single recipient"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        recipient = {
            'email': data.get('email', '').lower().strip(),
            'first_name': data.get('first_name', ''),
            'last_name': data.get('last_name', ''),
            'company': data.get('company', ''),
            'city': data.get('city', ''),
            'phone': data.get('phone', ''),
            'list_name': data.get('list_name', 'default')
        }
        
        count = db.add_recipients([recipient])
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/list', methods=['GET'])
@require_auth
def api_list_recipients(user_id):
    """Get list of all recipients"""
    try:
        list_name = request.args.get('list_name')
        recipients = db.get_recipients(list_name=list_name, user_id=user_id)
        return jsonify({'success': True, 'recipients': recipients})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/delete/<int:recipient_id>', methods=['DELETE'])
@require_auth
def api_delete_recipient(recipient_id, user_id):
    """Delete a single recipient"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if recipient exists and belongs to user
            result = db.supabase.client.table('recipients').select('id').eq('id', recipient_id).eq('user_id', user_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Recipient not found or access denied'}), 404
            
            # Delete related data first
            try:
                db.supabase.client.table('campaign_recipients').delete().eq('recipient_id', recipient_id).execute()
            except:
                pass
            db.supabase.client.table('email_queue').delete().eq('recipient_id', recipient_id).execute()
            
            # Delete recipient
            db.supabase.client.table('recipients').delete().eq('id', recipient_id).execute()
            
            return jsonify({'success': True, 'message': 'Recipient deleted'})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute("SELECT id FROM recipients WHERE id = ? AND user_id = ?", (recipient_id, user_id))
            if not cursor.fetchone():
                return jsonify({'error': 'Recipient not found or access denied'}), 404
            
            # Delete from recipients table
            cursor.execute("DELETE FROM campaign_recipients WHERE recipient_id = ?", (recipient_id,))
            cursor.execute("DELETE FROM email_queue WHERE recipient_id = ?", (recipient_id,))
            cursor.execute("DELETE FROM recipients WHERE id = ?", (recipient_id,))
            
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Recipient deleted'})
    except Exception as e:
        import traceback
        print(f"Error deleting recipient: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/delete/bulk', methods=['POST'])
@require_auth
def api_delete_recipients_bulk(user_id):
    """Delete multiple recipients"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        recipient_ids = data.get('recipient_ids', [])
        
        if not recipient_ids:
            return jsonify({'error': 'No recipient IDs provided'}), 400
        
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Verify ownership - only delete recipients that belong to user
            result = db.supabase.client.table('recipients').select('id').eq('user_id', user_id).in_('id', recipient_ids).execute()
            valid_ids = [r['id'] for r in (result.data or [])]
            
            if not valid_ids:
                return jsonify({'error': 'No valid recipients found or access denied'}), 404
            
            # Delete related data first
            try:
                db.supabase.client.table('campaign_recipients').delete().in_('recipient_id', valid_ids).execute()
            except:
                pass
            db.supabase.client.table('email_queue').delete().in_('recipient_id', valid_ids).execute()
            
            # Delete recipients
            db.supabase.client.table('recipients').delete().in_('id', valid_ids).execute()
            
            return jsonify({'success': True, 'deleted_count': len(valid_ids)})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Verify ownership
            placeholders = ','.join(['?'] * len(recipient_ids))
            cursor.execute(f"SELECT id FROM recipients WHERE id IN ({placeholders}) AND user_id = ?", recipient_ids + [user_id])
            valid_ids = [row[0] for row in cursor.fetchall()]
            
            if not valid_ids:
                return jsonify({'error': 'No valid recipients found or access denied'}), 404
            
            valid_placeholders = ','.join(['?'] * len(valid_ids))
            
            # Delete recipients and related data
            cursor.execute(f"DELETE FROM campaign_recipients WHERE recipient_id IN ({valid_placeholders})", valid_ids)
            cursor.execute(f"DELETE FROM email_queue WHERE recipient_id IN ({valid_placeholders})", valid_ids)
            cursor.execute(f"DELETE FROM recipients WHERE id IN ({valid_placeholders})", valid_ids)
            
            conn.commit()
            
            return jsonify({'success': True, 'deleted_count': len(valid_ids)})
    except Exception as e:
        import traceback
        print(f"Error deleting recipients: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recipients/delete/all', methods=['DELETE'])
@require_auth
def api_delete_all_recipients(user_id):
    """Delete all recipients for the current user"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if recipients table exists
            if hasattr(db, '_ensure_table_exists'):
                try:
                    db._ensure_table_exists('recipients', 'delete all recipients')
                except Exception as table_error:
                    return jsonify({'error': str(table_error)}), 500
            
            # Get all recipient IDs for this user
            result = db.supabase.client.table('recipients').select('id').eq('user_id', user_id).execute()
            recipient_ids = [r['id'] for r in (result.data or [])]
            count = len(recipient_ids)
            
            if count == 0:
                return jsonify({'success': True, 'deleted_count': 0, 'message': 'No recipients found'})
            
            # Delete related data first (only if tables exist)
            if recipient_ids:
                try:
                    db.supabase.client.table('campaign_recipients').delete().in_('recipient_id', recipient_ids).execute()
                except Exception as e:
                    # Table might not exist, continue
                    print(f"⚠ Could not delete from campaign_recipients: {e}")
                    pass
                
                # Check if email_queue table exists before trying to delete
                try:
                    if hasattr(db, '_check_table_exists') and db._check_table_exists('email_queue'):
                        db.supabase.client.table('email_queue').delete().in_('recipient_id', recipient_ids).execute()
                    else:
                        print("⚠ email_queue table does not exist, skipping deletion")
                except Exception as e:
                    # Table might not exist, continue
                    print(f"⚠ Could not delete from email_queue: {e}")
                    pass
            
            # Delete recipients
            db.supabase.client.table('recipients').delete().eq('user_id', user_id).execute()
            
            return jsonify({'success': True, 'deleted_count': count})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Get count before deletion
            cursor.execute("SELECT COUNT(*) FROM recipients WHERE user_id = ?", (user_id,))
            count = cursor.fetchone()[0]
            
            if count == 0:
                return jsonify({'success': True, 'deleted_count': 0, 'message': 'No recipients found'})
            
            # Get recipient IDs for related data deletion
            cursor.execute("SELECT id FROM recipients WHERE user_id = ?", (user_id,))
            recipient_ids = [row[0] for row in cursor.fetchall()]
            
            if recipient_ids:
                placeholders = ','.join(['?'] * len(recipient_ids))
                cursor.execute(f"DELETE FROM campaign_recipients WHERE recipient_id IN ({placeholders})", recipient_ids)
                cursor.execute(f"DELETE FROM email_queue WHERE recipient_id IN ({placeholders})", recipient_ids)
            
            # Delete all recipients for this user
            cursor.execute("DELETE FROM recipients WHERE user_id = ?", (user_id,))
            
            conn.commit()
            
            return jsonify({'success': True, 'deleted_count': count})
    except Exception as e:
        import traceback
        print(f"Error deleting all recipients: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/add', methods=['POST'])
@require_auth
def api_add_smtp(user_id):
    """Add SMTP server"""
    try:
        # Handle both JSON and form data
        if request.is_json and request.json:
            data = request.json
        else:
            # Try to get JSON from request
            try:
                data = request.get_json(silent=True)
                if not data:
                    # Fall back to form data
                    data = request.form.to_dict()
            except:
                data = request.form.to_dict()
        
        # Debug: Print received data (without password)
        debug_data = {k: v for k, v in data.items() if k != 'password'}
        print(f"📧 Received SMTP add request: {debug_data}")
        
        # Validate required fields
        required_fields = ['name', 'host', 'port', 'username', 'password']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            error_msg = f'Missing required fields: {", ".join(missing_fields)}'
            print(f"✗ Validation error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Decode password if it's URL-encoded (handles special characters like *)
        import urllib.parse
        password = data.get('password')
        if password:
            # Try to decode URL encoding if present
            try:
                password = urllib.parse.unquote(password)
            except:
                pass  # If decoding fails, use as-is
            # Ensure it's a string, not bytes
            if isinstance(password, bytes):
                password = password.decode('utf-8')
        
        use_ssl = data.get('use_ssl', True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.lower() in ('true', 'on', '1')
        
        use_tls = data.get('use_tls', False)
        if isinstance(use_tls, str):
            use_tls = use_tls.lower() in ('true', 'on', '1')
        
        # Get IMAP settings
        imap_host = data.get('imap_host', '')
        imap_port = int(data.get('imap_port', 993)) if data.get('imap_port') else 993
        save_to_sent = data.get('save_to_sent', True)
        if isinstance(save_to_sent, str):
            save_to_sent = save_to_sent.lower() in ('true', 'on', '1')
        
        # Get POP3 settings
        pop3_host = data.get('pop3_host', '')
        pop3_port = int(data.get('pop3_port', 995)) if data.get('pop3_port') else 995
        pop3_ssl = data.get('pop3_ssl', True)
        if isinstance(pop3_ssl, str):
            pop3_ssl = pop3_ssl.lower() in ('true', 'on', '1')
        pop3_leave_on_server = data.get('pop3_leave_on_server', True)
        if isinstance(pop3_leave_on_server, str):
            pop3_leave_on_server = pop3_leave_on_server.lower() in ('true', 'on', '1')
        incoming_protocol = data.get('incoming_protocol', 'imap')
        
        # Detect provider type
        provider_type = data.get('provider_type', 'smtp')
        username = data.get('username', '')
        if not provider_type or provider_type == 'smtp':
            provider_type = rate_limiter.detect_provider(username)
        
        server_id = db.add_smtp_server(
            name=data.get('name'),
            host=data.get('host'),
            port=int(data.get('port')),
            username=username,
            password=password,  # Use decoded password
            use_tls=use_tls,
            use_ssl=use_ssl,
            max_per_hour=int(data.get('max_per_hour', 100)),
            imap_host=imap_host,
            imap_port=imap_port,
            save_to_sent=save_to_sent,
            pop3_host=pop3_host,
            pop3_port=pop3_port,
            pop3_ssl=pop3_ssl,
            pop3_leave_on_server=pop3_leave_on_server,
            incoming_protocol=incoming_protocol,
            user_id=user_id,
            provider_type=provider_type
        )
        
        # If this is the first server or user wants it as default, set it
        set_as_default = data.get('set_as_default', False)
        if set_as_default:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE smtp_servers SET is_default = 0")
            cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
        
        print(f"✅ SMTP server added successfully with ID: {server_id}")
        return jsonify({
            'success': True, 
            'server_id': server_id,
            'message': f'SMTP server "{data.get("name")}" added successfully'
        })
    except ValueError as ve:
        error_msg = f'Invalid data format: {str(ve)}'
        print(f"✗ Validation error: {error_msg}")
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"✗ Error adding SMTP server: {str(e)}")
        print(f"Trace: {error_trace}")
        return jsonify({
            'error': str(e), 
            'message': 'Failed to add SMTP server. Please check all fields and try again.',
            'trace': error_trace
        }), 500

@app.route('/api/pop3/test', methods=['POST'])
def api_test_pop3():
    """Test POP3 connection"""
    try:
        import poplib
        data = request.json if request.is_json else request.form.to_dict()
        
        pop3_host = data.get('pop3_host')
        pop3_port = int(data.get('pop3_port', 995))
        username = data.get('username')
        password = data.get('password')
        use_ssl = data.get('use_ssl', True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.lower() in ('true', 'on', '1')
        
        if not pop3_host or not username or not password:
            return jsonify({'error': 'POP3 host, username and password are required'}), 400
        
        # Decode password if URL-encoded
        import urllib.parse
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass
        
        # Test POP3 connection
        try:
            if use_ssl or pop3_port == 995:
                pop3 = poplib.POP3_SSL(pop3_host, pop3_port, timeout=30)
            else:
                pop3 = poplib.POP3(pop3_host, pop3_port, timeout=30)
            
            # Login
            pop3.user(username)
            pop3.pass_(password)
            
            # Get mailbox stats
            num_messages, mailbox_size = pop3.stat()
            
            pop3.quit()
            
            return jsonify({
                'success': True,
                'message': f'POP3 connection successful! Found {num_messages} emails ({mailbox_size} bytes).'
            })
            
        except Exception as conn_error:
            return jsonify({'error': f'POP3 connection failed: {str(conn_error)}'}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/inbox/fetch-pop3/<int:account_id>')
def api_fetch_pop3(account_id):
    """Fetch emails from POP3 server"""
    try:
        import poplib
        limit = request.args.get('limit', 100, type=int)  # Increased limit to fetch more emails
        
        # Get account config
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', account_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Account not found'}), 404
            account = result.data[0]
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Account not found'}), 404
            
            account = dict(row)
        
        pop3_host = account.get('pop3_host')
        if not pop3_host:
            return jsonify({'error': 'POP3 settings not configured for this account'}), 400
        
        pop3_port = int(account.get('pop3_port', 995))
        username = account.get('username', '')
        password = account.get('password', '')
        use_ssl = account.get('pop3_ssl', 1)
        
        if not username or not password:
            return jsonify({'error': 'Email credentials missing'}), 400
        
        # Connect to POP3 server
        try:
            if use_ssl or pop3_port == 995:
                pop3 = poplib.POP3_SSL(pop3_host, pop3_port, timeout=30)
            else:
                pop3 = poplib.POP3(pop3_host, pop3_port, timeout=30)
            
            pop3.user(username)
            pop3.pass_(password)
        except Exception as conn_error:
            return jsonify({'error': f'Failed to connect to POP3 server: {str(conn_error)}'}), 500
        
        # Get message list
        num_messages, _ = pop3.stat()
        
        # Fetch last N messages (most recent)
        start_msg = max(1, num_messages - limit + 1)
        
        emails = []
        for i in range(num_messages, start_msg - 1, -1):
            try:
                # Get message
                response, lines, octets = pop3.retr(i)
                msg_content = b'\r\n'.join(lines)
                msg = email.message_from_bytes(msg_content)
                
                # Decode subject
                subject = msg.get('Subject', '')
                if subject:
                    decoded_parts = decode_header(subject)
                    subject = ''
                    for part, encoding in decoded_parts:
                        if isinstance(part, bytes):
                            subject += part.decode(encoding or 'utf-8', errors='ignore')
                        else:
                            subject += part
                
                # Decode from
                from_addr = msg.get('From', '')
                if from_addr:
                    decoded_parts = decode_header(from_addr)
                    from_decoded = ''
                    for part, encoding in decoded_parts:
                        if isinstance(part, bytes):
                            from_decoded += part.decode(encoding or 'utf-8', errors='ignore')
                        else:
                            from_decoded += str(part)
                    from_addr = from_decoded
                
                # Get body
                body = ''
                html_body = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain' and not body:
                            try:
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                body = str(part.get_payload())
                        elif content_type == 'text/html' and not html_body:
                            try:
                                html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            except:
                                html_body = str(part.get_payload())
                else:
                    content_type = msg.get_content_type()
                    payload = msg.get_payload(decode=True)
                    if payload:
                        try:
                            content = payload.decode('utf-8', errors='ignore')
                            if content_type == 'text/html':
                                html_body = content
                            else:
                                body = content
                        except:
                            body = str(msg.get_payload())
                
                emails.append({
                    'uid': str(i),
                    'subject': subject,
                    'from': from_addr,
                    'to': msg.get('To', ''),
                    'date': msg.get('Date', ''),
                    'body': body[:1000] if body else '',
                    'html': html_body[:5000] if html_body else '',
                    'unread': True
                })
                
            except Exception as email_error:
                print(f"Error processing POP3 message {i}: {email_error}")
                continue
        
        pop3.quit()
        
        return jsonify({
            'success': True,
            'emails': emails,
            'total': len(emails),
            'protocol': 'POP3'
        })
        
    except Exception as e:
        import traceback
        print(f"Error fetching POP3 emails: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/imap/test', methods=['POST'])
def api_test_imap():
    """Test IMAP connection"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        imap_host = data.get('imap_host')
        imap_port = int(data.get('imap_port', 993))
        username = data.get('username')
        password = data.get('password')
        
        if not imap_host or not username or not password:
            return jsonify({'error': 'IMAP host, username and password are required'}), 400
        
        # Decode password if URL-encoded
        import urllib.parse
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass
        
        # Test IMAP connection
        try:
            if imap_port == 993:
                imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=30)
            else:
                imap = imaplib.IMAP4(imap_host, imap_port, timeout=30)
                try:
                    imap.starttls()
                except:
                    pass
            
            # Login
            imap.login(username, password)
            
            # Try to select INBOX
            status, _ = imap.select('INBOX', readonly=True)
            if status != 'OK':
                imap.logout()
                return jsonify({'error': 'Could not access INBOX'}), 500
            
            # Get email count
            status, messages = imap.search(None, 'ALL')
            email_count = len(messages[0].split()) if status == 'OK' and messages[0] else 0
            
            imap.logout()
            
            return jsonify({
                'success': True,
                'message': f'IMAP connection successful! Found {email_count} emails in INBOX.'
            })
            
        except Exception as conn_error:
            return jsonify({'error': f'IMAP connection failed: {str(conn_error)}'}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/smtp/test', methods=['POST'])
def api_test_smtp():
    """Test SMTP connection"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        import smtplib
        import urllib.parse
        
        host = data.get('host')
        port = int(data.get('port'))
        username = data.get('username')
        password = data.get('password')
        
        # Decode password if it's URL-encoded (handles special characters like *)
        if password:
            try:
                password = urllib.parse.unquote(password)
            except:
                pass  # If decoding fails, use as-is
            # Ensure it's a string, not bytes
            if isinstance(password, bytes):
                password = password.decode('utf-8')
        
        use_ssl = data.get('use_ssl', True)
        if isinstance(use_ssl, str):
            use_ssl = use_ssl.lower() in ('true', 'on', '1')
        use_tls = data.get('use_tls', False)
        if isinstance(use_tls, str):
            use_tls = use_tls.lower() in ('true', 'on', '1')
        
        # Test connection with timeout
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=30)
            else:
                server = smtplib.SMTP(host, port, timeout=30)
                if use_tls:
                    server.starttls()
            
            # Test login
            server.login(username, password)
            
            # Test sending (NOOP command)
            server.noop()
            
            server.quit()
            
            return jsonify({'success': True, 'message': 'Connection test successful!'})
        except smtplib.SMTPConnectError as e:
            return jsonify({'error': f'Connection failed: {str(e)}. Check host and port.'}), 500
        except smtplib.SMTPAuthenticationError as e:
            return jsonify({'error': f'Authentication failed: {str(e)}. Check username and password.'}), 500
        except smtplib.SMTPException as e:
            return jsonify({'error': f'SMTP error: {str(e)}'}), 500
        except Exception as e:
            return jsonify({'error': f'Connection error: {str(e)}'}), 500
            
    except Exception as e:
        import traceback
        return jsonify({'error': f'Test failed: {str(e)}', 'details': traceback.format_exc()}), 500

@app.route('/api/smtp/update/<int:server_id>', methods=['POST', 'PUT'])
def api_update_smtp(server_id):
    """Update existing SMTP server settings"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        # Check if using Supabase
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if server exists
            result = db.supabase.client.table('smtp_servers').select('id').eq('id', server_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Server not found'}), 404
            
            # Build update data
            update_data = {}
            
            if 'name' in data:
                update_data['name'] = data['name']
            if 'host' in data:
                update_data['host'] = data['host']
            if 'port' in data:
                update_data['port'] = int(data['port'])
            if 'username' in data:
                update_data['username'] = data['username']
            if 'password' in data and data['password']:
                import urllib.parse
                from core.encryption import get_encryption_manager
                encryptor = get_encryption_manager()
                
                password = data['password']
                try:
                    password = urllib.parse.unquote(password)
                except:
                    pass
                # Encrypt password before storing
                update_data['password'] = encryptor.encrypt(password)
            if 'use_ssl' in data:
                use_ssl = data['use_ssl']
                if isinstance(use_ssl, str):
                    use_ssl = use_ssl.lower() in ('true', 'on', '1')
                update_data['use_ssl'] = 1 if use_ssl else 0
            if 'use_tls' in data:
                use_tls = data['use_tls']
                if isinstance(use_tls, str):
                    use_tls = use_tls.lower() in ('true', 'on', '1')
                update_data['use_tls'] = 1 if use_tls else 0
            if 'imap_host' in data:
                update_data['imap_host'] = data['imap_host']
            if 'imap_port' in data:
                update_data['imap_port'] = int(data['imap_port']) if data['imap_port'] else 993
            if 'save_to_sent' in data:
                save_to_sent = data['save_to_sent']
                if isinstance(save_to_sent, str):
                    save_to_sent = save_to_sent.lower() in ('true', 'on', '1')
                update_data['save_to_sent'] = 1 if save_to_sent else 0
            if 'max_per_hour' in data:
                update_data['max_per_hour'] = int(data['max_per_hour'])
            if 'pop3_host' in data:
                update_data['pop3_host'] = data['pop3_host']
            if 'pop3_port' in data:
                update_data['pop3_port'] = int(data['pop3_port']) if data['pop3_port'] else 995
            if 'pop3_ssl' in data:
                pop3_ssl = data['pop3_ssl']
                if isinstance(pop3_ssl, str):
                    pop3_ssl = pop3_ssl.lower() in ('true', 'on', '1')
                update_data['pop3_ssl'] = 1 if pop3_ssl else 0
            if 'pop3_leave_on_server' in data:
                pop3_leave = data['pop3_leave_on_server']
                if isinstance(pop3_leave, str):
                    pop3_leave = pop3_leave.lower() in ('true', 'on', '1')
                update_data['pop3_leave_on_server'] = 1 if pop3_leave else 0
            if 'incoming_protocol' in data:
                update_data['incoming_protocol'] = data['incoming_protocol']
            
            if not update_data:
                return jsonify({'error': 'No fields to update'}), 400
            
            # Execute update
            db.supabase.client.table('smtp_servers').update(update_data).eq('id', server_id).execute()
            
            return jsonify({'success': True, 'message': 'Email account updated successfully'})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Check if server exists
            cursor.execute("SELECT id FROM smtp_servers WHERE id = ?", (server_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Server not found'}), 404
            
            # Build update query dynamically based on provided fields
            updates = []
            params = []
            
            if 'name' in data:
                updates.append("name = ?")
                params.append(data['name'])
            if 'host' in data:
                updates.append("host = ?")
                params.append(data['host'])
            if 'port' in data:
                updates.append("port = ?")
                params.append(int(data['port']))
            if 'username' in data:
                updates.append("username = ?")
                params.append(data['username'])
            if 'password' in data and data['password']:
                import urllib.parse
                from core.encryption import get_encryption_manager
                encryptor = get_encryption_manager()
                
                password = data['password']
                try:
                    password = urllib.parse.unquote(password)
                except:
                    pass
                # Encrypt password before storing
                encrypted_password = encryptor.encrypt(password)
                updates.append("password = ?")
                params.append(encrypted_password)
            if 'use_ssl' in data:
                use_ssl = data['use_ssl']
                if isinstance(use_ssl, str):
                    use_ssl = use_ssl.lower() in ('true', 'on', '1')
                updates.append("use_ssl = ?")
                params.append(1 if use_ssl else 0)
            if 'use_tls' in data:
                use_tls = data['use_tls']
                if isinstance(use_tls, str):
                    use_tls = use_tls.lower() in ('true', 'on', '1')
                updates.append("use_tls = ?")
                params.append(1 if use_tls else 0)
            if 'imap_host' in data:
                updates.append("imap_host = ?")
                params.append(data['imap_host'])
            if 'imap_port' in data:
                updates.append("imap_port = ?")
                params.append(int(data['imap_port']) if data['imap_port'] else 993)
            if 'save_to_sent' in data:
                save_to_sent = data['save_to_sent']
                if isinstance(save_to_sent, str):
                    save_to_sent = save_to_sent.lower() in ('true', 'on', '1')
                updates.append("save_to_sent = ?")
                params.append(1 if save_to_sent else 0)
            if 'max_per_hour' in data:
                updates.append("max_per_hour = ?")
                params.append(int(data['max_per_hour']))
            
            # POP3 settings
            if 'pop3_host' in data:
                updates.append("pop3_host = ?")
                params.append(data['pop3_host'])
            if 'pop3_port' in data:
                updates.append("pop3_port = ?")
                params.append(int(data['pop3_port']) if data['pop3_port'] else 995)
            if 'pop3_ssl' in data:
                pop3_ssl = data['pop3_ssl']
                if isinstance(pop3_ssl, str):
                    pop3_ssl = pop3_ssl.lower() in ('true', 'on', '1')
                updates.append("pop3_ssl = ?")
                params.append(1 if pop3_ssl else 0)
            if 'pop3_leave_on_server' in data:
                pop3_leave = data['pop3_leave_on_server']
                if isinstance(pop3_leave, str):
                    pop3_leave = pop3_leave.lower() in ('true', 'on', '1')
                updates.append("pop3_leave_on_server = ?")
                params.append(1 if pop3_leave else 0)
            if 'incoming_protocol' in data:
                updates.append("incoming_protocol = ?")
                params.append(data['incoming_protocol'])
            
            if not updates:
                return jsonify({'error': 'No fields to update'}), 400
            
            # Add server_id to params
            params.append(server_id)
            
            # Execute update
            query = f"UPDATE smtp_servers SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Email account updated successfully'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500

@app.route('/api/smtp/list', methods=['GET'])
@require_auth
def api_list_smtp(user_id):
    """Get list of all SMTP servers"""
    try:
        servers = db.get_smtp_servers(active_only=False, user_id=user_id)
        # Get default server ID
        default_server_id = None
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            default_result = db.supabase.client.table('smtp_servers').select('id').eq('is_default', 1).limit(1).execute()
            if default_result.data and len(default_result.data) > 0:
                default_server_id = default_result.data[0]['id']
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM smtp_servers WHERE is_default = 1 LIMIT 1")
            default_row = cursor.fetchone()
            default_server_id = default_row[0] if default_row else None
        
        # If no default, set first active server as default
        if not default_server_id and servers:
            for server in servers:
                if server.get('is_active'):
                    default_server_id = server['id']
                    if hasattr(db, 'use_supabase') and db.use_supabase:
                        # Use Supabase
                        db.supabase.client.table('smtp_servers').update({'is_default': 1}).eq('id', default_server_id).execute()
                    else:
                        # SQLite
                        conn = db.connect()
                        cursor = conn.cursor()
                        cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (default_server_id,))
                        conn.commit()
                    break
        
        return jsonify({'success': True, 'servers': servers, 'default_server_id': default_server_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/set-default/<int:server_id>', methods=['POST'])
def api_set_default_smtp(server_id):
    """Set default SMTP server for sending"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            # First, get all servers with is_default = 1 and unset them
            default_servers = db.supabase.client.table('smtp_servers').select('id').eq('is_default', 1).execute()
            if default_servers.data:
                for server in default_servers.data:
                    db.supabase.client.table('smtp_servers').update({'is_default': 0}).eq('id', server['id']).execute()
            
            # Set new default
            result = db.supabase.client.table('smtp_servers').update({'is_default': 1}).eq('id', server_id).execute()
            
            if result.data and len(result.data) > 0:
                return jsonify({'success': True, 'message': 'Default SMTP server updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Unset all defaults
            cursor.execute("UPDATE smtp_servers SET is_default = 0")
            
            # Set new default
            cursor.execute("UPDATE smtp_servers SET is_default = 1 WHERE id = ?", (server_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True, 'message': 'Default SMTP server updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/get/<int:server_id>', methods=['GET'])
def api_get_smtp(server_id):
    """Get SMTP server configuration with decrypted password"""
    try:
        from core.encryption import get_encryption_manager
        encryptor = get_encryption_manager()
        
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            result = db.supabase.client.table('smtp_servers').select('*').eq('id', server_id).execute()
            if result.data and len(result.data) > 0:
                server = result.data[0]
                # Decrypt password
                if server.get('password'):
                    try:
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        pass  # If decryption fails, keep as-is
                return jsonify({'success': True, 'server': server})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM smtp_servers WHERE id = ?", (server_id,))
            row = cursor.fetchone()
            
            if row:
                server = dict(row)
                # Decrypt password
                if server.get('password'):
                    try:
                        server['password'] = encryptor.decrypt(server['password'])
                    except:
                        pass  # If decryption fails, keep as-is
                return jsonify({'success': True, 'server': server})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/delete/<int:server_id>', methods=['DELETE'])
@require_auth
def api_delete_smtp(server_id, user_id):
    """Delete SMTP server"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if server exists and belongs to user
            result = db.supabase.client.table('smtp_servers').select('id').eq('id', server_id).eq('user_id', user_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'SMTP server not found or access denied'}), 404
            
            # Delete server
            db.supabase.client.table('smtp_servers').delete().eq('id', server_id).execute()
            
            return jsonify({'success': True, 'message': 'SMTP server deleted'})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Check if server exists and belongs to user
            cursor.execute("SELECT id FROM smtp_servers WHERE id = ? AND user_id = ?", (server_id, user_id))
            if not cursor.fetchone():
                return jsonify({'error': 'SMTP server not found or access denied'}), 404
            
            # Delete server
            cursor.execute("DELETE FROM smtp_servers WHERE id = ?", (server_id,))
            conn.commit()
            
            return jsonify({'success': True, 'message': 'SMTP server deleted'})
    except Exception as e:
        import traceback
        print(f"Error deleting SMTP server: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/smtp/toggle/<int:server_id>', methods=['POST'])
def api_toggle_smtp(server_id):
    """Toggle SMTP server active status"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        is_active = data.get('is_active', 1)
        if isinstance(is_active, str):
            is_active = 1 if is_active.lower() in ('true', 'on', '1') else 0
        
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase
            result = db.supabase.client.table('smtp_servers').update({'is_active': is_active}).eq('id', server_id).execute()
            
            if result.data and len(result.data) > 0:
                return jsonify({'success': True, 'message': 'Server status updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("UPDATE smtp_servers SET is_active = ? WHERE id = ?", (is_active, server_id))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True, 'message': 'Server status updated'})
            else:
                return jsonify({'error': 'Server not found'}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/save', methods=['POST'])
def api_save_template():
    """Save template"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            data = request.form.to_dict()
        
        # Validate required fields
        name = data.get('name', '').strip()
        category = data.get('category', 'Other').strip() or 'Other'
        html_content = data.get('html_content', '').strip()
        
        if not name:
            return jsonify({'error': 'Template name is required'}), 400
        
        if not html_content:
            return jsonify({'error': 'HTML content is required'}), 400
        
        template_id = db.save_template(
            name=name,
            category=category,
            html_content=html_content
        )
        return jsonify({'success': True, 'template_id': template_id, 'message': 'Template saved successfully'})
    except Exception as e:
        import traceback
        print(f"Error saving template: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/list', methods=['GET'])
def api_list_templates():
    """Get all templates"""
    try:
        category = request.args.get('category')
        templates = db.get_templates(category=category)
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/<int:template_id>', methods=['GET'])
def api_get_template(template_id):
    """Get a single template"""
    try:
        templates = db.get_templates()
        template = next((t for t in templates if t['id'] == template_id), None)
        if template:
            return jsonify({'success': True, 'template': template})
        else:
            return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/templates/delete/<int:template_id>', methods=['DELETE'])
def api_delete_template(template_id):
    """Delete a template"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if template exists
            result = db.supabase.client.table('templates').select('id').eq('id', template_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Template not found'}), 404
            
            # Delete template
            db.supabase.client.table('templates').delete().eq('id', template_id).execute()
            
            return jsonify({'success': True, 'message': 'Template deleted'})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return jsonify({'success': True, 'message': 'Template deleted'})
            else:
                return jsonify({'error': 'Template not found'}), 404
    except Exception as e:
        import traceback
        print(f"Error deleting template: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns')
@require_auth
def api_get_campaigns(user_id):
    """Get all campaigns"""
    try:
        campaigns = db.get_campaigns(user_id=user_id)
        return jsonify({'campaigns': campaigns})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/delete/<int:campaign_id>', methods=['DELETE'])
@require_auth
def api_delete_campaign(campaign_id, user_id):
    """Delete a single campaign"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Check if campaign exists and belongs to user
            result = db.supabase.client.table('campaigns').select('id').eq('id', campaign_id).eq('user_id', user_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Campaign not found or access denied'}), 404
            
            # Delete related data first (CASCADE should handle this, but doing explicitly)
            db.supabase.client.table('email_queue').delete().eq('campaign_id', campaign_id).execute()
            # Note: campaign_recipients and tracking tables might not exist, handle gracefully
            try:
                db.supabase.client.table('campaign_recipients').delete().eq('campaign_id', campaign_id).execute()
            except:
                pass
            try:
                db.supabase.client.table('tracking').delete().eq('campaign_id', campaign_id).execute()
            except:
                pass
            
            # Delete campaign
            db.supabase.client.table('campaigns').delete().eq('id', campaign_id).execute()
            
            return jsonify({'success': True, 'message': 'Campaign deleted'})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Verify ownership
            cursor.execute("SELECT id FROM campaigns WHERE id = ? AND user_id = ?", (campaign_id, user_id))
            if not cursor.fetchone():
                return jsonify({'error': 'Campaign not found or access denied'}), 404
            
            # Delete campaign and related data
            cursor.execute("DELETE FROM email_queue WHERE campaign_id = ?", (campaign_id,))
            cursor.execute("DELETE FROM campaign_recipients WHERE campaign_id = ?", (campaign_id,))
            try:
                cursor.execute("DELETE FROM tracking WHERE campaign_id = ?", (campaign_id,))
            except:
                pass
            cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
            
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Campaign deleted'})
    except Exception as e:
        import traceback
        print(f"Error deleting campaign: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/delete/bulk', methods=['POST'])
@require_auth
def api_delete_campaigns_bulk(user_id):
    """Delete multiple campaigns"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        campaign_ids = data.get('campaign_ids', [])
        
        if not campaign_ids:
            return jsonify({'error': 'No campaign IDs provided'}), 400
        
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Verify ownership - only delete campaigns that belong to user
            result = db.supabase.client.table('campaigns').select('id').eq('user_id', user_id).in_('id', campaign_ids).execute()
            valid_ids = [c['id'] for c in (result.data or [])]
            
            if not valid_ids:
                return jsonify({'error': 'No valid campaigns found or access denied'}), 404
            
            # Delete related data first
            db.supabase.client.table('email_queue').delete().in_('campaign_id', valid_ids).execute()
            try:
                db.supabase.client.table('campaign_recipients').delete().in_('campaign_id', valid_ids).execute()
            except:
                pass
            try:
                db.supabase.client.table('tracking').delete().in_('campaign_id', valid_ids).execute()
            except:
                pass
            
            # Delete campaigns
            db.supabase.client.table('campaigns').delete().in_('id', valid_ids).execute()
            
            return jsonify({'success': True, 'deleted_count': len(valid_ids)})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Verify ownership and build placeholders
            placeholders = ','.join(['?'] * len(campaign_ids))
            cursor.execute(f"SELECT id FROM campaigns WHERE id IN ({placeholders}) AND user_id = ?", campaign_ids + [user_id])
            valid_ids = [row[0] for row in cursor.fetchall()]
            
            if not valid_ids:
                return jsonify({'error': 'No valid campaigns found or access denied'}), 404
            
            valid_placeholders = ','.join(['?'] * len(valid_ids))
            
            # Delete campaigns and related data
            cursor.execute(f"DELETE FROM email_queue WHERE campaign_id IN ({valid_placeholders})", valid_ids)
            cursor.execute(f"DELETE FROM campaign_recipients WHERE campaign_id IN ({valid_placeholders})", valid_ids)
            try:
                cursor.execute(f"DELETE FROM tracking WHERE campaign_id IN ({valid_placeholders})", valid_ids)
            except:
                pass
            cursor.execute(f"DELETE FROM campaigns WHERE id IN ({valid_placeholders})", valid_ids)
            
            conn.commit()
            
            return jsonify({'success': True, 'deleted_count': len(valid_ids)})
    except Exception as e:
        import traceback
        print(f"Error deleting campaigns: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/delete/drafts', methods=['DELETE'])
@require_auth
def api_delete_draft_campaigns(user_id):
    """Delete all draft campaigns for the current user"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        if use_supabase:
            # Get all draft campaign IDs for this user
            result = db.supabase.client.table('campaigns').select('id').eq('status', 'draft').eq('user_id', user_id).execute()
            draft_ids = [c['id'] for c in (result.data or [])]
            
            if not draft_ids:
                return jsonify({'success': True, 'deleted_count': 0, 'message': 'No draft campaigns found'})
            
            # Delete related data first
            db.supabase.client.table('email_queue').delete().in_('campaign_id', draft_ids).execute()
            try:
                db.supabase.client.table('campaign_recipients').delete().in_('campaign_id', draft_ids).execute()
            except:
                pass
            try:
                db.supabase.client.table('tracking').delete().in_('campaign_id', draft_ids).execute()
            except:
                pass
            
            # Delete campaigns
            db.supabase.client.table('campaigns').delete().in_('id', draft_ids).execute()
            
            return jsonify({'success': True, 'deleted_count': len(draft_ids)})
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            
            # Get all draft campaign IDs for this user
            cursor.execute("SELECT id FROM campaigns WHERE status = 'draft' AND user_id = ?", (user_id,))
            draft_ids = [row[0] for row in cursor.fetchall()]
            
            if not draft_ids:
                return jsonify({'success': True, 'deleted_count': 0, 'message': 'No draft campaigns found'})
            
            # Build placeholders
            placeholders = ','.join(['?'] * len(draft_ids))
            
            # Delete campaigns and related data
            cursor.execute(f"DELETE FROM email_queue WHERE campaign_id IN ({placeholders})", draft_ids)
            cursor.execute(f"DELETE FROM campaign_recipients WHERE campaign_id IN ({placeholders})", draft_ids)
            try:
                cursor.execute(f"DELETE FROM tracking WHERE campaign_id IN ({placeholders})", draft_ids)
            except:
                pass
            cursor.execute(f"DELETE FROM campaigns WHERE id IN ({placeholders})", draft_ids)
            
            conn.commit()
            
            return jsonify({'success': True, 'deleted_count': len(draft_ids)})
    except Exception as e:
        import traceback
        print(f"Error deleting draft campaigns: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/pause/<int:campaign_id>', methods=['POST'])
@require_auth
def api_pause_campaign(campaign_id, user_id):
    """Pause a sending campaign"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        # Get campaign
        if use_supabase:
            result = db.supabase.client.table('campaigns').select('id, status, user_id').eq('id', campaign_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = result.data[0]
        else:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id, status, user_id FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = {'id': row[0], 'status': row[1], 'user_id': row[2]}
        
        # Check if campaign belongs to user
        if campaign.get('user_id') != user_id:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Only allow pausing if status is 'sending'
        if campaign.get('status') != 'sending':
            return jsonify({'error': f'Can only pause campaigns with status "sending" (current: {campaign.get("status")})'}), 400
        
        # Update campaign status to 'paused'
        if use_supabase:
            db.supabase.client.table('campaigns').update({'status': 'paused'}).eq('id', campaign_id).execute()
        else:
            cursor.execute("UPDATE campaigns SET status = 'paused' WHERE id = ?", (campaign_id,))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Campaign paused successfully'})
    except Exception as e:
        import traceback
        print(f"Error pausing campaign: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/resume/<int:campaign_id>', methods=['POST'])
@require_auth
def api_resume_campaign(campaign_id, user_id):
    """Resume a paused/stopped campaign"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        # Get campaign and initialize connection if using SQLite
        conn = None
        cursor = None
        if use_supabase:
            result = db.supabase.client.table('campaigns').select('id, status, user_id').eq('id', campaign_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = result.data[0]
        else:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id, status, user_id FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = {'id': row[0], 'status': row[1], 'user_id': row[2]}
        
        # Check if campaign belongs to user
        if campaign.get('user_id') != user_id:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Only allow resuming if status is 'paused' or 'stopped'
        current_status = campaign.get('status')
        if current_status not in ['paused', 'stopped']:
            return jsonify({'error': f'Can only resume campaigns with status "paused" or "stopped" (current: {current_status})'}), 400
        
        # Update campaign status to 'sending' and reset skipped queue items back to pending
        if use_supabase:
            db.supabase.client.table('campaigns').update({'status': 'sending'}).eq('id', campaign_id).execute()
            # Reset skipped queue items back to pending (those skipped due to pause/stop)
            # Get skipped items with pause/stop messages - do it in batches to avoid query complexity
            try:
                # Get all skipped items for this campaign
                skipped_result = db.supabase.client.table('email_queue').select('id, error_message').eq('campaign_id', campaign_id).eq('status', 'skipped').execute()
                if skipped_result.data:
                    # Filter in Python for pause/stop messages
                    paused_stopped_ids = [
                        item['id'] for item in skipped_result.data 
                        if item.get('error_message') and ('Campaign is paused' in item['error_message'] or 'Campaign is stopped' in item['error_message'])
                    ]
                    # Update them back to pending
                    if paused_stopped_ids:
                        for skipped_id in paused_stopped_ids:
                            db.supabase.client.table('email_queue').update({
                                'status': 'pending',
                                'error_message': None
                            }).eq('id', skipped_id).execute()
            except Exception as resume_error:
                print(f"⚠ Could not reset skipped emails on resume: {resume_error}")
                # Continue anyway - campaign is resumed
        else:
            # Use the connection and cursor we already have
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            cursor.execute("""
                UPDATE email_queue 
                SET status = 'pending', error_message = NULL
                WHERE campaign_id = ? 
                AND status = 'skipped' 
                AND (error_message LIKE '%Campaign is paused%' OR error_message LIKE '%Campaign is stopped%')
            """, (campaign_id,))
            conn.commit()
        
        # Ensure email sender is running to process the resumed campaign
        global email_sender
        import threading
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started after resuming campaign {campaign_id} ({email_delay} sec delay)")
                else:
                    print("ℹ Email sender already running, resumed campaign will be processed")
            except Exception as e:
                print(f"✗ Error starting email sender after resume: {e}")
        
        sender_thread = threading.Thread(target=start_sender, daemon=True)
        sender_thread.start()
        
        # Give it a moment to start
        import time
        time.sleep(0.5)
        
        return jsonify({'success': True, 'message': 'Campaign resumed successfully'})
    except Exception as e:
        import traceback
        print(f"Error resuming campaign: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/stop/<int:campaign_id>', methods=['POST'])
@require_auth
def api_stop_campaign(campaign_id, user_id):
    """Stop a sending campaign (permanent stop)"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        # Get campaign
        if use_supabase:
            result = db.supabase.client.table('campaigns').select('id, status, user_id').eq('id', campaign_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = result.data[0]
        else:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT id, status, user_id FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = {'id': row[0], 'status': row[1], 'user_id': row[2]}
        
        # Check if campaign belongs to user
        if campaign.get('user_id') != user_id:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Only allow stopping if status is 'sending' or 'paused'
        current_status = campaign.get('status')
        if current_status not in ['sending', 'paused']:
            return jsonify({'error': f'Can only stop campaigns with status "sending" or "paused" (current: {current_status})'}), 400
        
        # Update campaign status to 'stopped'
        if use_supabase:
            db.supabase.client.table('campaigns').update({'status': 'stopped'}).eq('id', campaign_id).execute()
            # Mark pending/processing queue items as skipped
            db.supabase.client.table('email_queue').update({
                'status': 'skipped',
                'error_message': 'Campaign stopped by user'
            }).eq('campaign_id', campaign_id).in_('status', ['pending', 'processing']).execute()
        else:
            cursor.execute("UPDATE campaigns SET status = 'stopped' WHERE id = ?", (campaign_id,))
            cursor.execute("""
                UPDATE email_queue 
                SET status = 'skipped', error_message = 'Campaign stopped by user'
                WHERE campaign_id = ? 
                AND status IN ('pending', 'processing')
            """, (campaign_id,))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Campaign stopped successfully'})
    except Exception as e:
        import traceback
        print(f"Error stopping campaign: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/send/<int:campaign_id>', methods=['POST'])
@require_auth
def api_send_campaign(campaign_id, user_id):
    """Send a draft campaign"""
    try:
        # Check if using Supabase FIRST before trying to use SQLite methods
        use_supabase = hasattr(db, 'use_supabase') and db.use_supabase
        
        # Get campaign
        if use_supabase:
            result = db.supabase.client.table('campaigns').select('*').eq('id', campaign_id).execute()
            if not result.data or len(result.data) == 0:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = result.data[0]
        else:
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Campaign not found'}), 404
            campaign = dict(row)
        
        # Check if campaign belongs to user
        if campaign.get('user_id') != user_id:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Check if campaign is draft
        if campaign.get('status') != 'draft':
            return jsonify({'error': f'Campaign is not a draft (status: {campaign.get("status")})'}), 400
        
        # Get recipients for this user
        recipients = db.get_recipients(user_id=user_id)
        if not recipients or len(recipients) == 0:
            return jsonify({'error': 'No recipients found. Please add recipients first.'}), 400
        
        recipient_ids = [r['id'] for r in recipients]
        
        # Get SMTP servers for this user
        smtp_servers = db.get_smtp_servers(user_id=user_id, active_only=True)
        if not smtp_servers or len(smtp_servers) == 0:
            return jsonify({'error': 'No active SMTP server configured. Please add an SMTP server first.'}), 400
        
        # Get selected SMTP servers from request or use all active
        selected_smtp_servers = request.json.get('selected_smtp_servers', []) if request.is_json else request.form.getlist('selected_smtp_servers')
        if not selected_smtp_servers:
            selected_smtp_servers = [s['id'] for s in smtp_servers]
        
        # Update campaign status to 'sending'
        if use_supabase:
            db.supabase.client.table('campaigns').update({'status': 'sending'}).eq('id', campaign_id).execute()
        else:
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            conn.commit()
        
        # Add to queue with round-robin distribution
        try:
            if request.is_json:
                emails_per_server = int(request.json.get('emails_per_server', 20))
            else:
                emails_per_server = int(request.form.get('emails_per_server', 20))
        except:
            emails_per_server = 20
        
        # Add to queue with selected SMTP servers
        added_count = db.add_to_queue(
            campaign_id, 
            recipient_ids, 
            smtp_server_id=None, 
            emails_per_server=emails_per_server,
            selected_smtp_servers=selected_smtp_servers
        )
        
        if added_count == 0:
            return jsonify({'error': 'No emails were added to queue. Check if recipients are unsubscribed or already queued.'}), 400
        
        print(f"Added {added_count} emails to queue for campaign {campaign_id}")
        
        # Start sending in background thread
        import threading
        global email_sender
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for campaign {campaign_id} with {len(recipient_ids)} recipients ({email_delay} sec delay)")
                else:
                    print("ℹ Email sender already running, queue will be processed")
            except Exception as e:
                print(f"✗ Error starting email sender: {e}")
                import traceback
                traceback.print_exc()
        
        # Start in background thread
        sender_thread = threading.Thread(target=start_sender, daemon=True)
        sender_thread.start()
        
        return jsonify({
            'success': True, 
            'message': f'Campaign queued successfully. {added_count} emails added to queue.',
            'queued_count': added_count,
            'total_recipients': len(recipient_ids)
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error sending campaign: {error_details}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaigns/send/bulk', methods=['POST'])
def api_send_campaigns_bulk():
    """Send multiple draft campaigns"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        campaign_ids = data.get('campaign_ids', [])
        
        if not campaign_ids:
            return jsonify({'error': 'No campaign IDs provided'}), 400
        
        conn = db.connect()
        cursor = conn.cursor()
        
        # Verify all campaigns are drafts
        placeholders = ','.join(['?'] * len(campaign_ids))
        cursor.execute(f"SELECT id, status FROM campaigns WHERE id IN ({placeholders})", campaign_ids)
        campaigns = cursor.fetchall()
        
        if len(campaigns) != len(campaign_ids):
            return jsonify({'error': 'Some campaigns not found'}), 404
        
        # Check all are drafts
        non_drafts = [c[0] for c in campaigns if c[1] != 'draft']
        if non_drafts:
            return jsonify({'error': f'Campaigns {non_drafts} are not drafts'}), 400
        
        # Get recipients
        recipients = db.get_recipients()
        if not recipients:
            return jsonify({'error': 'No recipients found'}), 400
        
        recipient_ids = [r['id'] for r in recipients]
        
        # Get default SMTP server
        default_server = db.get_default_smtp_server()
        if not default_server:
            smtp_servers = db.get_smtp_servers()
            if not smtp_servers:
                return jsonify({'error': 'No SMTP server configured'}), 400
            smtp_id = smtp_servers[0]['id']
        else:
            smtp_id = default_server['id']
        
        # Update all campaigns to 'sending' and add to queue with round-robin distribution
        emails_per_server = 20  # 20 emails per SMTP server
        sent_count = 0
        for campaign_id in campaign_ids:
            cursor.execute("UPDATE campaigns SET status = 'sending' WHERE id = ?", (campaign_id,))
            db.add_to_queue(campaign_id, recipient_ids, smtp_server_id=None, emails_per_server=emails_per_server)
            sent_count += 1
            print(f"Added {len(recipient_ids)} emails to queue for campaign {campaign_id}")
        
        conn.commit()
        
        # Start sending in background thread
        import threading
        global email_sender
        
        def start_sender():
            try:
                global email_sender
                if not email_sender or not hasattr(email_sender, 'is_sending') or not email_sender.is_sending:
                    # Get delay from settings
                    email_delay = db.get_email_delay()
                    email_sender = EmailSender(db, interval=float(email_delay), max_threads=1)
                    email_sender.start_sending()
                    print(f"✓ Email sender started for {sent_count} campaigns with {len(recipient_ids)} recipients each ({email_delay} sec delay)")
                else:
                    print("ℹ Email sender already running, queue will be processed")
            except Exception as e:
                print(f"✗ Error starting email sender: {e}")
                import traceback
                traceback.print_exc()
        
        # Start in background thread
        sender_thread = threading.Thread(target=start_sender, daemon=True)
        sender_thread.start()
        
        return jsonify({'success': True, 'sent_count': sent_count, 'message': f'{sent_count} campaign(s) queued for sending'})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error sending campaigns: {error_details}")
        return jsonify({'error': str(e)}), 500

# Lead Scraping API Routes
@app.route('/api/leads/scrape', methods=['POST'])
@require_auth
def api_scrape_leads(user_id):
    """Start a lead scraping job"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        icp_description = data.get('icp_description', '')
        lead_type = data.get('lead_type', 'B2B').upper()  # B2B or B2C
        
        if not icp_description:
            return jsonify({'error': 'ICP description is required'}), 400
        
        if lead_type not in ['B2B', 'B2C']:
            return jsonify({'error': 'lead_type must be B2B or B2C'}), 400
        
        from core.lead_scraper import LeadScraper
        scraper = LeadScraper(db)
        
        # Create job record first to get job_id
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            job_id = db.create_scraping_job(icp_description, user_id, lead_type=lead_type)
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            # Add lead_type column if it doesn't exist
            try:
                import sqlite3
                cursor.execute("ALTER TABLE lead_scraping_jobs ADD COLUMN lead_type TEXT DEFAULT 'B2B'")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            cursor.execute("""
                INSERT INTO lead_scraping_jobs (icp_description, status, user_id, lead_type)
                VALUES (?, 'running', ?, ?)
            """, (icp_description, user_id, lead_type))
            job_id = cursor.lastrowid
            conn.commit()
        
        # Use Celery task for background processing
        try:
            from core.tasks import scrape_leads_task
            scrape_leads_task.delay(icp_description, job_id, user_id, lead_type)
        except:
            # Fallback to threading if Celery not available
            import threading
            def run_scraping():
                try:
                    result = scraper.run_full_scraping_job(icp_description, job_id=job_id, user_id=user_id, lead_type=lead_type)
                    print(f"Scraping job {result.get('job_id')} completed: {result.get('leads_found')} leads found, {result.get('verified_leads')} verified")
                except Exception as e:
                    print(f"Error in scraping job: {e}")
                    import traceback
                    traceback.print_exc()
                    # Update job status to failed
                    if hasattr(db, 'use_supabase') and db.use_supabase:
                        db.update_scraping_job(job_id, status='failed')
                    else:
                        conn = db.connect()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE lead_scraping_jobs 
                            SET status = 'failed'
                            WHERE id = ?
                        """, (job_id,))
                        conn.commit()
            
            thread = threading.Thread(target=run_scraping, daemon=True)
            thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Lead scraping job started. Check leads page for results.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/list', methods=['GET'])
@require_auth
def api_list_leads(user_id):
    """Get list of leads"""
    try:
        verified_only = request.args.get('verified_only', 'false').lower() == 'true'
        company_name = request.args.get('company_name', '')
        
        leads = db.get_leads(verified_only=verified_only, company_name=company_name, user_id=user_id)
        # Ensure leads is a list (handle None case)
        if leads is None:
            leads = []
        return jsonify({'success': True, 'leads': leads, 'count': len(leads)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/add', methods=['POST'])
@require_auth
def api_add_lead(user_id):
    """Add a single lead"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        lead_id = db.add_lead(
            name=data.get('name', ''),
            company_name=data.get('company_name', ''),
            domain=data.get('domain', ''),
            email=data.get('email', ''),
            title=data.get('title', ''),
            source=data.get('source', 'manual'),
            user_id=user_id
        )
        
        return jsonify({'success': True, 'lead_id': lead_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/verify/<int:lead_id>', methods=['POST'])
@optional_auth
def api_verify_lead(user_id, lead_id):
    """Verify a lead's email"""
    try:
        from core.email_verifier import EmailVerifier
        verifier = EmailVerifier(db)
        
        # Verify user owns this lead
        if user_id:
            # Check if using Supabase
            if hasattr(db, 'use_supabase') and db.use_supabase:
                lead = db.get_lead_by_id(lead_id)
                if not lead:
                    return jsonify({'error': 'Lead not found'}), 404
                if lead.get('user_id') != user_id:
                    return jsonify({'error': 'Unauthorized'}), 403
            else:
                # SQLite
                conn = db.connect()
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM leads WHERE id = ?", (lead_id,))
                row = cursor.fetchone()
                if row and row[0] != user_id:
                    return jsonify({'error': 'Unauthorized'}), 403
        
        result = verifier.verify_lead_email(lead_id)
        
        # If verified, add to recipients
        if result.get('is_valid') and user_id:
            try:
                lead = db.get_lead_by_id(lead_id)
                if lead and lead.get('email'):
                    # Add to recipients using add_recipients (plural) method
                    name = lead.get('name', '')
                    name_parts = name.split(maxsplit=1) if name else []
                    first_name = name_parts[0] if len(name_parts) > 0 else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    db.add_recipients([{
                        'email': lead['email'],
                        'first_name': first_name,
                        'last_name': last_name,
                        'company': lead.get('company_name', ''),
                        'list_name': 'verified_leads'
                    }], user_id=user_id)
            except Exception as e:
                print(f"Error adding lead to recipients: {e}")
        
        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"Verify lead error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/verify/batch', methods=['POST'])
@optional_auth
def api_verify_leads_batch(user_id):
    """Verify multiple leads"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        lead_ids = data.get('lead_ids', [])
        
        if not lead_ids:
            return jsonify({'error': 'No lead IDs provided'}), 400
        
        # Verify user owns these leads
        if user_id:
            # Check if using Supabase
            if hasattr(db, 'use_supabase') and db.use_supabase:
                # Get all leads and filter by user_id
                valid_ids = []
                for lead_id in lead_ids:
                    lead = db.get_lead_by_id(lead_id)
                    if lead and lead.get('user_id') == user_id:
                        valid_ids.append(lead_id)
                if len(valid_ids) != len(lead_ids):
                    return jsonify({'error': 'Some leads not found or unauthorized'}), 403
                lead_ids = valid_ids
            else:
                # SQLite
                conn = db.connect()
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(lead_ids))
                cursor.execute(f"SELECT id FROM leads WHERE id IN ({placeholders}) AND user_id = ?", lead_ids + [user_id])
                valid_ids = [row[0] for row in cursor.fetchall()]
                if len(valid_ids) != len(lead_ids):
                    return jsonify({'error': 'Some leads not found or unauthorized'}), 403
                lead_ids = valid_ids
        
        from core.email_verifier import EmailVerifier
        verifier = EmailVerifier(db)
        
        results = verifier.verify_batch_leads(lead_ids, delay=1.0)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        import traceback
        print(f"Batch verify error: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/scraping-jobs', methods=['GET'])
@optional_auth
def api_get_scraping_jobs(user_id):
    """Get all scraping jobs"""
    try:
        jobs = db.get_scraping_jobs(user_id=user_id)
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/scraping-job/<int:job_id>/status', methods=['GET'])
def api_get_scraping_job_status(job_id):
    """Get real-time status of a scraping job"""
    try:
        # Check if using Supabase
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Use Supabase methods
            job = db.get_scraping_job(job_id)
            if not job:
                return jsonify({'error': 'Job not found'}), 404
        else:
            # SQLite
            conn = db.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lead_scraping_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Job not found'}), 404
            
            job = dict(row)
        
        return jsonify({
            'success': True,
            'job': {
                'id': job['id'],
                'status': job.get('status', ''),
                'current_step': job.get('current_step', ''),
                'progress_percent': job.get('progress_percent', 0),
                'companies_found': job.get('companies_found', 0),
                'leads_found': job.get('leads_found', 0),
                'verified_leads': job.get('verified_leads', 0)
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/recent', methods=['GET'])
@optional_auth
def api_get_recent_leads(user_id):
    """Get recently added/updated leads for real-time updates"""
    try:
        limit = request.args.get('limit', 50, type=int)
        job_id = request.args.get('job_id', type=int)
        
        conn = db.connect()
        cursor = conn.cursor()
        
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if job_id:
            query += " AND source = ?"
            params.append(f'scraper_job_{job_id}')
        
        query += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        leads = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({'success': True, 'leads': leads, 'count': len(leads)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Inbox Monitoring API Routes
@app.route('/api/inbox/monitor/<int:account_id>', methods=['POST'])
def api_monitor_inbox(account_id):
    """Monitor inbox for responses and follow-ups"""
    try:
        from core.inbox_monitor import InboxMonitor
        monitor = InboxMonitor(db)
        
        result = monitor.monitor_and_update(account_id)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/responses', methods=['GET'])
def api_get_responses():
    """Get email responses"""
    try:
        hot_leads_only = request.args.get('hot_leads_only', 'false').lower() == 'true'
        responses = db.get_email_responses(hot_leads_only=hot_leads_only)
        return jsonify({'success': True, 'responses': responses, 'count': len(responses)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbox/follow-ups', methods=['GET'])
def api_get_follow_ups():
    """Get emails that need follow-ups"""
    try:
        follow_ups = db.get_follow_ups_needed()
        return jsonify({'success': True, 'follow_ups': follow_ups, 'count': len(follow_ups)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Personalization API Routes
@app.route('/api/personalize', methods=['POST'])
def api_personalize_email():
    """Personalize an email template"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        
        template = data.get('template', '')
        name = data.get('name', '')
        company = data.get('company', '')
        context = data.get('context', '')
        
        if not template:
            return jsonify({'error': 'Template is required'}), 400
        
        from core.personalization import EmailPersonalizer
        personalizer = EmailPersonalizer()
        
        personalized = personalizer.personalize_email(template, name, company, context)
        
        return jsonify({
            'success': True,
            'personalized_content': personalized
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# GDPR API Routes
@app.route('/api/gdpr/request-access', methods=['POST'])
@require_auth
def api_request_data_access(user_id):
    """Request data access (GDPR)"""
    try:
        user = auth_manager.get_user(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # In production, send email with data export
        return jsonify({
            'success': True,
            'message': 'Data access request received. You will receive an email with your data.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/request-deletion', methods=['POST'])
@require_auth
def api_request_data_deletion(user_id):
    """Request data deletion (GDPR)"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET is_active = 0,
                subscription_status = 'canceled'
            WHERE id = ?
        """, (user_id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Account marked for deletion. Data will be permanently deleted in 30 days.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gdpr/export-data', methods=['GET'])
@require_auth
def api_export_data(user_id):
    """Export user data (GDPR)"""
    try:
        user = auth_manager.get_user(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = {
            'user': {k: v for k, v in user.items() if k != 'password_hash'},
            'campaigns': db.get_campaigns(user_id=user_id),
            'leads': db.get_leads(user_id=user_id),
            'recipients': db.get_recipients(user_id=user_id),
            'smtp_servers': db.get_smtp_servers(user_id=user_id, active_only=False)
        }
        
        # Remove passwords
        for server in data['smtp_servers']:
            server.pop('password', None)
        
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Stripe Configuration API
@app.route('/api/settings/stripe', methods=['GET'])
@optional_auth
def api_get_stripe_config(user_id):
    """Get Stripe configuration"""
    try:
        from core.config import Config
        
        config = {
            'stripe_secret_key': settings_manager.get_setting('STRIPE_SECRET_KEY', user_id=user_id) or os.getenv('STRIPE_SECRET_KEY', ''),
            'stripe_publishable_key': settings_manager.get_setting('STRIPE_PUBLISHABLE_KEY', user_id=user_id) or os.getenv('STRIPE_PUBLISHABLE_KEY', ''),
            'subscription_plan': settings_manager.get_setting('SUBSCRIPTION_PLAN', user_id=user_id) or 'free'
        }
        
        # Mask secret key
        if config['stripe_secret_key']:
            key = config['stripe_secret_key']
            config['stripe_secret_key'] = key[:4] + '*' * (len(key) - 8) + key[-4:] if len(key) > 8 else '****'
        
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/stripe', methods=['POST'])
@optional_auth
def api_set_stripe_config(user_id):
    """Set Stripe configuration"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        from core.config import Config
        
        if data.get('stripe_secret_key'):
            settings_manager.set_setting('STRIPE_SECRET_KEY', data['stripe_secret_key'], user_id=user_id)
            Config._update_env_file('STRIPE_SECRET_KEY', data['stripe_secret_key'])
        
        if data.get('stripe_publishable_key'):
            settings_manager.set_setting('STRIPE_PUBLISHABLE_KEY', data['stripe_publishable_key'], user_id=user_id)
            Config._update_env_file('STRIPE_PUBLISHABLE_KEY', data['stripe_publishable_key'])
        
        if data.get('subscription_plan'):
            settings_manager.set_setting('SUBSCRIPTION_PLAN', data['subscription_plan'], user_id=user_id)
        
        return jsonify({'success': True, 'message': 'Stripe configuration saved'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/subscription-info', methods=['GET'])
@require_auth
def api_get_subscription_info(user_id):
    """Get subscription information"""
    try:
        info = billing_manager.get_subscription_info(user_id)
        return jsonify({'success': True, 'subscription': info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# DNS Verification Routes
@app.route('/api/dns/generate-dkim', methods=['POST'])
@require_auth
def api_generate_dkim(user_id):
    """Generate DKIM keys for a domain"""
    try:
        from core.dns_verifier import DNSVerifier
        
        data = request.json if request.is_json else request.form.to_dict()
        domain = data.get('domain', '').strip().lower()
        
        if not domain:
            return jsonify({'success': False, 'error': 'Domain is required'}), 400
        
        dns_verifier = DNSVerifier(db)
        keys = dns_verifier.generate_dkim_keys()
        
        if 'error' in keys:
            return jsonify({'success': False, 'error': keys['error']}), 500
        
        # Save to database
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            # Check if domain exists
            result = db.supabase.client.table('domains').select('id').eq('user_id', user_id).eq('domain', domain).execute()
            
            if result.data and len(result.data) > 0:
                # Update existing
                db.supabase.client.table('domains').update({
                    'dkim_public_key': keys['public_key'],
                    'dkim_private_key': keys['private_key'],
                    'dkim_selector': keys['selector'],
                    'updated_at': datetime.now().isoformat()
                }).eq('id', result.data[0]['id']).execute()
            else:
                # Create new
                db.supabase.client.table('domains').insert({
                    'user_id': user_id,
                    'domain': domain,
                    'dkim_public_key': keys['public_key'],
                    'dkim_private_key': keys['private_key'],
                    'dkim_selector': keys['selector'],
                    'verification_status': 'pending'
                }).execute()
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO domains (user_id, domain, dkim_public_key, dkim_private_key, dkim_selector, verification_status, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
            """, (user_id, domain, keys['public_key'], keys['private_key'], keys['selector']))
            conn.commit()
        
        # Get setup instructions
        instructions = dns_verifier.get_dns_setup_instructions(domain, keys['public_key'], keys['selector'])
        
        return jsonify({
            'success': True,
            'keys': {
                'selector': keys['selector'],
                'dns_record': keys['dns_record']
            },
            'instructions': instructions
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dns/verify', methods=['POST'])
@require_auth
def api_verify_dns(user_id):
    """Verify DNS records for a domain"""
    try:
        from core.dns_verifier import DNSVerifier
        
        data = request.json if request.is_json else request.form.to_dict()
        domain = data.get('domain', '').strip().lower()
        dkim_selector = data.get('dkim_selector', '').strip()
        
        if not domain:
            return jsonify({'success': False, 'error': 'Domain is required'}), 400
        
        dns_verifier = DNSVerifier(db)
        
        # Get selector from database if not provided
        if not dkim_selector:
            conn = db.connect()
            cursor = conn.cursor()
            
            if hasattr(db, 'use_supabase') and db.use_supabase:
                result = db.supabase.client.table('domains').select('dkim_selector').eq('user_id', user_id).eq('domain', domain).execute()
                if result.data and len(result.data) > 0:
                    dkim_selector = result.data[0].get('dkim_selector')
            else:
                cursor.execute("SELECT dkim_selector FROM domains WHERE user_id = ? AND domain = ?", (user_id, domain))
                row = cursor.fetchone()
                if row:
                    dkim_selector = row[0]
        
        # Verify all records
        results = dns_verifier.verify_all_records(domain, dkim_selector)
        
        # Update database with verification status
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            update_data = {
                'spf_verified': 1 if results['spf'].get('is_valid') else 0,
                'dkim_verified': 1 if results['dkim'].get('is_valid') else 0,
                'dmarc_verified': 1 if results['dmarc'].get('is_valid') else 0,
                'verification_status': 'verified' if results['all_valid'] else 'pending',
                'updated_at': datetime.now().isoformat()
            }
            db.supabase.client.table('domains').update(update_data).eq('user_id', user_id).eq('domain', domain).execute()
        else:
            cursor.execute("""
                UPDATE domains
                SET spf_verified = ?,
                    dkim_verified = ?,
                    dmarc_verified = ?,
                    verification_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND domain = ?
            """, (
                1 if results['spf'].get('is_valid') else 0,
                1 if results['dkim'].get('is_valid') else 0,
                1 if results['dmarc'].get('is_valid') else 0,
                'verified' if results['all_valid'] else 'pending',
                user_id,
                domain
            ))
            conn.commit()
        
        return jsonify({
            'success': True,
            'verification': results
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dns/domains', methods=['GET'])
@require_auth
def api_get_domains(user_id):
    """Get all domains for user"""
    try:
        conn = db.connect()
        cursor = conn.cursor()
        
        if hasattr(db, 'use_supabase') and db.use_supabase:
            result = db.supabase.client.table('domains').select('*').eq('user_id', user_id).execute()
            domains = result.data if result.data else []
        else:
            cursor.execute("SELECT * FROM domains WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            domains = [dict(row) for row in rows] if rows else []
        
        return jsonify({
            'success': True,
            'domains': domains
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Onboarding Routes
@app.route('/onboarding')
@require_auth
def onboarding_page(user_id):
    """Onboarding wizard page"""
    try:
        from core.onboarding import OnboardingManager
        onboarding_mgr = OnboardingManager(db)
        status = onboarding_mgr.get_onboarding_status(user_id)
        
        if status.get('completed'):
            return redirect('/dashboard')
        
        return render_template('onboarding.html', onboarding=status)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error loading onboarding: {str(e)}", 500

@app.route('/api/onboarding/status', methods=['GET'])
@require_auth
def api_get_onboarding_status(user_id):
    """Get onboarding status"""
    try:
        from core.onboarding import OnboardingManager
        onboarding_mgr = OnboardingManager(db)
        status = onboarding_mgr.get_onboarding_status(user_id)
        return jsonify({'success': True, 'onboarding': status})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/onboarding/update-step', methods=['POST'])
@require_auth
def api_update_onboarding_step(user_id):
    """Update onboarding step"""
    try:
        from core.onboarding import OnboardingManager
        import json
        
        data = request.json if request.is_json else request.form.to_dict()
        step = int(data.get('step', 0))
        step_data = data.get('data', {})
        
        onboarding_mgr = OnboardingManager(db)
        result = onboarding_mgr.update_onboarding_step(user_id, step, step_data)
        
        if result.get('success'):
            # Get updated status
            status = onboarding_mgr.get_onboarding_status(user_id)
            return jsonify({
                'success': True,
                'onboarding': status
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/onboarding/complete', methods=['POST'])
@require_auth
def api_complete_onboarding(user_id):
    """Complete onboarding"""
    try:
        from core.onboarding import OnboardingManager
        
        onboarding_mgr = OnboardingManager(db)
        result = onboarding_mgr.complete_onboarding(user_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Onboarding completed successfully'
            })
        else:
            return jsonify(result), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/settings/test-redis', methods=['POST'])
@optional_auth
def api_test_redis(user_id):
    """Test Redis connection - DYNAMIC"""
    try:
        data = request.json if request.is_json else request.form.to_dict()
        redis_url = data.get('redis_url') or settings_manager.get_setting('REDIS_URL', user_id=user_id) or os.getenv('REDIS_URL')
        
        if not redis_url:
            return jsonify({'success': False, 'error': 'Redis URL not configured'})
        
        try:
            import redis
            # Handle SSL connections (Upstash, etc.)
            ssl_params = {}
            if 'rediss://' in redis_url or 'ssl=true' in redis_url.lower():
                # For SSL connections, disable certificate verification if needed
                # Upstash and some providers use self-signed certificates
                ssl_params = {
                    'ssl_cert_reqs': None,  # Disable certificate verification
                    'ssl_check_hostname': False
                }
            
            r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5, **ssl_params)
            r.ping()
            
            # Test basic operations
            test_key = 'anagha_test_connection'
            r.set(test_key, 'test', ex=10)
            value = r.get(test_key)
            r.delete(test_key)
            
            return jsonify({
                'success': True, 
                'message': 'Redis connection successful',
                'details': {
                    'host': redis_url.split('@')[-1].split('/')[0] if '@' in redis_url else redis_url.split('/')[-1],
                    'test_operation': 'passed',
                    'timestamp': datetime.now().isoformat()
                }
            })
        except redis.ConnectionError as e:
            return jsonify({'success': False, 'error': f'Redis connection failed: {str(e)}'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Redis error: {str(e)}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/redis-status', methods=['GET'])
@optional_auth
def api_get_redis_status(user_id):
    """Get Redis connection status - DYNAMIC"""
    try:
        redis_url = settings_manager.get_setting('REDIS_URL', user_id=user_id) or os.getenv('REDIS_URL')
        connected = False
        error_message = None
        
        if redis_url:
            try:
                import redis
                # Handle SSL connections (Upstash, etc.)
                ssl_params = {}
                if 'rediss://' in redis_url or 'ssl=true' in redis_url.lower():
                    ssl_params = {
                        'ssl_cert_reqs': None,  # Disable certificate verification
                        'ssl_check_hostname': False
                    }
                
                r = redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3, **ssl_params)
                r.ping()
                connected = True
            except Exception as e:
                error_message = str(e)
        else:
            error_message = 'Redis URL not configured'
        
        return jsonify({
            'success': True,
            'status': {
                'connected': connected,
                'configured': bool(redis_url),
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get absolute path to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create directories if they don't exist (using absolute paths)
    os.makedirs(os.path.join(script_dir, 'templates'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'static'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'temp'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'attachments'), exist_ok=True)
    os.makedirs(os.path.join(script_dir, 'logs'), exist_ok=True)
    
    print("=" * 50)
    print("ANAGHA SOLUTION - Web Server Starting...")
    print("=" * 50)
    print("Access the application at:")
    print("  http://localhost:5001")
    print("  http://127.0.0.1:5001")
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Run with proper configuration
    # Using port 5001 to avoid conflict with macOS AirPlay Receiver on port 5000
    app.run(
        host='127.0.0.1',  # Use 127.0.0.1 instead of 0.0.0.0 for local access
        port=5001,
        debug=True,
        threaded=True,
        use_reloader=False
    )

