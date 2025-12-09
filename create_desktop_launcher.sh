#!/bin/bash

# Script to create desktop launcher for ANAGHA SOLUTION

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DESKTOP_PATH="$HOME/Desktop/ANAGHA SOLUTION.command"

echo "Creating desktop launcher..."

cat > "$DESKTOP_PATH" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
osascript << 'APPLESCRIPT'
tell application "Terminal"
    activate
    do script "cd '$SCRIPT_DIR' && source venv/bin/activate 2>/dev/null || true && echo '========================================' && echo '  ANAGHA SOLUTION - Web Server' && echo '========================================' && echo '' && echo 'Starting server...' && echo '' && echo 'Access the application at:' && echo '  http://localhost:5001' && echo '  http://127.0.0.1:5001' && echo '' && echo 'Press Ctrl+C to stop the server' && echo '========================================' && echo '' && python3 web_app.py"
end tell
APPLESCRIPT
EOF

chmod +x "$DESKTOP_PATH"

echo "✓ Desktop launcher created at: $DESKTOP_PATH"
echo ""
echo "You can now double-click 'ANAGHA SOLUTION.command' on your Desktop to launch the application!"

