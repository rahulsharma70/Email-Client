"""
Main Window for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk
from ui.dashboard import Dashboard
from ui.campaign_builder import CampaignBuilder
from ui.recipient_manager import RecipientManager
from ui.smtp_config import SMTPConfig
from ui.template_library import TemplateLibrary
from ui.analytics import Analytics
from ui.settings import Settings

class MainWindow:
    def __init__(self, root, db_manager):
        self.root = root
        self.db = db_manager
        self.root.title("ANAGHA SOLUTION - Bulk Email Software")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', font=('Arial', 18, 'bold'), background='#2c3e50', foreground='white')
        style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Nav.TButton', font=('Arial', 10), padding=10)
        
        self.create_ui()
        
    def create_ui(self):
        """Create the main UI"""
        # Header
        header = tk.Frame(self.root, bg='#2c3e50', height=80)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)
        
        title_label = tk.Label(header, text="ANAGHA SOLUTION", 
                              font=('Arial', 24, 'bold'), 
                              bg='#2c3e50', fg='white')
        title_label.pack(side=tk.LEFT, padx=20, pady=20)
        
        # Main container
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        sidebar = tk.Frame(main_container, bg='#34495e', width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
        sidebar.pack_propagate(False)
        
        # Navigation buttons
        nav_buttons = [
            ("📊 Dashboard", self.show_dashboard),
            ("✉️ Campaign Builder", self.show_campaign_builder),
            ("👥 Recipients", self.show_recipient_manager),
            ("⚙️ SMTP Config", self.show_smtp_config),
            ("📝 Templates", self.show_template_library),
            ("📈 Analytics", self.show_analytics),
            ("🔧 Settings", self.show_settings),
        ]
        
        self.nav_frame = tk.Frame(sidebar, bg='#34495e')
        self.nav_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=20)
        
        self.current_view = None
        self.buttons = {}
        
        for text, command in nav_buttons:
            btn = tk.Button(self.nav_frame, text=text, command=command,
                           bg='#34495e', fg='white', font=('Arial', 11),
                           relief=tk.FLAT, anchor='w', padx=15, pady=12,
                           cursor='hand2')
            btn.pack(fill=tk.X, pady=2)
            self.buttons[text] = btn
        
        # Content area
        self.content_frame = tk.Frame(main_container, bg='#ecf0f1')
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Show dashboard by default
        self.show_dashboard()
    
    def clear_content(self):
        """Clear content frame"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def highlight_button(self, button_text):
        """Highlight active navigation button"""
        for text, btn in self.buttons.items():
            if text == button_text:
                btn.config(bg='#3498db', activebackground='#2980b9')
            else:
                btn.config(bg='#34495e', activebackground='#2c3e50')
    
    def show_dashboard(self):
        """Show dashboard"""
        self.clear_content()
        self.highlight_button("📊 Dashboard")
        Dashboard(self.content_frame, self.db)
    
    def show_campaign_builder(self):
        """Show campaign builder"""
        self.clear_content()
        self.highlight_button("✉️ Campaign Builder")
        CampaignBuilder(self.content_frame, self.db)
    
    def show_recipient_manager(self):
        """Show recipient manager"""
        self.clear_content()
        self.highlight_button("👥 Recipients")
        RecipientManager(self.content_frame, self.db)
    
    def show_smtp_config(self):
        """Show SMTP configuration"""
        self.clear_content()
        self.highlight_button("⚙️ SMTP Config")
        SMTPConfig(self.content_frame, self.db)
    
    def show_template_library(self):
        """Show template library"""
        self.clear_content()
        self.highlight_button("📝 Templates")
        TemplateLibrary(self.content_frame, self.db)
    
    def show_analytics(self):
        """Show analytics"""
        self.clear_content()
        self.highlight_button("📈 Analytics")
        Analytics(self.content_frame, self.db)
    
    def show_settings(self):
        """Show settings"""
        self.clear_content()
        self.highlight_button("🔧 Settings")
        Settings(self.content_frame, self.db)

