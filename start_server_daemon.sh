#!/bin/bash

# ANAGHA SOLUTION - Background Server Launcher
# This script runs the server in the background, independent of terminal

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Create logs directory
mkdir -p logs

# Log file
LOG_FILE="$SCRIPT_DIR/logs/server.log"
PID_FILE="$SCRIPT_DIR/logs/server.pid"

# Function to check if server is running
check_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to start server
start_server() {
    if check_server; then
        echo "Server is already running (PID: $(cat "$PID_FILE"))"
        echo "Access at: http://127.0.0.1:5001"
        return 1
    fi
    
    echo "Starting ANAGHA SOLUTION server in background..."
    nohup python3 web_app.py > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > "$PID_FILE"
    
    # Wait a moment to check if it started
    sleep 2
    if ps -p "$SERVER_PID" > /dev/null 2>&1; then
        echo "✓ Server started successfully (PID: $SERVER_PID)"
        echo "Access at: http://127.0.0.1:5001"
        echo "Logs: $LOG_FILE"
        return 0
    else
        echo "✗ Server failed to start. Check logs: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to stop server
stop_server() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Server is not running"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping server (PID: $PID)..."
        kill "$PID"
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Force stopping..."
            kill -9 "$PID"
        fi
        rm -f "$PID_FILE"
        echo "✓ Server stopped"
        return 0
    else
        echo "Server process not found"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to show status
show_status() {
    if check_server; then
        PID=$(cat "$PID_FILE")
        echo "Server is running (PID: $PID)"
        echo "Access at: http://127.0.0.1:5001"
        echo "Logs: $LOG_FILE"
    else
        echo "Server is not running"
    fi
}

# Main command handling
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the server in background"
        echo "  stop    - Stop the running server"
        echo "  restart - Restart the server"
        echo "  status  - Check server status"
        exit 1
        ;;
esac

