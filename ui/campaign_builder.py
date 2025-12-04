"""
Campaign Builder UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from core.email_sender import EmailSender

class CampaignBuilder:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        self.attachments = []
        
        # Main container with scrollbar
        canvas = tk.Canvas(parent, bg='#ecf0f1')
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ecf0f1')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        container = scrollable_frame
        
        # Title
        title = tk.Label(container, text="Create New Campaign", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(20, 20), padx=20)
        
        # Form frame
        form_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Campaign Name
        tk.Label(form_frame, text="Campaign Name *", font=('Arial', 11, 'bold'),
                bg='white').grid(row=0, column=0, sticky='w', padx=20, pady=10)
        self.campaign_name = tk.Entry(form_frame, font=('Arial', 11), width=50)
        self.campaign_name.grid(row=0, column=1, padx=20, pady=10, sticky='ew')
        
        # Subject Line
        tk.Label(form_frame, text="Subject Line *", font=('Arial', 11, 'bold'),
                bg='white').grid(row=1, column=0, sticky='w', padx=20, pady=10)
        self.subject = tk.Entry(form_frame, font=('Arial', 11), width=50)
        self.subject.grid(row=1, column=1, padx=20, pady=10, sticky='ew')
        
        # Sender Name
        tk.Label(form_frame, text="Sender Name *", font=('Arial', 11, 'bold'),
                bg='white').grid(row=2, column=0, sticky='w', padx=20, pady=10)
        self.sender_name = tk.Entry(form_frame, font=('Arial', 11), width=50)
        self.sender_name.grid(row=2, column=1, padx=20, pady=10, sticky='ew')
        
        # Sender Email
        tk.Label(form_frame, text="Sender Email *", font=('Arial', 11, 'bold'),
                bg='white').grid(row=3, column=0, sticky='w', padx=20, pady=10)
        self.sender_email = tk.Entry(form_frame, font=('Arial', 11), width=50)
        self.sender_email.grid(row=3, column=1, padx=20, pady=10, sticky='ew')
        
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Template Selection
        template_select_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        template_select_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(template_select_frame, text="Load Template (Optional)", font=('Arial', 11, 'bold'),
                bg='white').grid(row=0, column=0, sticky='w', padx=20, pady=10)
        
        template_select_inner = tk.Frame(template_select_frame, bg='white')
        template_select_inner.grid(row=0, column=1, padx=20, pady=10, sticky='ew')
        template_select_frame.grid_columnconfigure(1, weight=1)
        
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_select_inner, textvariable=self.template_var, 
                                          width=40, state='readonly')
        self.template_combo.grid(row=0, column=0, padx=(0, 10), sticky='ew')
        template_select_inner.grid_columnconfigure(0, weight=1)
        
        # Load templates
        templates = self.db.get_templates()
        template_options = ['-- Select a template --']
        self.templates_dict = {}
        for template in templates:
            display_name = f"{template['name']} ({template.get('category', 'Other')})"
            template_options.append(display_name)
            self.templates_dict[display_name] = template
        
        self.template_combo['values'] = template_options
        self.template_combo.current(0)
        
        tk.Button(template_select_inner, text="Load Template", 
                 command=self.load_template_from_combo, bg='#3498db', fg='white',
                 font=('Arial', 10), padx=15, pady=5).grid(row=0, column=1)
        
        # Message Type Selection
        message_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        message_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(message_frame, text="Message Type", font=('Arial', 11, 'bold'),
                bg='white').grid(row=0, column=0, sticky='w', padx=20, pady=10)
        
        self.message_type = tk.StringVar(value='text')
        tk.Radiobutton(message_frame, text="Plain Text", variable=self.message_type, 
                      value='text', bg='white', font=('Arial', 10),
                      command=self.toggle_message_editor).grid(row=0, column=1, padx=10)
        tk.Radiobutton(message_frame, text="HTML", variable=self.message_type, 
                      value='html', bg='white', font=('Arial', 10),
                      command=self.toggle_message_editor).grid(row=0, column=2, padx=10)
        
        # Message Content Section
        template_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        template_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(template_frame, text="Message Content", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        # Text Content Editor
        self.text_frame = tk.Frame(template_frame, bg='white')
        self.text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        tk.Label(self.text_frame, text="Enter your message:", font=('Arial', 11, 'bold'),
                bg='white').pack(anchor='w', pady=(0, 5))
        
        self.text_content = tk.Text(self.text_frame, font=('Arial', 11), height=15, wrap=tk.WORD)
        text_scroll = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text_content.yview)
        self.text_content.configure(yscrollcommand=text_scroll.set)
        
        self.text_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # HTML Content Editor (hidden by default)
        self.html_frame = tk.Frame(template_frame, bg='white')
        
        tk.Label(self.html_frame, text="HTML Content:", font=('Arial', 11, 'bold'),
                bg='white').pack(anchor='w', pady=(0, 5))
        
        self.html_content = tk.Text(self.html_frame, font=('Courier', 10), height=15, wrap=tk.WORD)
        html_scroll = ttk.Scrollbar(self.html_frame, orient="vertical", command=self.html_content.yview)
        self.html_content.configure(yscrollcommand=html_scroll.set)
        
        self.html_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        html_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Merge tags info
        merge_info = tk.Label(template_frame, 
                             text="Available Merge Tags: {name}, {first_name}, {last_name}, {email}, {company}, {city}",
                             font=('Arial', 9), bg='white', fg='#7f8c8d')
        merge_info.pack(anchor='w', padx=20, pady=(0, 10))
        
        # Attachments section
        attach_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        attach_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(attach_frame, text="Attachments", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        attach_info = tk.Label(attach_frame, 
                              text="Supported formats: PDF, TXT, Word (DOC/DOCX), JPEG, PNG, MP3, MP4",
                              font=('Arial', 9), bg='white', fg='#7f8c8d')
        attach_info.pack(anchor='w', padx=20, pady=(0, 10))
        
        attach_btn_frame = tk.Frame(attach_frame, bg='white')
        attach_btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(attach_btn_frame, text="Add Attachments", 
                 command=self.add_attachment, bg='#e67e22', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        self.attachment_list = tk.Listbox(attach_frame, height=4, font=('Arial', 10))
        self.attachment_list.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Button(attach_btn_frame, text="Remove Selected", 
                 command=self.remove_attachment, bg='#e74c3c', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = tk.Frame(container, bg='#ecf0f1')
        button_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Button(button_frame, text="Save as Draft", command=self.save_draft,
                 bg='#95a5a6', fg='white', font=('Arial', 12, 'bold'),
                 padx=20, pady=10).pack(side=tk.LEFT, padx=10)
        
        tk.Button(button_frame, text="Send Campaign", command=self.send_campaign,
                 bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                 padx=20, pady=10).pack(side=tk.LEFT, padx=10)
        
        # Set default values from SMTP config if available
        smtp_servers = self.db.get_smtp_servers()
        if smtp_servers:
            server = smtp_servers[0]
            self.sender_email.insert(0, server.get('username', ''))
            if not self.sender_name.get():
                self.sender_name.insert(0, "ANAGHA SOLUTION")
    
    def load_template(self):
        """Load a saved template"""
        templates = self.db.get_templates()
        if not templates:
            messagebox.showinfo("Info", "No templates found. Please create a template first.")
            return
        
        # Create template selection dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title("Select Template")
        dialog.geometry("500x400")
        
        listbox = tk.Listbox(dialog, font=('Arial', 11))
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for template in templates:
            listbox.insert(tk.END, f"{template['name']} ({template['category']})")
        
        def load_selected():
            selection = listbox.curselection()
            if selection:
                template = templates[selection[0]]
                self.html_content.delete(1.0, tk.END)
                self.html_content.insert(1.0, template['html_content'])
                dialog.destroy()
        
        tk.Button(dialog, text="Load", command=load_selected,
                 bg='#3498db', fg='white', font=('Arial', 10),
                 padx=20, pady=5).pack(pady=10)
    
    def upload_html(self):
        """Upload HTML file"""
        file_path = filedialog.askopenfilename(
            title="Select HTML File",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.html_content.delete(1.0, tk.END)
                self.html_content.insert(1.0, content)
                messagebox.showinfo("Success", "HTML file loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")
    
    def open_template_builder(self):
        """Open template builder"""
        messagebox.showinfo("Template Builder", 
                          "Template builder will open in a new window.\n"
                          "For now, you can edit HTML directly in the editor above.")
    
    def load_template_from_combo(self):
        """Load selected template"""
        selected = self.template_var.get()
        if not selected or selected == '-- Select a template --':
            messagebox.showwarning("Warning", "Please select a template first!")
            return
        
        template = self.templates_dict.get(selected)
        if not template:
            messagebox.showerror("Error", "Template not found!")
            return
        
        # Switch to HTML mode
        self.message_type.set('html')
        self.toggle_message_editor()
        
        # Load template content
        self.html_content.delete(1.0, tk.END)
        self.html_content.insert(1.0, template.get('html_content', ''))
        
        messagebox.showinfo("Success", f"Template '{template['name']}' loaded successfully!")
    
    def toggle_message_editor(self):
        """Toggle between text and HTML editor"""
        if self.message_type.get() == 'text':
            self.text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            self.html_frame.pack_forget()
        else:
            self.html_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            self.text_frame.pack_forget()
    
    def add_attachment(self):
        """Add attachment"""
        file_paths = filedialog.askopenfilenames(
            title="Select Attachments",
            filetypes=[
                ("All supported", "*.pdf *.txt *.doc *.docx *.jpg *.jpeg *.png *.mp3 *.mp4"),
                ("PDF files", "*.pdf"),
                ("Text files", "*.txt"),
                ("Word files", "*.doc *.docx"),
                ("Image files", "*.jpg *.jpeg *.png"),
                ("Audio files", "*.mp3"),
                ("Video files", "*.mp4"),
                ("All files", "*.*")
            ]
        )
        for file_path in file_paths:
            if file_path:
                self.attachments.append(file_path)
                self.attachment_list.insert(tk.END, os.path.basename(file_path))
    
    def remove_attachment(self):
        """Remove selected attachment"""
        selection = self.attachment_list.curselection()
        if selection:
            index = selection[0]
            self.attachment_list.delete(index)
            self.attachments.pop(index)
    
    def save_draft(self):
        """Save campaign as draft"""
        if not self.validate_form():
            return
        
        try:
            # Get message content based on type
            message_type = self.message_type.get()
            if message_type == 'text':
                text_content = self.text_content.get(1.0, tk.END).strip()
                html_content = text_content.replace('\n', '<br>')
            else:
                html_content = self.html_content.get(1.0, tk.END).strip()
            
            campaign_id = self.db.create_campaign(
                name=self.campaign_name.get(),
                subject=self.subject.get(),
                sender_name=self.sender_name.get(),
                sender_email=self.sender_email.get(),
                reply_to=self.reply_to.get() or None,
                html_content=html_content
            )
            messagebox.showinfo("Success", f"Campaign saved as draft! ID: {campaign_id}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save campaign: {str(e)}")
    
    def validate_form(self):
        """Validate form fields"""
        if not self.campaign_name.get().strip():
            messagebox.showerror("Error", "Campaign name is required!")
            return False
        if not self.subject.get().strip():
            messagebox.showerror("Error", "Subject line is required!")
            return False
        if not self.sender_name.get().strip():
            messagebox.showerror("Error", "Sender name is required!")
            return False
        if not self.sender_email.get().strip():
            messagebox.showerror("Error", "Sender email is required!")
            return False
        
        # Validate message content based on type
        message_type = self.message_type.get()
        if message_type == 'text':
            if not self.text_content.get(1.0, tk.END).strip():
                messagebox.showerror("Error", "Message content is required!")
                return False
        else:
            if not self.html_content.get(1.0, tk.END).strip():
                messagebox.showerror("Error", "HTML content is required!")
                return False
        
        return True
    
    def send_campaign(self):
        """Send campaign"""
        if not self.validate_form():
            return
        
        # Check if recipients exist
        recipients = self.db.get_recipients()
        if not recipients:
            messagebox.showerror("Error", "No recipients found! Please import recipients first.")
            return
        
        # Check if SMTP server is configured
        smtp_servers = self.db.get_smtp_servers()
        if not smtp_servers:
            messagebox.showerror("Error", "No SMTP server configured! Please configure SMTP first.")
            return
        
        # Get message content based on type
        message_type = self.message_type.get()
        if message_type == 'text':
            text_content = self.text_content.get(1.0, tk.END).strip()
            # Convert text to HTML (simple conversion)
            html_content = text_content.replace('\n', '<br>')
        else:
            html_content = self.html_content.get(1.0, tk.END).strip()
        
        # Save campaign
        try:
            campaign_id = self.db.create_campaign(
                name=self.campaign_name.get(),
                subject=self.subject.get(),
                sender_name=self.sender_name.get(),
                sender_email=self.sender_email.get(),
                reply_to=None,
                html_content=html_content
            )
            
            # Handle attachments - copy to attachments folder
            if self.attachments:
                import shutil
                os.makedirs('attachments', exist_ok=True)
                attachment_paths = []
                for attachment_path in self.attachments:
                    if os.path.exists(attachment_path):
                        filename = f"{campaign_id}_{os.path.basename(attachment_path)}"
                        dest_path = os.path.join('attachments', filename)
                        shutil.copy2(attachment_path, dest_path)
                        attachment_paths.append(dest_path)
                
                # Store attachment paths in campaign HTML (temporary solution)
                if attachment_paths:
                    conn = self.db.connect()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE campaigns SET html_content = html_content || ? 
                        WHERE id = ?
                    """, (f"\n<!--ATTACHMENTS:{','.join(attachment_paths)}-->", campaign_id))
                    conn.commit()
            
            # Add to queue
            recipient_ids = [r['id'] for r in recipients]
            smtp_id = smtp_servers[0]['id'] if smtp_servers else None
            self.db.add_to_queue(campaign_id, recipient_ids, smtp_id)
            
            messagebox.showinfo("Success", 
                              f"Campaign created and added to queue!\n"
                              f"Campaign ID: {campaign_id}\n"
                              f"Recipients: {len(recipient_ids)}\n"
                              f"Attachments: {len(self.attachments)}")
            
            # Start sending in background
            sender = EmailSender(self.db)
            sender.start_sending()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send campaign: {str(e)}")

