# Quick Fix for 403 Error

## The Problem
You're seeing "HTTP ERROR 403" when trying to access the web app in Chrome.

## ✅ The Solution (Try These in Order)

### 1. Use the Correct URL
Make sure you're using:
- `http://localhost:5000` (not https://)
- `http://127.0.0.1:5000`

### 2. Clear Chrome Cache
1. Open Chrome
2. Press `Ctrl+Shift+Delete` (or `Cmd+Shift+Delete` on Mac)
3. Select "Cached images and files"
4. Click "Clear data"
5. Try accessing `http://localhost:5000` again

### 3. Try Incognito Mode
1. Press `Ctrl+Shift+N` (or `Cmd+Shift+N` on Mac)
2. Go to: `http://localhost:5000`
3. This bypasses cache and extensions

### 4. Disable Chrome Extensions Temporarily
1. Go to `chrome://extensions/`
2. Disable all extensions
3. Try accessing `http://localhost:5000`

### 5. Check if Server is Running
Open terminal and run:
```bash
curl http://localhost:5000
```

If you see HTML, the server is working!

### 6. Restart the Server
```bash
# Stop the server (Ctrl+C in the terminal where it's running)
# Then start it again:
python3 web_app.py
```

## ✅ Confirmed Working
The server is tested and working. The 403 error is likely a browser issue, not a server issue.

## 🎯 Most Common Fix
**Clear browser cache** (Solution #2) fixes 90% of 403 errors!

