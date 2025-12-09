# Setup Guide - API Keys Configuration

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment File**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Or create `.env` manually with:
     ```
     PERPLEXITY_API_KEY=your_key_here
     OPENROUTER_API_KEY=your_key_here
     OPENROUTER_MODEL=openai/gpt-4o-mini
     ```

3. **Configure API Keys via UI (Recommended)**
   - Start the application
   - Go to **Settings** page
   - Scroll to **API Keys Configuration** section
   - Enter your API keys
   - Click **Save API Keys**
   - Keys are automatically saved to `.env` file

## API Keys Setup

### Perplexity API Key (for Lead Scraping)
1. Sign up at https://www.perplexity.ai/
2. Get your API key from the dashboard
3. Add it to Settings → API Keys Configuration

### OpenRouter API Key (for Email Personalization)
1. Sign up at https://openrouter.ai/
2. Get your API key from the dashboard
3. Add it to Settings → API Keys Configuration

## Environment Variables

The application uses `.env` file for configuration. The file is automatically created/updated when you save API keys through the Settings page.

**Important**: The `.env` file is in `.gitignore` and will not be committed to version control.

## Manual Configuration

If you prefer to set environment variables manually:

```bash
export PERPLEXITY_API_KEY="your-key-here"
export OPENROUTER_API_KEY="your-key-here"
export OPENROUTER_MODEL="openai/gpt-4o-mini"
```

## Verification

After setting up API keys:
1. Go to **Leads** page → Try scraping leads (tests Perplexity)
2. Go to **Campaign Builder** → Enable personalization → Create campaign (tests OpenRouter)

## Troubleshooting

- **API keys not working**: Check that keys are saved correctly in Settings
- **.env file not found**: It will be created automatically when you save keys via Settings
- **Import errors**: Make sure `python-dotenv` is installed: `pip install python-dotenv`

