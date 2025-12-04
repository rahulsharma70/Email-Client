# Quick Start Guide - ANAGHA SOLUTION

## First Time Setup

### Windows Users:
1. **Double-click `install.bat`** - This will:
   - Check for Python
   - Create virtual environment
   - Install all dependencies
   - Set up everything automatically

2. **Double-click `run.bat`** to start the application

### Mac/Linux Users:
1. Open terminal in the project folder
2. Run:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

## Default SMTP Configuration

The application comes pre-filled with your SMTP settings:
- **Server Name**: UABIOTECH SMTP
- **SMTP Host**: smtpout.secureserver.net
- **Port**: 465
- **SSL**: Enabled
- **Email**: info@uabiotech.in
- **Password**: Uabiotech*2309

## Quick Workflow

1. **Configure SMTP** (if needed)
   - Go to "⚙️ SMTP Config"
   - Click "Test Connection" to verify
   - Click "Save SMTP Server"

2. **Import Recipients**
   - Go to "👥 Recipients"
   - Click "Import from CSV/Excel"
   - Select your contact file
   - Ensure file has an "email" column

3. **Create Campaign**
   - Go to "✉️ Campaign Builder"
   - Fill in campaign details
   - Add HTML content or load template
   - Click "Send Campaign"

4. **Monitor Progress**
   - Check "📊 Dashboard" for real-time stats
   - View "📈 Analytics" for detailed reports

## CSV/Excel Format

Your import file should have these columns (email is required):
- email (required)
- first_name
- last_name
- company
- city
- phone
- list_name

## Creating Executable

To create a standalone executable:

```bash
python build_exe.py
```

The executable will be in the `dist/` folder.

## Troubleshooting

### "Python not found"
- Install Python 3.8+ from python.org
- Make sure to check "Add Python to PATH" during installation

### "Module not found"
- Run: `pip install -r requirements.txt`
- Or re-run `install.bat`

### SMTP Connection Failed
- Verify your SMTP credentials
- Check firewall settings
- Ensure port 465 is not blocked

### Database Errors
- Delete `anagha_solution.db` to reset
- Restart the application

## Support

For issues or questions, check the README.md file.

