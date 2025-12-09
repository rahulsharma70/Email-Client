# ANAGHA SOLUTION - Mac Installation Guide

## Quick Installation

1. **Open Terminal** (Applications > Utilities > Terminal)

2. **Navigate to the dashboard folder:**
   ```bash
   cd ~/Desktop/dashboard
   ```

3. **Run the installation script:**
   ```bash
   ./install.sh
   ```

4. **Launch the application:**
   - Double-click **"ANAGHA SOLUTION.command"** on your Desktop
   - OR run: `./start_web_server.sh`
   - OR run: `./start_server_daemon.sh start` (runs in background)

5. **Access the application:**
   - Open your browser and go to: **http://localhost:5001**

## Running the Server

### Option 1: Desktop Launcher (Recommended)
- Double-click **"ANAGHA SOLUTION.command"** on your Desktop
- A Terminal window will open and start the server

### Option 2: Foreground Mode
```bash
./start_web_server.sh
```
- Server runs in the current terminal
- Press `Ctrl+C` to stop

### Option 3: Background/Daemon Mode (Independent of Terminal)
```bash
# Start server in background
./start_server_daemon.sh start

# Check status
./start_server_daemon.sh status

# Stop server
./start_server_daemon.sh stop

# Restart server
./start_server_daemon.sh restart
```

This mode runs the server independently - it will continue running even if you close the terminal or work on other projects.

## Troubleshooting

### Server Not Starting
- Check if port 5001 is already in use:
  ```bash
  lsof -i :5001
  ```
- Check server logs:
  ```bash
  cat logs/server.log
  ```

### Database/Settings Not Persisting
- The database is stored at: `~/Desktop/dashboard/anagha_solution.db`
- Make sure you have write permissions in the dashboard folder
- Settings are automatically saved when you configure SMTP servers

### Python Not Found
- Install Python 3:
  ```bash
  brew install python3
  ```
- Or download from: https://www.python.org/downloads/

## Features

✅ **Persistent Storage**: All email settings, recipients, and campaigns are saved to a local SQLite database  
✅ **Background Mode**: Server can run independently of terminal sessions  
✅ **Desktop Launcher**: One-click launch from Desktop  
✅ **Auto-Save**: Email settings are automatically saved when configured

## Uninstall

To remove the application:
1. Stop the server: `./start_server_daemon.sh stop`
2. Delete the dashboard folder
3. Delete the desktop launcher: `rm ~/Desktop/ANAGHA\ SOLUTION.command`

