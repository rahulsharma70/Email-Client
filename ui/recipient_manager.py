"""
Recipient Management UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import os

class RecipientManager:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        
        container = tk.Frame(parent, bg='#ecf0f1')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="Recipient Management", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(0, 20))
        
        # Import section
        import_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        import_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(import_frame, text="Import Recipients", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        btn_frame = tk.Frame(import_frame, bg='white')
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(btn_frame, text="Import from CSV/Excel", 
                 command=self.import_csv_excel, bg='#3498db', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Add Single Recipient", 
                 command=self.add_single, bg='#2ecc71', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Export Contacts", 
                 command=self.export_contacts, bg='#9b59b6', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Remove Duplicates", 
                 command=self.remove_duplicates, bg='#e67e22', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # List management
        list_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        list_header = tk.Frame(list_frame, bg='white')
        list_header.pack(fill=tk.X, padx=20, pady=(15, 10))
        
        tk.Label(list_header, text="Recipient Lists", font=('Arial', 14, 'bold'),
                bg='white').pack(side=tk.LEFT)
        
        self.list_filter = ttk.Combobox(list_header, width=20, state='readonly')
        self.list_filter.pack(side=tk.RIGHT, padx=10)
        self.list_filter['values'] = ['All Lists', 'default']
        self.list_filter.current(0)
        self.list_filter.bind('<<ComboboxSelected>>', self.filter_list)
        
        # Recipients table
        table_frame = tk.Frame(list_frame, bg='white')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Treeview with scrollbars
        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        
        self.tree = ttk.Treeview(table_frame, 
                                columns=('Email', 'First Name', 'Last Name', 'Company', 'City', 'List'),
                                show='headings', yscrollcommand=scroll_y.set,
                                xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        # Configure columns
        self.tree.heading('Email', text='Email')
        self.tree.heading('First Name', text='First Name')
        self.tree.heading('Last Name', text='Last Name')
        self.tree.heading('Company', text='Company')
        self.tree.heading('City', text='City')
        self.tree.heading('List', text='List')
        
        self.tree.column('Email', width=200)
        self.tree.column('First Name', width=120)
        self.tree.column('Last Name', width=120)
        self.tree.column('Company', width=150)
        self.tree.column('City', width=100)
        self.tree.column('List', width=100)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Action buttons
        action_frame = tk.Frame(list_frame, bg='white')
        action_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        tk.Button(action_frame, text="Delete Selected", 
                 command=self.delete_selected, bg='#e74c3c', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(action_frame, text="Unsubscribe Selected", 
                 command=self.unsubscribe_selected, bg='#c0392b', fg='white',
                 font=('Arial', 10), padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        # Stats
        stats_frame = tk.Frame(list_frame, bg='#ecf0f1')
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        self.stats_label = tk.Label(stats_frame, text="Total Recipients: 0", 
                                    font=('Arial', 11, 'bold'), bg='#ecf0f1')
        self.stats_label.pack()
        
        # Load recipients
        self.load_recipients()
    
    def import_csv_excel(self):
        """Import recipients from CSV or Excel"""
        file_path = filedialog.askopenfilename(
            title="Select CSV or Excel File",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            # Read file
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Normalize column names
            df.columns = df.columns.str.lower().str.strip()
            
            # Map common column names
            column_mapping = {
                'email': 'email',
                'e-mail': 'email',
                'email address': 'email',
                'firstname': 'first_name',
                'first name': 'first_name',
                'fname': 'first_name',
                'lastname': 'last_name',
                'last name': 'last_name',
                'lname': 'last_name',
                'company': 'company',
                'city': 'city',
                'phone': 'phone',
                'list': 'list_name',
                'listname': 'list_name'
            }
            
            # Rename columns
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df.rename(columns={old_col: new_col}, inplace=True)
            
            # Ensure email column exists
            if 'email' not in df.columns:
                messagebox.showerror("Error", "CSV/Excel file must contain an 'email' column!")
                return
            
            # Convert to list of dicts
            recipients = df.to_dict('records')
            
            # Add to database
            count = self.db.add_recipients(recipients)
            
            messagebox.showinfo("Success", 
                              f"Imported {count} recipients!\n"
                              f"Duplicates were automatically removed.")
            
            self.load_recipients()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import file: {str(e)}")
    
    def add_single(self):
        """Add a single recipient"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Add Recipient")
        dialog.geometry("400x350")
        
        tk.Label(dialog, text="Email *", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', padx=20, pady=10)
        email_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        email_entry.grid(row=0, column=1, padx=20, pady=10)
        
        tk.Label(dialog, text="First Name", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', padx=20, pady=10)
        first_name_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        first_name_entry.grid(row=1, column=1, padx=20, pady=10)
        
        tk.Label(dialog, text="Last Name", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=20, pady=10)
        last_name_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        last_name_entry.grid(row=2, column=1, padx=20, pady=10)
        
        tk.Label(dialog, text="Company", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', padx=20, pady=10)
        company_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        company_entry.grid(row=3, column=1, padx=20, pady=10)
        
        tk.Label(dialog, text="City", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', padx=20, pady=10)
        city_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        city_entry.grid(row=4, column=1, padx=20, pady=10)
        
        tk.Label(dialog, text="List Name", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky='w', padx=20, pady=10)
        list_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        list_entry.insert(0, 'default')
        list_entry.grid(row=5, column=1, padx=20, pady=10)
        
        def save():
            if not email_entry.get().strip():
                messagebox.showerror("Error", "Email is required!")
                return
            
            recipient = {
                'email': email_entry.get().strip(),
                'first_name': first_name_entry.get().strip(),
                'last_name': last_name_entry.get().strip(),
                'company': company_entry.get().strip(),
                'city': city_entry.get().strip(),
                'list_name': list_entry.get().strip() or 'default'
            }
            
            try:
                count = self.db.add_recipients([recipient])
                if count > 0:
                    messagebox.showinfo("Success", "Recipient added successfully!")
                    dialog.destroy()
                    self.load_recipients()
                else:
                    messagebox.showwarning("Warning", "Recipient already exists!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add recipient: {str(e)}")
        
        tk.Button(dialog, text="Save", command=save, bg='#3498db', fg='white',
                 font=('Arial', 10), padx=20, pady=5).grid(row=6, column=0, columnspan=2, pady=20)
    
    def export_contacts(self):
        """Export contacts to CSV"""
        recipients = self.db.get_recipients()
        if not recipients:
            messagebox.showwarning("Warning", "No recipients to export!")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export Contacts",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                df = pd.DataFrame(recipients)
                df.to_csv(file_path, index=False)
                messagebox.showinfo("Success", f"Exported {len(recipients)} contacts to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {str(e)}")
    
    def remove_duplicates(self):
        """Remove duplicate emails"""
        recipients = self.db.get_recipients()
        if not recipients:
            messagebox.showinfo("Info", "No recipients found!")
            return
        
        # Database already handles duplicates on insert, so just show info
        messagebox.showinfo("Info", 
                          "Duplicate emails are automatically removed when importing.\n"
                          "All existing recipients are unique.")
    
    def filter_list(self, event=None):
        """Filter recipients by list"""
        self.load_recipients()
    
    def load_recipients(self):
        """Load recipients into table"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get filter
        list_filter = self.list_filter.get()
        list_name = None if list_filter == 'All Lists' else list_filter
        
        # Get recipients
        recipients = self.db.get_recipients(list_name=list_name)
        
        # Populate table
        for recipient in recipients:
            self.tree.insert('', tk.END, values=(
                recipient.get('email', ''),
                recipient.get('first_name', ''),
                recipient.get('last_name', ''),
                recipient.get('company', ''),
                recipient.get('city', ''),
                recipient.get('list_name', 'default')
            ))
        
        # Update stats
        self.stats_label.config(text=f"Total Recipients: {len(recipients)}")
        
        # Update list filter options
        all_lists = set(['default'])
        for r in recipients:
            if r.get('list_name'):
                all_lists.add(r['list_name'])
        
        self.list_filter['values'] = ['All Lists'] + sorted(all_lists)
    
    def delete_selected(self):
        """Delete selected recipients"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select recipients to delete!")
            return
        
        if messagebox.askyesno("Confirm", f"Delete {len(selection)} recipient(s)?"):
            # Implementation would require delete method in db_manager
            messagebox.showinfo("Info", "Delete functionality to be implemented in database layer")
    
    def unsubscribe_selected(self):
        """Unsubscribe selected recipients"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select recipients to unsubscribe!")
            return
        
        for item in selection:
            values = self.tree.item(item, 'values')
            email = values[0]
            self.db.unsubscribe_email(email)
        
        messagebox.showinfo("Success", f"Unsubscribed {len(selection)} recipient(s)")
        self.load_recipients()

