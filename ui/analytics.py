"""
Analytics UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

class Analytics:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        
        container = tk.Frame(parent, bg='#ecf0f1')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="Analytics & Tracking", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(0, 20))
        
        # Campaign performance
        campaign_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        campaign_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        tk.Label(campaign_frame, text="Campaign Performance", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        # Campaign list
        list_frame = tk.Frame(campaign_frame, bg='white')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.campaigns_tree = ttk.Treeview(list_frame,
                                          columns=('Name', 'Subject', 'Sent', 'Opened', 'Clicked', 'Bounced', 'Status'),
                                          show='headings', yscrollcommand=scroll_y.set)
        
        scroll_y.config(command=self.campaigns_tree.yview)
        
        self.campaigns_tree.heading('Name', text='Campaign Name')
        self.campaigns_tree.heading('Subject', text='Subject')
        self.campaigns_tree.heading('Sent', text='Sent')
        self.campaigns_tree.heading('Opened', text='Opened')
        self.campaigns_tree.heading('Clicked', text='Clicked')
        self.campaigns_tree.heading('Bounced', text='Bounced')
        self.campaigns_tree.heading('Status', text='Status')
        
        self.campaigns_tree.column('Name', width=150)
        self.campaigns_tree.column('Subject', width=200)
        self.campaigns_tree.column('Sent', width=80)
        self.campaigns_tree.column('Opened', width=80)
        self.campaigns_tree.column('Clicked', width=80)
        self.campaigns_tree.column('Bounced', width=80)
        self.campaigns_tree.column('Status', width=100)
        
        self.campaigns_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Detailed stats
        stats_frame = tk.Frame(container, bg='white', relief=tk.RAISED, bd=2)
        stats_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(stats_frame, text="Detailed Statistics", font=('Arial', 14, 'bold'),
                bg='white').pack(anchor='w', padx=20, pady=(15, 10))
        
        stats_grid = tk.Frame(stats_frame, bg='white')
        stats_grid.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create stat cards
        self.stat_cards = []
        stats = [
            ("Email Opens", "opens", "#3498db"),
            ("Link Clicks", "clicks", "#2ecc71"),
            ("Bounce Rate", "bounces", "#e74c3c"),
            ("Spam Reports", "spam", "#f39c12"),
            ("Unsubscribes", "unsubscribes", "#9b59b6"),
            ("Delivery Rate", "delivery", "#1abc9c")
        ]
        
        for i, (label, key, color) in enumerate(stats):
            row = i // 3
            col = i % 3
            
            card = tk.Frame(stats_grid, bg=color, relief=tk.RAISED, bd=2)
            card.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            
            tk.Label(card, text=label, bg=color, fg='white',
                    font=('Arial', 11, 'bold')).pack(pady=(15, 5))
            
            value_label = tk.Label(card, text="0", bg=color, fg='white',
                                  font=('Arial', 18, 'bold'))
            value_label.pack(pady=(0, 15))
            
            self.stat_cards.append({
                'key': key,
                'value': value_label
            })
        
        stats_grid.grid_columnconfigure(0, weight=1)
        stats_grid.grid_columnconfigure(1, weight=1)
        stats_grid.grid_columnconfigure(2, weight=1)
        
        # Load data
        self.load_campaigns()
        self.update_stats()
    
    def load_campaigns(self):
        """Load campaigns"""
        # Clear existing items
        for item in self.campaigns_tree.get_children():
            self.campaigns_tree.delete(item)
        
        campaigns = self.db.get_campaigns()
        
        for campaign in campaigns:
            # Get stats for campaign (simplified)
            self.campaigns_tree.insert('', tk.END, values=(
                campaign.get('name', ''),
                campaign.get('subject', ''),
                '0',  # Sent count
                '0',  # Opened count
                '0',  # Clicked count
                '0',  # Bounced count
                campaign.get('status', 'draft')
            ))
    
    def update_stats(self):
        """Update statistics"""
        try:
            daily_stats = self.db.get_daily_stats()
            
            # Update stat cards
            for card in self.stat_cards:
                key = card['key']
                if key == 'opens':
                    card['value'].config(text=str(daily_stats.get('emails_opened', 0)))
                elif key == 'clicks':
                    card['value'].config(text=str(daily_stats.get('emails_clicked', 0)))
                elif key == 'bounces':
                    card['value'].config(text=str(daily_stats.get('emails_bounced', 0)))
                elif key == 'spam':
                    card['value'].config(text=str(daily_stats.get('spam_reports', 0)))
                elif key == 'unsubscribes':
                    card['value'].config(text=str(daily_stats.get('unsubscribes', 0)))
                elif key == 'delivery':
                    sent = daily_stats.get('emails_sent', 0)
                    delivered = daily_stats.get('emails_delivered', 0)
                    rate = (delivered / sent * 100) if sent > 0 else 0
                    card['value'].config(text=f"{rate:.1f}%")
        
        except Exception as e:
            print(f"Error updating stats: {e}")

