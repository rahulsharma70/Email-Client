"""
Dashboard UI for ANAGHA SOLUTION
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
import threading

class Dashboard:
    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db = db_manager
        
        # Main container
        container = tk.Frame(parent, bg='#ecf0f1')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(container, text="Dashboard", 
                        font=('Arial', 20, 'bold'), bg='#ecf0f1')
        title.pack(anchor='w', pady=(0, 20))
        
        # Stats frame
        stats_frame = tk.Frame(container, bg='#ecf0f1')
        stats_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.stats_cards = []
        self.create_stat_cards(stats_frame)
        
        # Charts frame
        charts_frame = tk.Frame(container, bg='#ecf0f1')
        charts_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left chart
        left_chart = tk.Frame(charts_frame, bg='white', relief=tk.RAISED, bd=1)
        left_chart.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        chart_title1 = tk.Label(left_chart, text="Campaign Performance", 
                               font=('Arial', 14, 'bold'), bg='white')
        chart_title1.pack(pady=10)
        
        self.chart_canvas1 = tk.Canvas(left_chart, bg='white', height=300)
        self.chart_canvas1.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Right chart
        right_chart = tk.Frame(charts_frame, bg='white', relief=tk.RAISED, bd=1)
        right_chart.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        chart_title2 = tk.Label(right_chart, text="Subscriber Growth", 
                               font=('Arial', 14, 'bold'), bg='white')
        chart_title2.pack(pady=10)
        
        self.chart_canvas2 = tk.Canvas(right_chart, bg='white', height=300)
        self.chart_canvas2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Update stats
        self.update_stats()
        
        # Auto-refresh every 5 seconds
        self.auto_refresh()
    
    def create_stat_cards(self, parent):
        """Create statistics cards"""
        stats = [
            ("Total Emails Sent Today", "sent_today", "#3498db"),
            ("Pending Queue", "pending", "#e74c3c"),
            ("Delivery Rate %", "delivery_rate", "#2ecc71"),
            ("Bounce Rate %", "bounce_rate", "#f39c12"),
            ("Spam Rate %", "spam_rate", "#e67e22"),
            ("Subscriber Growth", "subscribers", "#9b59b6")
        ]
        
        for i, (label, key, color) in enumerate(stats):
            card = tk.Frame(parent, bg=color, relief=tk.RAISED, bd=2)
            card.grid(row=0, column=i, padx=5, sticky='ew')
            parent.grid_columnconfigure(i, weight=1)
            
            label_widget = tk.Label(card, text=label, bg=color, fg='white',
                                   font=('Arial', 10))
            label_widget.pack(pady=(10, 5))
            
            value_widget = tk.Label(card, text="0", bg=color, fg='white',
                                   font=('Arial', 18, 'bold'))
            value_widget.pack(pady=(0, 10))
            
            self.stats_cards.append({
                'key': key,
                'value': value_widget
            })
    
    def update_stats(self):
        """Update dashboard statistics"""
        try:
            queue_stats = self.db.get_queue_stats()
            daily_stats = self.db.get_daily_stats()
            
            # Calculate rates
            total_sent = daily_stats.get('emails_sent', 0)
            delivered = daily_stats.get('emails_delivered', 0)
            bounced = daily_stats.get('emails_bounced', 0)
            spam = daily_stats.get('spam_reports', 0)
            
            delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
            bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
            spam_rate = (spam / total_sent * 100) if total_sent > 0 else 0
            
            # Get subscriber count
            recipients = self.db.get_recipients()
            subscriber_count = len(recipients)
            
            # Update cards
            for card in self.stats_cards:
                key = card['key']
                if key == 'sent_today':
                    card['value'].config(text=str(queue_stats.get('sent_today', 0)))
                elif key == 'pending':
                    card['value'].config(text=str(queue_stats.get('pending', 0)))
                elif key == 'delivery_rate':
                    card['value'].config(text=f"{delivery_rate:.1f}%")
                elif key == 'bounce_rate':
                    card['value'].config(text=f"{bounce_rate:.1f}%")
                elif key == 'spam_rate':
                    card['value'].config(text=f"{spam_rate:.1f}%")
                elif key == 'subscribers':
                    card['value'].config(text=str(subscriber_count))
            
            # Draw simple charts
            self.draw_chart1(daily_stats)
            self.draw_chart2()
            
        except Exception as e:
            print(f"Error updating stats: {e}")
    
    def draw_chart1(self, stats):
        """Draw campaign performance chart"""
        self.chart_canvas1.delete("all")
        width = self.chart_canvas1.winfo_width() or 400
        height = self.chart_canvas1.winfo_height() or 300
        
        if width < 10:
            return
        
        # Simple bar chart
        max_val = max(stats.get('emails_sent', 0), stats.get('emails_opened', 0), 
                     stats.get('emails_clicked', 0), 1)
        
        bar_width = width // 4
        bar_height = height - 40
        
        # Sent
        sent_height = (stats.get('emails_sent', 0) / max_val) * bar_height
        self.chart_canvas1.create_rectangle(bar_width * 0.5, height - sent_height - 20,
                                           bar_width * 1.5, height - 20,
                                           fill='#3498db', outline='')
        self.chart_canvas1.create_text(bar_width, height - 10, text="Sent", font=('Arial', 9))
        
        # Opened
        opened_height = (stats.get('emails_opened', 0) / max_val) * bar_height
        self.chart_canvas1.create_rectangle(bar_width * 1.7, height - opened_height - 20,
                                           bar_width * 2.7, height - 20,
                                           fill='#2ecc71', outline='')
        self.chart_canvas1.create_text(bar_width * 2.2, height - 10, text="Opened", font=('Arial', 9))
        
        # Clicked
        clicked_height = (stats.get('emails_clicked', 0) / max_val) * bar_height
        self.chart_canvas1.create_rectangle(bar_width * 2.9, height - clicked_height - 20,
                                           bar_width * 3.9, height - 20,
                                           fill='#f39c12', outline='')
        self.chart_canvas1.create_text(bar_width * 3.4, height - 10, text="Clicked", font=('Arial', 9))
    
    def draw_chart2(self):
        """Draw subscriber growth chart"""
        self.chart_canvas2.delete("all")
        width = self.chart_canvas2.winfo_width() or 400
        height = self.chart_canvas2.winfo_height() or 300
        
        if width < 10:
            return
        
        # Simple line chart placeholder
        recipients = self.db.get_recipients()
        count = len(recipients)
        
        # Draw a simple representation
        self.chart_canvas2.create_text(width // 2, height // 2, 
                                      text=f"Total Subscribers: {count}",
                                      font=('Arial', 16, 'bold'))
    
    def auto_refresh(self):
        """Auto-refresh dashboard"""
        self.update_stats()
        self.parent.after(5000, self.auto_refresh)
