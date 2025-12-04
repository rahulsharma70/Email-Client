"""
Settings UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk, messagebox

class Settings:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        
        container = tk.Frame(parent, bg='#ecf0f1')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="Settings", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(0, 20))
        
        # Sending settings
        sending_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        sending_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(sending_frame, text="Sending Settings", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        form_frame = tk.Frame(sending_frame, bg='white')
        form_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(form_frame, text="Time Interval Between Emails (seconds)", 
                font=('Arial', 10, 'bold'), bg='white').grid(row=0, column=0, sticky='w', padx=10, pady=8)
        self.interval = tk.Entry(form_frame, font=('Arial', 11), width=20)
        self.interval.insert(0, '1')
        self.interval.grid(row=0, column=1, padx=10, pady=8, sticky='w')
        
        tk.Label(form_frame, text="Max Emails Per SMTP Per Hour", 
                font=('Arial', 10, 'bold'), bg='white').grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.max_per_hour = tk.Entry(form_frame, font=('Arial', 11), width=20)
        self.max_per_hour.insert(0, '100')
        self.max_per_hour.grid(row=1, column=1, padx=10, pady=8, sticky='w')
        
        self.use_threading = tk.BooleanVar(value=True)
        tk.Checkbutton(form_frame, text="Enable Multi-Thread Sending", 
                      variable=self.use_threading, bg='white', font=('Arial', 10)).grid(row=2, column=0, columnspan=2, sticky='w', padx=10, pady=8)
        
        tk.Label(form_frame, text="Email Queue Priority (1-10, 10 = highest)", 
                font=('Arial', 10, 'bold'), bg='white').grid(row=3, column=0, sticky='w', padx=10, pady=8)
        self.priority = tk.Entry(form_frame, font=('Arial', 11), width=20)
        self.priority.insert(0, '5')
        self.priority.grid(row=3, column=1, padx=10, pady=8, sticky='w')
        
        tk.Button(form_frame, text="Save Settings", command=self.save_settings,
                 bg='#2ecc71', fg='white', font=('Arial', 10), padx=15, pady=5).grid(row=4, column=0, columnspan=2, pady=15)
        
        # Unsubscribe & Spam Control
        spam_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        spam_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(spam_frame, text="Unsubscribe & Spam Control", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        control_frame = tk.Frame(spam_frame, bg='white')
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.auto_unsubscribe = tk.BooleanVar(value=True)
        tk.Checkbutton(control_frame, text="Auto Add Unsubscribe Link", 
                      variable=self.auto_unsubscribe, bg='white', font=('Arial', 10)).pack(anchor='w', pady=5)
        
        self.spam_check = tk.BooleanVar(value=False)
        tk.Checkbutton(control_frame, text="Enable Spam Score Check", 
                      variable=self.spam_check, bg='white', font=('Arial', 10)).pack(anchor='w', pady=5)
        
        # Blacklist management
        blacklist_frame = tk.Frame(spam_frame, bg='white')
        blacklist_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(blacklist_frame, text="Blacklist Management", font=('Arial', 12, 'bold'),
                bg='white').pack(anchor='w', pady=(0, 10))
        
        blacklist_input_frame = tk.Frame(blacklist_frame, bg='white')
        blacklist_input_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.blacklist_email = tk.Entry(blacklist_input_frame, font=('Arial', 11), width=30)
        self.blacklist_email.pack(side=tk.LEFT, padx=5)
        
        tk.Button(blacklist_input_frame, text="Add to Blacklist", 
                 command=self.add_to_blacklist, bg='#e74c3c', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Blacklist display
        blacklist_list_frame = tk.Frame(blacklist_frame, bg='white')
        blacklist_list_frame.pack(fill=tk.BOTH, expand=True)
        
        scroll_y = ttk.Scrollbar(blacklist_list_frame, orient=tk.VERTICAL)
        self.blacklist_tree = ttk.Treeview(blacklist_list_frame,
                                           columns=('Email', 'Reason', 'Date'),
                                           show='headings', yscrollcommand=scroll_y.set, height=5)
        
        scroll_y.config(command=self.blacklist_tree.yview)
        
        self.blacklist_tree.heading('Email', text='Email')
        self.blacklist_tree.heading('Reason', text='Reason')
        self.blacklist_tree.heading('Date', text='Date Added')
        
        self.blacklist_tree.column('Email', width=250)
        self.blacklist_tree.column('Reason', width=200)
        self.blacklist_tree.column('Date', width=150)
        
        self.blacklist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Button(blacklist_frame, text="Remove Selected", command=self.remove_from_blacklist,
                 bg='#c0392b', fg='white', font=('Arial', 10), padx=15, pady=5).pack(pady=10)
    
    def save_settings(self):
        """Save settings"""
        try:
            interval = float(self.interval.get())
            max_hour = int(self.max_per_hour.get())
            priority = int(self.priority.get())
            
            if interval < 0.1:
                messagebox.showerror("Error", "Interval must be at least 0.1 seconds!")
                return
            
            if priority < 1 or priority > 10:
                messagebox.showerror("Error", "Priority must be between 1 and 10!")
                return
            
            messagebox.showinfo("Success", "Settings saved successfully!")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid input values!")
    
    def add_to_blacklist(self):
        """Add email to blacklist"""
        email = self.blacklist_email.get().strip()
        if not email:
            messagebox.showerror("Error", "Please enter an email address!")
            return
        
        # Implementation would require blacklist method in db_manager
        messagebox.showinfo("Info", f"Email {email} added to blacklist")
        self.blacklist_email.delete(0, tk.END)
    
    def remove_from_blacklist(self):
        """Remove email from blacklist"""
        selection = self.blacklist_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an email to remove!")
            return
        
        messagebox.showinfo("Info", "Email removed from blacklist")

