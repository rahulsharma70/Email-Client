# ANAGHA SOLUTION - Bulk Email Software

A professional bulk email software built with Python and Tkinter.

## Features

### 📊 Dashboard
- Total Emails Sent Today
- Pending Queue
- Delivery Rate %
- Bounce Rate %
- Spam Rate %
- Subscriber Growth
- Campaign Performance Graph

### ✉️ Email Campaign Builder
- Create New Campaign
- Subject Line
- Sender Name & Email
- Reply-to Email
- Upload HTML Template / Drag & Drop Template Builder
- Add Attachments (PDF, JPG, PNG, Doc)
- Merge Tags Support

### 👥 Recipient Management
- Upload via CSV / Excel
- Auto Remove Duplicate Emails
- Email Verification (Optional)
- Create Lists / Segments / Labels
- Import & Export Contacts

### ⚙️ SMTP Configuration
- Add Multiple SMTP Servers
- Rotate SMTP & IP for Bulk Sending
- SSL/TLS Support
- Bounce Handler Setup

### 📤 Sending Settings
- Time Interval Between Emails
- Max Emails Per SMTP Per Hour
- Multi-Thread Sending
- Email Queue Priority

### 📝 Template Library
- Saved Templates
- Corporate Templates
- Promotional Templates
- Personalized Merge Tags

### 📈 Tracking & Analytics
- Email Open Tracking (pixel based)
- Click Tracking
- Bounce Report
- Unsubscribe Tracking
- Geo-location Insights
- Device Insights

### 🛡️ Unsubscribe & Spam Control
- Auto Unsubscribe Link
- Blacklist Management
- Spam Score Check

## Installation

### Web Application (Recommended)

The application now has a **web-based interface** that runs in your browser!

#### Quick Start (Web Version):
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the web server:
   ```bash
   python web_app.py
   ```
   Or use the startup script:
   - Windows: Double-click `start_web_server.bat`
   - Mac/Linux: Run `./start_web_server.sh`
3. Open your browser and go to:
   ```
   http://localhost:5000
   ```

### Desktop Application (Tkinter)

#### Option 1: Using Batch File (Windows)
1. Double-click `run.bat`
2. The script will automatically:
   - Check for Python
   - Create virtual environment
   - Install dependencies
   - Run the application

#### Option 2: Manual Installation
1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

### Option 3: Create Executable
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Run build script:
   ```bash
   python build_exe.py
   ```
3. Find the executable in `dist/` folder

## Default SMTP Configuration

The application comes pre-configured with:
- **SMTP Host**: smtpout.secureserver.net
- **Port**: 465
- **SSL**: Enabled
- **Email**: info@uabiotech.in

## Usage

1. **Configure SMTP**: Go to SMTP Config and add your SMTP server details
2. **Import Recipients**: Go to Recipients and import your contact list (CSV/Excel)
3. **Create Campaign**: Go to Campaign Builder and create your email campaign
4. **Send**: Click "Send Campaign" to add emails to queue and start sending

## Database

The application uses SQLite database (`anagha_solution.db`) to store:
- Campaigns
- Recipients
- Templates
- SMTP configurations
- Tracking data
- Analytics

## Requirements

- Python 3.8+
- tkinter (usually included with Python) - for desktop version
- pandas
- openpyxl
- flask - for web version
- flask-cors - for web version

## License

Copyright © 2024 ANAGHA SOLUTION. All rights reserved.

