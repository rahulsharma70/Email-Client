"""
Template Library UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk, messagebox

class TemplateLibrary:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        
        container = tk.Frame(parent, bg='#ecf0f1')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="Template Library", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create template section
        create_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        create_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(create_frame, text="Create New Template", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        form_frame = tk.Frame(create_frame, bg='white')
        form_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(form_frame, text="Template Name *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=0, column=0, sticky='w', padx=10, pady=8)
        self.template_name = tk.Entry(form_frame, font=('Arial', 11), width=30)
        self.template_name.grid(row=0, column=1, padx=10, pady=8, sticky='ew')
        
        tk.Label(form_frame, text="Category *", font=('Arial', 10, 'bold'),
                bg='white').grid(row=1, column=0, sticky='w', padx=10, pady=8)
        self.category = ttk.Combobox(form_frame, width=27, state='readonly')
        self.category['values'] = ('Corporate', 'Promotional', 'Personal', 'Newsletter', 'Other')
        self.category.current(0)
        self.category.grid(row=1, column=1, padx=10, pady=8, sticky='ew')
        
        form_frame.grid_columnconfigure(1, weight=1)
        
        # HTML Editor
        tk.Label(create_frame, text="HTML Content:", font=('Arial', 11, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(10, 5))
        
        html_frame = tk.Frame(create_frame, bg='white')
        html_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.html_editor = tk.Text(html_frame, font=('Courier', 10), height=15, wrap=tk.WORD)
        html_scroll = ttk.Scrollbar(html_frame, orient="vertical", command=self.html_editor.yview)
        self.html_editor.configure(yscrollcommand=html_scroll.set)
        
        self.html_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        html_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Merge tags info
        merge_info = tk.Label(create_frame, 
                             text="Merge Tags: {name}, {first_name}, {last_name}, {email}, {company}, {city}",
                             font=('Arial', 9), bg='white', fg='#7f8c8d')
        merge_info.pack(anchor='w', padx=20, pady=(0, 10))
        
        # Save button
        btn_frame = tk.Frame(create_frame, bg='white')
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        tk.Button(btn_frame, text="Save Template", command=self.save_template,
                 bg='#2ecc71', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Load Sample Template", command=self.load_sample,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Templates list
        list_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(list_frame, text="Saved Templates", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        # Filter
        filter_frame = tk.Frame(list_frame, bg='white')
        filter_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(filter_frame, text="Filter by Category:", font=('Arial', 10),
                bg='white').pack(side=tk.LEFT, padx=5)
        
        self.category_filter = ttk.Combobox(filter_frame, width=20, state='readonly')
        self.category_filter['values'] = ('All', 'Corporate', 'Promotional', 'Personal', 'Newsletter', 'Other')
        self.category_filter.current(0)
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.bind('<<ComboboxSelected>>', self.filter_templates)
        
        # Templates table
        table_frame = tk.Frame(list_frame, bg='white')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        self.templates_tree = ttk.Treeview(table_frame,
                                          columns=('Name', 'Category', 'Created'),
                                          show='headings', yscrollcommand=scroll_y.set)
        
        scroll_y.config(command=self.templates_tree.yview)
        
        self.templates_tree.heading('Name', text='Template Name')
        self.templates_tree.heading('Category', text='Category')
        self.templates_tree.heading('Created', text='Created Date')
        
        self.templates_tree.column('Name', width=200)
        self.templates_tree.column('Category', width=150)
        self.templates_tree.column('Created', width=150)
        
        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action buttons
        action_frame = tk.Frame(list_frame, bg='white')
        action_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        tk.Button(action_frame, text="Load Selected", command=self.load_template,
                 bg='#3498db', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="Delete Selected", command=self.delete_template,
                 bg='#e74c3c', fg='white', font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Load templates
        self.load_templates()
    
    def save_template(self):
        """Save template"""
        if not self.template_name.get().strip():
            messagebox.showerror("Error", "Template name is required!")
            return
        
        if not self.category.get():
            messagebox.showerror("Error", "Category is required!")
            return
        
        html_content = self.html_editor.get(1.0, tk.END).strip()
        if not html_content:
            messagebox.showerror("Error", "HTML content is required!")
            return
        
        try:
            template_id = self.db.save_template(
                name=self.template_name.get().strip(),
                category=self.category.get(),
                html_content=html_content
            )
            
            messagebox.showinfo("Success", f"Template saved successfully! ID: {template_id}")
            
            # Clear form
            self.template_name.delete(0, tk.END)
            self.html_editor.delete(1.0, tk.END)
            
            self.load_templates()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")
    
    def load_sample(self):
        """Load sample template"""
        sample_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Email Template</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #3498db; color: white; padding: 20px; text-align: center;">
        <h1>Hello {name}!</h1>
    </div>
    <div style="padding: 20px; background-color: #f9f9f9;">
        <p>Dear {first_name},</p>
        <p>This is a sample email template. You can customize it with merge tags:</p>
        <ul>
            <li>Name: {name}</li>
            <li>Email: {email}</li>
            <li>Company: {company}</li>
            <li>City: {city}</li>
        </ul>
        <p>Best regards,<br>ANAGHA SOLUTION</p>
    </div>
    <div style="background-color: #34495e; color: white; padding: 10px; text-align: center; font-size: 12px;">
        <p>© 2024 ANAGHA SOLUTION. All rights reserved.</p>
        <p><a href="{unsubscribe_url}" style="color: #3498db;">Unsubscribe</a></p>
    </div>
</body>
</html>"""
        
        self.html_editor.delete(1.0, tk.END)
        self.html_editor.insert(1.0, sample_html)
    
    def load_templates(self):
        """Load templates"""
        # Clear existing items
        for item in self.templates_tree.get_children():
            self.templates_tree.delete(item)
        
        # Get filter
        category_filter = self.category_filter.get()
        category = None if category_filter == 'All' else category_filter
        
        # Get templates
        templates = self.db.get_templates(category=category)
        
        # Populate table
        for template in templates:
            created = template.get('created_at', '')[:10] if template.get('created_at') else ''
            self.templates_tree.insert('', tk.END, values=(
                template.get('name', ''),
                template.get('category', ''),
                created
            ), tags=(template.get('id'),))
    
    def filter_templates(self, event=None):
        """Filter templates by category"""
        self.load_templates()
    
    def load_template(self):
        """Load selected template into editor"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to load!")
            return
        
        item = self.templates_tree.item(selection[0])
        template_name = item['values'][0]
        
        templates = self.db.get_templates()
        template = next((t for t in templates if t['name'] == template_name), None)
        
        if template:
            self.template_name.delete(0, tk.END)
            self.template_name.insert(0, template['name'])
            self.category.set(template.get('category', 'Corporate'))
            self.html_editor.delete(1.0, tk.END)
            self.html_editor.insert(1.0, template.get('html_content', ''))
    
    def delete_template(self):
        """Delete selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to delete!")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected template?"):
            # Implementation would require delete method in db_manager
            messagebox.showinfo("Info", "Delete functionality to be implemented in database layer")

