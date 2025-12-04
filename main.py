"""
ANAGHA SOLUTION - Bulk Email Software
Main Application Entry Point
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow
from database.db_manager import DatabaseManager

def main():
    """Initialize and run the application"""
    try:
        # Initialize database
        db = DatabaseManager()
        db.initialize_database()
        
        # Create and run main window
        root = tk.Tk()
        app = MainWindow(root, db)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()

