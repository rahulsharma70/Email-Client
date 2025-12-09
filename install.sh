#!/bin/bash

echo ""
echo "========================================"
echo "  ANAGHA SOLUTION - Bulk Email Software"
echo "  Installation Script for macOS"
echo "========================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Python installation
echo "[1/5] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo ""
    echo "ERROR: Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.8 or higher:"
    echo "  brew install python3"
    echo "  or download from: https://www.python.org/downloads/"
    echo ""
    exit 1
fi

python3 --version
echo "Python found!"
echo ""

# Create virtual environment
echo "[2/5] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists."
else
    python3 -m venv venv
    echo "Virtual environment created."
fi
echo ""

# Activate and install dependencies
echo "[3/5] Installing dependencies..."
source venv/bin/activate
python3 -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "Dependencies installed successfully!"
echo ""

# Make scripts executable
echo "[4/5] Setting up scripts..."
chmod +x start_web_server.sh
chmod +x start_server_daemon.sh
chmod +x launch_anagha_solution.command
echo "Scripts configured!"
echo ""

# Create desktop launcher
echo "[5/5] Creating desktop launcher..."
DESKTOP_PATH="$HOME/Desktop/ANAGHA SOLUTION.command"
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
echo "Desktop launcher created at: $DESKTOP_PATH"
echo ""

echo "========================================"
echo "   Installation Successful!"
echo "========================================"
echo ""
echo "To run the application:"
echo "  1. Double-click 'ANAGHA SOLUTION.command' on your Desktop"
echo "  2. Or run: ./start_web_server.sh"
echo "  3. Or run: python3 web_app.py"
echo ""
echo "The application will be available at:"
echo "  http://localhost:5001"
echo "  http://127.0.0.1:5001"
echo ""

