# Project Structure - ANAGHA SOLUTION

## Clean Organization

```
Email-Client/
├── backend/                    # Backend Python code
│   ├── core/                  # Core business logic
│   │   ├── auth.py           # Authentication & JWT
│   │   ├── billing.py        # Stripe integration
│   │   ├── celery_app.py     # Celery configuration
│   │   ├── config.py         # Configuration management
│   │   ├── email_sender.py   # Email sending logic
│   │   ├── email_verifier.py # Email verification
│   │   ├── inbox_monitor.py  # Inbox monitoring
│   │   ├── lead_scraper.py   # Lead scraping
│   │   ├── middleware.py     # JWT middleware
│   │   ├── personalization.py # AI personalization
│   │   ├── rate_limiter.py   # Rate limiting
│   │   ├── supabase_client.py # Supabase client
│   │   ├── tasks.py          # Celery tasks
│   │   └── warmup.py         # Email warmup
│   ├── database/              # Database layer
│   │   ├── db_manager.py     # SQLite manager
│   │   ├── settings_manager.py # Persistent settings
│   │   ├── supabase_manager.py # Supabase manager
│   │   └── supabase_schema.py # Schema creation
│   └── web_app.py            # Flask application
│
├── frontend/                   # Frontend code
│   ├── templates/            # HTML templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── campaign_builder.html
│   │   ├── recipients.html
│   │   ├── leads.html
│   │   ├── settings.html
│   │   └── ... (other templates)
│   └── static/                # Static assets
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   └── main.js
│       └── images/
│
├── Dockerfile                 # Container configuration
├── railway.json              # Railway deployment
├── render.yaml               # Render deployment
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignore rules
│
├── README.md                 # Main documentation
├── DEPLOYMENT_GUIDE.md       # Deployment guide
├── COMPLETE_SETUP_GUIDE.md   # Setup guide
└── README_DEPLOYMENT.md      # Quick deployment

# Data directories (user content)
├── attachments/             # Email attachments
├── logs/                    # Application logs
└── temp/                    # Temporary files
```

## File Locations

### Backend Entry Point
- **Main App**: `backend/web_app.py`

### Database
- **SQLite**: `backend/database/db_manager.py`
- **Supabase**: `backend/database/supabase_manager.py`
- **Settings**: `backend/database/settings_manager.py`

### Frontend
- **Templates**: `frontend/templates/`
- **Static Files**: `frontend/static/`

## Running the Application

```bash
cd backend
python web_app.py
```

The Flask app will:
- Load templates from `frontend/templates/`
- Serve static files from `frontend/static/`
- Use backend code from `backend/`

## Deployment

All deployment configurations are in root:
- `Dockerfile` - For containerized deployment
- `railway.json` - Railway configuration
- `render.yaml` - Render configuration

## No Duplicates

✅ All duplicate files removed
✅ Clean structure
✅ All imports working correctly

