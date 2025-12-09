#!/bin/bash

<<<<<<< HEAD
=======
# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

>>>>>>> 5cd6a8d (New version with the dashboard)
echo "========================================"
echo "  ANAGHA SOLUTION - Web Server"
echo "========================================"
echo ""
echo "Starting web server..."
echo ""
echo "Access the application at:"
<<<<<<< HEAD
echo "  http://localhost:5000"
=======
echo "  http://localhost:5001"
echo "  http://127.0.0.1:5001"
>>>>>>> 5cd6a8d (New version with the dashboard)
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 web_app.py

