"""
SMTP Configuration UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk, messagebox
import smtplib
from email.mime.text import MIMEText

class SMTPConfig:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        
        container = tk.Frame(parent, bg='#ecf0f1')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="SMTP Configuration", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(0, 20))
        
        # Add SMTP section
        add_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        add_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(add_frame, text="Add New SMTP Server", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        form_frame = tk.Frame(add_frame, bg='white')
        form_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Server Name
        tk.Label(form_frame, text="Server Name *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=0, column=0, sticky='w', padx=10, pady=8)
        self.server_name = tk.Entry(form_frame, font=('Arial', 11), width=30)
        self.server_name.grid(row=0, column=1, padx=10, pady=8, sticky='ew')
        
        # SMTP Host
        tk.Label(form_frame, text="SMTP Host *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.smtp_host = tk.Entry(form_frame, font=('Arial', 11), width=30)
        self.smtp_host.grid(row=1, column=1, padx=10, pady=8, sticky='ew')
        
        # Port
        tk.Label(form_frame, text="Port *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=2, column=0, sticky='w', padx=10, pady=8)
        self.port = tk.Entry(form_frame, font=('Arial', 11), width=30)
        self.port.grid(row=2, column=1, padx=10, pady=8, sticky='ew')
        
        # Username
        tk.Label(form_frame, text="Username (Email) *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=3, column=0, sticky='w', padx=10, pady=8)
        self.username = tk.Entry(form_frame, font=('Arial', 11), width=30)
        self.username.grid(row=3, column=1, padx=10, pady=8, sticky='ew')
        
        # Password
        tk.Label(form_frame, text="Password *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=4, column=0, sticky='w', padx=10, pady=8)
        self.password = tk.Entry(form_frame, font=('Arial', 11), width=30, show='*')
        self.password.grid(row=4, column=1, padx=10, pady=8, sticky='ew')
        
        # Security options
        security_frame = tk.Frame(form_frame, bg='white')
        security_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=8, sticky='w')
        
        self.use_ssl = tk.BooleanVar(value=True)
        tk.Checkbutton(security_frame, text="Use SSL", variable=self.use_ssl,
                      bg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        
        self.use_tls = tk.BooleanVar(value=False)
        tk.Checkbutton(security_frame, text="Use TLS", variable=self.use_tls,
                      bg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
        
        # Max per hour
        tk.Label(form_frame, text="Max Emails/Hour", font=('Arial', 10, 'bold'),
                bg='white').grid(row=6, column=0, sticky='w', padx=10, pady=8)
        self.max_per_hour = tk.Entry(form_frame, font=('Arial', 11), width=30)
        self.max_per_hour.insert(0, '100')
        self.max_per_hour.grid(row=6, column=1, padx=10, pady=8, sticky='ew')
        
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Buttons
        btn_frame = tk.Frame(add_frame, bg='white')
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        tk.Button(btn_frame, text="Test Connection", command=self.test_connection,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Save SMTP Server", command=self.save_smtp,
                 bg='#2ecc71', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Pre-fill with provided credentials
        self.server_name.insert(0, "UABIOTECH SMTP")
        self.smtp_host.insert(0, "smtpout.secureserver.net")
        self.port.insert(0, "465")
        self.username.insert(0, "info@uabiotech.in")
        self.password.insert(0, "Uabiotech*2309")
        self.use_ssl.set(True)
        self.use_tls.set(False)
        
        # Existing SMTP servers
        servers_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        servers_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(servers_frame, text="Configured SMTP Servers", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        # Servers table
        table_frame = tk.Frame(servers_frame, bg='white')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        self.servers_tree = ttk.Treeview(table_frame,
                                         columns=('Name', 'Host', 'Port', 'Username', 'Status', 'Max/Hour'),
                                         show='headings', yscrollcommand=scroll_y.set)
        
        scroll_y.config(command=self.servers_tree.yview)
        
        self.servers_tree.heading('Name', text='Server Name')
        self.servers_tree.heading('Host', text='SMTP Host')
        self.servers_tree.heading('Port', text='Port')
        self.servers_tree.heading('Username', text='Username')
        self.servers_tree.heading('Status', text='Status')
        self.servers_tree.heading('Max/Hour', text='Max/Hour')
        
        self.servers_tree.column('Name', width=150)
        self.servers_tree.column('Host', width=200)
        self.servers_tree.column('Port', width=80)
        self.servers_tree.column('Username', width=200)
        self.servers_tree.column('Status', width=100)
        self.servers_tree.column('Max/Hour', width=100)
        
        self.servers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons
        action_frame = tk.Frame(servers_frame, bg='white')
        action_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        tk.Button(action_frame, text="Refresh", command=self.load_servers,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="Delete Selected", command=self.delete_server,
                 bg='#e74c3c', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Load existing servers
        self.load_servers()
    
    def test_connection(self):
        """Test SMTP connection"""
        if not self.validate_form():
            return
        
        try:
            host = self.smtp_host.get().strip()
            port = int(self.port.get().strip())
            username = self.username.get().strip()
            password = self.password.get().strip()
            use_ssl = self.use_ssl.get()
            
            # Test connection
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port)
            else:
                server = smtplib.SMTP(host, port)
                if self.use_tls.get():
                    server.starttls()
            
            server.login(username, password)
            server.quit()
            
            messagebox.showinfo("Success", "SMTP connection test successful!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Connection test failed: {str(e)}")
    
    def validate_form(self):
        """Validate form fields"""
        if not self.server_name.get().strip():
            messagebox.showerror("Error", "Server name is required!")
            return False
        if not self.smtp_host.get().strip():
            messagebox.showerror("Error", "SMTP host is required!")
            return False
        if not self.port.get().strip():
            messagebox.showerror("Error", "Port is required!")
            return False
        if not self.username.get().strip():
            messagebox.showerror("Error", "Username is required!")
            return False
        if not self.password.get().strip():
            messagebox.showerror("Error", "Password is required!")
            return False
        return True
    
    def save_smtp(self):
        """Save SMTP server configuration"""
        if not self.validate_form():
            return
        
        try:
            server_id = self.db.add_smtp_server(
                name=self.server_name.get().strip(),
                host=self.smtp_host.get().strip(),
                port=int(self.port.get().strip()),
                username=self.username.get().strip(),
                password=self.password.get().strip(),
                use_tls=self.use_tls.get(),
                use_ssl=self.use_ssl.get(),
                max_per_hour=int(self.max_per_hour.get() or '100')
            )
            
            messagebox.showinfo("Success", f"SMTP server saved successfully! ID: {server_id}")
            
            # Clear form
            self.server_name.delete(0, tk.END)
            self.smtp_host.delete(0, tk.END)
            self.port.delete(0, tk.END)
            self.username.delete(0, tk.END)
            self.password.delete(0, tk.END)
            self.max_per_hour.delete(0, tk.END)
            self.max_per_hour.insert(0, '100')
            
            self.load_servers()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save SMTP server: {str(e)}")
    
    def load_servers(self):
        """Load SMTP servers"""
        # Clear existing items
        for item in self.servers_tree.get_children():
            self.servers_tree.delete(item)
        
        # Get servers
        servers = self.db.get_smtp_servers(active_only=False)
        
        # Populate table
        for server in servers:
            status = "Active" if server.get('is_active') else "Inactive"
            self.servers_tree.insert('', tk.END, values=(
                server.get('name', ''),
                server.get('host', ''),
                server.get('port', ''),
                server.get('username', ''),
                status,
                server.get('max_per_hour', 100)
            ))
    
    def delete_server(self):
        """Delete selected SMTP server"""
        selection = self.servers_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a server to delete!")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected SMTP server?"):
            # Implementation would require delete method in db_manager
            messagebox.showinfo("Info", "Delete functionality to be implemented in database layer")

