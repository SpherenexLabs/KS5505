




# """
# Complete Emotion Detection System with Enhanced Face Capture and Database Migration
# Install: pip install deepface opencv-python tensorflow pillow reportlab

# Features:
# - Secure admin authentication with enhanced password visibility
# - Real-time emotion detection with auto-capture
# - Manual face capture with 'Capture Face' button
# - Individual face cropping and saving
# - Face gallery with thumbnails
# - Enhanced export capabilities including face gallery
# - Professional reporting with capture type tracking
# - Database migration for existing installations
# """

# import tkinter as tk
# from tkinter import ttk, messagebox, filedialog
# import cv2
# import numpy as np
# from deepface import DeepFace
# import threading
# import time
# from PIL import Image, ImageTk
# from collections import deque, Counter
# import sqlite3
# import os
# import csv
# import hashlib
# import secrets
# from datetime import datetime, timedelta
# import json

# # -------------------- Password Security --------------------
# def hash_password(password: str, iterations: int = 200_000) -> str:
#     """Hash password using PBKDF2"""
#     salt = secrets.token_bytes(16)
#     dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#     return f"{iterations}${salt.hex()}${dk.hex()}"

# def verify_password(password: str, stored: str) -> bool:
#     """Verify password against stored hash"""
#     try:
#         iterations_s, salt_hex, hash_hex = stored.split("$")
#         iterations = int(iterations_s)
#         salt = bytes.fromhex(salt_hex)
#         target = bytes.fromhex(hash_hex)
#         dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#         return secrets.compare_digest(dk, target)
#     except Exception:
#         return False

# # -------------------- Database Manager with Migration --------------------
# class DatabaseManager:
#     def __init__(self, db_path="emotion_system.db"):
#         self.db_path = db_path
#         self.init_database()
#         self.migrate_database()  # Add migration step
    
#     def init_database(self):
#         """Initialize database with required tables"""
#         os.makedirs("snapshots", exist_ok=True)
#         os.makedirs("faces", exist_ok=True)  # New folder for cropped faces
        
#         conn = sqlite3.connect(self.db_path)
        
#         # Users table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY,
#                 username TEXT UNIQUE NOT NULL,
#                 password_hash TEXT NOT NULL,
#                 role TEXT DEFAULT 'admin',
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Original detections table structure (for new installations)
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS detections (
#                 id INTEGER PRIMARY KEY,
#                 timestamp TEXT NOT NULL,
#                 emotion TEXT NOT NULL,
#                 confidence REAL NOT NULL,
#                 snapshot_path TEXT NOT NULL,
#                 face_crop_path TEXT,
#                 face_region TEXT,
#                 capture_type TEXT DEFAULT 'auto',
#                 person_id TEXT,
#                 session_id TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Create indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")
        
#         # Create default admin user if none exists
#         cursor = conn.execute("SELECT COUNT(*) FROM users")
#         if cursor.fetchone()[0] == 0:
#             admin_hash = hash_password("admin123")
#             conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#                         ("admin", admin_hash, "admin"))
        
#         conn.commit()
#         conn.close()
    
#     def migrate_database(self):
#         """Migrate existing database to add new columns"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
        
#         try:
#             # Check if new columns exist
#             cursor.execute("PRAGMA table_info(detections)")
#             columns = [column[1] for column in cursor.fetchall()]
            
#             # Add missing columns
#             if 'face_crop_path' not in columns:
#                 print("Adding face_crop_path column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")
                
#             if 'face_region' not in columns:
#                 print("Adding face_region column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")
                
#             if 'capture_type' not in columns:
#                 print("Adding capture_type column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")
                
#             conn.commit()
#             print("Database migration completed successfully!")
            
#         except Exception as e:
#             print(f"Migration error (this is normal for new installations): {e}")
            
#         finally:
#             conn.close()
    
#     def verify_user(self, username: str, password: str) -> bool:
#         """Verify user credentials"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
#         result = cursor.fetchone()
#         conn.close()
        
#         if result:
#             return verify_password(password, result[0])
#         return False
    
#     def save_detection(self, timestamp: str, emotion: str, confidence: float, 
#                       snapshot_path: str, face_crop_path: str = None, face_region: str = None,
#                       capture_type: str = 'auto', person_id: str = None, session_id: str = None):
#         """Save detection to database"""
#         conn = sqlite3.connect(self.db_path)
#         try:
#             conn.execute("""
#                 INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
#                                       face_region, capture_type, person_id, session_id)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, 
#                   capture_type, person_id, session_id))
#             conn.commit()
#         except sqlite3.OperationalError as e:
#             # Fallback for old database structure
#             print(f"Database error, trying fallback: {e}")
#             try:
#                 conn.execute("""
#                     INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
#                 conn.commit()
#             except Exception as fallback_error:
#                 print(f"Fallback failed: {fallback_error}")
#         finally:
#             conn.close()
    
#     def get_detections(self, start_date=None, end_date=None, emotion=None, limit=1000):
#         """Get filtered detections from database"""
#         conn = sqlite3.connect(self.db_path)
        
#         # Check if new columns exist
#         cursor = conn.cursor()
#         cursor.execute("PRAGMA table_info(detections)")
#         columns = [column[1] for column in cursor.fetchall()]
        
#         # Build query based on available columns
#         base_columns = "timestamp, emotion, confidence, snapshot_path"
#         if 'face_crop_path' in columns:
#             base_columns += ", face_crop_path"
#         else:
#             base_columns += ", NULL as face_crop_path"
            
#         if 'face_region' in columns:
#             base_columns += ", face_region"
#         else:
#             base_columns += ", NULL as face_region"
            
#         if 'capture_type' in columns:
#             base_columns += ", capture_type"
#         else:
#             base_columns += ", 'auto' as capture_type"
            
#         base_columns += ", person_id"
        
#         query = f"SELECT {base_columns} FROM detections WHERE 1=1"
#         params = []
        
#         if start_date:
#             query += " AND timestamp >= ?"
#             params.append(start_date)
#         if end_date:
#             query += " AND timestamp <= ?"
#             params.append(end_date)
#         if emotion and emotion.lower() != "all":
#             query += " AND emotion = ?"
#             params.append(emotion.lower())
        
#         query += " ORDER BY timestamp DESC LIMIT ?"
#         params.append(limit)
        
#         cursor = conn.execute(query, params)
#         results = cursor.fetchall()
#         conn.close()
        
#         return results

# # -------------------- Enhanced Login Window --------------------
# class LoginWindow:
#     def __init__(self, db_manager):
#         self.db_manager = db_manager
#         self.success = False
#         self.username = None
        
#         self.root = tk.Tk()
#         self.root.title("Emotion Detection System - Admin Login")
#         self.root.geometry("500x400")
#         self.root.configure(bg='#2c3e50')
#         self.root.resizable(False, False)
        
#         # Center the window
#         self.root.eval('tk::PlaceWindow . center')
        
#         self.setup_ui()
    
#     def setup_ui(self):
#         """Setup enhanced login UI with password features"""
#         # Main frame
#         main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
#         main_frame.pack(fill='both', expand=True)
        
#         # Title
#         title_label = tk.Label(main_frame, text="Admin Login", 
#                               font=('Arial', 24, 'bold'), 
#                               bg='#2c3e50', fg='white')
#         title_label.pack(pady=(0, 15))
        
#         # Login form
#         form_frame = tk.Frame(main_frame, bg='#2c3e50')
#         form_frame.pack(fill='x')
        
#         # Username
#         tk.Label(form_frame, text="Username:", font=('Arial', 12), 
#                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        
#         self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
#                                       bg='#34495e', fg='white', insertbackground='white',
#                                       relief='flat', bd=5)
#         self.username_entry.pack(fill='x', pady=(0, 15))
#         self.username_entry.insert(0, "admin")
        
#         # Password
#         tk.Label(form_frame, text="Password:", font=('Arial', 12), 
#                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        
#         self.password_entry = tk.Entry(form_frame, font=('Arial', 12), 
#                                       show="\u2022", bg='#34495e', fg='white',
#                                       insertbackground='white', relief='flat', bd=5)
#         self.password_entry.pack(fill='x', pady=(0, 10))
#         self.password_entry.bind('<KeyRelease>', self.update_password_feedback)
        
#         # Show password toggle and feedback
#         toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
#         toggle_frame.pack(fill='x', pady=(5, 10))
        
#         self.show_password_var = tk.BooleanVar()
#         show_password_check = tk.Checkbutton(
#             toggle_frame, 
#             text="Show Password", 
#             variable=self.show_password_var,
#             command=self.toggle_password_visibility,
#             bg='#2c3e50', 
#             fg='#bdc3c7',
#             selectcolor='#2c3e50',
#             font=('Arial', 10)
#         )
#         show_password_check.pack(side='left')
        
#         self.password_length_label = tk.Label(
#             toggle_frame, 
#             text="Characters: 0", 
#             font=('Arial', 9),
#             bg='#2c3e50', 
#             fg='#7f8c8d'
#         )
#         self.password_length_label.pack(side='right')
        
#         # Default credentials info
#         info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
#         info_frame.pack(fill='x', pady=(0, 20))
        
#         tk.Label(info_frame, text="Default: admin / admin123", 
#                 font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)
        
#         # Buttons
#         button_frame = tk.Frame(form_frame, bg='#2c3e50')
#         button_frame.pack(fill='x', pady=(10, 0))
        
#         login_btn = tk.Button(button_frame, text="Login", 
#                              command=self.login,
#                              bg='#27ae60', fg='white', 
#                              font=('Arial', 12, 'bold'),
#                              padx=30, pady=10, relief='flat')
#         login_btn.pack(side='left', padx=(0, 10))
        
#         cancel_btn = tk.Button(button_frame, text="Cancel", 
#                               command=self.cancel,
#                               bg='#e74c3c', fg='white', 
#                               font=('Arial', 12, 'bold'),
#                               padx=30, pady=10, relief='flat')
#         cancel_btn.pack(side='left')
        
#         # Bind Enter key
#         self.root.bind('<Return>', lambda e: self.login())
#         self.password_entry.focus()
    
#     def toggle_password_visibility(self):
#         """Toggle password field visibility"""
#         if self.show_password_var.get():
#             self.password_entry.config(show="")
#         else:
#             self.password_entry.config(show="\u2022")
    
#     def update_password_feedback(self, event=None):
#         """Update password input feedback"""
#         length = len(self.password_entry.get())
#         self.password_length_label.config(text=f"Characters: {length}")
    
#     def login(self):
#         """Handle login attempt"""
#         username = self.username_entry.get().strip()
#         password = self.password_entry.get()
        
#         if not username or not password:
#             messagebox.showerror("Error", "Please enter both username and password")
#             return
        
#         if self.db_manager.verify_user(username, password):
#             self.success = True
#             self.username = username
#             self.root.destroy()
#         else:
#             messagebox.showerror("Login Failed", "Invalid username or password")
#             self.password_entry.delete(0, tk.END)
#             self.password_entry.focus()
#             self.password_length_label.config(text="Characters: 0")
    
#     def cancel(self):
#         """Handle cancel"""
#         self.root.destroy()
    
#     def show(self):
#         """Show login window and return success status"""
#         self.root.mainloop()
#         return self.success, self.username

# # -------------------- Main Application --------------------
# class EmotionDetectionSystem:
#     def __init__(self, username):
#         self.username = username
#         self.db_manager = DatabaseManager()
#         self.session_id = f"session_{int(time.time())}"
        
#         # Core variables
#         self.cap = None
#         self.is_running = False
#         self.current_emotions = []
#         self.latest_frame = None
#         self.frame_count = 0
#         self.start_time = time.time()
#         self.last_capture_time = 0
#         self.capture_cooldown = 3.0  # Seconds between auto-captures
        
#         # Setup main window
#         self.root = tk.Tk()
#         self.root.title(f"Emotion Detection System - Welcome {username}")
#         self.root.geometry("1500x950")
#         self.root.configure(bg='#2c3e50')
        
#         self.setup_ui()
#         self.start_display_thread()
        
#         # Load initial data
#         self.apply_filters()
    
#     def setup_ui(self):
#         """Setup main application UI"""
#         # Header
#         header = tk.Frame(self.root, bg='#2c3e50', height=70)
#         header.pack(fill='x', padx=15, pady=10)
#         header.pack_propagate(False)
        
#         # Title and user info
#         title_frame = tk.Frame(header, bg='#2c3e50')
#         title_frame.pack(side='left', fill='y')
        
#         tk.Label(title_frame, text="Emotion Detection System", 
#                 font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
#         tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}", 
#                 font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')
        
#         # Controls
#         controls = tk.Frame(header, bg='#2c3e50')
#         controls.pack(side='right', fill='y')
        
#         self.start_btn = tk.Button(controls, text="Start Detection", command=self.start_detection,
#                                   bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), 
#                                   padx=20, pady=8, relief='flat')
#         self.start_btn.pack(side='left', padx=5)
        
#         self.stop_btn = tk.Button(controls, text="Stop Detection", command=self.stop_detection,
#                                  bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'), 
#                                  padx=20, pady=8, state='disabled', relief='flat')
#         self.stop_btn.pack(side='left', padx=5)
        
#         # Manual capture button
#         self.capture_btn = tk.Button(controls, text="Capture Face", command=self.manual_capture,
#                                     bg='#f39c12', fg='white', font=('Arial', 12, 'bold'), 
#                                     padx=20, pady=8, state='disabled', relief='flat')
#         self.capture_btn.pack(side='left', padx=5)
        
#         # Main content
#         main_frame = tk.Frame(self.root, bg='#2c3e50')
#         main_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
#         # Left side - Camera and real-time detection
#         left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
#         left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
#         # Camera section
#         camera_header = tk.Frame(left_frame, bg='#34495e')
#         camera_header.pack(fill='x', pady=10)
        
#         tk.Label(camera_header, text="Live Camera Feed", bg='#34495e', fg='white', 
#                 font=('Arial', 16, 'bold')).pack(side='left', padx=15)
        
#         self.detection_status = tk.StringVar(value="Camera stopped")
#         tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12', 
#                 font=('Arial', 12, 'bold')).pack(side='right', padx=15)
        
#         # Camera display
#         self.camera_label = tk.Label(left_frame, text="Camera feed will appear here\n\nClick 'Start Detection' to begin",
#                                     bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
#                                     width=70, height=20)
#         self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)
        
#         # Real-time detections list
#         rt_frame = tk.Frame(left_frame, bg='#34495e')
#         rt_frame.pack(fill='x', padx=15, pady=(0, 15))
        
#         tk.Label(rt_frame, text="Recent Live Detections", bg='#34495e', fg='white', 
#                 font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
        
#         self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
#                                          font=('Consolas', 10), relief='flat')
#         self.live_detections.pack(fill='x')
        
#         # Right side - Dashboard
#         right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
#         right_frame.pack(side='right', fill='y')
#         right_frame.pack_propagate(False)
        
#         # Create notebook for tabs
#         notebook = ttk.Notebook(right_frame)
#         notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Filters tab
#         filters_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(filters_frame, text="Filters & History")
#         self.setup_filters_tab(filters_frame)
        
#         # Face Gallery tab
#         gallery_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(gallery_frame, text="Face Gallery")
#         self.setup_gallery_tab(gallery_frame)
        
#         # Export tab
#         export_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(export_frame, text="Export")
#         self.setup_export_tab(export_frame)
        
#         # Status bar
#         status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
#         status_frame.pack(fill='x', padx=15, pady=5)
        
#         self.status_var = tk.StringVar(value="Ready - Click 'Start Detection' to begin")
#         tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
#                 font=('Arial', 10)).pack(side='left', pady=5)
    
#     def setup_filters_tab(self, parent):
#         """Setup filters and history tab"""
#         # Date filters
#         tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
#         self.start_date_entry = tk.Entry(parent, width=30)
#         self.start_date_entry.pack(padx=10, pady=5)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.end_date_entry = tk.Entry(parent, width=30)
#         self.end_date_entry.pack(padx=10, pady=5)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
#         # Emotion filter
#         tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.emotion_filter = ttk.Combobox(parent, values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"], 
#                                           state="readonly", width=27)
#         self.emotion_filter.pack(padx=10, pady=5)
#         self.emotion_filter.set("All")
        
#         # Filter buttons
#         btn_frame = tk.Frame(parent, bg='#34495e')
#         btn_frame.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
#                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
#                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left')
        
#         # Detection history
#         history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         history_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Treeview for detections
#         columns = ("Time", "Emotion", "Confidence", "Type")
#         self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
        
#         # Column configurations
#         self.detection_tree.heading("Time", text="Timestamp")
#         self.detection_tree.heading("Emotion", text="Emotion")
#         self.detection_tree.heading("Confidence", text="Confidence")
#         self.detection_tree.heading("Type", text="Capture")
#         self.detection_tree.column("Time", width=120)
#         self.detection_tree.column("Emotion", width=80)
#         self.detection_tree.column("Confidence", width=80)
#         self.detection_tree.column("Type", width=60)
        
#         # Scrollbar
#         tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
#         self.detection_tree.configure(yscrollcommand=tree_scroll.set)
        
#         self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
#         tree_scroll.pack(side='right', fill='y', pady=10)
        
#         # Bind double-click to view face
#         self.detection_tree.bind('<Double-1>', self.view_face_image)
    
#     def setup_gallery_tab(self, parent):
#         """Setup face gallery tab"""
#         # Gallery controls
#         gallery_controls = tk.Frame(parent, bg='#34495e')
#         gallery_controls.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
#                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
        
#         tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
#                  bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left')
        
#         # Face thumbnails display
#         gallery_frame = tk.Frame(parent, bg='#34495e')
#         gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Scrollable canvas for face thumbnails
#         self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
#         gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
#         self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')
        
#         self.scrollable_gallery.bind(
#             "<Configure>",
#             lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
#         )
        
#         self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
#         self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
        
#         self.gallery_canvas.pack(side="left", fill="both", expand=True)
#         gallery_scrollbar.pack(side="right", fill="y")
        
#         self.face_thumbnails = []  # Store face thumbnail references
    
#     def setup_export_tab(self, parent):
#         """Setup export tab"""
#         # Export options
#         export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         export_frame.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
#                  bg='#16a085', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        
#         tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
#                  bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        
#         tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
#                  bg='#e67e22', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
    
#     def start_display_thread(self):
#         """Start display update thread"""
#         self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
#         self.display_thread.start()
    
#     def start_detection(self):
#         """Start emotion detection"""
#         try:
#             # Try different camera indices
#             for camera_idx in [0, 1, 2]:
#                 self.cap = cv2.VideoCapture(camera_idx)
#                 if self.cap.isOpened():
#                     break
#                 self.cap.release()
            
#             if not self.cap.isOpened():
#                 messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
#                 return
            
#             # Set camera properties
#             self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
#             self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
#             self.cap.set(cv2.CAP_PROP_FPS, 30)
            
#             self.is_running = True
#             self.start_time = time.time()
#             self.frame_count = 0
            
#             # Update UI
#             self.start_btn.config(state='disabled')
#             self.stop_btn.config(state='normal')
#             self.capture_btn.config(state='normal')
#             self.detection_status.set("Detection running...")
            
#             # Start detection threads
#             threading.Thread(target=self.detection_loop, daemon=True).start()
            
#             self.status_var.set("Detection started - Auto-capturing emotions every 3 seconds")
            
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
    
#     def stop_detection(self):
#         """Stop emotion detection"""
#         self.is_running = False
        
#         if self.cap:
#             self.cap.release()
#             self.cap = None
        
#         # Update UI
#         self.start_btn.config(state='normal')
#         self.stop_btn.config(state='disabled')
#         self.capture_btn.config(state='disabled')
#         self.detection_status.set("Detection stopped")
#         self.camera_label.config(image="", text="Detection stopped\nStart Detection to resume")
#         self.status_var.set("Detection stopped")
    
#     def manual_capture(self):
#         """Manually capture current frame with all detected faces"""
#         if not self.is_running or self.latest_frame is None:
#             messagebox.showwarning("Capture Error", "Please start detection first")
#             return
        
#         try:
#             frame = self.latest_frame.copy()
#             timestamp = datetime.now()
            
#             if self.current_emotions:
#                 for i, emotion_data in enumerate(self.current_emotions):
#                     emotion = emotion_data['dominant_emotion']
#                     confidence = emotion_data['emotion'][emotion]
                    
#                     # Capture this face
#                     self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
                
#                 self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
#             else:
#                 messagebox.showinfo("Capture Info", "No faces detected in current frame")
                
#         except Exception as e:
#             messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")
    
#     def detection_loop(self):
#         """Main detection loop"""
#         while self.is_running:
#             try:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     time.sleep(0.01)
#                     continue
                
#                 # Flip frame horizontally for mirror effect
#                 frame = cv2.flip(frame, 1)
#                 self.latest_frame = frame.copy()
#                 self.frame_count += 1
                
#                 # Analyze every 10th frame
#                 if self.frame_count % 10 == 0:
#                     threading.Thread(target=self.analyze_emotion, 
#                                    args=(frame.copy(),), daemon=True).start()
                
#                 time.sleep(0.033)  # ~30 FPS
                
#             except Exception:
#                 time.sleep(0.1)
    
#     def analyze_emotion(self, frame):
#         """Analyze emotions and auto-capture"""
#         try:
#             # Convert to RGB for DeepFace
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
#             # Analyze emotions
#             results = DeepFace.analyze(
#                 img_path=rgb_frame,
#                 actions=['emotion'],
#                 detector_backend='opencv',
#                 enforce_detection=False,
#                 silent=True
#             )
            
#             if isinstance(results, list):
#                 self.current_emotions = results
#             else:
#                 self.current_emotions = [results]
            
#             # Auto-capture high-confidence detections
#             current_time = time.time()
#             if current_time - self.last_capture_time >= self.capture_cooldown:
#                 for emotion_data in self.current_emotions:
#                     try:
#                         emotion = emotion_data['dominant_emotion']
#                         confidence = emotion_data['emotion'][emotion]
                        
#                         if confidence > 60:  # High confidence threshold
#                             self.capture_emotion(emotion_data, frame.copy())
#                             self.last_capture_time = current_time
#                             break  # Only capture one per cooldown period
#                     except Exception:
#                         continue
                        
#         except Exception:
#             pass
    
#     def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
#         """Capture and save emotion detection with face cropping"""
#         try:
#             emotion = emotion_data['dominant_emotion']
#             confidence = emotion_data['emotion'][emotion]
#             timestamp = datetime.now()
            
#             # Extract face region
#             region = emotion_data['region']
#             x, y, w, h = region['x'], region['y'], region['w'], region['h']
            
#             # Add padding to face crop
#             padding = 20
#             x1 = max(0, x - padding)
#             y1 = max(0, y - padding)
#             x2 = min(frame.shape[1], x + w + padding)
#             y2 = min(frame.shape[0], y + h + padding)
            
#             # Crop face from original frame
#             face_crop = frame[y1:y2, x1:x2]
            
#             # Draw emotion on full frame
#             color = self.get_emotion_color(emotion)
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#             label = f"{emotion.upper()}: {confidence:.1f}%"
#             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
#             # Save full frame snapshot
#             snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
#             cv2.imwrite(snapshot_filename, frame)
            
#             # Save face crop if folder exists
#             face_filename = None
#             if os.path.exists("faces"):
#                 face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
#                 cv2.imwrite(face_filename, face_crop)
            
#             # Save region info as JSON
#             region_json = json.dumps({
#                 'x': x, 'y': y, 'w': w, 'h': h,
#                 'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
#             })
            
#             # Save to database with error handling
#             try:
#                 self.db_manager.save_detection(
#                     timestamp.isoformat(),
#                     emotion,
#                     confidence,
#                     snapshot_filename,
#                     face_filename,
#                     region_json,
#                     capture_type,
#                     "person1",
#                     self.session_id
#                 )
#                 print(f"Successfully saved detection: {emotion} {confidence:.1f}%")
#             except Exception as db_error:
#                 print(f"Database save error: {db_error}")
#                 # Continue anyway - at least the files are saved
            
#             # Update live detections list
#             detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
#             if self.live_detections.size() > 20:  # Keep only last 20
#                 self.root.after(0, lambda: self.live_detections.delete(tk.END))
            
#             # Update status
#             status_msg = f"Captured {emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.status_var.set(status_msg))
            
#             # Refresh gallery if it's the active tab
#             self.root.after(1000, self.refresh_gallery)
            
#         except Exception as e:
#             print(f"Capture error: {e}")
    
#     def refresh_gallery(self):
#         """Refresh the face gallery with latest captures"""
#         try:
#             # Clear existing thumbnails
#             for widget in self.scrollable_gallery.winfo_children():
#                 widget.destroy()
#             self.face_thumbnails = []
            
#             # Get recent detections with face crops
#             detections = self.db_manager.get_detections(limit=50)
            
#             # Display face thumbnails in grid
#             row, col = 0, 0
#             max_cols = 3
            
#             for detection in detections:
#                 timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         # Load and resize face image
#                         face_img = cv2.imread(face_crop_path)
#                         face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                         face_img = cv2.resize(face_img, (100, 100))
                        
#                         # Convert to PhotoImage
#                         pil_img = Image.fromarray(face_img)
#                         photo = ImageTk.PhotoImage(pil_img)
                        
#                         # Create frame for each thumbnail
#                         thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
#                         thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
                        
#                         # Face image
#                         face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
#                         face_label.pack(pady=5)
#                         face_label.image = photo  # Keep reference
                        
#                         # Emotion label
#                         dt = datetime.fromisoformat(timestamp)
#                         emotion_text = f"{emotion.upper()}: {confidence:.1f}%"
#                         time_text = dt.strftime('%m/%d %H:%M')
#                         type_text = f"[{capture_type.upper() if capture_type else 'AUTO'}]"
                        
#                         tk.Label(thumb_frame, text=emotion_text, bg='#2c3e50', fg='white',
#                                 font=('Arial', 8, 'bold')).pack()
#                         tk.Label(thumb_frame, text=time_text, bg='#2c3e50', fg='#bdc3c7',
#                                 font=('Arial', 7)).pack()
#                         tk.Label(thumb_frame, text=type_text, bg='#2c3e50', fg='#f39c12',
#                                 font=('Arial', 7)).pack()
                        
#                         # Store reference for viewing
#                         self.face_thumbnails.append({
#                             'frame': thumb_frame,
#                             'path': face_crop_path,
#                             'snapshot_path': snapshot_path,
#                             'data': detection
#                         })
                        
#                         # Bind click to view larger
#                         face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))
                        
#                         col += 1
#                         if col >= max_cols:
#                             col = 0
#                             row += 1
                            
#                     except Exception as e:
#                         print(f"Thumbnail error: {e}")
#                         continue
            
#             # Update scroll region
#             self.scrollable_gallery.update_idletasks()
#             self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
            
#         except Exception as e:
#             print(f"Gallery refresh error: {e}")
    
#     def view_face_full(self, face_path):
#         """View face image in full size"""
#         try:
#             if os.path.exists(face_path):
#                 # Create new window for full view
#                 view_window = tk.Toplevel(self.root)
#                 view_window.title("Face View")
#                 view_window.configure(bg='#2c3e50')
                
#                 # Load and display image
#                 face_img = cv2.imread(face_path)
#                 face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                
#                 # Resize for viewing (max 400x400)
#                 h, w = face_img.shape[:2]
#                 max_size = 400
#                 if max(h, w) > max_size:
#                     scale = max_size / max(h, w)
#                     new_w, new_h = int(w * scale), int(h * scale)
#                     face_img = cv2.resize(face_img, (new_w, new_h))
                
#                 pil_img = Image.fromarray(face_img)
#                 photo = ImageTk.PhotoImage(pil_img)
                
#                 label = tk.Label(view_window, image=photo, bg='#2c3e50')
#                 label.pack(padx=20, pady=20)
#                 label.image = photo  # Keep reference
                
#                 # Center window
#                 view_window.update_idletasks()
#                 x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
#                 y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
#                 view_window.geometry(f'+{x}+{y}')
                
#         except Exception as e:
#             messagebox.showerror("View Error", f"Cannot view face: {str(e)}")
    
#     def view_face_image(self, event):
#         """View face from detection tree double-click"""
#         selection = self.detection_tree.selection()
#         if selection:
#             item = self.detection_tree.item(selection[0])
#             # Get the detection data and show face
#             # This would need to store more data in the tree or query DB
#             pass
    
#     def view_selected_face(self):
#         """View selected face from gallery"""
#         # This could be enhanced to track selected thumbnails
#         messagebox.showinfo("Info", "Click on any face thumbnail to view full size")
    
#     def update_display_loop(self):
#         """Update camera display with emotion overlays"""
#         while True:
#             try:
#                 if self.is_running and self.latest_frame is not None:
#                     frame = self.latest_frame.copy()
                    
#                     # Draw emotion overlays
#                     for emotion_data in self.current_emotions:
#                         try:
#                             region = emotion_data['region']
#                             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                             emotion = emotion_data['dominant_emotion']
#                             confidence = emotion_data['emotion'][emotion]
#                             color = self.get_emotion_color(emotion)
                            
#                             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#                             label = f"{emotion.upper()}: {confidence:.1f}%"
#                             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                         except Exception:
#                             continue
                    
#                     # Convert and display
#                     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#                     pil_image = Image.fromarray(rgb_frame)
#                     pil_image = pil_image.resize((800, 600), Image.Resampling.LANCZOS)
#                     photo = ImageTk.PhotoImage(pil_image)
                    
#                     self.camera_label.configure(image=photo, text="")
#                     self.camera_label.image = photo
                
#                 time.sleep(0.033)  # ~30 FPS
                
#             except Exception:
#                 time.sleep(0.1)
    
#     def get_emotion_color(self, emotion):
#         """Get color for each emotion"""
#         colors = {
#             'happy': (0, 255, 0),      # Green
#             'sad': (255, 100, 100),    # Light Blue
#             'angry': (0, 0, 255),      # Red
#             'fear': (255, 0, 255),     # Magenta
#             'surprise': (0, 255, 255), # Yellow
#             'disgust': (128, 0, 128),  # Purple
#             'neutral': (128, 128, 128) # Gray
#         }
#         return colors.get(emotion, (255, 255, 255))
    
#     def apply_filters(self):
#         """Apply filters and refresh data"""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             # Clear and populate tree
#             for item in self.detection_tree.get_children():
#                 self.detection_tree.delete(item)
            
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 # Format timestamp for display
#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%m/%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 self.detection_tree.insert('', 'end', values=(formatted_time, emotion_name.upper(), f"{confidence:.1f}%", type_display))
            
#             self.status_var.set(f"Loaded {len(detections)} detections")
            
#             # Refresh gallery too
#             self.refresh_gallery()
            
#         except Exception as e:
#             messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
    
#     def clear_filters(self):
#         """Clear all filters"""
#         self.start_date_entry.delete(0, tk.END)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
#         self.end_date_entry.delete(0, tk.END)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
#         self.emotion_filter.set("All")
#         self.apply_filters()
    
#     def export_csv(self):
#         """Export detections to CSV"""
#         try:
#             # Get current filtered data
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".csv",
#                 filetypes=[("CSV files", "*.csv")],
#                 initialname=f"emotion_detections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#             )
            
#             if filename:
#                 with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#                     writer = csv.writer(csvfile)
#                     writer.writerow(["Timestamp", "Emotion", "Confidence", "Snapshot Path", "Face Crop Path", "Face Region", "Capture Type", "Person ID"])
#                     for detection in detections:
#                         writer.writerow(detection)
                
#                 messagebox.showinfo("Export", f"Data exported successfully to {filename}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")
    
#     def export_pdf(self):
#         """Export detections to PDF report"""
#         try:
#             from reportlab.lib.pagesizes import A4
#             from reportlab.pdfgen import canvas
#             from reportlab.lib.units import inch
#         except ImportError:
#             messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
#             return
        
#         try:
#             # Get current filtered data
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".pdf",
#                 filetypes=[("PDF files", "*.pdf")],
#                 initialname=f"emotion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#             )
            
#             if filename:
#                 c = canvas.Canvas(filename, pagesize=A4)
#                 width, height = A4
                
#                 # Title
#                 c.setFont("Helvetica-Bold", 20)
#                 c.drawString(50, height - 50, "Emotion Detection Report")
                
#                 # Statistics
#                 total = len(detections)
#                 emotion_counts = Counter([d[1] for d in detections])
#                 auto_count = sum(1 for d in detections if d[6] == 'auto')
#                 manual_count = sum(1 for d in detections if d[6] == 'manual')
                
#                 c.setFont("Helvetica-Bold", 14)
#                 c.drawString(50, height - 100, f"Total Detections: {total}")
#                 c.drawString(50, height - 120, f"Auto Captures: {auto_count}")
#                 c.drawString(50, height - 140, f"Manual Captures: {manual_count}")
                
#                 c.setFont("Helvetica-Bold", 14)
#                 c.drawString(50, height - 180, "Emotion Distribution:")
#                 c.setFont("Helvetica", 12)
#                 y_pos = 200
                
#                 for emotion, count in emotion_counts.most_common():
#                     percentage = (count / len(detections)) * 100
#                     c.drawString(70, height - y_pos, f"{emotion.upper()}: {count} ({percentage:.1f}%)")
#                     y_pos += 20
                
#                 # Recent detections
#                 c.setFont("Helvetica-Bold", 14)
#                 c.drawString(50, height - y_pos - 20, "Recent Detections:")
#                 c.setFont("Helvetica", 10)
#                 y_pos += 60
                
#                 for i, detection in enumerate(detections[:25]):  # First 25 detections
#                     if y_pos > height - 100:  # New page if needed
#                         c.showPage()
#                         y_pos = 50
                    
#                     timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                     dt = datetime.fromisoformat(timestamp)
#                     formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
#                     type_display = capture_type.upper() if capture_type else 'AUTO'
#                     text = f"{i+1:3d}. {formatted_time} - {emotion_name.upper()}: {confidence:.1f}% [{type_display}]"
#                     c.drawString(70, height - y_pos, text)
#                     y_pos += 15
                
#                 c.save()
#                 messagebox.showinfo("Export", f"Report exported successfully to {filename}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")
    
#     def export_faces(self):
#         """Export face gallery as ZIP file"""
#         try:
#             import zipfile
            
#             # Check if faces folder exists
#             if not os.path.exists("faces"):
#                 messagebox.showinfo("Export", "No faces folder found")
#                 return
            
#             # Get all face files
#             face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
            
#             if not face_files:
#                 messagebox.showinfo("Export", "No face images to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".zip",
#                 filetypes=[("ZIP files", "*.zip")],
#                 initialname=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
#             )
            
#             if filename:
#                 with zipfile.ZipFile(filename, 'w') as zipf:
#                     for face_file in face_files:
#                         face_path = os.path.join("faces", face_file)
#                         zipf.write(face_path, face_file)
                
#                 messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")
    
#     def run(self):
#         """Run the application"""
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
#         self.root.mainloop()
    
#     def on_closing(self):
#         """Handle application closing"""
#         if self.is_running:
#             self.stop_detection()
#         self.root.destroy()

# # -------------------- Main Application Entry Point --------------------
# def main():
#     """Main application entry point"""
#     print("Starting Enhanced Emotion Detection System with Database Migration...")
#     print("Features:")
#     print("- Secure admin authentication with enhanced password visibility")
#     print("- Real-time emotion detection with auto-capture")
#     print("- Manual face capture with 'Capture Face' button")
#     print("- Individual face cropping and saving")
#     print("- Face gallery with thumbnails")
#     print("- Enhanced export capabilities including face gallery")
#     print("- Professional reporting with capture type tracking")
#     print("- Automatic database migration for existing installations")
    
#     # Initialize database with migration
#     db_manager = DatabaseManager()
    
#     # Show login window
#     login_window = LoginWindow(db_manager)
#     success, username = login_window.show()
    
#     if success:
#         print(f"Login successful for user: {username}")
#         # Start main application
#         app = EmotionDetectionSystem(username)
#         app.run()
#     else:
#         print("Login cancelled or failed")

# if __name__ == "__main__":
#     main()




















# """
# Complete Emotion Detection System with Enhanced Face Capture and Database Migration
# Install: pip install deepface opencv-python tensorflow pillow reportlab

# Features:
# - Secure admin authentication with enhanced password visibility
# - Real-time emotion detection with auto-capture
# - Manual face capture with 'Capture Face' button
# - Individual face cropping and saving
# - Face gallery with thumbnails
# - Enhanced export capabilities including face gallery with Base64 image embedding
# - Professional reporting with embedded images and capture type tracking
# - Database migration for existing installations
# """

# import tkinter as tk
# from tkinter import ttk, messagebox, filedialog
# import cv2
# import numpy as np
# from deepface import DeepFace
# import threading
# import time
# from PIL import Image, ImageTk
# from collections import deque, Counter
# import sqlite3
# import os
# import csv
# import hashlib
# import secrets
# from datetime import datetime, timedelta
# import json
# import base64

# # -------------------- Password Security --------------------
# def hash_password(password: str, iterations: int = 200_000) -> str:
#     """Hash password using PBKDF2"""
#     salt = secrets.token_bytes(16)
#     dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#     return f"{iterations}${salt.hex()}${dk.hex()}"

# def verify_password(password: str, stored: str) -> bool:
#     """Verify password against stored hash"""
#     try:
#         iterations_s, salt_hex, hash_hex = stored.split("$")
#         iterations = int(iterations_s)
#         salt = bytes.fromhex(salt_hex)
#         target = bytes.fromhex(hash_hex)
#         dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#         return secrets.compare_digest(dk, target)
#     except Exception:
#         return False

# # -------------------- Database Manager with Migration --------------------
# class DatabaseManager:
#     def __init__(self, db_path="emotion_system.db"):
#         self.db_path = db_path
#         self.init_database()
#         self.migrate_database()  # Add migration step
    
#     def init_database(self):
#         """Initialize database with required tables"""
#         os.makedirs("snapshots", exist_ok=True)
#         os.makedirs("faces", exist_ok=True)  # New folder for cropped faces
        
#         conn = sqlite3.connect(self.db_path)
        
#         # Users table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY,
#                 username TEXT UNIQUE NOT NULL,
#                 password_hash TEXT NOT NULL,
#                 role TEXT DEFAULT 'admin',
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Original detections table structure (for new installations)
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS detections (
#                 id INTEGER PRIMARY KEY,
#                 timestamp TEXT NOT NULL,
#                 emotion TEXT NOT NULL,
#                 confidence REAL NOT NULL,
#                 snapshot_path TEXT NOT NULL,
#                 face_crop_path TEXT,
#                 face_region TEXT,
#                 capture_type TEXT DEFAULT 'auto',
#                 person_id TEXT,
#                 session_id TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Create indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")
        
#         # Create default admin user if none exists
#         cursor = conn.execute("SELECT COUNT(*) FROM users")
#         if cursor.fetchone()[0] == 0:
#             admin_hash = hash_password("admin123")
#             conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#                         ("admin", admin_hash, "admin"))
        
#         conn.commit()
#         conn.close()
    
#     def migrate_database(self):
#         """Migrate existing database to add new columns"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
        
#         try:
#             # Check if new columns exist
#             cursor.execute("PRAGMA table_info(detections)")
#             columns = [column[1] for column in cursor.fetchall()]
            
#             # Add missing columns
#             if 'face_crop_path' not in columns:
#                 print("Adding face_crop_path column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")
                
#             if 'face_region' not in columns:
#                 print("Adding face_region column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")
                
#             if 'capture_type' not in columns:
#                 print("Adding capture_type column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")
                
#             conn.commit()
#             print("Database migration completed successfully!")
            
#         except Exception as e:
#             print(f"Migration error (this is normal for new installations): {e}")
            
#         finally:
#             conn.close()
    
#     def verify_user(self, username: str, password: str) -> bool:
#         """Verify user credentials"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
#         result = cursor.fetchone()
#         conn.close()
        
#         if result:
#             return verify_password(password, result[0])
#         return False
    
#     def save_detection(self, timestamp: str, emotion: str, confidence: float, 
#                       snapshot_path: str, face_crop_path: str = None, face_region: str = None,
#                       capture_type: str = 'auto', person_id: str = None, session_id: str = None):
#         """Save detection to database"""
#         conn = sqlite3.connect(self.db_path)
#         try:
#             conn.execute("""
#                 INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
#                                       face_region, capture_type, person_id, session_id)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, 
#                   capture_type, person_id, session_id))
#             conn.commit()
#         except sqlite3.OperationalError as e:
#             # Fallback for old database structure
#             print(f"Database error, trying fallback: {e}")
#             try:
#                 conn.execute("""
#                     INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
#                 conn.commit()
#             except Exception as fallback_error:
#                 print(f"Fallback failed: {fallback_error}")
#         finally:
#             conn.close()
    
#     def get_detections(self, start_date=None, end_date=None, emotion=None, limit=1000):
#         """Get filtered detections from database"""
#         conn = sqlite3.connect(self.db_path)
        
#         # Check if new columns exist
#         cursor = conn.cursor()
#         cursor.execute("PRAGMA table_info(detections)")
#         columns = [column[1] for column in cursor.fetchall()]
        
#         # Build query based on available columns
#         base_columns = "timestamp, emotion, confidence, snapshot_path"
#         if 'face_crop_path' in columns:
#             base_columns += ", face_crop_path"
#         else:
#             base_columns += ", NULL as face_crop_path"
            
#         if 'face_region' in columns:
#             base_columns += ", face_region"
#         else:
#             base_columns += ", NULL as face_region"
            
#         if 'capture_type' in columns:
#             base_columns += ", capture_type"
#         else:
#             base_columns += ", 'auto' as capture_type"
            
#         base_columns += ", person_id"
        
#         query = f"SELECT {base_columns} FROM detections WHERE 1=1"
#         params = []
        
#         if start_date:
#             query += " AND timestamp >= ?"
#             params.append(start_date)
#         if end_date:
#             query += " AND timestamp <= ?"
#             params.append(end_date)
#         if emotion and emotion.lower() != "all":
#             query += " AND emotion = ?"
#             params.append(emotion.lower())
        
#         query += " ORDER BY timestamp DESC LIMIT ?"
#         params.append(limit)
        
#         cursor = conn.execute(query, params)
#         results = cursor.fetchall()
#         conn.close()
        
#         return results

# # -------------------- Enhanced Login Window --------------------
# class LoginWindow:
#     def __init__(self, db_manager):
#         self.db_manager = db_manager
#         self.success = False
#         self.username = None
        
#         self.root = tk.Tk()
#         self.root.title("Emotion Detection System - Admin Login")
#         self.root.geometry("500x400")
#         self.root.configure(bg='#2c3e50')
#         self.root.resizable(False, False)
        
#         # Center the window
#         self.root.eval('tk::PlaceWindow . center')
        
#         self.setup_ui()
    
#     def setup_ui(self):
#         """Setup enhanced login UI with password features"""
#         # Main frame
#         main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
#         main_frame.pack(fill='both', expand=True)
        
#         # Title
#         title_label = tk.Label(main_frame, text="Admin Login", 
#                               font=('Arial', 24, 'bold'), 
#                               bg='#2c3e50', fg='white')
#         title_label.pack(pady=(0, 15))
        
#         # Login form
#         form_frame = tk.Frame(main_frame, bg='#2c3e50')
#         form_frame.pack(fill='x')
        
#         # Username
#         tk.Label(form_frame, text="Username:", font=('Arial', 12), 
#                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        
#         self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
#                                       bg='#34495e', fg='white', insertbackground='white',
#                                       relief='flat', bd=5)
#         self.username_entry.pack(fill='x', pady=(0, 15))
#         self.username_entry.insert(0, "admin")
        
#         # Password
#         tk.Label(form_frame, text="Password:", font=('Arial', 12), 
#                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        
#         self.password_entry = tk.Entry(form_frame, font=('Arial', 12), 
#                                       show="\u2022", bg='#34495e', fg='white',
#                                       insertbackground='white', relief='flat', bd=5)
#         self.password_entry.pack(fill='x', pady=(0, 10))
#         self.password_entry.bind('<KeyRelease>', self.update_password_feedback)
        
#         # Show password toggle and feedback
#         toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
#         toggle_frame.pack(fill='x', pady=(5, 10))
        
#         self.show_password_var = tk.BooleanVar()
#         show_password_check = tk.Checkbutton(
#             toggle_frame, 
#             text="Show Password", 
#             variable=self.show_password_var,
#             command=self.toggle_password_visibility,
#             bg='#2c3e50', 
#             fg='#bdc3c7',
#             selectcolor='#2c3e50',
#             font=('Arial', 10)
#         )
#         show_password_check.pack(side='left')
        
#         self.password_length_label = tk.Label(
#             toggle_frame, 
#             text="Characters: 0", 
#             font=('Arial', 9),
#             bg='#2c3e50', 
#             fg='#7f8c8d'
#         )
#         self.password_length_label.pack(side='right')
        
#         # Default credentials info
#         info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
#         info_frame.pack(fill='x', pady=(0, 20))
        
#         tk.Label(info_frame, text="Default: admin / admin123", 
#                 font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)
        
#         # Buttons
#         button_frame = tk.Frame(form_frame, bg='#2c3e50')
#         button_frame.pack(fill='x', pady=(10, 0))
        
#         login_btn = tk.Button(button_frame, text="Login", 
#                              command=self.login,
#                              bg='#27ae60', fg='white', 
#                              font=('Arial', 12, 'bold'),
#                              padx=30, pady=10, relief='flat')
#         login_btn.pack(side='left', padx=(0, 10))
        
#         cancel_btn = tk.Button(button_frame, text="Cancel", 
#                               command=self.cancel,
#                               bg='#e74c3c', fg='white', 
#                               font=('Arial', 12, 'bold'),
#                               padx=30, pady=10, relief='flat')
#         cancel_btn.pack(side='left')
        
#         # Bind Enter key
#         self.root.bind('<Return>', lambda e: self.login())
#         self.password_entry.focus()
    
#     def toggle_password_visibility(self):
#         """Toggle password field visibility"""
#         if self.show_password_var.get():
#             self.password_entry.config(show="")
#         else:
#             self.password_entry.config(show="\u2022")
    
#     def update_password_feedback(self, event=None):
#         """Update password input feedback"""
#         length = len(self.password_entry.get())
#         self.password_length_label.config(text=f"Characters: {length}")
    
#     def login(self):
#         """Handle login attempt"""
#         username = self.username_entry.get().strip()
#         password = self.password_entry.get()
        
#         if not username or not password:
#             messagebox.showerror("Error", "Please enter both username and password")
#             return
        
#         if self.db_manager.verify_user(username, password):
#             self.success = True
#             self.username = username
#             self.root.destroy()
#         else:
#             messagebox.showerror("Login Failed", "Invalid username or password")
#             self.password_entry.delete(0, tk.END)
#             self.password_entry.focus()
#             self.password_length_label.config(text="Characters: 0")
    
#     def cancel(self):
#         """Handle cancel"""
#         self.root.destroy()
    
#     def show(self):
#         """Show login window and return success status"""
#         self.root.mainloop()
#         return self.success, self.username

# # -------------------- Main Application --------------------
# class EmotionDetectionSystem:
#     def __init__(self, username):
#         self.username = username
#         self.db_manager = DatabaseManager()
#         self.session_id = f"session_{int(time.time())}"
        
#         # Core variables
#         self.cap = None
#         self.is_running = False
#         self.current_emotions = []
#         self.latest_frame = None
#         self.frame_count = 0
#         self.start_time = time.time()
#         self.last_capture_time = 0
#         self.capture_cooldown = 3.0  # Seconds between auto-captures
        
#         # Setup main window
#         self.root = tk.Tk()
#         self.root.title(f"Emotion Detection System - Welcome {username}")
#         self.root.geometry("1500x950")
#         self.root.configure(bg='#2c3e50')
        
#         self.setup_ui()
#         self.start_display_thread()
        
#         # Load initial data
#         self.apply_filters()
    
#     def setup_ui(self):
#         """Setup main application UI"""
#         # Header
#         header = tk.Frame(self.root, bg='#2c3e50', height=70)
#         header.pack(fill='x', padx=15, pady=10)
#         header.pack_propagate(False)
        
#         # Title and user info
#         title_frame = tk.Frame(header, bg='#2c3e50')
#         title_frame.pack(side='left', fill='y')
        
#         tk.Label(title_frame, text="Emotion Detection System", 
#                 font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
#         tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}", 
#                 font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')
        
#         # Controls
#         controls = tk.Frame(header, bg='#2c3e50')
#         controls.pack(side='right', fill='y')
        
#         self.start_btn = tk.Button(controls, text="Start Detection", command=self.start_detection,
#                                   bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), 
#                                   padx=20, pady=8, relief='flat')
#         self.start_btn.pack(side='left', padx=5)
        
#         self.stop_btn = tk.Button(controls, text="Stop Detection", command=self.stop_detection,
#                                  bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'), 
#                                  padx=20, pady=8, state='disabled', relief='flat')
#         self.stop_btn.pack(side='left', padx=5)
        
#         # Manual capture button
#         self.capture_btn = tk.Button(controls, text="Capture Face", command=self.manual_capture,
#                                     bg='#f39c12', fg='white', font=('Arial', 12, 'bold'), 
#                                     padx=20, pady=8, state='disabled', relief='flat')
#         self.capture_btn.pack(side='left', padx=5)
        
#         # Main content
#         main_frame = tk.Frame(self.root, bg='#2c3e50')
#         main_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
#         # Left side - Camera and real-time detection
#         left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
#         left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
#         # Camera section
#         camera_header = tk.Frame(left_frame, bg='#34495e')
#         camera_header.pack(fill='x', pady=10)
        
#         tk.Label(camera_header, text="Live Camera Feed", bg='#34495e', fg='white', 
#                 font=('Arial', 16, 'bold')).pack(side='left', padx=15)
        
#         self.detection_status = tk.StringVar(value="Camera stopped")
#         tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12', 
#                 font=('Arial', 12, 'bold')).pack(side='right', padx=15)
        
#         # Camera display
#         self.camera_label = tk.Label(left_frame, text="Camera feed will appear here\n\nClick 'Start Detection' to begin",
#                                     bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
#                                     width=70, height=20)
#         self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)
        
#         # Real-time detections list
#         rt_frame = tk.Frame(left_frame, bg='#34495e')
#         rt_frame.pack(fill='x', padx=15, pady=(0, 15))
        
#         tk.Label(rt_frame, text="Recent Live Detections", bg='#34495e', fg='white',
#                  font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
        
#         self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
#                                          font=('Consolas', 10), relief='flat')
#         self.live_detections.pack(fill='x')
        
#         # Right side - Dashboard
#         right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
#         right_frame.pack(side='right', fill='y')
#         right_frame.pack_propagate(False)
        
#         # Create notebook for tabs
#         notebook = ttk.Notebook(right_frame)
#         notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Filters tab
#         filters_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(filters_frame, text="Filters & History")
#         self.setup_filters_tab(filters_frame)
        
#         # Face Gallery tab
#         gallery_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(gallery_frame, text="Face Gallery")
#         self.setup_gallery_tab(gallery_frame)
        
#         # Export tab
#         export_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(export_frame, text="Export")
#         self.setup_export_tab(export_frame)
        
#         # Status bar
#         status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
#         status_frame.pack(fill='x', padx=15, pady=5)
        
#         self.status_var = tk.StringVar(value="Ready - Click 'Start Detection' to begin")
#         tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
#                 font=('Arial', 10)).pack(side='left', pady=5)
    
#     def setup_filters_tab(self, parent):
#         """Setup filters and history tab"""
#         # Date filters
#         tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
#         self.start_date_entry = tk.Entry(parent, width=30)
#         self.start_date_entry.pack(padx=10, pady=5)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.end_date_entry = tk.Entry(parent, width=30)
#         self.end_date_entry.pack(padx=10, pady=5)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
#         # Emotion filter
#         tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.emotion_filter = ttk.Combobox(parent, values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"], 
#                                           state="readonly", width=27)
#         self.emotion_filter.pack(padx=10, pady=5)
#         self.emotion_filter.set("All")
        
#         # Filter buttons
#         btn_frame = tk.Frame(parent, bg='#34495e')
#         btn_frame.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
#                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
#                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left')
        
#         # Detection history
#         history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         history_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Treeview for detections
#         columns = ("Time", "Emotion", "Confidence", "Type")
#         self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
        
#         # Column configurations
#         self.detection_tree.heading("Time", text="Timestamp")
#         self.detection_tree.heading("Emotion", text="Emotion")
#         self.detection_tree.heading("Confidence", text="Confidence")
#         self.detection_tree.heading("Type", text="Capture")
#         self.detection_tree.column("Time", width=120)
#         self.detection_tree.column("Emotion", width=80)
#         self.detection_tree.column("Confidence", width=80)
#         self.detection_tree.column("Type", width=60)
        
#         # Scrollbar
#         tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
#         self.detection_tree.configure(yscrollcommand=tree_scroll.set)
        
#         self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
#         tree_scroll.pack(side='right', fill='y', pady=10)
        
#         # Bind double-click to view face
#         self.detection_tree.bind('<Double-1>', self.view_face_image)
    
#     def setup_gallery_tab(self, parent):
#         """Setup face gallery tab"""
#         # Gallery controls
#         gallery_controls = tk.Frame(parent, bg='#34495e')
#         gallery_controls.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
#                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
        
#         tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
#                  bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left')
        
#         # Face thumbnails display
#         gallery_frame = tk.Frame(parent, bg='#34495e')
#         gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Scrollable canvas for face thumbnails
#         self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
#         gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
#         self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')
        
#         self.scrollable_gallery.bind(
#             "<Configure>",
#             lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
#         )
        
#         self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
#         self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
        
#         self.gallery_canvas.pack(side="left", fill="both", expand=True)
#         gallery_scrollbar.pack(side="right", fill="y")
        
#         self.face_thumbnails = []  # Store face thumbnail references
    
#     def setup_export_tab(self, parent):
#         """Setup export tab"""
#         # Export options
#         export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         export_frame.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
#                  bg='#16a085', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        
#         tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
#                  bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        
#         tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
#                  bg='#e67e22', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
    
#     def start_display_thread(self):
#         """Start display update thread"""
#         self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
#         self.display_thread.start()
    
#     def start_detection(self):
#         """Start emotion detection"""
#         try:
#             # Try different camera indices
#             for camera_idx in [0, 1, 2]:
#                 self.cap = cv2.VideoCapture(camera_idx)
#                 if self.cap.isOpened():
#                     break
#                 self.cap.release()
            
#             if not self.cap.isOpened():
#                 messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
#                 return
            
#             # Set camera properties
#             self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
#             self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
#             self.cap.set(cv2.CAP_PROP_FPS, 30)
            
#             self.is_running = True
#             self.start_time = time.time()
#             self.frame_count = 0
            
#             # Update UI
#             self.start_btn.config(state='disabled')
#             self.stop_btn.config(state='normal')
#             self.capture_btn.config(state='normal')
#             self.detection_status.set("Detection running...")
            
#             # Start detection threads
#             threading.Thread(target=self.detection_loop, daemon=True).start()
            
#             self.status_var.set("Detection started - Auto-capturing emotions every 3 seconds")
            
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
    
#     def stop_detection(self):
#         """Stop emotion detection"""
#         self.is_running = False
        
#         if self.cap:
#             self.cap.release()
#             self.cap = None
        
#         # Update UI
#         self.start_btn.config(state='normal')
#         self.stop_btn.config(state='disabled')
#         self.capture_btn.config(state='disabled')
#         self.detection_status.set("Detection stopped")
#         self.camera_label.config(image="", text="Detection stopped\nStart Detection to resume")
#         self.status_var.set("Detection stopped")
    
#     def manual_capture(self):
#         """Manually capture current frame with all detected faces"""
#         if not self.is_running or self.latest_frame is None:
#             messagebox.showwarning("Capture Error", "Please start detection first")
#             return
        
#         try:
#             frame = self.latest_frame.copy()
#             timestamp = datetime.now()
            
#             if self.current_emotions:
#                 for i, emotion_data in enumerate(self.current_emotions):
#                     emotion = emotion_data['dominant_emotion']
#                     confidence = emotion_data['emotion'][emotion]
                    
#                     # Capture this face
#                     self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
                
#                 self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
#             else:
#                 messagebox.showinfo("Capture Info", "No faces detected in current frame")
                
#         except Exception as e:
#             messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")
    
#     def detection_loop(self):
#         """Main detection loop"""
#         while self.is_running:
#             try:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     time.sleep(0.01)
#                     continue
                
#                 # Flip frame horizontally for mirror effect
#                 frame = cv2.flip(frame, 1)
#                 self.latest_frame = frame.copy()
#                 self.frame_count += 1
                
#                 # Analyze every 10th frame
#                 if self.frame_count % 10 == 0:
#                     threading.Thread(target=self.analyze_emotion, 
#                                    args=(frame.copy(),), daemon=True).start()
                
#                 time.sleep(0.033)  # ~30 FPS
                
#             except Exception:
#                 time.sleep(0.1)
    
#     def analyze_emotion(self, frame):
#         """Analyze emotions and auto-capture"""
#         try:
#             # Convert to RGB for DeepFace
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
#             # Analyze emotions
#             results = DeepFace.analyze(
#                 img_path=rgb_frame,
#                 actions=['emotion'],
#                 detector_backend='opencv',
#                 enforce_detection=False,
#                 silent=True
#             )
            
#             if isinstance(results, list):
#                 self.current_emotions = results
#             else:
#                 self.current_emotions = [results]
            
#             # Auto-capture high-confidence detections
#             current_time = time.time()
#             if current_time - self.last_capture_time >= self.capture_cooldown:
#                 for emotion_data in self.current_emotions:
#                     try:
#                         emotion = emotion_data['dominant_emotion']
#                         confidence = emotion_data['emotion'][emotion]
                        
#                         if confidence > 60:  # High confidence threshold
#                             self.capture_emotion(emotion_data, frame.copy())
#                             self.last_capture_time = current_time
#                             break  # Only capture one per cooldown period
#                     except Exception:
#                         continue
                        
#         except Exception:
#             pass
    
#     def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
#         """Capture and save emotion detection with face cropping"""
#         try:
#             emotion = emotion_data['dominant_emotion']
#             confidence = emotion_data['emotion'][emotion]
#             timestamp = datetime.now()
            
#             # Extract face region
#             region = emotion_data['region']
#             x, y, w, h = region['x'], region['y'], region['w'], region['h']
            
#             # Add padding to face crop
#             padding = 20
#             x1 = max(0, x - padding)
#             y1 = max(0, y - padding)
#             x2 = min(frame.shape[1], x + w + padding)
#             y2 = min(frame.shape[0], y + h + padding)
            
#             # Crop face from original frame
#             face_crop = frame[y1:y2, x1:x2]
            
#             # Draw emotion on full frame
#             color = self.get_emotion_color(emotion)
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#             label = f"{emotion.upper()}: {confidence:.1f}%"
#             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
#             # Save full frame snapshot
#             snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
#             cv2.imwrite(snapshot_filename, frame)
            
#             # Save face crop if folder exists
#             face_filename = None
#             if os.path.exists("faces"):
#                 face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
#                 cv2.imwrite(face_filename, face_crop)
            
#             # Save region info as JSON
#             region_json = json.dumps({
#                 'x': x, 'y': y, 'w': w, 'h': h,
#                 'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
#             })
            
#             # Save to database with error handling
#             try:
#                 self.db_manager.save_detection(
#                     timestamp.isoformat(),
#                     emotion,
#                     confidence,
#                     snapshot_filename,
#                     face_filename,
#                     region_json,
#                     capture_type,
#                     "person1",
#                     self.session_id
#                 )
#                 print(f"Successfully saved detection: {emotion} {confidence:.1f}%")
#             except Exception as db_error:
#                 print(f"Database save error: {db_error}")
#                 # Continue anyway - at least the files are saved
            
#             # Update live detections list
#             detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
#             if self.live_detections.size() > 20:  # Keep only last 20
#                 self.root.after(0, lambda: self.live_detections.delete(tk.END))
            
#             # Update status
#             status_msg = f"Captured {emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.status_var.set(status_msg))
            
#             # Refresh gallery if it's the active tab
#             self.root.after(1000, self.refresh_gallery)
            
#         except Exception as e:
#             print(f"Capture error: {e}")
    
#     def refresh_gallery(self):
#         """Refresh the face gallery with latest captures"""
#         try:
#             # Clear existing thumbnails
#             for widget in self.scrollable_gallery.winfo_children():
#                 widget.destroy()
#             self.face_thumbnails = []
            
#             # Get recent detections with face crops
#             detections = self.db_manager.get_detections(limit=50)
            
#             # Display face thumbnails in grid
#             row, col = 0, 0
#             max_cols = 3
            
#             for detection in detections:
#                 timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         # Load and resize face image
#                         face_img = cv2.imread(face_crop_path)
#                         face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                         face_img = cv2.resize(face_img, (100, 100))
                        
#                         # Convert to PhotoImage
#                         pil_img = Image.fromarray(face_img)
#                         photo = ImageTk.PhotoImage(pil_img)
                        
#                         # Create frame for each thumbnail
#                         thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
#                         thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
                        
#                         # Face image
#                         face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
#                         face_label.pack(pady=5)
#                         face_label.image = photo  # Keep reference
                        
#                         # Emotion label
#                         dt = datetime.fromisoformat(timestamp)
                        
#                         # Robust confidence handling for gallery
#                         confidence_float = 0.0
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             pass

#                         emotion_text = f"{emotion.upper()}: {confidence_float:.1f}%"
#                         time_text = dt.strftime('%m/%d %H:%M')
#                         type_text = f"[{capture_type.upper() if capture_type else 'AUTO'}]"
                        
#                         tk.Label(thumb_frame, text=emotion_text, bg='#2c3e50', fg='white',
#                                 font=('Arial', 8, 'bold')).pack()
#                         tk.Label(thumb_frame, text=time_text, bg='#2c3e50', fg='#bdc3c7',
#                                 font=('Arial', 7)).pack()
#                         tk.Label(thumb_frame, text=type_text, bg='#2c3e50', fg='#f39c12',
#                                 font=('Arial', 7)).pack()
                        
#                         # Store reference for viewing
#                         self.face_thumbnails.append({
#                             'frame': thumb_frame,
#                             'path': face_crop_path,
#                             'snapshot_path': snapshot_path,
#                             'data': detection
#                         })
                        
#                         # Bind click to view larger
#                         face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))
                        
#                         col += 1
#                         if col >= max_cols:
#                             col = 0
#                             row += 1
                            
#                     except Exception as e:
#                         print(f"Thumbnail error: {e}")
#                         continue
            
#             # Update scroll region
#             self.scrollable_gallery.update_idletasks()
#             self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
            
#         except Exception as e:
#             print(f"Gallery refresh error: {e}")
    
#     def view_face_full(self, face_path):
#         """View face image in full size"""
#         try:
#             if os.path.exists(face_path):
#                 # Create new window for full view
#                 view_window = tk.Toplevel(self.root)
#                 view_window.title("Face View")
#                 view_window.configure(bg='#2c3e50')
                
#                 # Load and display image
#                 face_img = cv2.imread(face_path)
#                 face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                
#                 # Resize for viewing (max 400x400)
#                 h, w = face_img.shape[:2]
#                 max_size = 400
#                 if max(h, w) > max_size:
#                     scale = max_size / max(h, w)
#                     new_w, new_h = int(w * scale), int(h * scale)
#                     face_img = cv2.resize(face_img, (new_w, new_h))
                
#                 pil_img = Image.fromarray(face_img)
#                 photo = ImageTk.PhotoImage(pil_img)
                
#                 label = tk.Label(view_window, image=photo, bg='#2c3e50')
#                 label.pack(padx=20, pady=20)
#                 label.image = photo  # Keep reference
                
#                 # Center window
#                 view_window.update_idletasks()
#                 x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
#                 y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
#                 view_window.geometry(f'+{x}+{y}')
                
#         except Exception as e:
#             messagebox.showerror("View Error", f"Cannot view face: {str(e)}")
    
#     def view_face_image(self, event):
#         """View face from detection tree double-click"""
#         selection = self.detection_tree.selection()
#         if selection:
#             item = self.detection_tree.item(selection[0])
#             # Get the detection data and show face
#             # This would need to store more data in the tree or query DB
#             pass
    
#     def view_selected_face(self):
#         """View selected face from gallery"""
#         # This could be enhanced to track selected thumbnails
#         messagebox.showinfo("Info", "Click on any face thumbnail to view full size")
    
#     def update_display_loop(self):
#         """Update camera display with emotion overlays"""
#         while True:
#             try:
#                 if self.is_running and self.latest_frame is not None:
#                     frame = self.latest_frame.copy()
                    
#                     # Draw emotion overlays
#                     for emotion_data in self.current_emotions:
#                         try:
#                             region = emotion_data['region']
#                             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                             emotion = emotion_data['dominant_emotion']
#                             confidence = emotion_data['emotion'][emotion]
#                             color = self.get_emotion_color(emotion)
                            
#                             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#                             label = f"{emotion.upper()}: {confidence:.1f}%"
#                             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                         except Exception:
#                             continue
                    
#                     # Convert and display
#                     rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#                     pil_image = Image.fromarray(rgb_frame)
#                     pil_image = pil_image.resize((800, 600), Image.Resampling.LANCZOS)
#                     photo = ImageTk.PhotoImage(pil_image)
                    
#                     self.camera_label.configure(image=photo, text="")
#                     self.camera_label.image = photo
                
#                 time.sleep(0.033)  # ~30 FPS
                
#             except Exception:
#                 time.sleep(0.1)
    
#     def get_emotion_color(self, emotion):
#         """Get color for each emotion"""
#         colors = {
#             'happy': (0, 255, 0),      # Green
#             'sad': (255, 100, 100),    # Light Blue
#             'angry': (0, 0, 255),      # Red
#             'fear': (255, 0, 255),     # Magenta
#             'surprise': (0, 255, 255), # Yellow
#             'disgust': (128, 0, 128),  # Purple
#             'neutral': (128, 128, 128) # Gray
#         }
#         return colors.get(emotion, (255, 255, 255))
    
#     def apply_filters(self):
#         """Apply filters and refresh data"""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             # Clear and populate tree
#             for item in self.detection_tree.get_children():
#                 self.detection_tree.delete(item)
            
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                
#                 # Robust confidence handling for display
#                 confidence_float = 0.0
#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     pass # Keep as 0.0 if conversion fails

#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%m/%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 self.detection_tree.insert('', 'end', values=(formatted_time, emotion_name.upper(), f"{confidence_float:.1f}%", type_display))
            
#             self.status_var.set(f"Loaded {len(detections)} detections")
            
#             # Refresh gallery too
#             self.refresh_gallery()
            
#         except Exception as e:
#             messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
    
#     def clear_filters(self):
#         """Clear all filters"""
#         self.start_date_entry.delete(0, tk.END)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
#         self.end_date_entry.delete(0, tk.END)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
#         self.emotion_filter.set("All")
#         self.apply_filters()
    
#     def export_csv(self):
#         """Export detections to CSV, embedding images as Base64 strings."""
#         try:
#             # Get current filtered data
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
            
#             # Ask where to save the CSV file
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".csv",
#                 filetypes=[("CSV files", "*.csv")],
#                 initialfile=f"emotion_detections_base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#             )
            
#             if filename:
#                 with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#                     writer = csv.writer(csvfile)
#                     # Updated header for the Base64 image data
#                     writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Base64"])
                    
#                     for detection in detections:
#                         timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                        
#                         image_base64_string = "N/A"
                        
#                         # Robust confidence handling
#                         confidence_float = 0.0
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             print(f"Could not convert confidence '{confidence}' to float for {timestamp}. Defaulting to 0.0.")
                        
#                         try:
#                             # Load the original snapshot
#                             if snapshot_path and os.path.exists(snapshot_path):
#                                 image = cv2.imread(snapshot_path)
                                
#                                 # Draw bounding box if region data is available
#                                 if image is not None and face_region:
#                                     region = json.loads(face_region)
#                                     x, y, w, h = region['x'], region['y'], region['w'], region['h']
                                    
#                                     color = self.get_emotion_color(emotion_name)
#                                     cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
#                                     label = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                                     cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                                
#                                 # Encode the final image (with or without box) to Base64
#                                 _, buffer = cv2.imencode('.jpg', image)
#                                 image_base64_string = base64.b64encode(buffer).decode('utf-8')
                                
#                             else:
#                                 image_base64_string = "Snapshot not found"

#                         except Exception as e:
#                             print(f"Could not process and encode image for {timestamp}: {e}")
#                             image_base64_string = "Error encoding image"
                        
#                         # Write the row to the CSV file
#                         writer.writerow([timestamp, emotion_name, f"{confidence_float:.1f}%", image_base64_string])

#                 messagebox.showinfo("Export", f"Data and embedded images exported successfully to {filename}")

#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")

            
#     def export_pdf(self):
#         """Export detections to PDF report with embedded images."""
#         try:
#             from reportlab.lib.pagesizes import A4
#             from reportlab.pdfgen import canvas
#             from reportlab.lib.utils import ImageReader
#             from reportlab.lib.units import inch
#         except ImportError:
#             messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
#             return
        
#         try:
#             # Get current filtered data
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".pdf",
#                 filetypes=[("PDF files", "*.pdf")],
#                 initialfile=f"emotion_report_with_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#             )
            
#             if filename:
#                 c = canvas.Canvas(filename, pagesize=A4)
#                 width, height = A4
                
#                 # --- PDF Header ---
#                 c.setFont("Helvetica-Bold", 20)
#                 c.drawString(inch, height - inch, "Emotion Detection Report")
                
#                 # --- Summary Stats ---
#                 total = len(detections)
#                 emotion_counts = Counter([d[1] for d in detections])
#                 auto_count = sum(1 for d in detections if d[6] == 'auto')
#                 manual_count = sum(1 for d in detections if d[6] == 'manual')
                
#                 y_pos = height - inch * 1.5
#                 c.setFont("Helvetica-Bold", 12)
#                 c.drawString(inch, y_pos, f"Total Detections: {total}")
#                 c.drawString(inch, y_pos - 20, f"Auto Captures: {auto_count}")
#                 c.drawString(inch, y_pos - 40, f"Manual Captures: {manual_count}")
                
#                 c.setFont("Helvetica-Bold", 12)
#                 c.drawString(inch * 4, y_pos, "Emotion Distribution:")
#                 c.setFont("Helvetica", 10)
                
#                 stat_y = y_pos - 20
#                 for emotion_name, count in emotion_counts.most_common():
#                     percentage = (count / total) * 100 if total > 0 else 0
#                     c.drawString(inch * 4, stat_y, f"{emotion_name.upper()}: {count} ({percentage:.1f}%)")
#                     stat_y -= 15
                
#                 # --- Detection List with Images ---
#                 y_pos -= 100
#                 c.setFont("Helvetica-Bold", 14)
#                 c.drawString(inch, y_pos, "Detection Log")
#                 y_pos -= 30

#                 for i, detection in enumerate(detections):
#                     # Check for new page
#                     if y_pos < inch * 2:
#                         c.showPage()
#                         y_pos = height - inch

#                     timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                    
#                     # Robust confidence handling
#                     confidence_float = 0.0
#                     try:
#                         confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                         confidence_float = float(confidence_str)
#                     except (ValueError, TypeError):
#                         pass

#                     dt = datetime.fromisoformat(timestamp)
#                     formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
#                     type_display = capture_type.upper() if capture_type else 'AUTO'
                    
#                     # Draw text
#                     c.setFont("Helvetica", 9)
#                     text = f"{i+1}. {formatted_time} | {emotion_name.upper()} | {confidence_float:.1f}% | {type_display}"
#                     c.drawString(inch, y_pos, text)
#                     y_pos -= 15
                    
#                     # Draw image if it exists
#                     if face_crop_path and os.path.exists(face_crop_path):
#                         try:
#                             img_width = 1.5 * inch
#                             img_height = 1.5 * inch
                            
#                             if y_pos < img_height + inch: # Check space for image
#                                 c.showPage()
#                                 y_pos = height - inch

#                             c.drawImage(face_crop_path, inch, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
#                             y_pos -= (img_height + 10) # Move position down after drawing image
#                         except Exception as e:
#                             c.drawString(inch + 5, y_pos, f"  (Error loading image: {e})")
#                             y_pos -= 15
#                     else:
#                         c.setFont("Helvetica-Oblique", 8)
#                         c.drawString(inch + 5, y_pos, "  (No face image available)")
#                         y_pos -= 15

#                 c.save()
#                 messagebox.showinfo("Export", f"Report with images exported successfully to {filename}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")
    
#     def export_faces(self):
#         """Export face gallery as ZIP file"""
#         try:
#             import zipfile
            
#             # Check if faces folder exists
#             if not os.path.exists("faces"):
#                 messagebox.showinfo("Export", "No faces folder found")
#                 return
            
#             # Get all face files
#             face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
            
#             if not face_files:
#                 messagebox.showinfo("Export", "No face images to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".zip",
#                 filetypes=[("ZIP files", "*.zip")],
#                 initialfile=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
#             )
            
#             if filename:
#                 with zipfile.ZipFile(filename, 'w') as zipf:
#                     for face_file in face_files:
#                         face_path = os.path.join("faces", face_file)
#                         zipf.write(face_path, face_file)
                
#                 messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")
    
#     def run(self):
#         """Run the application"""
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
#         self.root.mainloop()
    
#     def on_closing(self):
#         """Handle application closing"""
#         if self.is_running:
#             self.stop_detection()
#         self.root.destroy()

# # -------------------- Main Application Entry Point --------------------
# def main():
#     """Main application entry point"""
#     print("Starting Enhanced Emotion Detection System with Database Migration...")
#     print("Features:")
#     print("- Secure admin authentication with enhanced password visibility")
#     print("- Real-time emotion detection with auto-capture")
#     print("- Manual face capture with 'Capture Face' button")
#     print("- Individual face cropping and saving")
#     print("- Face gallery with thumbnails")
#     print("- Enhanced export capabilities including face gallery with Base64 embedding")
#     print("- Professional reporting with embedded images and capture type tracking")
#     print("- Automatic database migration for existing installations")
    
#     # Initialize database with migration
#     db_manager = DatabaseManager()
    
#     # Show login window
#     login_window = LoginWindow(db_manager)
#     success, username = login_window.show()
    
#     if success:
#         print(f"Login successful for user: {username}")
#         # Start main application
#         app = EmotionDetectionSystem(username)
#         app.run()
#     else:
#         print("Login cancelled or failed")

# if __name__ == "__main__":
#     main()





















# """
# Complete Emotion Detection System with Image/Video Upload and Analysis
# Install: pip install deepface opencv-python tensorflow pillow reportlab

# Features:
# - Secure admin authentication
# - Real-time emotion detection from webcam
# - Upload and analyze emotions from image files (JPG, PNG)
# - Upload and analyze emotions from video files (MP4, AVI)
# - Robust data handling and professional PDF/CSV exporting
# - Automatic database migration for existing installations
# """

# import tkinter as tk
# from tkinter import ttk, messagebox, filedialog
# import cv2
# import numpy as np
# from deepface import DeepFace
# import threading
# import time
# from PIL import Image, ImageTk
# from collections import deque, Counter
# import sqlite3
# import os
# import csv
# import hashlib
# import secrets
# from datetime import datetime, timedelta
# import json
# import base64

# # -------------------- Password Security --------------------
# def hash_password(password: str, iterations: int = 200_000) -> str:
#     """Hash password using PBKDF2"""
#     salt = secrets.token_bytes(16)
#     dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#     return f"{iterations}${salt.hex()}${dk.hex()}"

# def verify_password(password: str, stored: str) -> bool:
#     """Verify password against stored hash"""
#     try:
#         iterations_s, salt_hex, hash_hex = stored.split("$")
#         iterations = int(iterations_s)
#         salt = bytes.fromhex(salt_hex)
#         target = bytes.fromhex(hash_hex)
#         dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#         return secrets.compare_digest(dk, target)
#     except Exception:
#         return False

# # -------------------- Database Manager with Migration --------------------
# class DatabaseManager:
#     def __init__(self, db_path="emotion_system.db"):
#         self.db_path = db_path
#         self.init_database()
#         self.migrate_database()  # Add migration step
    
#     def init_database(self):
#         """Initialize database with required tables"""
#         os.makedirs("snapshots", exist_ok=True)
#         os.makedirs("faces", exist_ok=True)  # New folder for cropped faces
        
#         conn = sqlite3.connect(self.db_path)
        
#         # Users table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY,
#                 username TEXT UNIQUE NOT NULL,
#                 password_hash TEXT NOT NULL,
#                 role TEXT DEFAULT 'admin',
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Original detections table structure (for new installations)
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS detections (
#                 id INTEGER PRIMARY KEY,
#                 timestamp TEXT NOT NULL,
#                 emotion TEXT NOT NULL,
#                 confidence REAL NOT NULL,
#                 snapshot_path TEXT NOT NULL,
#                 face_crop_path TEXT,
#                 face_region TEXT,
#                 capture_type TEXT DEFAULT 'auto',
#                 person_id TEXT,
#                 session_id TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Create indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")
        
#         # Create default admin user if none exists
#         cursor = conn.execute("SELECT COUNT(*) FROM users")
#         if cursor.fetchone()[0] == 0:
#             admin_hash = hash_password("admin123")
#             conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#                         ("admin", admin_hash, "admin"))
        
#         conn.commit()
#         conn.close()
    
#     def migrate_database(self):
#         """Migrate existing database to add new columns"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
        
#         try:
#             # Check if new columns exist
#             cursor.execute("PRAGMA table_info(detections)")
#             columns = [column[1] for column in cursor.fetchall()]
            
#             # Add missing columns
#             if 'face_crop_path' not in columns:
#                 print("Adding face_crop_path column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")
                
#             if 'face_region' not in columns:
#                 print("Adding face_region column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")
                
#             if 'capture_type' not in columns:
#                 print("Adding capture_type column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")
                
#             conn.commit()
#             print("Database migration completed successfully!")
            
#         except Exception as e:
#             print(f"Migration error (this is normal for new installations): {e}")
            
#         finally:
#             conn.close()
    
#     def verify_user(self, username: str, password: str) -> bool:
#         """Verify user credentials"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
#         result = cursor.fetchone()
#         conn.close()
        
#         if result:
#             return verify_password(password, result[0])
#         return False
    
#     def save_detection(self, timestamp: str, emotion: str, confidence: float, 
#                       snapshot_path: str, face_crop_path: str = None, face_region: str = None,
#                       capture_type: str = 'auto', person_id: str = None, session_id: str = None):
#         """Save detection to database"""
#         conn = sqlite3.connect(self.db_path)
#         try:
#             conn.execute("""
#                 INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
#                                       face_region, capture_type, person_id, session_id)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, 
#                   capture_type, person_id, session_id))
#             conn.commit()
#         except sqlite3.OperationalError as e:
#             # Fallback for old database structure
#             print(f"Database error, trying fallback: {e}")
#             try:
#                 conn.execute("""
#                     INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
#                 conn.commit()
#             except Exception as fallback_error:
#                 print(f"Fallback failed: {fallback_error}")
#         finally:
#             conn.close()
    
#     def get_detections(self, start_date=None, end_date=None, emotion=None, limit=1000):
#         """Get filtered detections from database"""
#         conn = sqlite3.connect(self.db_path)
        
#         # Check if new columns exist
#         cursor = conn.cursor()
#         cursor.execute("PRAGMA table_info(detections)")
#         columns = [column[1] for column in cursor.fetchall()]
        
#         # Build query based on available columns
#         base_columns = "timestamp, emotion, confidence, snapshot_path"
#         if 'face_crop_path' in columns:
#             base_columns += ", face_crop_path"
#         else:
#             base_columns += ", NULL as face_crop_path"
            
#         if 'face_region' in columns:
#             base_columns += ", face_region"
#         else:
#             base_columns += ", NULL as face_region"
            
#         if 'capture_type' in columns:
#             base_columns += ", capture_type"
#         else:
#             base_columns += ", 'auto' as capture_type"
            
#         base_columns += ", person_id"
        
#         query = f"SELECT {base_columns} FROM detections WHERE 1=1"
#         params = []
        
#         if start_date:
#             query += " AND timestamp >= ?"
#             params.append(start_date)
#         if end_date:
#             query += " AND timestamp <= ?"
#             params.append(end_date)
#         if emotion and emotion.lower() != "all":
#             query += " AND emotion = ?"
#             params.append(emotion.lower())
        
#         query += " ORDER BY timestamp DESC LIMIT ?"
#         params.append(limit)
        
#         cursor = conn.execute(query, params)
#         results = cursor.fetchall()
#         conn.close()
        
#         return results

# # -------------------- Enhanced Login Window --------------------
# class LoginWindow:
#     def __init__(self, db_manager):
#         self.db_manager = db_manager
#         self.success = False
#         self.username = None
        
#         self.root = tk.Tk()
#         self.root.title("Emotion Detection System - Admin Login")
#         self.root.geometry("500x400")
#         self.root.configure(bg='#2c3e50')
#         self.root.resizable(False, False)
        
#         # Center the window
#         self.root.eval('tk::PlaceWindow . center')
        
#         self.setup_ui()
    
#     def setup_ui(self):
#         """Setup enhanced login UI with password features"""
#         # Main frame
#         main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
#         main_frame.pack(fill='both', expand=True)
        
#         # Title
#         title_label = tk.Label(main_frame, text="Admin Login", 
#                               font=('Arial', 24, 'bold'), 
#                               bg='#2c3e50', fg='white')
#         title_label.pack(pady=(0, 15))
        
#         # Login form
#         form_frame = tk.Frame(main_frame, bg='#2c3e50')
#         form_frame.pack(fill='x')
        
#         # Username
#         tk.Label(form_frame, text="Username:", font=('Arial', 12), 
#                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        
#         self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
#                                       bg='#34495e', fg='white', insertbackground='white',
#                                       relief='flat', bd=5)
#         self.username_entry.pack(fill='x', pady=(0, 15))
#         self.username_entry.insert(0, "admin")
        
#         # Password
#         tk.Label(form_frame, text="Password:", font=('Arial', 12), 
#                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        
#         self.password_entry = tk.Entry(form_frame, font=('Arial', 12), 
#                                       show="\u2022", bg='#34495e', fg='white',
#                                       insertbackground='white', relief='flat', bd=5)
#         self.password_entry.pack(fill='x', pady=(0, 10))
#         self.password_entry.bind('<KeyRelease>', self.update_password_feedback)
        
#         # Show password toggle and feedback
#         toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
#         toggle_frame.pack(fill='x', pady=(5, 10))
        
#         self.show_password_var = tk.BooleanVar()
#         show_password_check = tk.Checkbutton(
#             toggle_frame, 
#             text="Show Password", 
#             variable=self.show_password_var,
#             command=self.toggle_password_visibility,
#             bg='#2c3e50', 
#             fg='#bdc3c7',
#             selectcolor='#2c3e50',
#             font=('Arial', 10)
#         )
#         show_password_check.pack(side='left')
        
#         self.password_length_label = tk.Label(
#             toggle_frame, 
#             text="Characters: 0", 
#             font=('Arial', 9),
#             bg='#2c3e50', 
#             fg='#7f8c8d'
#         )
#         self.password_length_label.pack(side='right')
        
#         # Default credentials info
#         info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
#         info_frame.pack(fill='x', pady=(0, 20))
        
#         tk.Label(info_frame, text="Default: admin / admin123", 
#                 font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)
        
#         # Buttons
#         button_frame = tk.Frame(form_frame, bg='#2c3e50')
#         button_frame.pack(fill='x', pady=(10, 0))
        
#         login_btn = tk.Button(button_frame, text="Login", 
#                              command=self.login,
#                              bg='#27ae60', fg='white', 
#                              font=('Arial', 12, 'bold'),
#                              padx=30, pady=10, relief='flat')
#         login_btn.pack(side='left', padx=(0, 10))
        
#         cancel_btn = tk.Button(button_frame, text="Cancel", 
#                               command=self.cancel,
#                               bg='#e74c3c', fg='white', 
#                               font=('Arial', 12, 'bold'),
#                               padx=30, pady=10, relief='flat')
#         cancel_btn.pack(side='left')
        
#         # Bind Enter key
#         self.root.bind('<Return>', lambda e: self.login())
#         self.password_entry.focus()
    
#     def toggle_password_visibility(self):
#         """Toggle password field visibility"""
#         if self.show_password_var.get():
#             self.password_entry.config(show="")
#         else:
#             self.password_entry.config(show="\u2022")
    
#     def update_password_feedback(self, event=None):
#         """Update password input feedback"""
#         length = len(self.password_entry.get())
#         self.password_length_label.config(text=f"Characters: {length}")
    
#     def login(self):
#         """Handle login attempt"""
#         username = self.username_entry.get().strip()
#         password = self.password_entry.get()
        
#         if not username or not password:
#             messagebox.showerror("Error", "Please enter both username and password")
#             return
        
#         if self.db_manager.verify_user(username, password):
#             self.success = True
#             self.username = username
#             self.root.destroy()
#         else:
#             messagebox.showerror("Login Failed", "Invalid username or password")
#             self.password_entry.delete(0, tk.END)
#             self.password_entry.focus()
#             self.password_length_label.config(text="Characters: 0")
    
#     def cancel(self):
#         """Handle cancel"""
#         self.root.destroy()
    
#     def show(self):
#         """Show login window and return success status"""
#         self.root.mainloop()
#         return self.success, self.username

# # -------------------- Main Application --------------------
# class EmotionDetectionSystem:
#     def __init__(self, username):
#         self.username = username
#         self.db_manager = DatabaseManager()
#         self.session_id = f"session_{int(time.time())}"
        
#         # Core variables
#         self.cap = None
#         self.is_running = False
#         self.current_emotions = []
#         self.latest_frame = None
#         self.frame_count = 0
#         self.start_time = time.time()
#         self.last_capture_time = 0
#         self.capture_cooldown = 3.0  # Seconds between auto-captures
        
#         # Setup main window
#         self.root = tk.Tk()
#         self.root.title(f"Emotion Detection System - Welcome {username}")
#         self.root.geometry("1500x950")
#         self.root.configure(bg='#2c3e50')
        
#         self.setup_ui()
#         self.start_display_thread()
        
#         # Load initial data
#         self.apply_filters()
    
#     def setup_ui(self):
#         """Setup main application UI"""
#         # Header
#         header = tk.Frame(self.root, bg='#2c3e50', height=70)
#         header.pack(fill='x', padx=15, pady=10)
#         header.pack_propagate(False)
        
#         # Title and user info
#         title_frame = tk.Frame(header, bg='#2c3e50')
#         title_frame.pack(side='left', fill='y')
        
#         tk.Label(title_frame, text="Emotion Detection System", 
#                 font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
#         tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}", 
#                 font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')
        
#         # --- Controls ---
#         controls = tk.Frame(header, bg='#2c3e50')
#         controls.pack(side='right', fill='y')
        
#         # Webcam controls
#         self.start_btn = tk.Button(controls, text="Start Webcam", command=self.start_detection,
#                                   bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), 
#                                   padx=20, pady=8, relief='flat')
#         self.start_btn.pack(side='left', padx=5)
        
#         self.stop_btn = tk.Button(controls, text="Stop Webcam", command=self.stop_detection,
#                                  bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'), 
#                                  padx=20, pady=8, state='disabled', relief='flat')
#         self.stop_btn.pack(side='left', padx=5)
        
#         self.capture_btn = tk.Button(controls, text="Capture Face", command=self.manual_capture,
#                                     bg='#f39c12', fg='white', font=('Arial', 12, 'bold'), 
#                                     padx=20, pady=8, state='disabled', relief='flat')
#         self.capture_btn.pack(side='left', padx=5)
        
#         # Upload controls
#         tk.Button(controls, text="Upload Image", command=self.upload_image,
#                   bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=8, relief='flat').pack(side='left', padx=5)
        
#         tk.Button(controls, text="Upload Video", command=self.upload_video,
#                   bg='#9b59b6', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=8, relief='flat').pack(side='left', padx=5)
        
#         # Main content
#         main_frame = tk.Frame(self.root, bg='#2c3e50')
#         main_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
#         # Left side - Camera and real-time detection
#         left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
#         left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
#         # Camera section
#         camera_header = tk.Frame(left_frame, bg='#34495e')
#         camera_header.pack(fill='x', pady=10)
        
#         tk.Label(camera_header, text="Live Feed / Uploaded Media", bg='#34495e', fg='white', 
#                 font=('Arial', 16, 'bold')).pack(side='left', padx=15)
        
#         self.detection_status = tk.StringVar(value="Idle")
#         tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12', 
#                 font=('Arial', 12, 'bold')).pack(side='right', padx=15)
        
#         # Camera display
#         self.camera_label = tk.Label(left_frame, text="Feed will appear here\n\nStart Webcam or Upload a File",
#                                     bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
#                                     width=70, height=20)
#         self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)
        
#         # Real-time detections list
#         rt_frame = tk.Frame(left_frame, bg='#34495e')
#         rt_frame.pack(fill='x', padx=15, pady=(0, 15))
        
#         tk.Label(rt_frame, text="Recent Detections", bg='#34495e', fg='white',
#                  font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
        
#         self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
#                                          font=('Consolas', 10), relief='flat')
#         self.live_detections.pack(fill='x')
        
#         # Right side - Dashboard
#         right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
#         right_frame.pack(side='right', fill='y')
#         right_frame.pack_propagate(False)
        
#         # Create notebook for tabs
#         notebook = ttk.Notebook(right_frame)
#         notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Filters tab
#         filters_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(filters_frame, text="Filters & History")
#         self.setup_filters_tab(filters_frame)
        
#         # Face Gallery tab
#         gallery_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(gallery_frame, text="Face Gallery")
#         self.setup_gallery_tab(gallery_frame)
        
#         # Export tab
#         export_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(export_frame, text="Export")
#         self.setup_export_tab(export_frame)
        
#         # Status bar
#         status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
#         status_frame.pack(fill='x', padx=15, pady=5)
        
#         self.status_var = tk.StringVar(value="Ready")
#         tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
#                 font=('Arial', 10)).pack(side='left', pady=5)
    
#     def setup_filters_tab(self, parent):
#         """Setup filters and history tab"""
#         # Date filters
#         tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
#         self.start_date_entry = tk.Entry(parent, width=30)
#         self.start_date_entry.pack(padx=10, pady=5)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.end_date_entry = tk.Entry(parent, width=30)
#         self.end_date_entry.pack(padx=10, pady=5)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
#         # Emotion filter
#         tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.emotion_filter = ttk.Combobox(parent, values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"], 
#                                           state="readonly", width=27)
#         self.emotion_filter.pack(padx=10, pady=5)
#         self.emotion_filter.set("All")
        
#         # Filter buttons
#         btn_frame = tk.Frame(parent, bg='#34495e')
#         btn_frame.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
#                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
#                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left')
        
#         # Detection history
#         history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         history_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Treeview for detections
#         columns = ("Time", "Emotion", "Confidence", "Type")
#         self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
        
#         # Column configurations
#         self.detection_tree.heading("Time", text="Timestamp")
#         self.detection_tree.heading("Emotion", text="Emotion")
#         self.detection_tree.heading("Confidence", text="Confidence")
#         self.detection_tree.heading("Type", text="Capture")
#         self.detection_tree.column("Time", width=120)
#         self.detection_tree.column("Emotion", width=80)
#         self.detection_tree.column("Confidence", width=80)
#         self.detection_tree.column("Type", width=60)
        
#         # Scrollbar
#         tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
#         self.detection_tree.configure(yscrollcommand=tree_scroll.set)
        
#         self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
#         tree_scroll.pack(side='right', fill='y', pady=10)
        
#         # Bind double-click to view face
#         self.detection_tree.bind('<Double-1>', self.view_face_image)
    
#     def setup_gallery_tab(self, parent):
#         """Setup face gallery tab"""
#         # Gallery controls
#         gallery_controls = tk.Frame(parent, bg='#34495e')
#         gallery_controls.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
#                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
        
#         tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
#                  bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'), 
#                  padx=15, relief='flat').pack(side='left')
        
#         # Face thumbnails display
#         gallery_frame = tk.Frame(parent, bg='#34495e')
#         gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Scrollable canvas for face thumbnails
#         self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
#         gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
#         self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')
        
#         self.scrollable_gallery.bind(
#             "<Configure>",
#             lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
#         )
        
#         self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
#         self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
        
#         self.gallery_canvas.pack(side="left", fill="both", expand=True)
#         gallery_scrollbar.pack(side="right", fill="y")
        
#         self.face_thumbnails = []  # Store face thumbnail references
    
#     def setup_export_tab(self, parent):
#         """Setup export tab"""
#         # Export options
#         export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         export_frame.pack(fill='x', padx=10, pady=10)
        
#         tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
#                  bg='#16a085', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        
#         tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
#                  bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        
#         tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
#                  bg='#e67e22', fg='white', font=('Arial', 12, 'bold'), 
#                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
    
#     def start_display_thread(self):
#         """Start display update thread"""
#         self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
#         self.display_thread.start()
    
#     def start_detection(self):
#         """Start emotion detection"""
#         if self.is_running:
#             self.stop_detection()

#         try:
#             # Try different camera indices
#             for camera_idx in [0, 1, 2]:
#                 self.cap = cv2.VideoCapture(camera_idx)
#                 if self.cap.isOpened():
#                     break
#                 self.cap.release()
            
#             if not self.cap or not self.cap.isOpened():
#                 messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
#                 return
            
#             # Set camera properties
#             self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
#             self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
#             self.cap.set(cv2.CAP_PROP_FPS, 30)
            
#             self.is_running = True
#             self.start_time = time.time()
#             self.frame_count = 0
            
#             # Update UI
#             self.start_btn.config(text="Stop Webcam")
#             self.capture_btn.config(state='normal')
#             self.detection_status.set("Webcam running...")
            
#             # Start detection threads
#             threading.Thread(target=self.detection_loop, daemon=True).start()
            
#             self.status_var.set("Webcam started - Auto-capturing emotions every 3 seconds")
            
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
    
#     def stop_detection(self):
#         """Stop emotion detection"""
#         self.is_running = False
        
#         if self.cap:
#             self.cap.release()
#             self.cap = None
        
#         # Update UI
#         self.start_btn.config(text="Start Webcam")
#         self.capture_btn.config(state='disabled')
#         self.detection_status.set("Idle")
#         self.camera_label.config(image="", text="Feed will appear here\n\nStart Webcam or Upload a File")
#         self.status_var.set("Ready")
    
#     def manual_capture(self):
#         """Manually capture current frame with all detected faces"""
#         if not self.is_running or self.latest_frame is None:
#             messagebox.showwarning("Capture Error", "Please start detection first")
#             return
        
#         try:
#             frame = self.latest_frame.copy()
#             timestamp = datetime.now()
            
#             if self.current_emotions:
#                 for i, emotion_data in enumerate(self.current_emotions):
#                     emotion = emotion_data['dominant_emotion']
#                     confidence = emotion_data['emotion'][emotion]
                    
#                     # Capture this face
#                     self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
                
#                 self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
#             else:
#                 messagebox.showinfo("Capture Info", "No faces detected in current frame")
                
#         except Exception as e:
#             messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")
    
#     def detection_loop(self):
#         """Main detection loop"""
#         while self.is_running:
#             try:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     time.sleep(0.01)
#                     continue
                
#                 # Flip frame horizontally for mirror effect
#                 frame = cv2.flip(frame, 1)
#                 self.latest_frame = frame.copy()
#                 self.frame_count += 1
                
#                 # Analyze every 10th frame
#                 if self.frame_count % 10 == 0:
#                     threading.Thread(target=self.analyze_emotion, 
#                                    args=(frame.copy(),), daemon=True).start()
                
#                 time.sleep(0.033)  # ~30 FPS
                
#             except Exception:
#                 time.sleep(0.1)
    
#     def analyze_emotion(self, frame):
#         """Analyze emotions and auto-capture"""
#         try:
#             # Convert to RGB for DeepFace
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
#             # Analyze emotions
#             results = DeepFace.analyze(
#                 img_path=rgb_frame,
#                 actions=['emotion'],
#                 detector_backend='opencv',
#                 enforce_detection=False,
#                 silent=True
#             )
            
#             if isinstance(results, list):
#                 self.current_emotions = results
#             else:
#                 self.current_emotions = [results]
            
#             # Auto-capture high-confidence detections
#             current_time = time.time()
#             if current_time - self.last_capture_time >= self.capture_cooldown:
#                 for emotion_data in self.current_emotions:
#                     try:
#                         emotion = emotion_data['dominant_emotion']
#                         confidence = emotion_data['emotion'][emotion]
                        
#                         if confidence > 60:  # High confidence threshold
#                             self.capture_emotion(emotion_data, frame.copy())
#                             self.last_capture_time = current_time
#                             break  # Only capture one per cooldown period
#                     except Exception:
#                         continue
                        
#         except Exception:
#             pass
            
#     def upload_image(self):
#         """Upload and analyze a single image file."""
#         if self.is_running:
#             self.stop_detection()
        
#         filepath = filedialog.askopenfilename(
#             title="Select an Image",
#             filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
#         )
#         if not filepath:
#             return
            
#         try:
#             self.status_var.set(f"Analyzing image: {os.path.basename(filepath)}...")
#             self.root.update_idletasks()
            
#             img = cv2.imread(filepath)
#             if img is None:
#                 messagebox.showerror("Error", "Could not load the image file.")
#                 return

#             results = DeepFace.analyze(img_path=img, actions=['emotion'], enforce_detection=False, silent=True)
            
#             summary = ""
#             for i, face in enumerate(results):
#                 region = face['region']
#                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                 emotion = face['dominant_emotion']
#                 confidence = face['emotion'][emotion]
                
#                 color = self.get_emotion_color(emotion)
#                 cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
#                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                 cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                
#                 summary += f"Face {i+1}: {emotion.capitalize()} ({confidence:.1f}%)\n"
            
#             self.display_image(img)
#             self.status_var.set(f"Image analysis complete.")
#             messagebox.showinfo("Image Analysis Results", summary if summary else "No faces detected in the image.")

#         except Exception as e:
#             self.status_var.set("Error during image analysis.")
#             messagebox.showerror("Analysis Error", f"Failed to analyze image: {e}")

#     def upload_video(self):
#         """Upload and process a video file frame by frame."""
#         if self.is_running:
#             self.stop_detection()
            
#         filepath = filedialog.askopenfilename(
#             title="Select a Video",
#             filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv")]
#         )
#         if not filepath:
#             return

#         self.is_running = True
#         self.cap = cv2.VideoCapture(filepath)
        
#         if not self.cap.isOpened():
#             messagebox.showerror("Error", "Could not open the video file.")
#             self.is_running = False
#             return
            
#         self.detection_status.set("Video playing...")
#         self.start_btn.config(text="Stop Video")

#         # Start video processing in a new thread
#         threading.Thread(target=self.process_video_frames, daemon=True).start()
        
#     def process_video_frames(self):
#         """Loop to process video frames for display and analysis."""
#         frame_skip = 5 # Analyze every 5th frame to speed up processing
#         frame_counter = 0
        
#         while self.is_running and self.cap.isOpened():
#             ret, frame = self.cap.read()
#             if not ret:
#                 break # End of video
                
#             self.latest_frame = frame.copy()
            
#             if frame_counter % frame_skip == 0:
#                 # Run analysis in a separate thread to keep the video smooth
#                 threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
            
#             frame_counter += 1
#             time.sleep(1 / 30) # Maintain ~30fps playback

#         self.stop_detection() # Clean up when video ends
    
#     def display_image(self, frame):
#         """Utility to display a single OpenCV frame in the UI."""
#         rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#         pil_image = Image.fromarray(rgb_frame)
        
#         # Resize to fit the label
#         label_w, label_h = self.camera_label.winfo_width(), self.camera_label.winfo_height()
#         pil_image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
        
#         photo = ImageTk.PhotoImage(pil_image)
#         self.camera_label.configure(image=photo, text="")
#         self.camera_label.image = photo

#     def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
#         """Capture and save emotion detection with face cropping"""
#         try:
#             emotion = emotion_data['dominant_emotion']
#             confidence = emotion_data['emotion'][emotion]
#             timestamp = datetime.now()
            
#             # Extract face region
#             region = emotion_data['region']
#             x, y, w, h = region['x'], region['y'], region['w'], region['h']
            
#             # Add padding to face crop
#             padding = 20
#             x1 = max(0, x - padding)
#             y1 = max(0, y - padding)
#             x2 = min(frame.shape[1], x + w + padding)
#             y2 = min(frame.shape[0], y + h + padding)
            
#             # Crop face from original frame
#             face_crop = frame[y1:y2, x1:x2]
            
#             # Draw emotion on full frame
#             color = self.get_emotion_color(emotion)
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#             label = f"{emotion.upper()}: {confidence:.1f}%"
#             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
#             # Save full frame snapshot
#             snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
#             cv2.imwrite(snapshot_filename, frame)
            
#             # Save face crop if folder exists
#             face_filename = None
#             if os.path.exists("faces"):
#                 face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
#                 cv2.imwrite(face_filename, face_crop)
            
#             # Save region info as JSON
#             region_json = json.dumps({
#                 'x': x, 'y': y, 'w': w, 'h': h,
#                 'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
#             })
            
#             # Save to database with error handling
#             try:
#                 self.db_manager.save_detection(
#                     timestamp.isoformat(),
#                     emotion,
#                     confidence,
#                     snapshot_filename,
#                     face_filename,
#                     region_json,
#                     capture_type,
#                     "person1",
#                     self.session_id
#                 )
#                 print(f"Successfully saved detection: {emotion} {confidence:.1f}%")
#             except Exception as db_error:
#                 print(f"Database save error: {db_error}")
#                 # Continue anyway - at least the files are saved
            
#             # Update live detections list
#             detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
#             if self.live_detections.size() > 20:  # Keep only last 20
#                 self.root.after(0, lambda: self.live_detections.delete(tk.END))
            
#             # Update status
#             status_msg = f"Captured {emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.status_var.set(status_msg))
            
#             # Refresh gallery if it's the active tab
#             self.root.after(1000, self.refresh_gallery)
            
#         except Exception as e:
#             print(f"Capture error: {e}")
    
#     def refresh_gallery(self):
#         """Refresh the face gallery with latest captures"""
#         try:
#             # Clear existing thumbnails
#             for widget in self.scrollable_gallery.winfo_children():
#                 widget.destroy()
#             self.face_thumbnails = []
            
#             # Get recent detections with face crops
#             detections = self.db_manager.get_detections(limit=50)
            
#             # Display face thumbnails in grid
#             row, col = 0, 0
#             max_cols = 3
            
#             for detection in detections:
#                 timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         # Load and resize face image
#                         face_img = cv2.imread(face_crop_path)
#                         face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                         face_img = cv2.resize(face_img, (100, 100))
                        
#                         # Convert to PhotoImage
#                         pil_img = Image.fromarray(face_img)
#                         photo = ImageTk.PhotoImage(pil_img)
                        
#                         # Create frame for each thumbnail
#                         thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
#                         thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
                        
#                         # Face image
#                         face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
#                         face_label.pack(pady=5)
#                         face_label.image = photo  # Keep reference
                        
#                         # Emotion label
#                         dt = datetime.fromisoformat(timestamp)
                        
#                         # Robust confidence handling for gallery
#                         confidence_float = 0.0
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             pass

#                         emotion_text = f"{emotion.upper()}: {confidence_float:.1f}%"
#                         time_text = dt.strftime('%m/%d %H:%M')
#                         type_text = f"[{capture_type.upper() if capture_type else 'AUTO'}]"
                        
#                         tk.Label(thumb_frame, text=emotion_text, bg='#2c3e50', fg='white',
#                                 font=('Arial', 8, 'bold')).pack()
#                         tk.Label(thumb_frame, text=time_text, bg='#2c3e50', fg='#bdc3c7',
#                                 font=('Arial', 7)).pack()
#                         tk.Label(thumb_frame, text=type_text, bg='#2c3e50', fg='#f39c12',
#                                 font=('Arial', 7)).pack()
                        
#                         # Store reference for viewing
#                         self.face_thumbnails.append({
#                             'frame': thumb_frame,
#                             'path': face_crop_path,
#                             'snapshot_path': snapshot_path,
#                             'data': detection
#                         })
                        
#                         # Bind click to view larger
#                         face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))
                        
#                         col += 1
#                         if col >= max_cols:
#                             col = 0
#                             row += 1
                            
#                     except Exception as e:
#                         print(f"Thumbnail error: {e}")
#                         continue
            
#             # Update scroll region
#             self.scrollable_gallery.update_idletasks()
#             self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
            
#         except Exception as e:
#             print(f"Gallery refresh error: {e}")
    
#     def view_face_full(self, face_path):
#         """View face image in full size"""
#         try:
#             if os.path.exists(face_path):
#                 # Create new window for full view
#                 view_window = tk.Toplevel(self.root)
#                 view_window.title("Face View")
#                 view_window.configure(bg='#2c3e50')
                
#                 # Load and display image
#                 face_img = cv2.imread(face_path)
#                 face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                
#                 # Resize for viewing (max 400x400)
#                 h, w = face_img.shape[:2]
#                 max_size = 400
#                 if max(h, w) > max_size:
#                     scale = max_size / max(h, w)
#                     new_w, new_h = int(w * scale), int(h * scale)
#                     face_img = cv2.resize(face_img, (new_w, new_h))
                
#                 pil_img = Image.fromarray(face_img)
#                 photo = ImageTk.PhotoImage(pil_img)
                
#                 label = tk.Label(view_window, image=photo, bg='#2c3e50')
#                 label.pack(padx=20, pady=20)
#                 label.image = photo  # Keep reference
                
#                 # Center window
#                 view_window.update_idletasks()
#                 x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
#                 y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
#                 view_window.geometry(f'+{x}+{y}')
                
#         except Exception as e:
#             messagebox.showerror("View Error", f"Cannot view face: {str(e)}")
    
#     def view_face_image(self, event):
#         """View face from detection tree double-click"""
#         selection = self.detection_tree.selection()
#         if selection:
#             item = self.detection_tree.item(selection[0])
#             # Get the detection data and show face
#             # This would need to store more data in the tree or query DB
#             pass
    
#     def view_selected_face(self):
#         """View selected face from gallery"""
#         # This could be enhanced to track selected thumbnails
#         messagebox.showinfo("Info", "Click on any face thumbnail to view full size")
    
#     def update_display_loop(self):
#         """Update camera display with emotion overlays"""
#         while True:
#             try:
#                 if self.is_running and self.latest_frame is not None:
#                     frame = self.latest_frame.copy()
                    
#                     # Draw emotion overlays
#                     if self.current_emotions:
#                         for emotion_data in self.current_emotions:
#                             try:
#                                 region = emotion_data['region']
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 emotion = emotion_data['dominant_emotion']
#                                 confidence = emotion_data['emotion'][emotion]
#                                 color = self.get_emotion_color(emotion)
                                
#                                 cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#                                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                                 cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                             except Exception:
#                                 continue
                    
#                     self.display_image(frame)
                
#                 time.sleep(0.033)  # ~30 FPS
                
#             except Exception:
#                 time.sleep(0.1)
    
#     def get_emotion_color(self, emotion):
#         """Get color for each emotion"""
#         colors = {
#             'happy': (0, 255, 0),      # Green
#             'sad': (255, 100, 100),    # Light Blue
#             'angry': (0, 0, 255),      # Red
#             'fear': (255, 0, 255),     # Magenta
#             'surprise': (0, 255, 255), # Yellow
#             'disgust': (128, 0, 128),  # Purple
#             'neutral': (128, 128, 128) # Gray
#         }
#         return colors.get(emotion, (255, 255, 255))
    
#     def apply_filters(self):
#         """Apply filters and refresh data"""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             # Clear and populate tree
#             for item in self.detection_tree.get_children():
#                 self.detection_tree.delete(item)
            
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                
#                 # Robust confidence handling for display
#                 confidence_float = 0.0
#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     pass # Keep as 0.0 if conversion fails

#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%m/%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 self.detection_tree.insert('', 'end', values=(formatted_time, emotion_name.upper(), f"{confidence_float:.1f}%", type_display))
            
#             self.status_var.set(f"Loaded {len(detections)} detections")
            
#             # Refresh gallery too
#             self.refresh_gallery()
            
#         except Exception as e:
#             messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
    
#     def clear_filters(self):
#         """Clear all filters"""
#         self.start_date_entry.delete(0, tk.END)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
#         self.end_date_entry.delete(0, tk.END)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
#         self.emotion_filter.set("All")
#         self.apply_filters()
    
#     def export_csv(self):
#         """Export detections to CSV, embedding images as Base64 strings."""
#         try:
#             # Get current filtered data
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
            
#             # Ask where to save the CSV file
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".csv",
#                 filetypes=[("CSV files", "*.csv")],
#                 initialfile=f"emotion_detections_base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#             )
            
#             if filename:
#                 with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#                     writer = csv.writer(csvfile)
#                     # Updated header for the Base64 image data
#                     writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Base64"])
                    
#                     for detection in detections:
#                         timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                        
#                         image_base64_string = "N/A"
                        
#                         # Robust confidence handling
#                         confidence_float = 0.0
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             print(f"Could not convert confidence '{confidence}' to float for {timestamp}. Defaulting to 0.0.")
                        
#                         try:
#                             # Load the original snapshot
#                             if snapshot_path and os.path.exists(snapshot_path):
#                                 image = cv2.imread(snapshot_path)
                                
#                                 # Draw bounding box if region data is available
#                                 if image is not None and face_region:
#                                     region = json.loads(face_region)
#                                     x, y, w, h = region['x'], region['y'], region['w'], region['h']
                                    
#                                     color = self.get_emotion_color(emotion_name)
#                                     cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
#                                     label = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                                     cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                                
#                                 # Encode the final image (with or without box) to Base64
#                                 _, buffer = cv2.imencode('.jpg', image)
#                                 image_base64_string = base64.b64encode(buffer).decode('utf-8')
                                
#                             else:
#                                 image_base64_string = "Snapshot not found"

#                         except Exception as e:
#                             print(f"Could not process and encode image for {timestamp}: {e}")
#                             image_base64_string = "Error encoding image"
                        
#                         # Write the row to the CSV file
#                         writer.writerow([timestamp, emotion_name, f"{confidence_float:.1f}%", image_base64_string])

#                 messagebox.showinfo("Export", f"Data and embedded images exported successfully to {filename}")

#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")

            
#     def export_pdf(self):
#         """Export detections to PDF report with embedded images."""
#         try:
#             from reportlab.lib.pagesizes import A4
#             from reportlab.pdfgen import canvas
#             from reportlab.lib.utils import ImageReader
#             from reportlab.lib.units import inch
#         except ImportError:
#             messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
#             return
        
#         try:
#             # Get current filtered data
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
            
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
            
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
            
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".pdf",
#                 filetypes=[("PDF files", "*.pdf")],
#                 initialfile=f"emotion_report_with_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#             )
            
#             if filename:
#                 c = canvas.Canvas(filename, pagesize=A4)
#                 width, height = A4
                
#                 # --- PDF Header ---
#                 c.setFont("Helvetica-Bold", 20)
#                 c.drawString(inch, height - inch, "Emotion Detection Report")
                
#                 # --- Summary Stats ---
#                 total = len(detections)
#                 emotion_counts = Counter([d[1] for d in detections])
#                 auto_count = sum(1 for d in detections if d[6] == 'auto')
#                 manual_count = sum(1 for d in detections if d[6] == 'manual')
                
#                 y_pos = height - inch * 1.5
#                 c.setFont("Helvetica-Bold", 12)
#                 c.drawString(inch, y_pos, f"Total Detections: {total}")
#                 c.drawString(inch, y_pos - 20, f"Auto Captures: {auto_count}")
#                 c.drawString(inch, y_pos - 40, f"Manual Captures: {manual_count}")
                
#                 c.setFont("Helvetica-Bold", 12)
#                 c.drawString(inch * 4, y_pos, "Emotion Distribution:")
#                 c.setFont("Helvetica", 10)
                
#                 stat_y = y_pos - 20
#                 for emotion_name, count in emotion_counts.most_common():
#                     percentage = (count / total) * 100 if total > 0 else 0
#                     c.drawString(inch * 4, stat_y, f"{emotion_name.upper()}: {count} ({percentage:.1f}%)")
#                     stat_y -= 15
                
#                 # --- Detection List with Images ---
#                 y_pos -= 100
#                 c.setFont("Helvetica-Bold", 14)
#                 c.drawString(inch, y_pos, "Detection Log")
#                 y_pos -= 30

#                 for i, detection in enumerate(detections):
#                     # Check for new page
#                     if y_pos < inch * 2:
#                         c.showPage()
#                         y_pos = height - inch

#                     timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                    
#                     # Robust confidence handling
#                     confidence_float = 0.0
#                     try:
#                         confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                         confidence_float = float(confidence_str)
#                     except (ValueError, TypeError):
#                         pass

#                     dt = datetime.fromisoformat(timestamp)
#                     formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
#                     type_display = capture_type.upper() if capture_type else 'AUTO'
                    
#                     # Draw text
#                     c.setFont("Helvetica", 9)
#                     text = f"{i+1}. {formatted_time} | {emotion_name.upper()} | {confidence_float:.1f}% | {type_display}"
#                     c.drawString(inch, y_pos, text)
#                     y_pos -= 15
                    
#                     # Draw image if it exists
#                     if face_crop_path and os.path.exists(face_crop_path):
#                         try:
#                             img_width = 1.5 * inch
#                             img_height = 1.5 * inch
                            
#                             if y_pos < img_height + inch: # Check space for image
#                                 c.showPage()
#                                 y_pos = height - inch

#                             c.drawImage(face_crop_path, inch, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
#                             y_pos -= (img_height + 10) # Move position down after drawing image
#                         except Exception as e:
#                             c.drawString(inch + 5, y_pos, f"  (Error loading image: {e})")
#                             y_pos -= 15
#                     else:
#                         c.setFont("Helvetica-Oblique", 8)
#                         c.drawString(inch + 5, y_pos, "  (No face image available)")
#                         y_pos -= 15

#                 c.save()
#                 messagebox.showinfo("Export", f"Report with images exported successfully to {filename}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")
    
#     def export_faces(self):
#         """Export face gallery as ZIP file"""
#         try:
#             import zipfile
            
#             # Check if faces folder exists
#             if not os.path.exists("faces"):
#                 messagebox.showinfo("Export", "No faces folder found")
#                 return
            
#             # Get all face files
#             face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
            
#             if not face_files:
#                 messagebox.showinfo("Export", "No face images to export")
#                 return
            
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".zip",
#                 filetypes=[("ZIP files", "*.zip")],
#                 initialfile=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
#             )
            
#             if filename:
#                 with zipfile.ZipFile(filename, 'w') as zipf:
#                     for face_file in face_files:
#                         face_path = os.path.join("faces", face_file)
#                         zipf.write(face_path, face_file)
                
#                 messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")
                
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")
    
#     def run(self):
#         """Run the application"""
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
#         self.root.mainloop()
    
#     def on_closing(self):
#         """Handle application closing"""
#         if self.is_running:
#             self.stop_detection()
#         self.root.destroy()

# # -------------------- Main Application Entry Point --------------------
# def main():
#     """Main application entry point"""
#     print("Starting Enhanced Emotion Detection System with Database Migration...")
    
#     # Initialize database with migration
#     db_manager = DatabaseManager()
    
#     # Show login window
#     login_window = LoginWindow(db_manager)
#     success, username = login_window.show()
    
#     if success:
#         print(f"Login successful for user: {username}")
#         # Start main application
#         app = EmotionDetectionSystem(username)
#         app.run()
#     else:
#         print("Login cancelled or failed")

# if __name__ == "__main__":
#     main()

















# """
# Complete Emotion Detection System with Image/Video Upload and Analysis
# Install: pip install deepface opencv-python tensorflow pillow reportlab matplotlib
#
# Features:
# - Secure admin authentication
# - Real-time emotion detection from webcam
# - Capture short video clips with emotion annotations
# - Upload and analyze emotions from image files (JPG, PNG)
# - Upload and analyze emotions from video files (MP4, AVI)
# - Robust data handling and professional PDF/CSV exporting
# - Automatic database migration for existing installations
# - NEW: Graphs (Pie + Line) for emotion analytics based on current filters
# """

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from deepface import DeepFace
import threading
import time
from PIL import Image, ImageTk
from collections import deque, Counter
import sqlite3
import os
import csv
import hashlib
import secrets
from datetime import datetime, timedelta
import json
import base64

# Charts
from matplotlib.figure import Figure
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# # -------------------- Password Security --------------------
# def hash_password(password: str, iterations: int = 200_000) -> str:
#     """Hash password using PBKDF2"""
#     salt = secrets.token_bytes(16)
#     dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#     return f"{iterations}${salt.hex()}${dk.hex()}"


# def verify_password(password: str, stored: str) -> bool:
#     """Verify password against stored hash"""
#     try:
#         iterations_s, salt_hex, hash_hex = stored.split("$")
#         iterations = int(iterations_s)
#         salt = bytes.fromhex(salt_hex)
#         target = bytes.fromhex(hash_hex)
#         dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#         return secrets.compare_digest(dk, target)
#     except Exception:
#         return False


# # -------------------- Database Manager with Migration --------------------
# class DatabaseManager:
#     def __init__(self, db_path="emotion_system.db"):
#         self.db_path = db_path
#         self.init_database()
#         self.migrate_database()  # Add migration step

#     def init_database(self):
#         """Initialize database with required tables"""
#         os.makedirs("snapshots", exist_ok=True)
#         os.makedirs("faces", exist_ok=True)   # New folder for cropped faces
#         os.makedirs("videos", exist_ok=True)  # New folder for video captures

#         conn = sqlite3.connect(self.db_path)

#         # Users table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY,
#                 username TEXT UNIQUE NOT NULL,
#                 password_hash TEXT NOT NULL,
#                 role TEXT DEFAULT 'admin',
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)

#         # Detections table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS detections (
#                 id INTEGER PRIMARY KEY,
#                 timestamp TEXT NOT NULL,
#                 emotion TEXT NOT NULL,
#                 confidence REAL NOT NULL,
#                 snapshot_path TEXT NOT NULL,
#                 face_crop_path TEXT,
#                 face_region TEXT,
#                 capture_type TEXT DEFAULT 'auto',
#                 person_id TEXT,
#                 session_id TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)

#         # Indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")

#         # Default admin user
#         cursor = conn.execute("SELECT COUNT(*) FROM users")
#         if cursor.fetchone()[0] == 0:
#             admin_hash = hash_password("admin123")
#             conn.execute(
#                 "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#                 ("admin", admin_hash, "admin"),
#             )

#         conn.commit()
#         conn.close()

#     def migrate_database(self):
#         """Migrate existing database to add new columns"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()

#         try:
#             cursor.execute("PRAGMA table_info(detections)")
#             columns = [column[1] for column in cursor.fetchall()]

#             if 'face_crop_path' not in columns:
#                 print("Adding face_crop_path column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")

#             if 'face_region' not in columns:
#                 print("Adding face_region column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")

#             if 'capture_type' not in columns:
#                 print("Adding capture_type column...")
#                 cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")

#             conn.commit()
#             print("Database migration completed successfully!")
#         except Exception as e:
#             print(f"Migration error (this is normal for new installations): {e}")
#         finally:
#             conn.close()

#     def verify_user(self, username: str, password: str) -> bool:
#         """Verify user credentials"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
#         result = cursor.fetchone()
#         conn.close()

#         if result:
#             return verify_password(password, result[0])
#         return False

#     def save_detection(self, timestamp: str, emotion: str, confidence: float,
#                        snapshot_path: str, face_crop_path: str = None, face_region: str = None,
#                        capture_type: str = 'auto', person_id: str = None, session_id: str = None):
#         """Save detection to database"""
#         conn = sqlite3.connect(self.db_path)
#         try:
#             conn.execute("""
#                 INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
#                                         face_region, capture_type, person_id, session_id)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region,
#                   capture_type, person_id, session_id))
#             conn.commit()
#         except sqlite3.OperationalError as e:
#             # Fallback for old structure
#             print(f"Database error, trying fallback: {e}")
#             try:
#                 conn.execute("""
#                     INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
#                 conn.commit()
#             except Exception as fallback_error:
#                 print(f"Fallback failed: {fallback_error}")
#         finally:
#             conn.close()

#     def get_detections(self, start_date=None, end_date=None, emotion=None, limit=1000):
#         """Get filtered detections from database"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
#         cursor.execute("PRAGMA table_info(detections)")
#         columns = [column[1] for column in cursor.fetchall()]

#         base_columns = "timestamp, emotion, confidence, snapshot_path"
#         base_columns += ", face_crop_path" if 'face_crop_path' in columns else ", NULL as face_crop_path"
#         base_columns += ", face_region" if 'face_region' in columns else ", NULL as face_region"
#         base_columns += ", capture_type" if 'capture_type' in columns else ", 'auto' as capture_type"
#         base_columns += ", person_id"

#         query = f"SELECT {base_columns} FROM detections WHERE 1=1"
#         params = []

#         if start_date:
#             query += " AND timestamp >= ?"
#             params.append(start_date)
#         if end_date:
#             query += " AND timestamp <= ?"
#             params.append(end_date)
#         if emotion and emotion.lower() != "all":
#             query += " AND emotion = ?"
#             params.append(emotion.lower())

#         query += " ORDER BY timestamp DESC LIMIT ?"
#         params.append(limit)

#         cursor = conn.execute(query, params)
#         results = cursor.fetchall()
#         conn.close()
#         return results


# # -------------------- Enhanced Login Window --------------------
# class LoginWindow:
#     def __init__(self, db_manager):
#         self.db_manager = db_manager
#         self.success = False
#         self.username = None

#         self.root = tk.Tk()
#         self.root.title("Emotion Detection System - Admin Login")
#         self.root.geometry("500x400")
#         self.root.configure(bg='#2c3e50')
#         self.root.resizable(False, False)

#         # Center the window
#         self.root.eval('tk::PlaceWindow . center')

#         self.setup_ui()

#     def setup_ui(self):
#         """Setup enhanced login UI with password features"""
#         main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
#         main_frame.pack(fill='both', expand=True)

#         title_label = tk.Label(main_frame, text="Admin Login",
#                                font=('Arial', 24, 'bold'),
#                                bg='#2c3e50', fg='white')
#         title_label.pack(pady=(0, 15))

#         form_frame = tk.Frame(main_frame, bg='#2c3e50')
#         form_frame.pack(fill='x')

#         tk.Label(form_frame, text="Username:", font=('Arial', 12),
#                  bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))

#         self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
#                                        bg='#34495e', fg='white', insertbackground='white',
#                                        relief='flat', bd=5)
#         self.username_entry.pack(fill='x', pady=(0, 15))
#         self.username_entry.insert(0, "admin")

#         tk.Label(form_frame, text="Password:", font=('Arial', 12),
#                  bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))

#         self.password_entry = tk.Entry(form_frame, font=('Arial', 12),
#                                        show="\u2022", bg='#34495e', fg='white',
#                                        insertbackground='white', relief='flat', bd=5)
#         self.password_entry.pack(fill='x', pady=(0, 10))
#         self.password_entry.bind('<KeyRelease>', self.update_password_feedback)

#         toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
#         toggle_frame.pack(fill='x', pady=(5, 10))

#         self.show_password_var = tk.BooleanVar()
#         show_password_check = tk.Checkbutton(
#             toggle_frame,
#             text="Show Password",
#             variable=self.show_password_var,
#             command=self.toggle_password_visibility,
#             bg='#2c3e50',
#             fg='#bdc3c7',
#             selectcolor='#2c3e50',
#             font=('Arial', 10)
#         )
#         show_password_check.pack(side='left')

#         self.password_length_label = tk.Label(
#             toggle_frame,
#             text="Characters: 0",
#             font=('Arial', 9),
#             bg='#2c3e50',
#             fg='#7f8c8d'
#         )
#         self.password_length_label.pack(side='right')

#         info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
#         info_frame.pack(fill='x', pady=(0, 20))
#         tk.Label(info_frame, text="Default: admin / admin123",
#                  font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)

#         button_frame = tk.Frame(form_frame, bg='#2c3e50')
#         button_frame.pack(fill='x', pady=(10, 0))

#         login_btn = tk.Button(button_frame, text="Login",
#                               command=self.login,
#                               bg='#27ae60', fg='white',
#                               font=('Arial', 12, 'bold'),
#                               padx=30, pady=10, relief='flat')
#         login_btn.pack(side='left', padx=(0, 10))

#         cancel_btn = tk.Button(button_frame, text="Cancel",
#                                command=self.cancel,
#                                bg='#e74c3c', fg='white',
#                                font=('Arial', 12, 'bold'),
#                                padx=30, pady=10, relief='flat')
#         cancel_btn.pack(side='left')

#         self.root.bind('<Return>', lambda e: self.login())
#         self.password_entry.focus()

#     def toggle_password_visibility(self):
#         """Toggle password field visibility"""
#         self.password_entry.config(show="" if self.show_password_var.get() else "\u2022")

#     def update_password_feedback(self, event=None):
#         """Update password input feedback"""
#         length = len(self.password_entry.get())
#         self.password_length_label.config(text=f"Characters: {length}")

#     def login(self):
#         """Handle login attempt"""
#         username = self.username_entry.get().strip()
#         password = self.password_entry.get()

#         if not username or not password:
#             messagebox.showerror("Error", "Please enter both username and password")
#             return

#         if self.db_manager.verify_user(username, password):
#             self.success = True
#             self.username = username
#             self.root.destroy()
#         else:
#             messagebox.showerror("Login Failed", "Invalid username or password")
#             self.password_entry.delete(0, tk.END)
#             self.password_entry.focus()
#             self.password_length_label.config(text="Characters: 0")

#     def cancel(self):
#         """Handle cancel"""
#         self.root.destroy()

#     def show(self):
#         """Show login window and return success status"""
#         self.root.mainloop()
#         return self.success, self.username


# # -------------------- Main Application --------------------
# class EmotionDetectionSystem:
#     def __init__(self, username):
#         self.username = username
#         self.db_manager = DatabaseManager()
#         self.session_id = f"session_{int(time.time())}"

#         # Core variables
#         self.cap = None
#         self.is_running = False
#         self.is_recording = False
#         self.current_emotions = []
#         self.latest_frame = None
#         self.frame_count = 0
#         self.start_time = time.time()
#         self.last_capture_time = 0
#         self.capture_cooldown = 3.0  # Seconds between auto-captures

#         # Setup main window
#         self.root = tk.Tk()
#         self.root.title(f"Emotion Detection System - Welcome {username}")
#         self.root.geometry("1500x950")
#         self.root.configure(bg='#2c3e50')

#         self.setup_ui()
#         self.start_display_thread()

#         # Load initial data
#         self.apply_filters()

#     def setup_ui(self):
#         """Setup main application UI"""
#         # Header
#         header = tk.Frame(self.root, bg='#2c3e50', height=70)
#         header.pack(fill='x', padx=15, pady=10)
#         header.pack_propagate(False)

#         # Title and user info
#         title_frame = tk.Frame(header, bg='#2c3e50')
#         title_frame.pack(side='left', fill='y', padx=(0, 20))

#         tk.Label(title_frame, text="Emotion Detection System",
#                  font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
#         tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}",
#                  font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')

#         # Controls
#         controls = tk.Frame(header, bg='#2c3e50')
#         controls.pack(side='right', fill='y')

#         button_font = ('Arial', 11, 'bold')
#         button_padx = 15
#         button_pady = 10
#         pack_padx = 4

#         # Start Webcam
#         self.start_btn = tk.Button(controls, text="Start Webcam", command=self.start_detection,
#                                    bg='#27ae60', fg='white', font=button_font,
#                                    padx=button_padx, pady=button_pady, relief='flat')
#         self.start_btn.pack(side='left', padx=pack_padx)

#         # Stop Webcam (separate button; we'll enable/disable it)
#         self.stop_btn = tk.Button(controls, text="Stop Webcam", command=self.stop_detection,
#                                   bg='#e74c3c', fg='white', font=button_font,
#                                   padx=button_padx, pady=button_pady, state='disabled', relief='flat')
#         self.stop_btn.pack(side='left', padx=pack_padx)

#         # Capture Face
#         self.capture_btn = tk.Button(controls, text="Capture Face", command=self.manual_capture,
#                                      bg='#f39c12', fg='white', font=button_font,
#                                      padx=button_padx, pady=button_pady, state='disabled', relief='flat')
#         self.capture_btn.pack(side='left', padx=pack_padx)

#         # Capture Video
#         self.videocapture_btn = tk.Button(controls, text="Capture Video", command=self.manual_video_capture,
#                                           bg='#3498db', fg='white', font=button_font,
#                                           padx=button_padx, pady=button_pady, state='disabled', relief='flat')
#         self.videocapture_btn.pack(side='left', padx=pack_padx)

#         # Upload Image
#         tk.Button(controls, text="Upload Image", command=self.upload_image,
#                   bg='#5dade2', fg='white', font=button_font,
#                   padx=button_padx, pady=button_pady, relief='flat').pack(side='left', padx=pack_padx)

#         # Upload Video
#         tk.Button(controls, text="Upload Video", command=self.upload_video,
#                   bg='#8e44ad', fg='white', font=button_font,
#                   padx=button_padx, pady=button_pady, relief='flat').pack(side='left', padx=pack_padx)

#         # Main content
#         main_frame = tk.Frame(self.root, bg='#2c3e50')
#         main_frame.pack(fill='both', expand=True, padx=15, pady=5)

#         # Left: Camera and real-time detection
#         left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
#         left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

#         camera_header = tk.Frame(left_frame, bg='#34495e')
#         camera_header.pack(fill='x', pady=10)

#         tk.Label(camera_header, text="Live Feed / Uploaded Media", bg='#34495e', fg='white',
#                  font=('Arial', 16, 'bold')).pack(side='left', padx=15)

#         self.detection_status = tk.StringVar(value="Idle")
#         tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12',
#                  font=('Arial', 12, 'bold')).pack(side='right', padx=15)

#         self.camera_label = tk.Label(left_frame, text="Feed will appear here\n\nStart Webcam or Upload a File",
#                                      bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
#                                      width=70, height=20)
#         self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)

#         # Recent detections list
#         rt_frame = tk.Frame(left_frame, bg='#34495e')
#         rt_frame.pack(fill='x', padx=15, pady=(0, 15))
#         tk.Label(rt_frame, text="Recent Detections", bg='#34495e', fg='white',
#                  font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
#         self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
#                                           font=('Consolas', 10), relief='flat')
#         self.live_detections.pack(fill='x')

#         # Right: Dashboard tabs
#         right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
#         right_frame.pack(side='right', fill='y')
#         right_frame.pack_propagate(False)

#         notebook = ttk.Notebook(right_frame)
#         notebook.pack(fill='both', expand=True, padx=10, pady=10)

#         # Filters tab
#         filters_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(filters_frame, text="Filters & History")
#         self.setup_filters_tab(filters_frame)

#         # Face Gallery tab
#         gallery_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(gallery_frame, text="Face Gallery")
#         self.setup_gallery_tab(gallery_frame)

#         # Export tab
#         export_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(export_frame, text="Export")
#         self.setup_export_tab(export_frame)

#         # Status bar
#         status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
#         status_frame.pack(fill='x', padx=15, pady=5)

#         self.status_var = tk.StringVar(value="Ready")
#         tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
#                  font=('Arial', 10)).pack(side='left', pady=5)

#     def setup_filters_tab(self, parent):
#         """Setup filters and history tab"""
#         tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
#         self.start_date_entry = tk.Entry(parent, width=30)
#         self.start_date_entry.pack(padx=10, pady=5)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))

#         tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.end_date_entry = tk.Entry(parent, width=30)
#         self.end_date_entry.pack(padx=10, pady=5)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

#         tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.emotion_filter = ttk.Combobox(parent,
#                                            values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"],
#                                            state="readonly", width=27)
#         self.emotion_filter.pack(padx=10, pady=5)
#         self.emotion_filter.set("All")

#         btn_frame = tk.Frame(parent, bg='#34495e')
#         btn_frame.pack(fill='x', padx=10, pady=10)

#         tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
#                   bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
#                   bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left')

#         history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white',
#                                       font=('Arial', 12, 'bold'))
#         history_frame.pack(fill='both', expand=True, padx=10, pady=10)

#         columns = ("Time", "Emotion", "Confidence", "Type")
#         self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
#         self.detection_tree.heading("Time", text="Timestamp")
#         self.detection_tree.heading("Emotion", text="Emotion")
#         self.detection_tree.heading("Confidence", text="Confidence")
#         self.detection_tree.heading("Type", text="Capture")
#         self.detection_tree.column("Time", width=120)
#         self.detection_tree.column("Emotion", width=80)
#         self.detection_tree.column("Confidence", width=80)
#         self.detection_tree.column("Type", width=60)

#         tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
#         self.detection_tree.configure(yscrollcommand=tree_scroll.set)

#         self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
#         tree_scroll.pack(side='right', fill='y', pady=10)

#         self.detection_tree.bind('<Double-1>', self.view_face_image)

#     def setup_gallery_tab(self, parent):
#         """Setup face gallery tab"""
#         gallery_controls = tk.Frame(parent, bg='#34495e')
#         gallery_controls.pack(fill='x', padx=10, pady=10)

#         tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
#                   bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
#                   bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left')

#         gallery_frame = tk.Frame(parent, bg='#34495e')
#         gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)

#         self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
#         gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
#         self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')

#         self.scrollable_gallery.bind(
#             "<Configure>",
#             lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
#         )

#         self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
#         self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)

#         self.gallery_canvas.pack(side="left", fill="both", expand=True)
#         gallery_scrollbar.pack(side="right", fill="y")

#         self.face_thumbnails = []  # Store face thumbnail references

#     def setup_export_tab(self, parent):
#         """Setup export tab"""
#         export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white',
#                                      font=('Arial', 12, 'bold'))
#         export_frame.pack(fill='x', padx=10, pady=10)

#         tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
#                   bg='#16a085', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

#         tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
#                   bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

#         tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
#                   bg='#e67e22', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

#         # NEW: Graphs button
#         tk.Button(export_frame, text="Show Graphs (Pie + Line)", command=self.show_graphs,
#                   bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

#     # -------------------- Graphs --------------------
#     def show_graphs(self):
#         """Open a window with a Pie chart of emotion distribution and a Line chart of trends over time."""
#         try:
#             # Use current filters
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion_filter_value = self.emotion_filter.get()

#             start_iso = f"{start_date}T00:00:00" if start_date else None
#             end_iso = f"{end_date}T23:59:59" if end_date else None

#             detections = self.db_manager.get_detections(start_iso, end_iso, emotion_filter_value)
#             if not detections:
#                 messagebox.showinfo("Graphs", "No detections for the current filters.")
#                 return

#             # Aggregates
#             from collections import Counter, defaultdict
#             emotion_counts = Counter([d[1] for d in detections])

#             timestamps = []
#             for d in detections:
#                 try:
#                     dt = datetime.fromisoformat(d[0])
#                     timestamps.append(dt)
#                 except Exception:
#                     continue

#             if not timestamps:
#                 messagebox.showinfo("Graphs", "No valid timestamps to display.")
#                 return

#             min_dt, max_dt = min(timestamps), max(timestamps)
#             delta_days = (max_dt.date() - min_dt.date()).days
#             group_by_hour = delta_days <= 2

#             series_counts = defaultdict(int)
#             if group_by_hour:
#                 for dt in timestamps:
#                     key = dt.replace(minute=0, second=0, microsecond=0)
#                     series_counts[key] += 1
#                 x_sorted = sorted(series_counts.keys())
#                 x_labels = [k.strftime("%Y-%m-%d %H:00") for k in x_sorted]
#             else:
#                 for dt in timestamps:
#                     key = datetime(dt.year, dt.month, dt.day)
#                     series_counts[key] += 1
#                 x_sorted = sorted(series_counts.keys())
#                 x_labels = [k.strftime("%Y-%m-%d") for k in x_sorted]
#             y_values = [series_counts[k] for k in x_sorted]

#             # UI window
#             win = tk.Toplevel(self.root)
#             win.title("Emotion Analytics")
#             win.configure(bg='#2c3e50')

#             top_frame = tk.Frame(win, bg='#2c3e50')
#             top_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
#             bottom_frame = tk.Frame(win, bg='#2c3e50')
#             bottom_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

#             # Pie chart
#             fig_pie = Figure(figsize=(4.8, 4.0), dpi=100)
#             ax_pie = fig_pie.add_subplot(111)
#             labels = list(emotion_counts.keys())
#             sizes = [emotion_counts[k] for k in labels]
#             if sum(sizes) == 0:
#                 labels, sizes = ["No Data"], [1]
#             ax_pie.pie(sizes, labels=[s.upper() for s in labels], autopct='%1.1f%%', startangle=90)
#             ax_pie.set_title("Emotion Distribution", fontsize=12)
#             ax_pie.axis('equal')
#             canvas_pie = FigureCanvasTkAgg(fig_pie, master=top_frame)
#             canvas_pie.draw()
#             canvas_pie.get_tk_widget().pack(fill='both', expand=True)

#             # Line chart
#             fig_line = Figure(figsize=(6.8, 3.4), dpi=100)
#             ax_line = fig_line.add_subplot(111)
#             ax_line.plot(x_labels, y_values, marker='o')
#             ax_line.set_title("Detections Over Time", fontsize=12)
#             ax_line.set_xlabel("Time" if group_by_hour else "Date")
#             ax_line.set_ylabel("Detections")
#             ax_line.grid(True, linestyle='--', alpha=0.3)
#             if len(x_labels) > 6:
#                 for label in ax_line.get_xticklabels():
#                     label.set_rotation(30)
#                     label.set_horizontalalignment('right')
#             canvas_line = FigureCanvasTkAgg(fig_line, master=bottom_frame)
#             canvas_line.draw()
#             canvas_line.get_tk_widget().pack(fill='both', expand=True)

#             # Center the window roughly
#             win.update_idletasks()
#             x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
#             y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
#             win.geometry(f'+{x}+{y}')
#         except Exception as e:
#             messagebox.showerror("Graphs Error", f"Could not render graphs: {e}")

#     # -------------------- Core flows --------------------
#     def start_display_thread(self):
#         """Start display update thread"""
#         self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
#         self.display_thread.start()

#     def start_detection(self):
#         """Start emotion detection"""
#         if self.is_running:
#             self.stop_detection()
#         try:
#             for camera_idx in [0, 1, 2]:
#                 self.cap = cv2.VideoCapture(camera_idx)
#                 if self.cap.isOpened():
#                     break
#                 self.cap.release()

#             if not self.cap or not self.cap.isOpened():
#                 messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
#                 return

#             # Set camera properties
#             self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
#             self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
#             self.cap.set(cv2.CAP_PROP_FPS, 30)

#             self.is_running = True
#             self.start_time = time.time()
#             self.frame_count = 0

#             # Update UI
#             self.start_btn.config(text="Stop Webcam", command=self.stop_detection)
#             self.stop_btn.config(state='normal')
#             self.capture_btn.config(state='normal')
#             self.videocapture_btn.config(state='normal')
#             self.detection_status.set("Webcam running...")

#             threading.Thread(target=self.detection_loop, daemon=True).start()
#             self.status_var.set("Webcam started - Auto-capturing emotions every 3 seconds")
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to start detection: {str(e)}")

#     def stop_detection(self):
#         """Stop emotion detection"""
#         self.is_running = False
#         if self.cap:
#             self.cap.release()
#             self.cap = None

#         self.start_btn.config(text="Start Webcam", command=self.start_detection)
#         self.stop_btn.config(state='disabled')
#         self.capture_btn.config(state='disabled')
#         self.videocapture_btn.config(state='disabled')
#         self.detection_status.set("Idle")
#         self.camera_label.config(image="", text="Feed will appear here\n\nStart Webcam or Upload a File")
#         self.status_var.set("Ready")

#     def manual_capture(self):
#         """Manually capture current frame with all detected faces"""
#         if not self.is_running or self.latest_frame is None:
#             messagebox.showwarning("Capture Error", "Please start detection first")
#             return
#         try:
#             frame = self.latest_frame.copy()
#             if self.current_emotions:
#                 for i, emotion_data in enumerate(self.current_emotions):
#                     self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
#                 self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
#             else:
#                 messagebox.showinfo("Capture Info", "No faces detected in current frame")
#         except Exception as e:
#             messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")

#     def manual_video_capture(self):
#         """Starts a thread to record a short video clip."""
#         if not self.is_running:
#             messagebox.showwarning("Video Capture Error", "Please start the webcam first.")
#             return
#         if self.is_recording:
#             messagebox.showwarning("Video Capture Error", "A recording is already in progress.")
#             return
#         threading.Thread(target=self._record_video_thread, daemon=True).start()

#     def _record_video_thread(self):
#         """Records a 5-second video clip with emotion annotations and saves it."""
#         self.is_recording = True
#         self.videocapture_btn.config(state='disabled')
#         self.status_var.set("Recording video with annotations for 5 seconds...")

#         duration = 5  # seconds
#         fps = 20.0
#         width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#         height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

#         if width == 0 or height == 0:
#             self.status_var.set("Error: Invalid frame dimensions from camera.")
#             self.is_recording = False
#             self.videocapture_btn.config(state='normal')
#             messagebox.showerror("Recording Error", "Could not get valid frame dimensions.")
#             return

#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         filename = f"videos/capture_{timestamp}_annotated.mp4"

#         # Try avc1, then fallback to mp4v
#         fourcc = cv2.VideoWriter_fourcc(*'avc1')
#         out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
#         if not out.isOpened():
#             fourcc = cv2.VideoWriter_fourcc(*'mp4v')
#             out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
#         if not out.isOpened():
#             self.status_var.set("Error: Could not open video writer.")
#             self.is_recording = False
#             self.videocapture_btn.config(state='normal')
#             messagebox.showerror("Recording Error", "Failed to initialize video recording.")
#             return

#         start_time = time.time()
#         while time.time() - start_time < duration:
#             if self.latest_frame is not None:
#                 annotated_frame = self.latest_frame.copy()
#                 if self.current_emotions:
#                     for emotion_data in self.current_emotions:
#                         try:
#                             region = emotion_data['region']
#                             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                             emotion = emotion_data['dominant_emotion']
#                             confidence = emotion_data['emotion'][emotion]
#                             color = self.get_emotion_color(emotion)
#                             cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 3)
#                             label = f"{emotion.upper()}: {confidence:.1f}%"
#                             cv2.putText(annotated_frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                         except Exception:
#                             continue
#                 out.write(annotated_frame)
#             time.sleep(1 / fps)

#         out.release()
#         self.is_recording = False
#         if self.is_running:
#             self.videocapture_btn.config(state='normal')

#         self.status_var.set(f"Annotated video saved successfully as {filename}")
#         messagebox.showinfo("Video Capture", f"Video with annotations saved to {filename}")

#     def detection_loop(self):
#         """Main detection loop"""
#         while self.is_running:
#             try:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     time.sleep(0.01)
#                     continue

#                 frame = cv2.flip(frame, 1)  # mirror
#                 self.latest_frame = frame.copy()
#                 self.frame_count += 1

#                 if self.frame_count % 10 == 0:
#                     threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()

#                 time.sleep(0.033)  # ~30fps
#             except Exception:
#                 time.sleep(0.1)

#     def analyze_emotion(self, frame):
#         """Analyze emotions and auto-capture"""
#         try:
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             results = DeepFace.analyze(
#                 img_path=rgb_frame,
#                 actions=['emotion'],
#                 detector_backend='opencv',
#                 enforce_detection=False,
#                 silent=True
#             )
#             self.current_emotions = results if isinstance(results, list) else [results]

#             current_time = time.time()
#             if current_time - self.last_capture_time >= self.capture_cooldown:
#                 for emotion_data in self.current_emotions:
#                     try:
#                         emotion = emotion_data['dominant_emotion']
#                         confidence = emotion_data['emotion'][emotion]
#                         if confidence > 60:
#                             self.capture_emotion(emotion_data, frame.copy())
#                             self.last_capture_time = current_time
#                             break
#                     except Exception:
#                         continue
#         except Exception:
#             pass

#     def upload_image(self):
#         """Upload and analyze a single image file."""
#         if self.is_running:
#             self.stop_detection()

#         filepath = filedialog.askopenfilename(
#             title="Select an Image",
#             filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
#         )
#         if not filepath:
#             return

#         try:
#             self.status_var.set(f"Analyzing image: {os.path.basename(filepath)}...")
#             self.root.update_idletasks()

#             img = cv2.imread(filepath)
#             if img is None:
#                 messagebox.showerror("Error", "Could not load the image file.")
#                 return

#             results = DeepFace.analyze(img_path=img, actions=['emotion'], enforce_detection=False, silent=True)

#             summary = ""
#             faces = results if isinstance(results, list) else [results]
#             for i, face in enumerate(faces):
#                 region = face['region']
#                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                 emotion = face['dominant_emotion']
#                 confidence = face['emotion'][emotion]

#                 color = self.get_emotion_color(emotion)
#                 cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
#                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                 cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

#                 summary += f"Face {i+1}: {emotion.capitalize()} ({confidence:.1f}%)\n"

#             self.display_image(img)
#             self.status_var.set("Image analysis complete.")
#             messagebox.showinfo("Image Analysis Results", summary if summary else "No faces detected in the image.")

#         except Exception as e:
#             self.status_var.set("Error during image analysis.")
#             messagebox.showerror("Analysis Error", f"Failed to analyze image: {e}")

#     def upload_video(self):
#         """Upload and process a video file frame by frame."""
#         if self.is_running:
#             self.stop_detection()

#         filepath = filedialog.askopenfilename(
#             title="Select a Video",
#             filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv")]
#         )
#         if not filepath:
#             return

#         self.is_running = True
#         self.cap = cv2.VideoCapture(filepath)

#         if not self.cap.isOpened():
#             messagebox.showerror("Error", "Could not open the video file.")
#             self.is_running = False
#             return

#         self.detection_status.set("Video playing...")
#         self.start_btn.config(text="Stop Video", command=self.stop_detection)
#         self.stop_btn.config(state='normal')

#         threading.Thread(target=self.process_video_frames, daemon=True).start()

#     def process_video_frames(self):
#         """Loop to process video frames for display and analysis."""
#         frame_skip = 5  # analyze every 5th frame to speed
#         frame_counter = 0

#         while self.is_running and self.cap.isOpened():
#             ret, frame = self.cap.read()
#             if not ret:
#                 break

#             self.latest_frame = frame.copy()

#             if frame_counter % frame_skip == 0:
#                 threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()

#             frame_counter += 1
#             time.sleep(1 / 30)  # ~30fps playback

#         self.stop_detection()

#     def display_image(self, frame):
#         """Display a single OpenCV frame in the UI."""
#         if frame is None or frame.size == 0:
#             return
#         try:
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             pil_image = Image.fromarray(rgb_frame)

#             label_w, label_h = self.camera_label.winfo_width(), self.camera_label.winfo_height()
#             if label_w > 1 and label_h > 1:
#                 pil_image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)

#             photo = ImageTk.PhotoImage(pil_image)
#             self.camera_label.configure(image=photo, text="")
#             self.camera_label.image = photo
#         except Exception as e:
#             print(f"Error displaying image: {e}")

#     def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
#         """Capture and save emotion detection with face cropping"""
#         try:
#             emotion = emotion_data['dominant_emotion']
#             confidence = emotion_data['emotion'][emotion]
#             timestamp = datetime.now()

#             region = emotion_data['region']
#             x, y, w, h = region['x'], region['y'], region['w'], region['h']

#             padding = 20
#             x1 = max(0, x - padding)
#             y1 = max(0, y - padding)
#             x2 = min(frame.shape[1], x + w + padding)
#             y2 = min(frame.shape[0], y + h + padding)
#             face_crop = frame[y1:y2, x1:x2]

#             color = self.get_emotion_color(emotion)
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#             label = f"{emotion.upper()}: {confidence:.1f}%"
#             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

#             snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
#             cv2.imwrite(snapshot_filename, frame)

#             face_filename = None
#             if os.path.exists("faces"):
#                 face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
#                 cv2.imwrite(face_filename, face_crop)

#             region_json = json.dumps({
#                 'x': x, 'y': y, 'w': w, 'h': h,
#                 'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
#             })

#             try:
#                 self.db_manager.save_detection(
#                     timestamp.isoformat(),
#                     emotion,
#                     confidence,
#                     snapshot_filename,
#                     face_filename,
#                     region_json,
#                     capture_type,
#                     "person1",
#                     self.session_id
#                 )
#                 print(f"Successfully saved detection: {emotion} {confidence:.1f}%")
#             except Exception as db_error:
#                 print(f"Database save error: {db_error}")

#             detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
#             if self.live_detections.size() > 20:
#                 self.root.after(0, lambda: self.live_detections.delete(tk.END))

#             self.root.after(0, lambda: self.status_var.set(
#                 f"Captured {emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
#             ))

#             self.root.after(1000, self.refresh_gallery)
#         except Exception as e:
#             print(f"Capture error: {e}")

#     def refresh_gallery(self):
#         """Refresh the face gallery with latest captures"""
#         try:
#             for widget in self.scrollable_gallery.winfo_children():
#                 widget.destroy()
#             self.face_thumbnails = []

#             detections = self.db_manager.get_detections(limit=50)
#             row, col = 0, 0
#             max_cols = 3

#             for detection in detections:
#                 timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         face_img = cv2.imread(face_crop_path)
#                         face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                         face_img = cv2.resize(face_img, (100, 100))

#                         pil_img = Image.fromarray(face_img)
#                         photo = ImageTk.PhotoImage(pil_img)

#                         thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
#                         thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

#                         face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
#                         face_label.pack(pady=5)
#                         face_label.image = photo  # keep ref

#                         dt = datetime.fromisoformat(timestamp)
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             confidence_float = 0.0

#                         tk.Label(thumb_frame, text=f"{emotion.upper()}: {confidence_float:.1f}%",
#                                  bg='#2c3e50', fg='white',
#                                  font=('Arial', 8, 'bold')).pack()
#                         tk.Label(thumb_frame, text=dt.strftime('%m/%d %H:%M'),
#                                  bg='#2c3e50', fg='#bdc3c7',
#                                  font=('Arial', 7)).pack()
#                         tk.Label(thumb_frame, text=f"[{capture_type.upper() if capture_type else 'AUTO'}]",
#                                  bg='#2c3e50', fg='#f39c12',
#                                  font=('Arial', 7)).pack()

#                         self.face_thumbnails.append({
#                             'frame': thumb_frame,
#                             'path': face_crop_path,
#                             'snapshot_path': snapshot_path,
#                             'data': detection
#                         })

#                         face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))

#                         col += 1
#                         if col >= max_cols:
#                             col = 0
#                             row += 1

#                     except Exception as e:
#                         print(f"Thumbnail error: {e}")
#                         continue

#             self.scrollable_gallery.update_idletasks()
#             self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))

#         except Exception as e:
#             print(f"Gallery refresh error: {e}")

#     def view_face_full(self, face_path):
#         """View face image in full size"""
#         try:
#             if os.path.exists(face_path):
#                 view_window = tk.Toplevel(self.root)
#                 view_window.title("Face View")
#                 view_window.configure(bg='#2c3e50')

#                 face_img = cv2.imread(face_path)
#                 face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

#                 h, w = face_img.shape[:2]
#                 max_size = 400
#                 if max(h, w) > max_size:
#                     scale = max_size / max(h, w)
#                     new_w, new_h = int(w * scale), int(h * scale)
#                     face_img = cv2.resize(face_img, (new_w, new_h))

#                 pil_img = Image.fromarray(face_img)
#                 photo = ImageTk.PhotoImage(pil_img)

#                 label = tk.Label(view_window, image=photo, bg='#2c3e50')
#                 label.pack(padx=20, pady=20)
#                 label.image = photo  # keep ref

#                 view_window.update_idletasks()
#                 x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
#                 y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
#                 view_window.geometry(f'+{x}+{y}')
#         except Exception as e:
#             messagebox.showerror("View Error", f"Cannot view face: {e}")

#     def view_face_image(self, event):
#         """Double-click on a history row"""
#         selection = self.detection_tree.selection()
#         if selection:
#             messagebox.showinfo("Info", "This feature requires linking tree items to the database. "
#                                         "For now, please find the face in the gallery tab.")

#     def view_selected_face(self):
#         messagebox.showinfo("Info", "Click on any face thumbnail to view it in full size.")

#     def update_display_loop(self):
#         """Update camera display with emotion overlays"""
#         while True:
#             try:
#                 if self.is_running and self.latest_frame is not None:
#                     frame = self.latest_frame.copy()
#                     if self.current_emotions:
#                         for emotion_data in self.current_emotions:
#                             try:
#                                 region = emotion_data['region']
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 emotion = emotion_data['dominant_emotion']
#                                 confidence = emotion_data['emotion'][emotion]
#                                 color = self.get_emotion_color(emotion)
#                                 cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#                                 cv2.putText(frame, f"{emotion.upper()}: {confidence:.1f}%",
#                                             (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                             except Exception:
#                                 continue
#                     self.display_image(frame)
#                 time.sleep(0.033)
#             except Exception:
#                 time.sleep(0.1)

#     def get_emotion_color(self, emotion):
#         """Get color for each emotion"""
#         colors = {
#             'happy': (0, 255, 0),      # Green
#             'sad': (255, 100, 100),    # Light Blue-ish
#             'angry': (0, 0, 255),      # Red (BGR)
#             'fear': (255, 0, 255),     # Magenta
#             'surprise': (0, 255, 255), # Yellow
#             'disgust': (128, 0, 128),  # Purple
#             'neutral': (128, 128, 128) # Gray
#         }
#         return colors.get(emotion.lower(), (255, 255, 255))

#     def apply_filters(self):
#         """Apply filters and refresh data"""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()

#             start_iso = f"{start_date}T00:00:00" if start_date else None
#             end_iso = f"{end_date}T23:59:59" if end_date else None

#             detections = self.db_manager.get_detections(start_iso, end_iso, emotion)

#             for item in self.detection_tree.get_children():
#                 self.detection_tree.delete(item)

#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection

#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     confidence_float = 0.0

#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%m/%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 self.detection_tree.insert('', 'end',
#                                            values=(formatted_time, emotion_name.upper(),
#                                                    f"{confidence_float:.1f}%", type_display))

#             self.status_var.set(f"Loaded {len(detections)} detections")

#             # Refresh gallery too
#             self.refresh_gallery()

#         except Exception as e:
#             messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")

#     def clear_filters(self):
#         """Clear all filters"""
#         self.start_date_entry.delete(0, tk.END)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
#         self.end_date_entry.delete(0, tk.END)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
#         self.emotion_filter.set("All")
#         self.apply_filters()

#     def export_csv(self):
#         """Export detections to CSV, embedding images as Base64 strings."""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()

#             start_iso = f"{start_date}T00:00:00" if start_date else None
#             end_iso = f"{end_date}T23:59:59" if end_date else None

#             detections = self.db_manager.get_detections(start_iso, end_iso, emotion)
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return

#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".csv",
#                 filetypes=[("CSV files", "*.csv")],
#                 initialfile=f"emotion_detections_base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#             )
#             if not filename:
#                 return

#             with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#                 writer = csv.writer(csvfile)
#                 writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Base64"])

#                 for detection in detections:
#                     timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection

#                     try:
#                         confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                         confidence_float = float(confidence_str)
#                     except (ValueError, TypeError):
#                         confidence_float = 0.0

#                     image_base64_string = "N/A"
#                     try:
#                         if snapshot_path and os.path.exists(snapshot_path):
#                             image = cv2.imread(snapshot_path)

#                             # Draw bounding box if region data available
#                             if image is not None and face_region:
#                                 region = json.loads(face_region)
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 color = self.get_emotion_color(emotion_name)
#                                 cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
#                                 label = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                                 cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

#                             _, buffer = cv2.imencode('.jpg', image)
#                             image_base64_string = base64.b64encode(buffer).decode('utf-8')
#                         else:
#                             image_base64_string = "Snapshot not found"
#                     except Exception as e:
#                         print(f"Could not process and encode image for {timestamp}: {e}")
#                         image_base64_string = "Error encoding image"

#                     writer.writerow([timestamp, emotion_name, f"{confidence_float:.1f}%", image_base64_string])

#             messagebox.showinfo("Export", f"Data and embedded images exported successfully to {filename}")

#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")

#     def export_pdf(self):
#         """Export detections to PDF report with embedded images."""
#         try:
#             from reportlab.lib.pagesizes import A4
#             from reportlab.pdfgen import canvas
#             from reportlab.lib.units import inch
#         except ImportError:
#             messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
#             return

#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()

#             start_iso = f"{start_date}T00:00:00" if start_date else None
#             end_iso = f"{end_date}T23:59:59" if end_date else None

#             detections = self.db_manager.get_detections(start_iso, end_iso, emotion)
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return

#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".pdf",
#                 filetypes=[("PDF files", "*.pdf")],
#                 initialfile=f"emotion_report_with_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#             )
#             if not filename:
#                 return

#             c = canvas.Canvas(filename, pagesize=A4)
#             width, height = A4

#             c.setFont("Helvetica-Bold", 20)
#             c.drawString(inch, height - inch, "Emotion Detection Report")

#             total = len(detections)
#             emotion_counts = Counter([d[1] for d in detections])
#             auto_count = sum(1 for d in detections if d[6] == 'auto')
#             manual_count = sum(1 for d in detections if d[6] == 'manual')

#             y_pos = height - inch * 1.5
#             c.setFont("Helvetica-Bold", 12)
#             c.drawString(inch, y_pos, f"Total Detections: {total}")
#             c.drawString(inch, y_pos - 20, f"Auto Captures: {auto_count}")
#             c.drawString(inch, y_pos - 40, f"Manual Captures: {manual_count}")

#             c.setFont("Helvetica-Bold", 12)
#             c.drawString(inch * 4, y_pos, "Emotion Distribution:")
#             c.setFont("Helvetica", 10)
#             stat_y = y_pos - 20
#             for emotion_name, count in emotion_counts.most_common():
#                 percentage = (count / total) * 100 if total > 0 else 0
#                 c.drawString(inch * 4, stat_y, f"{emotion_name.upper()}: {count} ({percentage:.1f}%)")
#                 stat_y -= 15

#             # Detection list with images
#             y_pos -= 100
#             c.setFont("Helvetica-Bold", 14)
#             c.drawString(inch, y_pos, "Detection Log")
#             y_pos -= 30

#             for i, detection in enumerate(detections):
#                 if y_pos < inch * 2:
#                     c.showPage()
#                     y_pos = height - inch

#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection

#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     confidence_float = 0.0

#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'

#                 c.setFont("Helvetica", 9)
#                 text = f"{i+1}. {formatted_time} | {emotion_name.upper()} | {confidence_float:.1f}% | {type_display}"
#                 c.drawString(inch, y_pos, text)
#                 y_pos -= 15

#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         img_width = 1.5 * inch
#                         img_height = 1.5 * inch

#                         if y_pos < img_height + inch:
#                             c.showPage()
#                             y_pos = height - inch

#                         c.drawImage(face_crop_path, inch, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
#                         y_pos -= (img_height + 10)
#                     except Exception as e:
#                         c.drawString(inch + 5, y_pos, f"  (Error loading image: {e})")
#                         y_pos -= 15
#                 else:
#                     c.setFont("Helvetica-Oblique", 8)
#                     c.drawString(inch + 5, y_pos, "  (No face image available)")
#                     y_pos -= 15

#             c.save()
#             messagebox.showinfo("Export", f"Report with images exported successfully to {filename}")

#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")

#     def export_faces(self):
#         """Export face gallery as ZIP file"""
#         try:
#             import zipfile

#             if not os.path.exists("faces"):
#                 messagebox.showinfo("Export", "No faces folder found")
#                 return

#             face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
#             if not face_files:
#                 messagebox.showinfo("Export", "No face images to export")
#                 return

#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".zip",
#                 filetypes=[("ZIP files", "*.zip")],
#                 initialfile=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
#             )
#             if not filename:
#                 return

#             with zipfile.ZipFile(filename, 'w') as zipf:
#                 for face_file in face_files:
#                     face_path = os.path.join("faces", face_file)
#                     zipf.write(face_path, face_file)

#             messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")

#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")

#     def run(self):
#         """Run the application"""
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
#         self.root.mainloop()

#     def on_closing(self):
#         """Handle application closing"""
#         if self.is_running:
#             self.stop_detection()
#         self.root.destroy()


# # -------------------- Main Application Entry Point --------------------
# def main():
#     """Main application entry point"""
#     print("Starting Enhanced Emotion Detection System with Database Migration...")

#     # Initialize database with migration
#     db_manager = DatabaseManager()

#     # Show login window
#     login_window = LoginWindow(db_manager)
#     success, username = login_window.show()

#     if success:
#         print(f"Login successful for user: {username}")
#         app = EmotionDetectionSystem(username)
#         app.run()
#     else:
#         print("Login cancelled or failed")


# if __name__ == "__main__":
#     main()







































# # """
# # Complete Emotion Detection System with Image/Video Upload and Analysis
# # Install:
# #   pip install deepface opencv-python tensorflow pillow reportlab matplotlib
# #
# # Features:
# # - Secure admin authentication
# # - Real-time emotion detection from webcam
# # - Capture short video clips with emotion annotations
# # - Upload and analyze emotions from image files (JPG, PNG)
# # - Upload and analyze emotions from video files (MP4, AVI)
# # - Robust data handling and professional PDF/CSV exporting
# # - Automatic database migration for existing installations
# # - Graphs (Pie + Multi-line) are based on the CURRENT FACE GALLERY items
# # """

# import tkinter as tk
# from tkinter import ttk, messagebox, filedialog
# import cv2
# import numpy as np
# from deepface import DeepFace
# import threading
# import time
# from PIL import Image, ImageTk
# from collections import Counter
# import sqlite3
# import os
# import csv
# import hashlib
# import secrets
# from datetime import datetime, timedelta
# import json
# import base64

# # Charts
# from matplotlib.figure import Figure
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# # -------------------- Password Security --------------------
# def hash_password(password: str, iterations: int = 200_000) -> str:
#     """Hash password using PBKDF2"""
#     salt = secrets.token_bytes(16)
#     dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#     return f"{iterations}${salt.hex()}${dk.hex()}"

# def verify_password(password: str, stored: str) -> bool:
#     """Verify password against stored hash"""
#     try:
#         iterations_s, salt_hex, hash_hex = stored.split("$")
#         iterations = int(iterations_s)
#         salt = bytes.fromhex(salt_hex)
#         target = bytes.fromhex(hash_hex)
#         dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#         return secrets.compare_digest(dk, target)
#     except Exception:
#         return False

# # -------------------- Database Manager with Migration --------------------
# class DatabaseManager:
#     def __init__(self, db_path="emotion_system.db"):
#         self.db_path = db_path
#         self.init_database()
#         self.migrate_database()  # Add migration step
    
#     def init_database(self):
#         """Initialize database with required tables"""
#         os.makedirs("snapshots", exist_ok=True)
#         os.makedirs("faces", exist_ok=True)   # New folder for cropped faces
#         os.makedirs("videos", exist_ok=True)  # New folder for video captures

#         conn = sqlite3.connect(self.db_path)
        
#         # Users table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY,
#                 username TEXT UNIQUE NOT NULL,
#                 password_hash TEXT NOT NULL,
#                 role TEXT DEFAULT 'admin',
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Detections table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS detections (
#                 id INTEGER PRIMARY KEY,
#                 timestamp TEXT NOT NULL,
#                 emotion TEXT NOT NULL,
#                 confidence REAL NOT NULL,
#                 snapshot_path TEXT NOT NULL,
#                 face_crop_path TEXT,
#                 face_region TEXT,
#                 capture_type TEXT DEFAULT 'auto',
#                 person_id TEXT,
#                 session_id TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Create indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")
        
#         # Create default admin user if none exists
#         cursor = conn.execute("SELECT COUNT(*) FROM users")
#         if cursor.fetchone()[0] == 0:
#             admin_hash = hash_password("admin123")
#             conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#                         ("admin", admin_hash, "admin"))
        
#         conn.commit()
#         conn.close()
    
#     def migrate_database(self):
#         """Migrate existing database to add new columns if missing"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
        
#         try:
#             cursor.execute("PRAGMA table_info(detections)")
#             columns = [column[1] for column in cursor.fetchall()]
            
#             if 'face_crop_path' not in columns:
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")
#             if 'face_region' not in columns:
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")
#             if 'capture_type' not in columns:
#                 cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")
                
#             conn.commit()
#         except Exception as e:
#             print(f"Migration note: {e}")
#         finally:
#             conn.close()
    
#     def verify_user(self, username: str, password: str) -> bool:
#         """Verify user credentials"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
#         result = cursor.fetchone()
#         conn.close()
#         if result:
#             return verify_password(password, result[0])
#         return False
    
#     def save_detection(self, timestamp: str, emotion: str, confidence: float, 
#                        snapshot_path: str, face_crop_path: str = None, face_region: str = None,
#                        capture_type: str = 'auto', person_id: str = None, session_id: str = None):
#         """Save detection to database"""
#         conn = sqlite3.connect(self.db_path)
#         try:
#             conn.execute("""
#                 INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
#                                         face_region, capture_type, person_id, session_id)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, 
#                   capture_type, person_id, session_id))
#             conn.commit()
#         except sqlite3.OperationalError as e:
#             print(f"Database error, trying fallback: {e}")
#             try:
#                 conn.execute("""
#                     INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
#                 conn.commit()
#             except Exception as fallback_error:
#                 print(f"Fallback failed: {fallback_error}")
#         finally:
#             conn.close()
    
#     def get_detections(self, start_date=None, end_date=None, emotion=None, limit=1000):
#         """Get filtered detections from database"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
#         cursor.execute("PRAGMA table_info(detections)")
#         columns = [column[1] for column in cursor.fetchall()]
        
#         base_columns = "timestamp, emotion, confidence, snapshot_path"
#         base_columns += ", face_crop_path" if 'face_crop_path' in columns else ", NULL as face_crop_path"
#         base_columns += ", face_region" if 'face_region' in columns else ", NULL as face_region"
#         base_columns += ", capture_type" if 'capture_type' in columns else ", 'auto' as capture_type"
#         base_columns += ", person_id"
        
#         query = f"SELECT {base_columns} FROM detections WHERE 1=1"
#         params = []
#         if start_date:
#             query += " AND timestamp >= ?"
#             params.append(start_date)
#         if end_date:
#             query += " AND timestamp <= ?"
#             params.append(end_date)
#         if emotion and emotion.lower() != "all":
#             query += " AND emotion = ?"
#             params.append(emotion.lower())
        
#         query += " ORDER BY timestamp DESC LIMIT ?"
#         params.append(limit)
        
#         rows = conn.execute(query, params).fetchall()
#         conn.close()
#         return rows

# # -------------------- Enhanced Login Window --------------------
# class LoginWindow:
#     def __init__(self, db_manager):
#         self.db_manager = db_manager
#         self.success = False
#         self.username = None
        
#         self.root = tk.Tk()
#         self.root.title("Emotion Detection System - Admin Login")
#         self.root.geometry("500x400")
#         self.root.configure(bg='#2c3e50')
#         self.root.resizable(False, False)
#         self.root.eval('tk::PlaceWindow . center')
#         self.setup_ui()
    
#     def setup_ui(self):
#         main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
#         main_frame.pack(fill='both', expand=True)
        
#         title_label = tk.Label(main_frame, text="Admin Login", 
#                                font=('Arial', 24, 'bold'), bg='#2c3e50', fg='white')
#         title_label.pack(pady=(0, 15))
        
#         form_frame = tk.Frame(main_frame, bg='#2c3e50')
#         form_frame.pack(fill='x')
        
#         tk.Label(form_frame, text="Username:", font=('Arial', 12), 
#                  bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
#         self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
#                                        bg='#34495e', fg='white', insertbackground='white',
#                                        relief='flat', bd=5)
#         self.username_entry.pack(fill='x', pady=(0, 15))
#         self.username_entry.insert(0, "admin")
        
#         tk.Label(form_frame, text="Password:", font=('Arial', 12), 
#                  bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
#         self.password_entry = tk.Entry(form_frame, font=('Arial', 12), 
#                                        show="\u2022", bg='#34495e', fg='white',
#                                        insertbackground='white', relief='flat', bd=5)
#         self.password_entry.pack(fill='x', pady=(0, 10))
#         self.password_entry.bind('<KeyRelease>', self.update_password_feedback)
        
#         toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
#         toggle_frame.pack(fill='x', pady=(5, 10))
#         self.show_password_var = tk.BooleanVar()
#         tk.Checkbutton(toggle_frame, text="Show Password", variable=self.show_password_var,
#                        command=self.toggle_password_visibility, bg='#2c3e50', fg='#bdc3c7',
#                        selectcolor='#2c3e50', font=('Arial', 10)).pack(side='left')
#         self.password_length_label = tk.Label(toggle_frame, text="Characters: 0",
#                                               font=('Arial', 9), bg='#2c3e50', fg='#7f8c8d')
#         self.password_length_label.pack(side='right')
        
#         info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
#         info_frame.pack(fill='x', pady=(0, 20))
#         tk.Label(info_frame, text="Default: admin / admin123",
#                  font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)
        
#         button_frame = tk.Frame(form_frame, bg='#2c3e50')
#         button_frame.pack(fill='x', pady=(10, 0))
#         tk.Button(button_frame, text="Login", command=self.login,
#                   bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
#                   padx=30, pady=10, relief='flat').pack(side='left', padx=(0, 10))
#         tk.Button(button_frame, text="Cancel", command=self.cancel,
#                   bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'),
#                   padx=30, pady=10, relief='flat').pack(side='left')
        
#         self.root.bind('<Return>', lambda e: self.login())
#         self.password_entry.focus()
    
#     def toggle_password_visibility(self):
#         self.password_entry.config(show="" if self.show_password_var.get() else "\u2022")
    
#     def update_password_feedback(self, event=None):
#         self.password_length_label.config(text=f"Characters: {len(self.password_entry.get())}")
    
#     def login(self):
#         username = self.username_entry.get().strip()
#         password = self.password_entry.get()
#         if not username or not password:
#             messagebox.showerror("Error", "Please enter both username and password")
#             return
#         if self.db_manager.verify_user(username, password):
#             self.success = True
#             self.username = username
#             self.root.destroy()
#         else:
#             messagebox.showerror("Login Failed", "Invalid username or password")
#             self.password_entry.delete(0, tk.END)
#             self.password_entry.focus()
#             self.password_length_label.config(text="Characters: 0")
    
#     def cancel(self):
#         self.root.destroy()
    
#     def show(self):
#         self.root.mainloop()
#         return self.success, self.username

# # -------------------- Main Application --------------------
# class EmotionDetectionSystem:
#     def __init__(self, username):
#         self.username = username
#         self.db_manager = DatabaseManager()
#         self.session_id = f"session_{int(time.time())}"
        
#         # Core variables
#         self.cap = None
#         self.is_running = False
#         self.is_recording = False
#         self.current_emotions = []
#         self.latest_frame = None
#         self.frame_count = 0
#         self.start_time = time.time()
#         self.last_capture_time = 0
#         self.capture_cooldown = 3.0  # seconds between auto-captures
        
#         # Setup main window
#         self.root = tk.Tk()
#         self.root.title(f"Emotion Detection System - Welcome {username}")
#         self.root.geometry("1500x950")
#         self.root.configure(bg='#2c3e50')
        
#         self.setup_ui()
#         self.start_display_thread()
        
#         # Load initial data
#         self.apply_filters()
    
#     def setup_ui(self):
#         # Header
#         header = tk.Frame(self.root, bg='#2c3e50', height=70)
#         header.pack(fill='x', padx=15, pady=10)
#         header.pack_propagate(False)
        
#         # Title and user info
#         title_frame = tk.Frame(header, bg='#2c3e50')
#         title_frame.pack(side='left', fill='y', padx=(0, 20))
#         tk.Label(title_frame, text="Emotion Detection System", 
#                  font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
#         tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}", 
#                  font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')
        
#         # Controls
#         controls = tk.Frame(header, bg='#2c3e50')
#         controls.pack(side='right', fill='y')
#         button_font = ('Arial', 11, 'bold')
#         button_padx, button_pady, pack_padx = 15, 10, 4

#         # Start / Stop Webcam buttons
#         self.start_btn = tk.Button(controls, text="Start Webcam", command=self.start_detection,
#                                    bg='#27ae60', fg='white', font=button_font,
#                                    padx=button_padx, pady=button_pady, relief='flat')
#         self.start_btn.pack(side='left', padx=pack_padx)

#         self.stop_btn = tk.Button(controls, text="Stop Webcam", command=self.stop_detection,
#                                   bg='#e74c3c', fg='white', font=button_font,
#                                   padx=button_padx, pady=button_pady, relief='flat', state='disabled')
#         self.stop_btn.pack(side='left', padx=pack_padx)
        
#         # Capture Face
#         self.capture_btn = tk.Button(controls, text="Capture Face", command=self.manual_capture,
#                                      bg='#f39c12', fg='white', font=button_font,
#                                      padx=button_padx, pady=button_pady, relief='flat', state='disabled')
#         self.capture_btn.pack(side='left', padx=pack_padx)

#         # Capture Video
#         self.videocapture_btn = tk.Button(controls, text="Capture Video", command=self.manual_video_capture,
#                                           bg='#3498db', fg='white', font=button_font,
#                                           padx=button_padx, pady=button_pady, relief='flat', state='disabled')
#         self.videocapture_btn.pack(side='left', padx=pack_padx)
        
#         # Uploads
#         tk.Button(controls, text="Upload Image", command=self.upload_image,
#                   bg='#5dade2', fg='white', font=button_font,
#                   padx=button_padx, pady=button_pady, relief='flat').pack(side='left', padx=pack_padx)
#         tk.Button(controls, text="Upload Video", command=self.upload_video,
#                   bg='#8e44ad', fg='white', font=button_font,
#                   padx=button_padx, pady=button_pady, relief='flat').pack(side='left', padx=pack_padx)
        
#         # Main content
#         main_frame = tk.Frame(self.root, bg='#2c3e50')
#         main_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
#         # Left side - Camera and real-time detection
#         left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
#         left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
#         # Camera header
#         camera_header = tk.Frame(left_frame, bg='#34495e')
#         camera_header.pack(fill='x', pady=10)
#         tk.Label(camera_header, text="Live Feed / Uploaded Media", bg='#34495e', fg='white', 
#                  font=('Arial', 16, 'bold')).pack(side='left', padx=15)
#         self.detection_status = tk.StringVar(value="Idle")
#         tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12', 
#                  font=('Arial', 12, 'bold')).pack(side='right', padx=15)
        
#         # Camera display
#         self.camera_label = tk.Label(left_frame, text="Feed will appear here\n\nStart Webcam or Upload a File",
#                                      bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
#                                      width=70, height=20)
#         self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)
        
#         # Real-time detections list
#         rt_frame = tk.Frame(left_frame, bg='#34495e')
#         rt_frame.pack(fill='x', padx=15, pady=(0, 15))
#         tk.Label(rt_frame, text="Recent Detections", bg='#34495e', fg='white',
#                  font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
#         self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
#                                           font=('Consolas', 10), relief='flat')
#         self.live_detections.pack(fill='x')
        
#         # Right side - Dashboard
#         right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
#         right_frame.pack(side='right', fill='y')
#         right_frame.pack_propagate(False)
        
#         notebook = ttk.Notebook(right_frame)
#         notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Filters tab
#         filters_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(filters_frame, text="Filters & History")
#         self.setup_filters_tab(filters_frame)
        
#         # Face Gallery tab
#         gallery_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(gallery_frame, text="Face Gallery")
#         self.setup_gallery_tab(gallery_frame)
        
#         # Export tab
#         export_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(export_frame, text="Export")
#         self.setup_export_tab(export_frame)
        
#         # Status bar
#         status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
#         status_frame.pack(fill='x', padx=15, pady=5)
#         self.status_var = tk.StringVar(value="Ready")
#         tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
#                  font=('Arial', 10)).pack(side='left', pady=5)
    
#     def setup_filters_tab(self, parent):
#         tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
#         self.start_date_entry = tk.Entry(parent, width=30)
#         self.start_date_entry.pack(padx=10, pady=5)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.end_date_entry = tk.Entry(parent, width=30)
#         self.end_date_entry.pack(padx=10, pady=5)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.emotion_filter = ttk.Combobox(parent, values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"], 
#                                            state="readonly", width=27)
#         self.emotion_filter.pack(padx=10, pady=5)
#         self.emotion_filter.set("All")
        
#         btn_frame = tk.Frame(parent, bg='#34495e')
#         btn_frame.pack(fill='x', padx=10, pady=10)
#         tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
#                   bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
#                   bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left')
        
#         # Detection history
#         history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         history_frame.pack(fill='both', expand=True, padx=10, pady=10)
#         columns = ("Time", "Emotion", "Confidence", "Type")
#         self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
#         self.detection_tree.heading("Time", text="Timestamp")
#         self.detection_tree.heading("Emotion", text="Emotion")
#         self.detection_tree.heading("Confidence", text="Confidence")
#         self.detection_tree.heading("Type", text="Capture")
#         self.detection_tree.column("Time", width=120)
#         self.detection_tree.column("Emotion", width=80)
#         self.detection_tree.column("Confidence", width=80)
#         self.detection_tree.column("Type", width=60)
#         tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
#         self.detection_tree.configure(yscrollcommand=tree_scroll.set)
#         self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
#         tree_scroll.pack(side='right', fill='y', pady=10)
#         self.detection_tree.bind('<Double-1>', self.view_face_image)
    
#     def setup_gallery_tab(self, parent):
#         gallery_controls = tk.Frame(parent, bg='#34495e')
#         gallery_controls.pack(fill='x', padx=10, pady=10)
#         tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
#                   bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
#                   bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left')
        
#         gallery_frame = tk.Frame(parent, bg='#34495e')
#         gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)
#         self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
#         gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
#         self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')
#         self.scrollable_gallery.bind("<Configure>", lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
#         self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
#         self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
#         self.gallery_canvas.pack(side="left", fill="both", expand=True)
#         gallery_scrollbar.pack(side="right", fill="y")
#         self.face_thumbnails = []   # list of {"data": detection_tuple, ...}
    
#     def setup_export_tab(self, parent):
#         export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         export_frame.pack(fill='x', padx=10, pady=10)
#         tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
#                   bg='#16a085', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
#         tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
#                   bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
#         tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
#                   bg='#e67e22', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
#         # Graphs button — now driven by FACE GALLERY items
#         tk.Button(export_frame, text="Show Graphs (Pie + Line)", command=self.show_graphs,
#                   bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

#     # -------------------- Graphs (Pie + Multi-line Trend) --------------------
#     def show_graphs(self):
#         """Pie + Multi-line charts based ONLY on the currently displayed Face Gallery items."""
#         try:
#             # Build detections from the current thumbnails (what the user actually sees)
#             detections = [item['data'] for item in self.face_thumbnails]
#             if not detections:
#                 messagebox.showinfo("Graphs", "No items in the Face Gallery to chart.")
#                 return

#             from collections import Counter, defaultdict

#             # Pie: overall distribution across emotions (from gallery list)
#             emotion_counts = Counter([d[1] for d in detections])  # d[1] = emotion

#             # Time-series: per emotion per time bucket (from gallery list)
#             timestamps = []
#             for d in detections:
#                 try:
#                     timestamps.append(datetime.fromisoformat(d[0]))  # d[0] = timestamp
#                 except Exception:
#                     continue
#             if not timestamps:
#                 messagebox.showinfo("Graphs", "No valid timestamps in the Face Gallery.")
#                 return

#             min_dt, max_dt = min(timestamps), max(timestamps)
#             delta_days = (max_dt.date() - min_dt.date()).days
#             group_by_hour = delta_days <= 2  # if small range, group by hour

#             def bucket_key(dt: datetime) -> datetime:
#                 if group_by_hour:
#                     return dt.replace(minute=0, second=0, microsecond=0)
#                 return datetime(dt.year, dt.month, dt.day)

#             per_emotion_counts = defaultdict(Counter)  # emotion -> Counter(bucket -> count)
#             for ts, emo, *_ in detections:
#                 try:
#                     dt = datetime.fromisoformat(ts)
#                 except Exception:
#                     continue
#                 per_emotion_counts[emo][bucket_key(dt)] += 1

#             all_buckets = sorted({b for c in per_emotion_counts.values() for b in c.keys()})
#             if not all_buckets:
#                 messagebox.showinfo("Graphs", "No time buckets to plot.")
#                 return

#             x_labels = [b.strftime("%Y-%m-%d %H:00") if group_by_hour else b.strftime("%Y-%m-%d")
#                         for b in all_buckets]
#             emotions = sorted(per_emotion_counts.keys())
#             y_by_emotion = {
#                 emo: [per_emotion_counts[emo].get(b, 0) for b in all_buckets]
#                 for emo in emotions
#             }

#             # -------- UI Window --------
#             win = tk.Toplevel(self.root)
#             win.title("Emotion Analytics")
#             win.configure(bg='#2c3e50')

#             top_frame = tk.Frame(win, bg='#2c3e50')
#             top_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
#             bottom_frame = tk.Frame(win, bg='#2c3e50')
#             bottom_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

#             # -------- Pie Chart --------
#             fig_pie = Figure(figsize=(4.8, 4.0), dpi=100)
#             ax_pie = fig_pie.add_subplot(111)
#             labels = list(emotion_counts.keys())
#             sizes = [emotion_counts[k] for k in labels]
#             if sum(sizes) == 0:
#                 labels, sizes = ["No Data"], [1]
#             ax_pie.pie(sizes, labels=[s.upper() for s in labels], autopct='%1.1f%%', startangle=90)
#             ax_pie.set_title("Emotion Distribution (Face Gallery)", fontsize=12)
#             ax_pie.axis('equal')
#             canvas_pie = FigureCanvasTkAgg(fig_pie, master=top_frame)
#             canvas_pie.draw()
#             canvas_pie.get_tk_widget().pack(fill='both', expand=True)

#             # -------- Multi-line Chart --------
#             fig_line = Figure(figsize=(7.2, 3.8), dpi=100)
#             ax_line = fig_line.add_subplot(111)
#             for emo in emotions:
#                 ax_line.plot(x_labels, y_by_emotion[emo], marker='o', label=emo.upper())
#             ax_line.set_title("Detections per Emotion Over Time (Face Gallery)", fontsize=12)
#             ax_line.set_xlabel("Time" if group_by_hour else "Date")
#             ax_line.set_ylabel("Detections")
#             ax_line.grid(True, linestyle='--', alpha=0.3)
#             if len(x_labels) > 6:
#                 for label in ax_line.get_xticklabels():
#                     label.set_rotation(30)
#                     label.set_horizontalalignment('right')
#             ax_line.legend(loc='upper left', ncol=2, fontsize=8)
#             canvas_line = FigureCanvasTkAgg(fig_line, master=bottom_frame)
#             canvas_line.draw()
#             canvas_line.get_tk_widget().pack(fill='both', expand=True)

#             # Center the window roughly
#             win.update_idletasks()
#             x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
#             y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
#             win.geometry(f'+{x}+{y}')

#         except Exception as e:
#             messagebox.showerror("Graphs Error", f"Could not render graphs: {e}")

#     # -------------------- Capture / Display / Analysis --------------------
#     def start_display_thread(self):
#         self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
#         self.display_thread.start()
    
#     def start_detection(self):
#         """Start webcam and emotion detection"""
#         if self.is_running:
#             self.stop_detection()
#         try:
#             # Try different camera indices
#             self.cap = None
#             for camera_idx in [0, 1, 2]:
#                 cap = cv2.VideoCapture(camera_idx)
#                 if cap.isOpened():
#                     self.cap = cap
#                     break
#                 cap.release()
#             if not self.cap or not self.cap.isOpened():
#                 messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
#                 return
            
#             self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
#             self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
#             self.cap.set(cv2.CAP_PROP_FPS, 30)
            
#             self.is_running = True
#             self.start_time = time.time()
#             self.frame_count = 0
            
#             # UI states
#             self.start_btn.config(state='disabled')
#             self.stop_btn.config(state='normal')
#             self.capture_btn.config(state='normal')
#             self.videocapture_btn.config(state='normal')
#             self.detection_status.set("Webcam running...")
#             self.status_var.set("Webcam started - Auto-capturing emotions every 3 seconds")
            
#             threading.Thread(target=self.detection_loop, daemon=True).start()
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
    
#     def stop_detection(self):
#         """Stop any detection (webcam or uploaded video)"""
#         self.is_running = False
#         if self.cap:
#             try:
#                 self.cap.release()
#             except Exception:
#                 pass
#             self.cap = None
        
#         # UI states
#         self.start_btn.config(state='normal')
#         self.stop_btn.config(state='disabled')
#         self.capture_btn.config(state='disabled')
#         self.videocapture_btn.config(state='disabled')
#         self.detection_status.set("Idle")
#         self.camera_label.config(image="", text="Feed will appear here\n\nStart Webcam or Upload a File")
#         self.status_var.set("Ready")
    
#     def manual_capture(self):
#         """Manually capture current frame with all detected faces"""
#         if not self.is_running or self.latest_frame is None:
#             messagebox.showwarning("Capture Error", "Please start detection first")
#             return
#         try:
#             frame = self.latest_frame.copy()
#             if self.current_emotions:
#                 for i, emotion_data in enumerate(self.current_emotions):
#                     self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
#                 self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
#             else:
#                 messagebox.showinfo("Capture Info", "No faces detected in current frame")
#         except Exception as e:
#             messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")

#     def manual_video_capture(self):
#         """Start a 5-second recording with emotion overlays"""
#         if not self.is_running:
#             messagebox.showwarning("Video Capture Error", "Please start the webcam first.")
#             return
#         if self.is_recording:
#             messagebox.showwarning("Video Capture Error", "A recording is already in progress.")
#             return
#         threading.Thread(target=self._record_video_thread, daemon=True).start()

#     def _record_video_thread(self):
#         self.is_recording = True
#         self.videocapture_btn.config(state='disabled')
#         self.status_var.set("Recording video with annotations for 5 seconds...")
#         duration = 5
#         fps = 20.0
        
#         width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#         height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#         if width == 0 or height == 0:
#             self.status_var.set("Error: Invalid frame dimensions from camera.")
#             self.is_recording = False
#             self.videocapture_btn.config(state='normal')
#             messagebox.showerror("Recording Error", "Could not get valid frame dimensions.")
#             return

#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         filename = f"videos/capture_{timestamp}_annotated.mp4"
#         fourcc = cv2.VideoWriter_fourcc(*'avc1')
#         out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
#         if not out.isOpened():
#             self.status_var.set("Error: Could not open video writer.")
#             self.is_recording = False
#             self.videocapture_btn.config(state='normal')
#             messagebox.showerror("Recording Error", "Failed to initialize video recording.")
#             return

#         start_time = time.time()
#         while time.time() - start_time < duration:
#             if self.latest_frame is not None:
#                 annotated_frame = self.latest_frame.copy()
#                 if self.current_emotions:
#                     for emotion_data in self.current_emotions:
#                         try:
#                             region = emotion_data['region']
#                             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                             emotion = emotion_data['dominant_emotion']
#                             confidence = emotion_data['emotion'][emotion]
#                             color = self.get_emotion_color(emotion)
#                             cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 3)
#                             label = f"{emotion.upper()}: {confidence:.1f}%"
#                             cv2.putText(annotated_frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                         except Exception:
#                             continue
#                 out.write(annotated_frame)
#             time.sleep(1 / fps)
#         out.release()
#         self.is_recording = False
#         if self.is_running:
#             self.videocapture_btn.config(state='normal')
#         self.status_var.set(f"Annotated video saved successfully as {filename}")
#         messagebox.showinfo("Video Capture", f"Video with annotations saved to {filename}")
    
#     def detection_loop(self):
#         """Main detection loop for webcam"""
#         while self.is_running and self.cap:
#             try:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     time.sleep(0.01)
#                     continue
#                 frame = cv2.flip(frame, 1)
#                 self.latest_frame = frame.copy()
#                 self.frame_count += 1
#                 if self.frame_count % 10 == 0:
#                     threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
#                 time.sleep(0.033)  # ~30 FPS
#             except Exception:
#                 time.sleep(0.1)
    
#     def analyze_emotion(self, frame):
#         """Analyze emotions and auto-capture high-confidence faces"""
#         try:
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             results = DeepFace.analyze(
#                 img_path=rgb_frame,
#                 actions=['emotion'],
#                 detector_backend='opencv',
#                 enforce_detection=False,
#                 silent=True
#             )
#             self.current_emotions = results if isinstance(results, list) else [results]
#             current_time = time.time()
#             if current_time - self.last_capture_time >= self.capture_cooldown:
#                 for emotion_data in self.current_emotions:
#                     try:
#                         emotion = emotion_data['dominant_emotion']
#                         confidence = emotion_data['emotion'][emotion]
#                         if confidence > 60:
#                             self.capture_emotion(emotion_data, frame.copy())
#                             self.last_capture_time = current_time
#                             break
#                     except Exception:
#                         continue
#         except Exception:
#             pass
    
#     def upload_image(self):
#         """Upload and analyze a single image file."""
#         if self.is_running:
#             self.stop_detection()
#         filepath = filedialog.askopenfilename(
#             title="Select an Image",
#             filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
#         )
#         if not filepath:
#             return
#         try:
#             self.status_var.set(f"Analyzing image: {os.path.basename(filepath)}...")
#             self.root.update_idletasks()
#             img = cv2.imread(filepath)
#             if img is None:
#                 messagebox.showerror("Error", "Could not load the image file.")
#                 return

#             results = DeepFace.analyze(img_path=img, actions=['emotion'], enforce_detection=False, silent=True)
#             summary = ""
#             faces = results if isinstance(results, list) else [results]
#             for i, face in enumerate(faces):
#                 region = face['region']
#                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                 emotion = face['dominant_emotion']
#                 confidence = face['emotion'][emotion]
#                 color = self.get_emotion_color(emotion)
#                 cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
#                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                 cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                 summary += f"Face {i+1}: {emotion.capitalize()} ({confidence:.1f}%)\n"
#             self.display_image(img)
#             self.status_var.set("Image analysis complete.")
#             messagebox.showinfo("Image Analysis Results", summary if summary else "No faces detected in the image.")
#         except Exception as e:
#             self.status_var.set("Error during image analysis.")
#             messagebox.showerror("Analysis Error", f"Failed to analyze image: {e}")

#     def upload_video(self):
#         """Upload and process a video file frame by frame."""
#         if self.is_running:
#             self.stop_detection()
#         filepath = filedialog.askopenfilename(
#             title="Select a Video",
#             filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv")]
#         )
#         if not filepath:
#             return
#         self.cap = cv2.VideoCapture(filepath)
#         if not self.cap.isOpened():
#             messagebox.showerror("Error", "Could not open the video file.")
#             self.is_running = False
#             return

#         self.is_running = True
#         self.detection_status.set("Video playing...")
#         self.start_btn.config(state='disabled')
#         self.stop_btn.config(state='normal')
#         threading.Thread(target=self.process_video_frames, daemon=True).start()
        
#     def process_video_frames(self):
#         """Loop to process video frames for display and analysis."""
#         frame_skip = 5
#         frame_counter = 0
#         while self.is_running and self.cap and self.cap.isOpened():
#             ret, frame = self.cap.read()
#             if not ret:
#                 break
#             self.latest_frame = frame.copy()
#             if frame_counter % frame_skip == 0:
#                 threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
#             frame_counter += 1
#             time.sleep(1 / 30)
#         self.stop_detection()
    
#     def display_image(self, frame):
#         """Display a single OpenCV frame in the UI."""
#         if frame is None or frame.size == 0:
#             return
#         try:
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             pil_image = Image.fromarray(rgb_frame)
#             label_w, label_h = self.camera_label.winfo_width(), self.camera_label.winfo_height()
#             if label_w > 1 and label_h > 1:
#                 pil_image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
#             photo = ImageTk.PhotoImage(pil_image)
#             self.camera_label.configure(image=photo, text="")
#             self.camera_label.image = photo
#         except Exception as e:
#             print(f"Error displaying image: {e}")

#     def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
#         """Capture and save emotion detection with face cropping"""
#         try:
#             emotion = emotion_data['dominant_emotion']
#             confidence = emotion_data['emotion'][emotion]
#             timestamp = datetime.now()
#             region = emotion_data['region']
#             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#             padding = 20
#             x1 = max(0, x - padding)
#             y1 = max(0, y - padding)
#             x2 = min(frame.shape[1], x + w + padding)
#             y2 = min(frame.shape[0], y + h + padding)
#             face_crop = frame[y1:y2, x1:x2]
#             color = self.get_emotion_color(emotion)
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#             label = f"{emotion.upper()}: {confidence:.1f}%"
#             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#             snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
#             cv2.imwrite(snapshot_filename, frame)
#             face_filename = None
#             if os.path.exists("faces"):
#                 face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
#                 cv2.imwrite(face_filename, face_crop)
#             region_json = json.dumps({
#                 'x': x, 'y': y, 'w': w, 'h': h,
#                 'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
#             })
#             try:
#                 self.db_manager.save_detection(
#                     timestamp.isoformat(), emotion, confidence, snapshot_filename,
#                     face_filename, region_json, capture_type, "person1", self.session_id
#                 )
#             except Exception as db_error:
#                 print(f"Database save error: {db_error}")
#             detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
#             if self.live_detections.size() > 20:
#                 self.root.after(0, lambda: self.live_detections.delete(tk.END))
#             self.root.after(0, lambda: self.status_var.set(
#                 f"Captured {emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
#             ))
#             # Refresh gallery so it shows filtered items (and graphs will reflect it)
#             self.root.after(1000, self.refresh_gallery)
#         except Exception as e:
#             print(f"Capture error: {e}")
    
#     def refresh_gallery(self):
#         """Refresh the face gallery with latest captures (RESPECTS FILTERS)."""
#         try:
#             # Clear existing thumbnails
#             for widget in self.scrollable_gallery.winfo_children():
#                 widget.destroy()
#             self.face_thumbnails = []

#             # Use current filters to decide which detections the gallery shows
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             start_iso = f"{start_date}T00:00:00" if start_date else None
#             end_iso = f"{end_date}T23:59:59" if end_date else None

#             detections = self.db_manager.get_detections(start_iso, end_iso, emotion, limit=50)

#             # Display face thumbnails in grid
#             row, col, max_cols = 0, 0, 3
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         # Load and resize face image
#                         face_img = cv2.imread(face_crop_path)
#                         face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                         face_img = cv2.resize(face_img, (100, 100))
#                         pil_img = Image.fromarray(face_img)
#                         photo = ImageTk.PhotoImage(pil_img)

#                         # Create frame for each thumbnail
#                         thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
#                         thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

#                         face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
#                         face_label.pack(pady=5)
#                         face_label.image = photo  # Keep reference

#                         dt = datetime.fromisoformat(timestamp)

#                         # Robust confidence handling
#                         confidence_float = 0.0
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             pass

#                         emotion_text = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                         time_text = dt.strftime('%m/%d %H:%M')
#                         type_text = f"[{capture_type.upper() if capture_type else 'AUTO'}]"

#                         tk.Label(thumb_frame, text=emotion_text, bg='#2c3e50', fg='white',
#                                  font=('Arial', 8, 'bold')).pack()
#                         tk.Label(thumb_frame, text=time_text, bg='#2c3e50', fg='#bdc3c7',
#                                  font=('Arial', 7)).pack()
#                         tk.Label(thumb_frame, text=type_text, bg='#2c3e50', fg='#f39c12',
#                                  font=('Arial', 7)).pack()

#                         # Store reference for viewing + graphing
#                         self.face_thumbnails.append({
#                             'frame': thumb_frame,
#                             'path': face_crop_path,
#                             'snapshot_path': snapshot_path,
#                             'data': detection  # <--- used by show_graphs()
#                         })

#                         # Bind click to view larger
#                         face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))

#                         col += 1
#                         if col >= max_cols:
#                             col = 0
#                             row += 1
#                     except Exception as e:
#                         print(f"Thumbnail error: {e}")
#                         continue

#             self.scrollable_gallery.update_idletasks()
#             self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
#         except Exception as e:
#             print(f"Gallery refresh error: {e}")
    
#     def view_face_full(self, face_path):
#         """View face image in full size"""
#         try:
#             if os.path.exists(face_path):
#                 view_window = tk.Toplevel(self.root)
#                 view_window.title("Face View")
#                 view_window.configure(bg='#2c3e50')
#                 face_img = cv2.imread(face_path)
#                 face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                 h, w = face_img.shape[:2]
#                 max_size = 400
#                 if max(h, w) > max_size:
#                     scale = max_size / max(h, w)
#                     new_w, new_h = int(w * scale), int(h * scale)
#                     face_img = cv2.resize(face_img, (new_w, new_h))
#                 pil_img = Image.fromarray(face_img)
#                 photo = ImageTk.PhotoImage(pil_img)
#                 label = tk.Label(view_window, image=photo, bg='#2c3e50')
#                 label.pack(padx=20, pady=20)
#                 label.image = photo
#                 view_window.update_idletasks()
#                 x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
#                 y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
#                 view_window.geometry(f'+{x}+{y}')
#         except Exception as e:
#             messagebox.showerror("View Error", f"Cannot view face: {str(e)}")
    
#     def view_face_image(self, event):
#         """View face from detection tree double-click (placeholder)"""
#         selection = self.detection_tree.selection()
#         if selection:
#             messagebox.showinfo("Info", "This feature requires linking tree items to the database. Please use the Face Gallery tab for now.")
    
#     def view_selected_face(self):
#         messagebox.showinfo("Info", "Click on any face thumbnail to view it in full size.")
    
#     def update_display_loop(self):
#         """Continuously update live feed with overlays"""
#         while True:
#             try:
#                 if self.is_running and self.latest_frame is not None:
#                     frame = self.latest_frame.copy()
#                     if self.current_emotions:
#                         for emotion_data in self.current_emotions:
#                             try:
#                                 region = emotion_data['region']
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 emotion = emotion_data['dominant_emotion']
#                                 confidence = emotion_data['emotion'][emotion]
#                                 color = self.get_emotion_color(emotion)
#                                 cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#                                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                                 cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                             except Exception:
#                                 continue
#                     self.display_image(frame)
#                 time.sleep(0.033)
#             except Exception:
#                 time.sleep(0.1)
    
#     def get_emotion_color(self, emotion):
#         colors = {
#             'happy': (0, 255, 0),      # Green
#             'sad': (255, 100, 100),    # Light Blue
#             'angry': (0, 0, 255),      # Red
#             'fear': (255, 0, 255),     # Magenta
#             'surprise': (0, 255, 255), # Yellow
#             'disgust': (128, 0, 128),  # Purple
#             'neutral': (128, 128, 128) # Gray
#         }
#         return colors.get(emotion.lower(), (255, 255, 255))
    
#     def apply_filters(self):
#         """Apply filters and refresh data"""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
#             for item in self.detection_tree.get_children():
#                 self.detection_tree.delete(item)
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 confidence_float = 0.0
#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     pass
#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%m/%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 self.detection_tree.insert('', 'end', values=(formatted_time, emotion_name.upper(), f"{confidence_float:.1f}%", type_display))
#             self.status_var.set(f"Loaded {len(detections)} detections")
#             # Keep gallery in sync with the filters so graphs reflect exactly what is shown
#             self.refresh_gallery()
#         except Exception as e:
#             messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
    
#     def clear_filters(self):
#         self.start_date_entry.delete(0, tk.END)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
#         self.end_date_entry.delete(0, tk.END)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
#         self.emotion_filter.set("All")
#         self.apply_filters()
    
#     # -------------------- Exporting --------------------
#     def export_csv(self):
#         """Export detections to CSV with Base64-embedded snapshot images."""
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".csv",
#                 filetypes=[("CSV files", "*.csv")],
#                 initialfile=f"emotion_detections_base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#             )
#             if not filename:
#                 return
#             with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#                 writer = csv.writer(csvfile)
#                 writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Base64"])
#                 for detection in detections:
#                     timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                     image_base64_string = "N/A"
#                     confidence_float = 0.0
#                     try:
#                         confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                         confidence_float = float(confidence_str)
#                     except (ValueError, TypeError):
#                         pass
#                     try:
#                         if snapshot_path and os.path.exists(snapshot_path):
#                             image = cv2.imread(snapshot_path)
#                             if image is not None and face_region:
#                                 region = json.loads(face_region)
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 color = self.get_emotion_color(emotion_name)
#                                 cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
#                                 label = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                                 cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                             _, buffer = cv2.imencode('.jpg', image)
#                             image_base64_string = base64.b64encode(buffer).decode('utf-8')
#                         else:
#                             image_base64_string = "Snapshot not found"
#                     except Exception:
#                         image_base64_string = "Error encoding image"
#                     writer.writerow([timestamp, emotion_name, f"{confidence_float:.1f}%", image_base64_string])
#             messagebox.showinfo("Export", f"Data and embedded images exported successfully to {filename}")
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")
    
#     def export_pdf(self):
#         """Export detections to a PDF report with embedded face crops."""
#         try:
#             from reportlab.lib.pagesizes import A4
#             from reportlab.pdfgen import canvas
#             from reportlab.lib.units import inch
#         except ImportError:
#             messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
#             return
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".pdf",
#                 filetypes=[("PDF files", "*.pdf")],
#                 initialfile=f"emotion_report_with_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#             )
#             if not filename:
#                 return
#             c = canvas.Canvas(filename, pagesize=A4)
#             width, height = A4
#             c.setFont("Helvetica-Bold", 20)
#             c.drawString(inch, height - inch, "Emotion Detection Report")
#             total = len(detections)
#             emotion_counts = Counter([d[1] for d in detections])
#             auto_count = sum(1 for d in detections if d[6] == 'auto')
#             manual_count = sum(1 for d in detections if d[6] == 'manual')
#             y_pos = height - inch * 1.5
#             c.setFont("Helvetica-Bold", 12)
#             c.drawString(inch, y_pos, f"Total Detections: {total}")
#             c.drawString(inch, y_pos - 20, f"Auto Captures: {auto_count}")
#             c.drawString(inch, y_pos - 40, f"Manual Captures: {manual_count}")
#             c.setFont("Helvetica-Bold", 12)
#             c.drawString(inch * 4, y_pos, "Emotion Distribution:")
#             c.setFont("Helvetica", 10)
#             stat_y = y_pos - 20
#             for emotion_name, count in emotion_counts.most_common():
#                 percentage = (count / total) * 100 if total > 0 else 0
#                 c.drawString(inch * 4, stat_y, f"{emotion_name.upper()}: {count} ({percentage:.1f}%)")
#                 stat_y -= 15
#             y_pos -= 100
#             c.setFont("Helvetica-Bold", 14)
#             c.drawString(inch, y_pos, "Detection Log")
#             y_pos -= 30
#             for i, detection in enumerate(detections):
#                 if y_pos < inch * 2:
#                     c.showPage()
#                     y_pos = height - inch
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 confidence_float = 0.0
#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     pass
#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 c.setFont("Helvetica", 9)
#                 text = f"{i+1}. {formatted_time} | {emotion_name.upper()} | {confidence_float:.1f}% | {type_display}"
#                 c.drawString(inch, y_pos, text)
#                 y_pos -= 15
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         img_width = 1.5 * inch
#                         img_height = 1.5 * inch
#                         if y_pos < img_height + inch:
#                             c.showPage()
#                             y_pos = height - inch
#                         c.drawImage(face_crop_path, inch, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
#                         y_pos -= (img_height + 10)
#                     except Exception as e:
#                         c.drawString(inch + 5, y_pos, f"  (Error loading image: {e})")
#                         y_pos -= 15
#                 else:
#                     c.setFont("Helvetica-Oblique", 8)
#                     c.drawString(inch + 5, y_pos, "  (No face image available)")
#                     y_pos -= 15
#             c.save()
#             messagebox.showinfo("Export", f"Report with images exported successfully to {filename}")
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")
    
#     def export_faces(self):
#         """Export face gallery as ZIP file"""
#         try:
#             import zipfile
#             if not os.path.exists("faces"):
#                 messagebox.showinfo("Export", "No faces folder found")
#                 return
#             face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
#             if not face_files:
#                 messagebox.showinfo("Export", "No face images to export")
#                 return
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".zip",
#                 filetypes=[("ZIP files", "*.zip")],
#                 initialfile=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
#             )
#             if not filename:
#                 return
#             with zipfile.ZipFile(filename, 'w') as zipf:
#                 for face_file in face_files:
#                     face_path = os.path.join("faces", face_file)
#                     zipf.write(face_path, face_file)
#             messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")
    
#     def run(self):
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
#         self.root.mainloop()
    
#     def on_closing(self):
#         if self.is_running:
#             self.stop_detection()
#         self.root.destroy()

# # -------------------- Main Application Entry Point --------------------
# def main():
#     print("Starting Enhanced Emotion Detection System with Database Migration...")
#     db_manager = DatabaseManager()
#     login_window = LoginWindow(db_manager)
#     success, username = login_window.show()
#     if success:
#         print(f"Login successful for user: {username}")
#         app = EmotionDetectionSystem(username)
#         app.run()
#     else:
#         print("Login cancelled or failed")

# if __name__ == "__main__":
#     main()









































# """
# Complete Emotion Detection System with Image/Video Upload, Voice SER, and Analysis
# Install:
#   pip install deepface opencv-python tensorflow pillow reportlab matplotlib
#   pip install sounddevice webrtcvad transformers torch --upgrade
#
# Features:
# - Secure admin authentication
# - Real-time emotion detection from webcam
# - Capture short video clips with emotion annotations
# - Upload and analyze emotions from image files (JPG, PNG)
# - Upload and analyze emotions from video files (MP4, AVI)
# - Real-time voice emotion detection (VAD-gated) using HF transformers
# - Robust data handling and professional PDF/CSV exporting
# - Automatic database migration for existing installations
# - Graphs (Pie + Multi-line) are based on the CURRENT FACE GALLERY items
#   (Voice detections are logged to history but excluded from Face Gallery & graphs.)
# """

# import tkinter as tk
# from tkinter import ttk, messagebox, filedialog
# import cv2
# import numpy as np
# from deepface import DeepFace
# import threading
# import time
# from PIL import Image, ImageTk
# from collections import Counter
# import sqlite3
# import os
# import csv
# import hashlib
# import secrets
# from datetime import datetime, timedelta
# import json
# import base64
# import wave  # for saving voiced segments

# # Charts
# from matplotlib.figure import Figure
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# # -------------------- Password Security --------------------
# def hash_password(password: str, iterations: int = 200_000) -> str:
#     """Hash password using PBKDF2"""
#     salt = secrets.token_bytes(16)
#     dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#     return f"{iterations}${salt.hex()}${dk.hex()}"

# def verify_password(password: str, stored: str) -> bool:
#     """Verify password against stored hash"""
#     try:
#         iterations_s, salt_hex, hash_hex = stored.split("$")
#         iterations = int(iterations_s)
#         salt = bytes.fromhex(salt_hex)
#         target = bytes.fromhex(hash_hex)
#         dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
#         return secrets.compare_digest(dk, target)
#     except Exception:
#         return False

# # -------------------- Database Manager with Migration --------------------
# class DatabaseManager:
#     def __init__(self, db_path="emotion_system.db"):
#         self.db_path = db_path
#         self.init_database()
#         self.migrate_database()  # Add migration step
    
#     def init_database(self):
#         """Initialize database with required tables"""
#         os.makedirs("snapshots", exist_ok=True)
#         os.makedirs("faces", exist_ok=True)   # New folder for cropped faces
#         os.makedirs("videos", exist_ok=True)  # New folder for video captures
#         os.makedirs("audio", exist_ok=True)   # New folder for voice segments

#         conn = sqlite3.connect(self.db_path)
        
#         # Users table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS users (
#                 id INTEGER PRIMARY KEY,
#                 username TEXT UNIQUE NOT NULL,
#                 password_hash TEXT NOT NULL,
#                 role TEXT DEFAULT 'admin',
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Detections table
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS detections (
#                 id INTEGER PRIMARY KEY,
#                 timestamp TEXT NOT NULL,
#                 emotion TEXT NOT NULL,
#                 confidence REAL NOT NULL,
#                 snapshot_path TEXT NOT NULL,
#                 face_crop_path TEXT,
#                 face_region TEXT,
#                 capture_type TEXT DEFAULT 'auto',
#                 person_id TEXT,
#                 session_id TEXT,
#                 created_at TEXT DEFAULT CURRENT_TIMESTAMP
#             )
#         """)
        
#         # Create indexes
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
#         conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")
        
#         # Create default admin user if none exists
#         cursor = conn.execute("SELECT COUNT(*) FROM users")
#         if cursor.fetchone()[0] == 0:
#             admin_hash = hash_password("admin123")
#             conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
#                         ("admin", admin_hash, "admin"))
        
#         conn.commit()
#         conn.close()
    
#     def migrate_database(self):
#         """Migrate existing database to add new columns if missing"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
        
#         try:
#             cursor.execute("PRAGMA table_info(detections)")
#             columns = [column[1] for column in cursor.fetchall()]
            
#             if 'face_crop_path' not in columns:
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")
#             if 'face_region' not in columns:
#                 cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")
#             if 'capture_type' not in columns:
#                 cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")
                
#             conn.commit()
#         except Exception as e:
#             print(f"Migration note: {e}")
#         finally:
#             conn.close()
    
#     def verify_user(self, username: str, password: str) -> bool:
#         """Verify user credentials"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
#         result = cursor.fetchone()
#         conn.close()
#         if result:
#             return verify_password(password, result[0])
#         return False
    
#     def save_detection(self, timestamp: str, emotion: str, confidence: float, 
#                        snapshot_path: str, face_crop_path: str = None, face_region: str = None,
#                        capture_type: str = 'auto', person_id: str = None, session_id: str = None):
#         """Save detection to database"""
#         conn = sqlite3.connect(self.db_path)
#         try:
#             conn.execute("""
#                 INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
#                                         face_region, capture_type, person_id, session_id)
#                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
#             """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, 
#                   capture_type, person_id, session_id))
#             conn.commit()
#         except sqlite3.OperationalError as e:
#             print(f"Database error, trying fallback: {e}")
#             try:
#                 conn.execute("""
#                     INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
#                     VALUES (?, ?, ?, ?, ?, ?)
#                 """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
#                 conn.commit()
#             except Exception as fallback_error:
#                 print(f"Fallback failed: {fallback_error}")
#         finally:
#             conn.close()
    
#     def get_detections(self, start_date=None, end_date=None, emotion=None, limit=1000):
#         """Get filtered detections from database"""
#         conn = sqlite3.connect(self.db_path)
#         cursor = conn.cursor()
#         cursor.execute("PRAGMA table_info(detections)")
#         columns = [column[1] for column in cursor.fetchall()]
        
#         base_columns = "timestamp, emotion, confidence, snapshot_path"
#         base_columns += ", face_crop_path" if 'face_crop_path' in columns else ", NULL as face_crop_path"
#         base_columns += ", face_region" if 'face_region' in columns else ", NULL as face_region"
#         base_columns += ", capture_type" if 'capture_type' in columns else ", 'auto' as capture_type"
#         base_columns += ", person_id"
        
#         query = f"SELECT {base_columns} FROM detections WHERE 1=1"
#         params = []
#         if start_date:
#             query += " AND timestamp >= ?"
#             params.append(start_date)
#         if end_date:
#             query += " AND timestamp <= ?"
#             params.append(end_date)
#         if emotion and emotion.lower() != "all":
#             query += " AND emotion = ?"
#             params.append(emotion.lower())
        
#         query += " ORDER BY timestamp DESC LIMIT ?"
#         params.append(limit)
        
#         rows = conn.execute(query, params).fetchall()
#         conn.close()
#         return rows

# # -------------------- Enhanced Login Window --------------------
# class LoginWindow:
#     def __init__(self, db_manager):
#         self.db_manager = db_manager
#         self.success = False
#         self.username = None
        
#         self.root = tk.Tk()
#         self.root.title("Emotion Detection System - Admin Login")
#         self.root.geometry("500x400")
#         self.root.configure(bg='#2c3e50')
#         self.root.resizable(False, False)
#         self.root.eval('tk::PlaceWindow . center')
#         self.setup_ui()
    
#     def setup_ui(self):
#         main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
#         main_frame.pack(fill='both', expand=True)
        
#         title_label = tk.Label(main_frame, text="Admin Login", 
#                                font=('Arial', 24, 'bold'), bg='#2c3e50', fg='white')
#         title_label.pack(pady=(0, 15))
        
#         form_frame = tk.Frame(main_frame, bg='#2c3e50')
#         form_frame.pack(fill='x')
        
#         tk.Label(form_frame, text="Username:", font=('Arial', 12), 
#                  bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
#         self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
#                                        bg='#34495e', fg='white', insertbackground='white',
#                                        relief='flat', bd=5)
#         self.username_entry.pack(fill='x', pady=(0, 15))
#         self.username_entry.insert(0, "admin")
        
#         tk.Label(form_frame, text="Password:", font=('Arial', 12), 
#                  bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
#         self.password_entry = tk.Entry(form_frame, font=('Arial', 12), 
#                                        show="\u2022", bg='#34495e', fg='white',
#                                        insertbackground='white', relief='flat', bd=5)
#         self.password_entry.pack(fill='x', pady=(0, 10))
#         self.password_entry.bind('<KeyRelease>', self.update_password_feedback)
        
#         toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
#         toggle_frame.pack(fill='x', pady=(5, 10))
#         self.show_password_var = tk.BooleanVar()
#         tk.Checkbutton(toggle_frame, text="Show Password", variable=self.show_password_var,
#                        command=self.toggle_password_visibility, bg='#2c3e50', fg='#bdc3c7',
#                        selectcolor='#2c3e50', font=('Arial', 10)).pack(side='left')
#         self.password_length_label = tk.Label(toggle_frame, text="Characters: 0",
#                                               font=('Arial', 9), bg='#2c3e50', fg='#7f8c8d')
#         self.password_length_label.pack(side='right')
        
#         info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
#         info_frame.pack(fill='x', pady=(0, 20))
#         tk.Label(info_frame, text="Default: admin / admin123",
#                  font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)
        
#         button_frame = tk.Frame(form_frame, bg='#2c3e50')
#         button_frame.pack(fill='x', pady=(10, 0))
#         tk.Button(button_frame, text="Login", command=self.login,
#                   bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
#                   padx=30, pady=10, relief='flat').pack(side='left', padx=(0, 10))
#         tk.Button(button_frame, text="Cancel", command=self.cancel,
#                   bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'),
#                   padx=30, pady=10, relief='flat').pack(side='left')
        
#         self.root.bind('<Return>', lambda e: self.login())
#         self.password_entry.focus()
    
#     def toggle_password_visibility(self):
#         self.password_entry.config(show="" if self.show_password_var.get() else "\u2022")
    
#     def update_password_feedback(self, event=None):
#         self.password_length_label.config(text=f"Characters: {len(self.password_entry.get())}")
    
#     def login(self):
#         username = self.username_entry.get().strip()
#         password = self.password_entry.get()
#         if not username or not password:
#             messagebox.showerror("Error", "Please enter both username and password")
#             return
#         if self.db_manager.verify_user(username, password):
#             self.success = True
#             self.username = username
#             self.root.destroy()
#         else:
#             messagebox.showerror("Login Failed", "Invalid username or password")
#             self.password_entry.delete(0, tk.END)
#             self.password_entry.focus()
#             self.password_length_label.config(text="Characters: 0")
    
#     def cancel(self):
#         self.root.destroy()
    
#     def show(self):
#         self.root.mainloop()
#         return self.success, self.username

# # -------------------- Main Application --------------------
# class EmotionDetectionSystem:
#     def __init__(self, username):
#         self.username = username
#         self.db_manager = DatabaseManager()
#         self.session_id = f"session_{int(time.time())}"
        
#         # Core variables (vision)
#         self.cap = None
#         self.is_running = False
#         self.is_recording = False
#         self.current_emotions = []
#         self.latest_frame = None
#         self.frame_count = 0
#         self.start_time = time.time()
#         self.last_capture_time = 0
#         self.capture_cooldown = 3.0  # seconds between auto-captures

#         # Voice SER variables
#         self.voice_running = False
#         self.voice_thread = None
#         self.voice_status = "Idle"
#         self.voice_latest_text = ""   # e.g., "VOICE: HAPPY (82.0%)"
#         self.voice_list_max = 20

#         # Setup main window
#         self.root = tk.Tk()
#         self.root.title(f"Emotion Detection System - Welcome {username}")
#         self.root.geometry("1500x950")
#         self.root.configure(bg='#2c3e50')
        
#         self.setup_ui()
#         self.start_display_thread()
        
#         # Load initial data
#         self.apply_filters()

#     # ---------- VISUAL HELPERS ----------
#     def _shade(self, hex_color, factor=0.9):
#         hex_color = hex_color.lstrip('#')
#         r = int(hex_color[0:2], 16)
#         g = int(hex_color[2:4], 16)
#         b = int(hex_color[4:6], 16)
#         r = max(0, min(255, int(r * factor)))
#         g = max(0, min(255, int(g * factor)))
#         b = max(0, min(255, int(b * factor)))
#         return f"#{r:02x}{g:02x}{b:02x}"

#     def _add_hover(self, btn, base):
#         hover = self._shade(base, 1.08)
#         active = self._shade(base, 0.92)
#         def on_e(_): btn.configure(bg=hover)
#         def on_l(_): btn.configure(bg=base)
#         def on_p(_): btn.configure(bg=active)
#         def on_r(_): btn.configure(bg=hover)
#         btn.bind("<Enter>", on_e)
#         btn.bind("<Leave>", on_l)
#         btn.bind("<ButtonPress-1>", on_p)
#         btn.bind("<ButtonRelease-1>", on_r)

#     def _add_tooltip(self, widget, text):
#         tip = {"win": None}
#         def show(_):
#             if tip["win"] or not text:
#                 return
#             x = widget.winfo_rootx() + widget.winfo_width()//2
#             y = widget.winfo_rooty() + widget.winfo_height() + 8
#             tip["win"] = tw = tk.Toplevel(widget)
#             tw.wm_overrideredirect(True)
#             tw.wm_geometry(f"+{x}+{y}")
#             lbl = tk.Label(tw, text=text, bg="#000000", fg="white",
#                            font=("Arial", 9), padx=8, pady=4)
#             lbl.pack()
#         def hide(_):
#             if tip["win"]:
#                 tip["win"].destroy()
#                 tip["win"] = None
#         widget.bind("<Enter>", show)
#         widget.bind("<Leave>", hide)

#     def _mk_btn(self, parent, text, command, color, tooltip=None, width=13):
#         b = tk.Button(parent, text=text, command=command,
#                       bg=color, fg="white", activebackground=self._shade(color, 1.05),
#                       bd=0, padx=22, pady=12, width=width,
#                       font=('Arial', 12, 'bold'), cursor="hand2",
#                       highlightthickness=1, highlightbackground=self._shade(color, 0.8))
#         self._add_hover(b, color)
#         if tooltip: self._add_tooltip(b, tooltip)
#         return b

#     def _make_led(self, parent, label_text):
#         wrap = tk.Frame(parent, bg="#2c3e50")
#         c = tk.Canvas(wrap, width=14, height=14, bg="#2c3e50", highlightthickness=0)
#         c.grid(row=0, column=0, padx=(0,6))
#         dot = c.create_oval(2, 2, 12, 12, fill="#7f8c8d", outline="#7f8c8d")
#         lbl = tk.Label(wrap, text=label_text, bg="#2c3e50", fg="#bdc3c7", font=("Arial", 10, "bold"))
#         lbl.grid(row=0, column=1)
#         return wrap, c, dot

#     def _set_led(self, canvas, dot, on, color="#27ae60"):
#         fill = color if on else "#7f8c8d"
#         canvas.itemconfig(dot, fill=fill, outline=fill)

#     def _disable_visually(self, btn, disabled=True, base_color="#7f8c8d"):
#         if disabled:
#             btn.config(state="disabled", bg=base_color, activebackground=base_color)
#         else:
#             btn.config(state="normal")

#     def _set_webcam_state(self, running: bool):
#         self._set_led(self.cam_led_canvas, self.cam_led_dot, running)
#         if running:
#             self._disable_visually(self.start_btn, True)
#             self.stop_btn.config(state='normal', bg="#e74c3c")
#             self.capture_btn.config(state='normal', bg="#f39c12")
#             self.videocapture_btn.config(state='normal', bg="#3498db")
#         else:
#             self.start_btn.config(state='normal', bg="#27ae60")
#             self._disable_visually(self.stop_btn, True)
#             self._disable_visually(self.capture_btn, True)
#             self._disable_visually(self.videocapture_btn, True)

#     def _set_voice_state(self, running: bool, loading: bool=False):
#         self._set_led(self.voice_led_canvas, self.voice_led_dot, running)
#         if loading:
#             self.voice_loader.pack(side='left', padx=8)
#             self.voice_loader.start(8)
#         else:
#             try:
#                 self.voice_loader.stop()
#                 self.voice_loader.pack_forget()
#             except Exception:
#                 pass
#         if running:
#             self._disable_visually(self.voice_start_btn, True)
#             self.voice_stop_btn.config(state='normal', bg="#c0392b")
#         else:
#             self.voice_start_btn.config(state='normal', bg="#1abc9c")
#             self._disable_visually(self.voice_stop_btn, True)

#     def setup_ui(self):
#         # Header (height slightly increased to fit scrollbar if it appears)
#         header = tk.Frame(self.root, bg='#2c3e50', height=86)
#         header.pack(fill='x', padx=15, pady=10)
#         header.pack_propagate(False)
        
#         # Title and user info (left)
#         title_frame = tk.Frame(header, bg='#2c3e50')
#         title_frame.pack(side='left', fill='y', padx=(0, 20))
#         tk.Label(title_frame, text="Emotion Detection System", 
#                  font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
#         tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}", 
#                  font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')
        
#         # -------- Controls (RIGHT) inside a horizontally-scrollable toolbar --------
#         # Wrapper
#         toolbar_wrap = tk.Frame(header, bg='#2c3e50')
#         toolbar_wrap.pack(side='right', fill='both', expand=False)

#         # Canvas + scrollbar
#         self.toolbar_canvas = tk.Canvas(toolbar_wrap, bg='#2c3e50', height=64,
#                                         highlightthickness=0, bd=0)
#         hscroll = ttk.Scrollbar(toolbar_wrap, orient='horizontal',
#                                 command=self.toolbar_canvas.xview)
#         self.toolbar_canvas.configure(xscrollcommand=hscroll.set)
#         self.toolbar_canvas.pack(side='top', fill='x')
#         hscroll.pack(side='bottom', fill='x')

#         # Inner frame living in the canvas
#         controls = tk.Frame(self.toolbar_canvas, bg='#2c3e50')
#         self.toolbar_canvas.create_window((0, 0), window=controls, anchor='nw')
#         # Keep scrollregion in sync
#         def _sync_scroll(_evt=None):
#             self.toolbar_canvas.configure(scrollregion=self.toolbar_canvas.bbox('all'))
#         controls.bind("<Configure>", _sync_scroll)

#         # Palette
#         CL_GREEN  = "#27ae60"
#         CL_RED    = "#e74c3c"
#         CL_ORANGE = "#f39c12"
#         CL_BLUE   = "#3498db"
#         CL_TEAL   = "#1abc9c"
#         CL_DRED   = "#c0392b"
#         CL_AZURE  = "#5dade2"  # Upload Image
#         CL_PURPLE = "#8e44ad"  # Upload Video

#         # Buttons (uniform width)
#         self.start_btn   = self._mk_btn(controls, "Start Webcam",  self.start_detection,  CL_GREEN,  "Open camera and begin detection")
#         self.stop_btn    = self._mk_btn(controls, "Stop Webcam",   self.stop_detection,   CL_RED,    "Release camera and stop detection")
#         self.capture_btn = self._mk_btn(controls, "Capture Face",  self.manual_capture,   CL_ORANGE, "Save current detected faces")
#         self.videocapture_btn = self._mk_btn(controls, "Capture Video", self.manual_video_capture, CL_BLUE, "Record 5s annotated clip")
#         self.voice_start_btn  = self._mk_btn(controls, "Start Voice",   self.start_voice,  CL_TEAL,  "Begin VAD + speech emotion")
#         self.voice_stop_btn   = self._mk_btn(controls, "Stop Voice",    self.stop_voice,   CL_DRED,  "Stop microphone listening")
#         self.upload_img_btn   = self._mk_btn(controls, "Upload Image",  self.upload_image, CL_AZURE, "Analyze an image file (JPG/PNG)")
#         self.upload_vid_btn   = self._mk_btn(controls, "Upload Video",  self.upload_video, CL_PURPLE,"Analyze a video file (MP4/AVI)")

#         # Inline layout with small gaps (scroll if overflow)
#         for w in (self.start_btn, self.stop_btn, self.capture_btn, self.videocapture_btn,
#                   self.voice_start_btn, self.voice_stop_btn, self.upload_img_btn, self.upload_vid_btn):
#             w.pack(side='left', padx=8, pady=4)

#         # LEDs + tiny loader for voice (also inside the scrollable area so it never gets clipped)
#         led_wrap = tk.Frame(controls, bg='#2c3e50')
#         led_wrap.pack(side='left', padx=(12, 0))

#         self.cam_led_wrap, self.cam_led_canvas, self.cam_led_dot = self._make_led(led_wrap, "Camera")
#         self.cam_led_wrap.pack(side='left', padx=10)
#         self.voice_led_wrap, self.voice_led_canvas, self.voice_led_dot = self._make_led(led_wrap, "Voice")
#         self.voice_led_wrap.pack(side='left', padx=10)

#         self.voice_loader = ttk.Progressbar(led_wrap, length=80, mode="indeterminate")

#         # initial states
#         self.stop_btn.config(state='disabled')
#         self.capture_btn.config(state='disabled')
#         self.videocapture_btn.config(state='disabled')
#         self.voice_stop_btn.config(state='disabled')
#         self._set_led(self.cam_led_canvas, self.cam_led_dot, False)
#         self._set_led(self.voice_led_canvas, self.voice_led_dot, False)

#         # Main content
#         main_frame = tk.Frame(self.root, bg='#2c3e50')
#         main_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
#         # Left side - Camera and real-time detection
#         left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
#         left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
#         # Camera header
#         camera_header = tk.Frame(left_frame, bg='#34495e')
#         camera_header.pack(fill='x', pady=10)
#         tk.Label(camera_header, text="Live Feed / Uploaded Media", bg='#34495e', fg='white', 
#                  font=('Arial', 16, 'bold')).pack(side='left', padx=15)
#         self.detection_status = tk.StringVar(value="Idle")
#         tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12', 
#                  font=('Arial', 12, 'bold')).pack(side='right', padx=15)
        
#         # Camera display
#         self.camera_label = tk.Label(left_frame, text="Feed will appear here\n\nStart Webcam or Upload a File",
#                                      bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
#                                      width=70, height=20)
#         self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)
        
#         # Real-time detections list (faces)
#         rt_frame = tk.Frame(left_frame, bg='#34495e')
#         rt_frame.pack(fill='x', padx=15, pady=(0, 15))
#         tk.Label(rt_frame, text="Recent Detections", bg='#34495e', fg='white',
#                  font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
#         self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
#                                           font=('Consolas', 10), relief='flat')
#         self.live_detections.pack(fill='x')

#         # Voice detections list + status
#         voice_box = tk.Frame(left_frame, bg='#34495e')
#         voice_box.pack(fill='x', padx=15, pady=(0, 15))
#         tk.Label(voice_box, text="Recent Voice Detections", bg='#34495e', fg='white',
#                  font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
#         self.voice_detections = tk.Listbox(voice_box, height=5, bg='#2c3e50', fg='#ecf0f1',
#                                            font=('Consolas', 10), relief='flat')
#         self.voice_detections.pack(fill='x')
#         self.voice_status_var = tk.StringVar(value="Voice: Idle")
#         tk.Label(voice_box, textvariable=self.voice_status_var, bg='#34495e', fg='#bdc3c7',
#                  font=('Arial', 10)).pack(anchor='w', pady=(6, 0))
        
#         # Right side - Dashboard
#         right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
#         right_frame.pack(side='right', fill='y')
#         right_frame.pack_propagate(False)
        
#         notebook = ttk.Notebook(right_frame)
#         notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
#         # Filters tab
#         filters_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(filters_frame, text="Filters & History")
#         self.setup_filters_tab(filters_frame)
        
#         # Face Gallery tab
#         gallery_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(gallery_frame, text="Face Gallery")
#         self.setup_gallery_tab(gallery_frame)
        
#         # Export tab
#         export_frame = tk.Frame(notebook, bg='#34495e')
#         notebook.add(export_frame, text="Export")
#         self.setup_export_tab(export_frame)
        
#         # Status bar
#         status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
#         status_frame.pack(fill='x', padx=15, pady=5)
#         self.status_var = tk.StringVar(value="Ready")
#         tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
#                  font=('Arial', 10)).pack(side='left', pady=5)
    
#     def setup_filters_tab(self, parent):
#         tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
#         self.start_date_entry = tk.Entry(parent, width=30)
#         self.start_date_entry.pack(padx=10, pady=5)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.end_date_entry = tk.Entry(parent, width=30)
#         self.end_date_entry.pack(padx=10, pady=5)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
#         tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
#         self.emotion_filter = ttk.Combobox(parent, values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"], 
#                                            state="readonly", width=27)
#         self.emotion_filter.pack(padx=10, pady=5)
#         self.emotion_filter.set("All")
        
#         btn_frame = tk.Frame(parent, bg='#34495e')
#         btn_frame.pack(fill='x', padx=10, pady=10)
#         tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
#                   bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
#                   bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left')
        
#         # Detection history
#         history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         history_frame.pack(fill='both', expand=True, padx=10, pady=10)
#         columns = ("Time", "Emotion", "Confidence", "Type")
#         self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
#         self.detection_tree.heading("Time", text="Timestamp")
#         self.detection_tree.heading("Emotion", text="Emotion")
#         self.detection_tree.heading("Confidence", text="Confidence")
#         self.detection_tree.heading("Type", text="Capture")
#         self.detection_tree.column("Time", width=120)
#         self.detection_tree.column("Emotion", width=80)
#         self.detection_tree.column("Confidence", width=80)
#         self.detection_tree.column("Type", width=60)
#         tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
#         self.detection_tree.configure(yscrollcommand=tree_scroll.set)
#         self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
#         tree_scroll.pack(side='right', fill='y', pady=10)
#         self.detection_tree.bind('<Double-1>', self.view_face_image)
    
#     def setup_gallery_tab(self, parent):
#         gallery_controls = tk.Frame(parent, bg='#34495e')
#         gallery_controls.pack(fill='x', padx=10, pady=10)
#         tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
#                   bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left', padx=(0, 5))
#         tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
#                   bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
#                   padx=15, relief='flat').pack(side='left')
        
#         gallery_frame = tk.Frame(parent, bg='#34495e')
#         gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)
#         self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
#         gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
#         self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')
#         self.scrollable_gallery.bind("<Configure>", lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
#         self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
#         self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
#         self.gallery_canvas.pack(side="left", fill="both", expand=True)
#         gallery_scrollbar.pack(side="right", fill="y")
#         self.face_thumbnails = []   # list of {"data": detection_tuple, ...}
    
#     def setup_export_tab(self, parent):
#         export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
#         export_frame.pack(fill='x', padx=10, pady=10)
#         tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
#                   bg='#16a085', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
#         tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
#                   bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
#         tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
#                   bg='#e67e22', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
#         tk.Button(export_frame, text="Show Graphs (Pie + Line)", command=self.show_graphs,
#                   bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
#                   padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

#     # -------------------- Graphs (Pie + Multi-line Trend) --------------------
#     def show_graphs(self):
#         try:
#             detections = [item['data'] for item in self.face_thumbnails]
#             if not detections:
#                 messagebox.showinfo("Graphs", "No items in the Face Gallery to chart.")
#                 return

#             from collections import Counter, defaultdict

#             emotion_counts = Counter([d[1] for d in detections])

#             timestamps = []
#             for d in detections:
#                 try:
#                     timestamps.append(datetime.fromisoformat(d[0]))
#                 except Exception:
#                     continue
#             if not timestamps:
#                 messagebox.showinfo("Graphs", "No valid timestamps in the Face Gallery.")
#                 return

#             min_dt, max_dt = min(timestamps), max(timestamps)
#             delta_days = (max_dt.date() - min_dt.date()).days
#             group_by_hour = delta_days <= 2

#             def bucket_key(dt: datetime) -> datetime:
#                 if group_by_hour:
#                     return dt.replace(minute=0, second=0, microsecond=0)
#                 return datetime(dt.year, dt.month, dt.day)

#             from collections import defaultdict
#             per_emotion_counts = defaultdict(Counter)
#             for ts, emo, *_ in detections:
#                 try:
#                     dt = datetime.fromisoformat(ts)
#                 except Exception:
#                     continue
#                 per_emotion_counts[emo][bucket_key(dt)] += 1

#             all_buckets = sorted({b for c in per_emotion_counts.values() for b in c.keys()})
#             if not all_buckets:
#                 messagebox.showinfo("Graphs", "No time buckets to plot.")
#                 return

#             x_labels = [b.strftime("%Y-%m-%d %H:00") if group_by_hour else b.strftime("%Y-%m-%d")
#                         for b in all_buckets]
#             emotions = sorted(per_emotion_counts.keys())
#             y_by_emotion = {
#                 emo: [per_emotion_counts[emo].get(b, 0) for b in all_buckets]
#                 for emo in emotions
#             }

#             win = tk.Toplevel(self.root)
#             win.title("Emotion Analytics")
#             win.configure(bg='#2c3e50')

#             top_frame = tk.Frame(win, bg='#2c3e50')
#             top_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
#             bottom_frame = tk.Frame(win, bg='#2c3e50')
#             bottom_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

#             fig_pie = Figure(figsize=(4.8, 4.0), dpi=100)
#             ax_pie = fig_pie.add_subplot(111)
#             labels = list(emotion_counts.keys())
#             sizes = [emotion_counts[k] for k in labels]
#             if sum(sizes) == 0:
#                 labels, sizes = ["No Data"], [1]
#             ax_pie.pie(sizes, labels=[s.upper() for s in labels], autopct='%1.1f%%', startangle=90)
#             ax_pie.set_title("Emotion Distribution (Face Gallery)", fontsize=12)
#             ax_pie.axis('equal')
#             canvas_pie = FigureCanvasTkAgg(fig_pie, master=top_frame)
#             canvas_pie.draw()
#             canvas_pie.get_tk_widget().pack(fill='both', expand=True)

#             fig_line = Figure(figsize=(7.2, 3.8), dpi=100)
#             ax_line = fig_line.add_subplot(111)
#             for emo in emotions:
#                 ax_line.plot(x_labels, y_by_emotion[emo], marker='o', label=emo.upper())
#             ax_line.set_title("Detections per Emotion Over Time (Face Gallery)", fontsize=12)
#             ax_line.set_xlabel("Time" if group_by_hour else "Date")
#             ax_line.set_ylabel("Detections")
#             ax_line.grid(True, linestyle='--', alpha=0.3)
#             if len(x_labels) > 6:
#                 for label in ax_line.get_xticklabels():
#                     label.set_rotation(30)
#                     label.set_horizontalalignment('right')
#             ax_line.legend(loc='upper left', ncol=2, fontsize=8)
#             canvas_line = FigureCanvasTkAgg(fig_line, master=bottom_frame)
#             canvas_line.draw()
#             canvas_line.get_tk_widget().pack(fill='both', expand=True)

#             win.update_idletasks()
#             x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
#             y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
#             win.geometry(f'+{x}+{y}')

#         except Exception as e:
#             messagebox.showerror("Graphs Error", f"Could not render graphs: {e}")

#     # -------------------- Capture / Display / Analysis (Vision) --------------------
#     def start_display_thread(self):
#         self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
#         self.display_thread.start()
    
#     def start_detection(self):
#         if self.is_running:
#             self.stop_detection()
#         try:
#             self.cap = None
#             for camera_idx in [0, 1, 2]:
#                 cap = cv2.VideoCapture(camera_idx)
#                 if cap.isOpened():
#                     self.cap = cap
#                     break
#                 cap.release()
#             if not self.cap or not self.cap.isOpened():
#                 messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
#                 return
            
#             self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
#             self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
#             self.cap.set(cv2.CAP_PROP_FPS, 30)
            
#             self.is_running = True
#             self.start_time = time.time()
#             self.frame_count = 0
            
#             self._set_webcam_state(True)
#             self.detection_status.set("Webcam running...")
#             self.status_var.set("Webcam started - Auto-capturing emotions every 3 seconds")
            
#             threading.Thread(target=self.detection_loop, daemon=True).start()
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
    
#     def stop_detection(self):
#         self.is_running = False
#         if self.cap:
#             try:
#                 self.cap.release()
#             except Exception:
#                 pass
#             self.cap = None
        
#         self._set_webcam_state(False)
#         self.detection_status.set("Idle")
#         self.camera_label.config(image="", text="Feed will appear here\n\nStart Webcam or Upload a File")
#         self.status_var.set("Ready")
    
#     def manual_capture(self):
#         if not self.is_running or self.latest_frame is None:
#             messagebox.showwarning("Capture Error", "Please start detection first")
#             return
#         try:
#             frame = self.latest_frame.copy()
#             if self.current_emotions:
#                 for i, emotion_data in enumerate(self.current_emotions):
#                     self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
#                 self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
#             else:
#                 messagebox.showinfo("Capture Info", "No faces detected in current frame")
#         except Exception as e:
#             messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")

#     def manual_video_capture(self):
#         if not self.is_running:
#             messagebox.showwarning("Video Capture Error", "Please start the webcam first.")
#             return
#         if self.is_recording:
#             messagebox.showwarning("Video Capture Error", "A recording is already in progress.")
#             return
#         threading.Thread(target=self._record_video_thread, daemon=True).start()

#     def _record_video_thread(self):
#         self.is_recording = True
#         self.videocapture_btn.config(state='disabled')
#         self.status_var.set("Recording video with annotations for 5 seconds...")
#         duration = 5
#         fps = 20.0
        
#         width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#         height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#         if width == 0 or height == 0:
#             self.status_var.set("Error: Invalid frame dimensions from camera.")
#             self.is_recording = False
#             self.videocapture_btn.config(state='normal')
#             messagebox.showerror("Recording Error", "Could not get valid frame dimensions.")
#             return

#         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#         filename = f"videos/capture_{timestamp}_annotated.mp4"
#         fourcc = cv2.VideoWriter_fourcc(*'avc1')
#         out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
#         if not out.isOpened():
#             self.status_var.set("Error: Could not open video writer.")
#             self.is_recording = False
#             self.videocapture_btn.config(state='normal')
#             messagebox.showerror("Recording Error", "Failed to initialize video recording.")
#             return

#         start_time = time.time()
#         while time.time() - start_time < duration:
#             if self.latest_frame is not None:
#                 annotated_frame = self.latest_frame.copy()
#                 if self.current_emotions:
#                     for emotion_data in self.current_emotions:
#                         try:
#                             region = emotion_data['region']
#                             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                             emotion = emotion_data['dominant_emotion']
#                             confidence = emotion_data['emotion'][emotion]
#                             color = self.get_emotion_color(emotion)
#                             cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 3)
#                             label = f"{emotion.upper()}: {confidence:.1f}%"
#                             cv2.putText(annotated_frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                         except Exception:
#                             continue
#                 if self.voice_latest_text:
#                     cv2.putText(annotated_frame, self.voice_latest_text, (15, 35),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
#                 out.write(annotated_frame)
#             time.sleep(1 / fps)
#         out.release()
#         self.is_recording = False
#         if self.is_running:
#             self.videocapture_btn.config(state='normal')
#         self.status_var.set(f"Annotated video saved successfully as {filename}")
#         messagebox.showinfo("Video Capture", f"Video with annotations saved to {filename}")
    
#     def detection_loop(self):
#         while self.is_running and self.cap:
#             try:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     time.sleep(0.01)
#                     continue
#                 frame = cv2.flip(frame, 1)
#                 self.latest_frame = frame.copy()
#                 self.frame_count += 1
#                 if self.frame_count % 10 == 0:
#                     threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
#                 time.sleep(0.033)  # ~30 FPS
#             except Exception:
#                 time.sleep(0.1)
    
#     def analyze_emotion(self, frame):
#         try:
#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             results = DeepFace.analyze(
#                 img_path=rgb_frame,
#                 actions=['emotion'],
#                 detector_backend='opencv',
#                 enforce_detection=False,
#                 silent=True
#             )
#             self.current_emotions = results if isinstance(results, list) else [results]
#             current_time = time.time()
#             if current_time - self.last_capture_time >= self.capture_cooldown:
#                 for emotion_data in self.current_emotions:
#                     try:
#                         emotion = emotion_data['dominant_emotion']
#                         confidence = emotion_data['emotion'][emotion]
#                         if confidence > 60:
#                             self.capture_emotion(emotion_data, frame.copy())
#                             self.last_capture_time = current_time
#                             break
#                     except Exception:
#                         continue
#         except Exception:
#             pass
    
#     def upload_image(self):
#         if self.is_running:
#             self.stop_detection()
#         filepath = filedialog.askopenfilename(
#             title="Select an Image",
#             filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
#         )
#         if not filepath:
#             return
#         try:
#             self.status_var.set(f"Analyzing image: {os.path.basename(filepath)}...")
#             self.root.update_idletasks()
#             img = cv2.imread(filepath)
#             if img is None:
#                 messagebox.showerror("Error", "Could not load the image file.")
#                 return

#             results = DeepFace.analyze(img_path=img, actions=['emotion'], enforce_detection=False, silent=True)
#             summary = ""
#             faces = results if isinstance(results, list) else [results]
#             for i, face in enumerate(faces):
#                 region = face['region']
#                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                 emotion = face['dominant_emotion']
#                 confidence = face['emotion'][emotion]
#                 color = self.get_emotion_color(emotion)
#                 cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
#                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                 cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                 summary += f"Face {i+1}: {emotion.capitalize()} ({confidence:.1f}%)\n"
#             self.display_image(img)
#             self.status_var.set("Image analysis complete.")
#             messagebox.showinfo("Image Analysis Results", summary if summary else "No faces detected in the image.")
#         except Exception as e:
#             self.status_var.set("Error during image analysis.")
#             messagebox.showerror("Analysis Error", f"Failed to analyze image: {e}")

#     def upload_video(self):
#         if self.is_running:
#             self.stop_detection()
#         filepath = filedialog.askopenfilename(
#             title="Select a Video",
#             filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv")]
#         )
#         if not filepath:
#             return
#         self.cap = cv2.VideoCapture(filepath)
#         if not self.cap.isOpened():
#             messagebox.showerror("Error", "Could not open the video file.")
#             self.is_running = False
#             return

#         self.is_running = True
#         self.detection_status.set("Video playing...")
#         self._set_webcam_state(True)
#         threading.Thread(target=self.process_video_frames, daemon=True).start()
        
#     def process_video_frames(self):
#         frame_skip = 5
#         frame_counter = 0
#         while self.is_running and self.cap and self.cap.isOpened():
#             ret, frame = self.cap.read()
#             if not ret:
#                 break
#             self.latest_frame = frame.copy()
#             if frame_counter % frame_skip == 0:
#                 threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
#             frame_counter += 1
#             time.sleep(1 / 30)
#         self.stop_detection()
    
#     def display_image(self, frame):
#         if frame is None or frame.size == 0:
#             return
#         try:
#             if self.voice_latest_text:
#                 cv2.putText(frame, self.voice_latest_text, (15, 35),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

#             rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             pil_image = Image.fromarray(rgb_frame)
#             label_w, label_h = self.camera_label.winfo_width(), self.camera_label.winfo_height()
#             if label_w > 1 and label_h > 1:
#                 pil_image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
#             photo = ImageTk.PhotoImage(pil_image)
#             self.camera_label.configure(image=photo, text="")
#             self.camera_label.image = photo
#         except Exception as e:
#             print(f"Error displaying image: {e}")

#     def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
#         try:
#             emotion = emotion_data['dominant_emotion']
#             confidence = emotion_data['emotion'][emotion]
#             timestamp = datetime.now()
#             region = emotion_data['region']
#             x, y, w, h = region['x'], region['y'], region['w'], region['h']
#             padding = 20
#             x1 = max(0, x - padding)
#             y1 = max(0, y - padding)
#             x2 = min(frame.shape[1], x + w + padding)
#             y2 = min(frame.shape[0], y + h + padding)
#             face_crop = frame[y1:y2, x1:x2]
#             color = self.get_emotion_color(emotion)
#             cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#             label = f"{emotion.upper()}: {confidence:.1f}%"
#             cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#             snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
#             cv2.imwrite(snapshot_filename, frame)
#             face_filename = None
#             if os.path.exists("faces"):
#                 face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
#                 cv2.imwrite(face_filename, face_crop)
#             region_json = json.dumps({
#                 'x': x, 'y': y, 'w': w, 'h': h,
#                 'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
#             })
#             try:
#                 self.db_manager.save_detection(
#                     timestamp.isoformat(), emotion, confidence, snapshot_filename,
#                     face_filename, region_json, capture_type, "person1", self.session_id
#                 )
#             except Exception as db_error:
#                 print(f"Database save error: {db_error}")
#             detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
#             self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
#             if self.live_detections.size() > 20:
#                 self.root.after(0, lambda: self.live_detections.delete(tk.END))
#             self.root.after(0, lambda: self.status_var.set(
#                 f"Captured {emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
#             ))
#             self.root.after(1000, self.refresh_gallery)
#         except Exception as e:
#             print(f"Capture error: {e}")
    
#     def refresh_gallery(self):
#         try:
#             for widget in self.scrollable_gallery.winfo_children():
#                 widget.destroy()
#             self.face_thumbnails = []

#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             start_iso = f"{start_date}T00:00:00" if start_date else None
#             end_iso = f"{end_date}T23:59:59" if end_date else None

#             detections = self.db_manager.get_detections(start_iso, end_iso, emotion, limit=50)

#             row, col, max_cols = 0, 0, 3
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 if face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         face_img = cv2.imread(face_crop_path)
#                         face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                         face_img = cv2.resize(face_img, (100, 100))
#                         pil_img = Image.fromarray(face_img)
#                         photo = ImageTk.PhotoImage(pil_img)

#                         thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
#                         thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

#                         face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
#                         face_label.pack(pady=5)
#                         face_label.image = photo

#                         dt = datetime.fromisoformat(timestamp)

#                         confidence_float = 0.0
#                         try:
#                             confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                             confidence_float = float(confidence_str)
#                         except (ValueError, TypeError):
#                             pass

#                         emotion_text = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                         time_text = dt.strftime('%m/%d %H:%M')
#                         type_text = f"[{(capture_type or 'auto').upper()}]"

#                         tk.Label(thumb_frame, text=emotion_text, bg='#2c3e50', fg='white',
#                                  font=('Arial', 8, 'bold')).pack()
#                         tk.Label(thumb_frame, text=time_text, bg='#2c3e50', fg='#bdc3c7',
#                                  font=('Arial', 7)).pack()
#                         tk.Label(thumb_frame, text=type_text, bg='#2c3e50', fg='#f39c12',
#                                  font=('Arial', 7)).pack()

#                         self.face_thumbnails.append({
#                             'frame': thumb_frame,
#                             'path': face_crop_path,
#                             'snapshot_path': snapshot_path,
#                             'data': detection
#                         })

#                         face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))

#                         col += 1
#                         if col >= max_cols:
#                             col = 0
#                             row += 1
#                     except Exception as e:
#                         print(f"Thumbnail error: {e}")
#                         continue

#             self.scrollable_gallery.update_idletasks()
#             self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
#         except Exception as e:
#             print(f"Gallery refresh error: {e}")
    
#     def view_face_full(self, face_path):
#         try:
#             if os.path.exists(face_path):
#                 view_window = tk.Toplevel(self.root)
#                 view_window.title("Face View")
#                 view_window.configure(bg='#2c3e50')
#                 face_img = cv2.imread(face_path)
#                 face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
#                 h, w = face_img.shape[:2]
#                 max_size = 400
#                 if max(h, w) > max_size:
#                     scale = max_size / max(h, w)
#                     new_w, new_h = int(w * scale), int(h * scale)
#                     face_img = cv2.resize(face_img, (new_w, new_h))
#                 pil_img = Image.fromarray(face_img)
#                 photo = ImageTk.PhotoImage(pil_img)
#                 label = tk.Label(view_window, image=photo, bg='#2c3e50')
#                 label.pack(padx=20, pady=20)
#                 label.image = photo
#                 view_window.update_idletasks()
#                 x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
#                 y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
#                 view_window.geometry(f'+{x}+{y}')
#         except Exception as e:
#             messagebox.showerror("View Error", f"Cannot view face: {str(e)}")
    
#     def view_face_image(self, event):
#         selection = self.detection_tree.selection()
#         if selection:
#             messagebox.showinfo("Info", "This feature requires linking tree items to the database. Please use the Face Gallery tab for now.")
    
#     def view_selected_face(self):
#         messagebox.showinfo("Info", "Click on any face thumbnail to view it in full size.")
    
#     def update_display_loop(self):
#         while True:
#             try:
#                 if self.is_running and self.latest_frame is not None:
#                     frame = self.latest_frame.copy()
#                     if self.current_emotions:
#                         for emotion_data in self.current_emotions:
#                             try:
#                                 region = emotion_data['region']
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 emotion = emotion_data['dominant_emotion']
#                                 confidence = emotion_data['emotion'][emotion]
#                                 color = self.get_emotion_color(emotion)
#                                 cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
#                                 label = f"{emotion.upper()}: {confidence:.1f}%"
#                                 cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                             except Exception:
#                                 continue
#                     self.display_image(frame)
#                 time.sleep(0.033)
#             except Exception:
#                 time.sleep(0.1)
    
#     def get_emotion_color(self, emotion):
#         colors = {
#             'happy': (0, 255, 0),      # Green
#             'sad': (255, 100, 100),    # Light Blue
#             'angry': (0, 0, 255),      # Red
#             'fear': (255, 0, 255),     # Magenta
#             'surprise': (0, 255, 255), # Yellow
#             'disgust': (128, 0, 128),  # Purple
#             'neutral': (128, 128, 128) # Gray
#         }
#         return colors.get(emotion.lower(), (255, 255, 255))
    
#     def apply_filters(self):
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
#             for item in self.detection_tree.get_children():
#                 self.detection_tree.delete(item)
#             for detection in detections:
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 confidence_float = 0.0
#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     pass
#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%m/%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 self.detection_tree.insert('', 'end', values=(formatted_time, emotion_name.upper(), f"{confidence_float:.1f}%", type_display))
#             self.status_var.set(f"Loaded {len(detections)} detections")
#             self.refresh_gallery()
#         except Exception as e:
#             messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
    
#     def clear_filters(self):
#         self.start_date_entry.delete(0, tk.END)
#         self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
#         self.end_date_entry.delete(0, tk.END)
#         self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
#         self.emotion_filter.set("All")
#         self.apply_filters()
    
#     # -------------------- Exporting --------------------
#     def export_csv(self):
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".csv",
#                 filetypes=[("CSV files", "*.csv")],
#                 initialfile=f"emotion_detections_base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
#             )
#             if not filename:
#                 return
#             with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
#                 writer = csv.writer(csvfile)
#                 writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Base64"])
#                 for detection in detections:
#                     timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                     image_base64_string = "N/A"
#                     confidence_float = 0.0
#                     try:
#                         confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                         confidence_float = float(confidence_str)
#                     except (ValueError, TypeError):
#                         pass
#                     try:
#                         if snapshot_path and os.path.exists(snapshot_path):
#                             image = cv2.imread(snapshot_path)
#                             if image is not None and face_region:
#                                 region = json.loads(face_region)
#                                 x, y, w, h = region['x'], region['y'], region['w'], region['h']
#                                 color = self.get_emotion_color(emotion_name)
#                                 cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
#                                 label = f"{emotion_name.upper()}: {confidence_float:.1f}%"
#                                 cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
#                             _, buffer = cv2.imencode('.jpg', image)
#                             image_base64_string = base64.b64encode(buffer).decode('utf-8')
#                         else:
#                             image_base64_string = "Snapshot not found"
#                     except Exception:
#                         image_base64_string = "Error encoding image"
#                     writer.writerow([timestamp, emotion_name, f"{confidence_float:.1f}%", image_base64_string])
#             messagebox.showinfo("Export", f"Data and embedded images exported successfully to {filename}")
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")
    
#     def export_pdf(self):
#         try:
#             from reportlab.lib.pagesizes import A4
#             from reportlab.pdfgen import canvas
#             from reportlab.lib.units import inch
#         except ImportError:
#             messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
#             return
#         try:
#             start_date = self.start_date_entry.get().strip()
#             end_date = self.end_date_entry.get().strip()
#             emotion = self.emotion_filter.get()
#             if start_date:
#                 start_date = f"{start_date}T00:00:00"
#             if end_date:
#                 end_date = f"{end_date}T23:59:59"
#             detections = self.db_manager.get_detections(start_date, end_date, emotion)
#             if not detections:
#                 messagebox.showinfo("Export", "No data to export")
#                 return
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".pdf",
#                 filetypes=[("PDF files", "*.pdf")],
#                 initialfile=f"emotion_report_with_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#             )
#             if not filename:
#                 return
#             c = canvas.Canvas(filename, pagesize=A4)
#             width, height = A4
#             c.setFont("Helvetica-Bold", 20)
#             c.drawString(inch, height - inch, "Emotion Detection Report")
#             total = len(detections)
#             emotion_counts = Counter([d[1] for d in detections])
#             auto_count = sum(1 for d in detections if d[6] == 'auto')
#             manual_count = sum(1 for d in detections if d[6] == 'manual')
#             voice_count = sum(1 for d in detections if d[6] == 'voice')
#             y_pos = height - inch * 1.5
#             c.setFont("Helvetica-Bold", 12)
#             c.drawString(inch, y_pos, f"Total Detections: {total}")
#             c.drawString(inch, y_pos - 20, f"Auto Captures: {auto_count}")
#             c.drawString(inch, y_pos - 40, f"Manual Captures: {manual_count}")
#             c.drawString(inch, y_pos - 60, f"Voice Segments: {voice_count}")
#             c.setFont("Helvetica-Bold", 12)
#             c.drawString(inch * 4, y_pos, "Emotion Distribution:")
#             c.setFont("Helvetica", 10)
#             stat_y = y_pos - 20
#             for emotion_name, count in emotion_counts.most_common():
#                 percentage = (count / total) * 100 if total > 0 else 0
#                 c.drawString(inch * 4, stat_y, f"{emotion_name.upper()}: {count} ({percentage:.1f}%)")
#                 stat_y -= 15
#             y_pos -= 120
#             c.setFont("Helvetica-Bold", 14)
#             c.drawString(inch, y_pos, "Detection Log")
#             y_pos -= 30
#             for i, detection in enumerate(detections):
#                 if y_pos < inch * 2:
#                     c.showPage()
#                     y_pos = height - inch
#                 timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
#                 confidence_float = 0.0
#                 try:
#                     confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
#                     confidence_float = float(confidence_str)
#                 except (ValueError, TypeError):
#                     pass
#                 dt = datetime.fromisoformat(timestamp)
#                 formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
#                 type_display = capture_type.upper() if capture_type else 'AUTO'
#                 c.setFont("Helvetica", 9)
#                 text = f"{i+1}. {formatted_time} | {emotion_name.upper()} | {confidence_float:.1f}% | {type_display}"
#                 c.drawString(inch, y_pos, text)
#                 y_pos -= 15
#                 if capture_type != 'voice' and face_crop_path and os.path.exists(face_crop_path):
#                     try:
#                         img_width = 1.5 * inch
#                         img_height = 1.5 * inch
#                         if y_pos < img_height + inch:
#                             c.showPage()
#                             y_pos = height - inch
#                         c.drawImage(face_crop_path, inch, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
#                         y_pos -= (img_height + 10)
#                     except Exception as e:
#                         c.drawString(inch + 5, y_pos, f"  (Error loading image: {e})")
#                         y_pos -= 15
#                 else:
#                     c.setFont("Helvetica-Oblique", 8)
#                     c.drawString(inch + 5, y_pos, "  (No face image available)")
#                     y_pos -= 15
#             c.save()
#             messagebox.showinfo("Export", f"Report with images exported successfully to {filename}")
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")
    
#     def export_faces(self):
#         try:
#             import zipfile
#             if not os.path.exists("faces"):
#                 messagebox.showinfo("Export", "No faces folder found")
#                 return
#             face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
#             if not face_files:
#                 messagebox.showinfo("Export", "No face images to export")
#                 return
#             filename = filedialog.asksaveasfilename(
#                 defaultextension=".zip",
#                 filetypes=[("ZIP files", "*.zip")],
#                 initialfile=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
#             )
#             if not filename:
#                 return
#             with zipfile.ZipFile(filename, 'w') as zipf:
#                 for face_file in face_files:
#                     face_path = os.path.join("faces", face_file)
#                     zipf.write(face_path, face_file)
#             messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")
#         except Exception as e:
#             messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")

#     # -------------------- Voice SER (VAD-gated) --------------------
#     def start_voice(self):
#         if self.voice_running:
#             return
#         try:
#             import sounddevice as sd  # noqa
#             import webrtcvad         # noqa
#         except Exception as e:
#             messagebox.showerror("Voice Error", f"Missing dependency: {e}\nInstall with: pip install sounddevice webrtcvad transformers torch")
#             return

#         self.voice_running = True
#         self._set_voice_state(running=False, loading=True)
#         self.voice_thread = threading.Thread(target=self._voice_worker, daemon=True)
#         self.voice_thread.start()

#     def stop_voice(self):
#         if not self.voice_running:
#             return
#         self.voice_running = False
#         self._set_voice_state(running=False, loading=False)

#     def _voice_worker(self):
#         import collections, queue
#         import numpy as np
#         import sounddevice as sd
#         import webrtcvad
#         from transformers import pipeline

#         SR = 16000
#         FRAME_MS = 30
#         FRAME_SAMPLES = int(SR * FRAME_MS / 1000)
#         AGGR = 2
#         MIN_SEG_MS = 1500
#         MAX_SEG_MS = 4000
#         SILENCE_TAIL_MS = 400
#         SMOOTH_N = 5

#         def to_bytes_i16(x: np.ndarray) -> bytes:
#             assert x.dtype == np.int16 and x.ndim == 1
#             return x.tobytes()

#         self.root.after(0, lambda: self.voice_status_var.set("Voice: Loading SER model (first run may take a bit)..."))
#         try:
#             clf = pipeline("audio-classification", model="superb/wav2vec2-base-superb-er")
#         except Exception as e:
#             self.root.after(0, lambda: messagebox.showerror("Voice Error", f"Failed to load SER model: {e}"))
#             self.root.after(0, lambda: self._set_voice_state(running=False, loading=False))
#             self.voice_running = False
#             return

#         self.root.after(0, lambda: self._set_voice_state(running=True, loading=False))
#         self.root.after(0, lambda: self.voice_status_var.set("Voice: Listening (speak)…"))

#         vad = webrtcvad.Vad(AGGR)
#         audio_q: "queue.Queue[bytes]" = queue.Queue()
#         window = collections.deque(maxlen=SMOOTH_N)

#         def segmenter():
#             ring = []
#             voiced_ms = 0
#             silence_ms = 0
#             while True:
#                 frame = yield
#                 is_voiced = vad.is_speech(frame, SR)
#                 if is_voiced:
#                     ring.append(frame)
#                     voiced_ms += FRAME_MS
#                     silence_ms = 0
#                     if voiced_ms >= MAX_SEG_MS:
#                         audio_q.put(b"".join(ring))
#                         ring.clear(); voiced_ms = 0; silence_ms = 0
#                 else:
#                     if ring:
#                         silence_ms += FRAME_MS
#                         should_flush = (voiced_ms >= MIN_SEG_MS and silence_ms >= SILENCE_TAIL_MS) or (voiced_ms >= MAX_SEG_MS)
#                         if should_flush:
#                             audio_q.put(b"".join(ring))
#                             ring.clear(); voiced_ms = 0; silence_ms = 0

#         seg = segmenter()
#         next(seg)

#         def on_audio(indata, frames, time_info, status):
#             if not self.voice_running:
#                 return
#             mono = indata[:, 0] if indata.ndim > 1 else indata
#             i16 = np.clip(mono * 32768.0, -32768, 32767).astype(np.int16)
#             start = 0
#             while start + FRAME_SAMPLES <= len(i16):
#                 frame = i16[start:start+FRAME_SAMPLES]
#                 try:
#                     seg.send(to_bytes_i16(frame))
#                 except StopIteration:
#                     break
#                 start += FRAME_SAMPLES

#         try:
#             with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
#                                 blocksize=FRAME_SAMPLES, callback=on_audio):
#                 while self.voice_running:
#                     try:
#                         seg_bytes = audio_q.get(timeout=0.2)
#                     except Exception:
#                         continue
#                     try:
#                         seg_i16 = np.frombuffer(seg_bytes, dtype=np.int16)
#                         seg_f32 = seg_i16.astype(np.float32) / 32768.0
#                         preds = clf({"array": seg_f32, "sampling_rate": SR}, top_k=4)
#                         top = preds[0]
#                         raw_label = top["label"].lower()
#                         normalize = {"neutral": "neutral emotion",
#                                      "happy": "happy emotion",
#                                      "sad": "sad emotion",
#                                      "angry": "angry emotion"}
#                         out_text_simple = normalize.get(raw_label, f"{raw_label} emotion")
#                         score_pct = float(top["score"]) * 100.0

#                         window.append(out_text_simple)
#                         smoothed = max(set(window), key=window.count)

#                         overlay_text = f"VOICE: {raw_label.upper()} ({score_pct:.1f}%)"
#                         self.voice_latest_text = overlay_text
#                         ts = datetime.now()
#                         log_line = f"{ts.strftime('%H:%M:%S')} - {raw_label.upper()}: {score_pct:.1f}% [VOICE]"
#                         self.root.after(0, lambda s=log_line: self.voice_detections.insert(0, s))
#                         if self.voice_detections.size() > self.voice_list_max:
#                             self.root.after(0, lambda: self.voice_detections.delete(tk.END))
#                         self.root.after(0, lambda: self.voice_status_var.set(f"Voice: {smoothed}"))

#                         try:
#                             fname = f"audio/voice_{ts.strftime('%Y%m%d_%H%M%S_%f')}.wav"
#                             with wave.open(fname, "wb") as wf:
#                                 wf.setnchannels(1)
#                                 wf.setsampwidth(2)
#                                 wf.setframerate(SR)
#                                 wf.writeframes(seg_bytes)
#                             self.db_manager.save_detection(
#                                 ts.isoformat(), raw_label, score_pct,
#                                 snapshot_path=fname,
#                                 face_crop_path=None, face_region=None,
#                                 capture_type='voice', person_id="voice", session_id=self.session_id
#                             )
#                         except Exception as e:
#                             print(f"Voice save error: {e}")

#                     except Exception as e:
#                         print(f"Voice classify error: {e}")
#         except Exception as e:
#             self.root.after(0, lambda: messagebox.showerror("Voice Error", f"Microphone/stream error: {e}"))

#         self.voice_running = False
#         self.root.after(0, lambda: self._set_voice_state(running=False, loading=False))
#         self.voice_latest_text = ""

#     # -------------------- Run / Close --------------------
#     def run(self):
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
#         self.root.mainloop()
    
#     def on_closing(self):
#         if self.is_running:
#             self.stop_detection()
#         if self.voice_running:
#             self.stop_voice()
#             time.sleep(0.3)
#         self.root.destroy()

# # -------------------- Main Application Entry Point --------------------
# def main():
#     print("Starting Enhanced Emotion Detection System with Voice SER and Database Migration...")
#     db_manager = DatabaseManager()
#     login_window = LoginWindow(db_manager)
#     success, username = login_window.show()
#     if success:
#         print(f"Login successful for user: {username}")
#         app = EmotionDetectionSystem(username)
#         app.run()
#     else:
#         print("Login cancelled or failed")

# if __name__ == "__main__":
#     main()









































# """
# Complete Emotion Detection System with Image/Video Upload, Voice SER, and Analysis
# Install:
#   pip install deepface opencv-python tensorflow pillow reportlab matplotlib
#   pip install sounddevice webrtcvad transformers torch --upgrade
#
# Features:
# - Secure admin authentication
# - Real-time emotion detection from webcam
# - Capture short video clips with emotion annotations
# - Upload and analyze emotions from image files (JPG, PNG)
# - Upload and analyze emotions from video files (MP4, AVI)
# - Real-time voice emotion detection (VAD-gated) using HF transformers
# - Robust data handling and professional PDF/CSV exporting
# - Automatic database migration for existing installations
# - Graphs (Pie + Multi-line) are based on the CURRENT FACE GALLERY items
#   (Voice detections are logged to history but excluded from Face Gallery & graphs.)
# """

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from deepface import DeepFace
import threading
import time
from PIL import Image, ImageTk
from collections import Counter
import sqlite3
import os
import csv
import hashlib
import secrets
from datetime import datetime, timedelta
import json
import base64
import wave  # for saving voiced segments

# Charts
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# -------------------- Password Security --------------------
def hash_password(password: str, iterations: int = 200_000) -> str:
    """Hash password using PBKDF2"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f"{iterations}${salt.hex()}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash"""
    try:
        iterations_s, salt_hex, hash_hex = stored.split("$")
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        target = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
        return secrets.compare_digest(dk, target)
    except Exception:
        return False

# -------------------- Database Manager with Migration --------------------
class DatabaseManager:
    def __init__(self, db_path="emotion_system.db"):
        self.db_path = db_path
        self.init_database()
        self.migrate_database()  # Add migration step
    
    def init_database(self):
        """Initialize database with required tables"""
        os.makedirs("snapshots", exist_ok=True)
        os.makedirs("faces", exist_ok=True)   # New folder for cropped faces
        os.makedirs("videos", exist_ok=True)  # New folder for video captures
        os.makedirs("audio", exist_ok=True)   # New folder for voice segments

        conn = sqlite3.connect(self.db_path)
        
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Detections table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                emotion TEXT NOT NULL,
                confidence REAL NOT NULL,
                snapshot_path TEXT NOT NULL,
                face_crop_path TEXT,
                face_region TEXT,
                capture_type TEXT DEFAULT 'auto',
                person_id TEXT,
                session_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_timestamp ON detections(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_detections_emotion ON detections(emotion)")
        
        # Create default admin user if none exists
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            admin_hash = hash_password("admin123")
            conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                        ("admin", admin_hash, "admin"))
        
        conn.commit()
        conn.close()
    
    def migrate_database(self):
        """Migrate existing database to add new columns if missing"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("PRAGMA table_info(detections)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'face_crop_path' not in columns:
                cursor.execute("ALTER TABLE detections ADD COLUMN face_crop_path TEXT")
            if 'face_region' not in columns:
                cursor.execute("ALTER TABLE detections ADD COLUMN face_region TEXT")
            if 'capture_type' not in columns:
                cursor.execute("ALTER TABLE detections ADD COLUMN capture_type TEXT DEFAULT 'auto'")
                
            conn.commit()
        except Exception as e:
            print(f"Migration note: {e}")
        finally:
            conn.close()
    
    def verify_user(self, username: str, password: str) -> bool:
        """Verify user credentials"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return verify_password(password, result[0])
        return False
    
    def save_detection(self, timestamp: str, emotion: str, confidence: float, 
                       snapshot_path: str, face_crop_path: str = None, face_region: str = None,
                       capture_type: str = 'auto', person_id: str = None, session_id: str = None):
        """Save detection to database"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, face_crop_path, 
                                        face_region, capture_type, person_id, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, emotion, confidence, snapshot_path, face_crop_path, face_region, 
                  capture_type, person_id, session_id))
            conn.commit()
        except sqlite3.OperationalError as e:
            print(f"Database error, trying fallback: {e}")
            try:
                conn.execute("""
                    INSERT INTO detections (timestamp, emotion, confidence, snapshot_path, person_id, session_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, emotion, confidence, snapshot_path, person_id, session_id))
                conn.commit()
            except Exception as fallback_error:
                print(f"Fallback failed: {fallback_error}")
        finally:
            conn.close()
    
    def get_detections(self, start_date=None, end_date=None, emotion=None, capture_type=None, limit=1000):
        """Get filtered detections from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(detections)")
        columns = [column[1] for column in cursor.fetchall()]
        
        base_columns = "timestamp, emotion, confidence, snapshot_path"
        base_columns += ", face_crop_path" if 'face_crop_path' in columns else ", NULL as face_crop_path"
        base_columns += ", face_region" if 'face_region' in columns else ", NULL as face_region"
        base_columns += ", capture_type" if 'capture_type' in columns else ", 'auto' as capture_type"
        base_columns += ", person_id"
        
        query = f"SELECT {base_columns} FROM detections WHERE 1=1"
        params = []
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        if emotion and emotion.lower() != "all":
            query += " AND emotion = ?"
            params.append(emotion.lower())
        if capture_type and capture_type.lower() != "all":
            query += " AND capture_type = ?"
            params.append(capture_type.lower())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return rows

# -------------------- Enhanced Login Window --------------------
class LoginWindow:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.success = False
        self.username = None
        
        self.root = tk.Tk()
        self.root.title("Emotion Detection System - Admin Login")
        self.root.geometry("500x400")
        self.root.configure(bg='#2c3e50')
        self.root.resizable(False, False)
        self.root.eval('tk::PlaceWindow . center')
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg='#2c3e50', padx=40, pady=40)
        main_frame.pack(fill='both', expand=True)
        
        title_label = tk.Label(main_frame, text="Admin Login", 
                               font=('Arial', 24, 'bold'), bg='#2c3e50', fg='white')
        title_label.pack(pady=(0, 15))
        
        form_frame = tk.Frame(main_frame, bg='#2c3e50')
        form_frame.pack(fill='x')
        
        tk.Label(form_frame, text="Username:", font=('Arial', 12), 
                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        self.username_entry = tk.Entry(form_frame, font=('Arial', 12), width=35,
                                       bg='#34495e', fg='white', insertbackground='white',
                                       relief='flat', bd=5)
        self.username_entry.pack(fill='x', pady=(0, 15))
        self.username_entry.insert(0, "admin")
        
        tk.Label(form_frame, text="Password:", font=('Arial', 12), 
                 bg='#2c3e50', fg='white').pack(anchor='w', pady=(0, 5))
        self.password_entry = tk.Entry(form_frame, font=('Arial', 12), 
                                       show="\u2022", bg='#34495e', fg='white',
                                       insertbackground='white', relief='flat', bd=5)
        self.password_entry.pack(fill='x', pady=(0, 10))
        self.password_entry.bind('<KeyRelease>', self.update_password_feedback)
        
        toggle_frame = tk.Frame(form_frame, bg='#2c3e50')
        toggle_frame.pack(fill='x', pady=(5, 10))
        self.show_password_var = tk.BooleanVar()
        tk.Checkbutton(toggle_frame, text="Show Password", variable=self.show_password_var,
                       command=self.toggle_password_visibility, bg='#2c3e50', fg='#bdc3c7',
                       selectcolor='#2c3e50', font=('Arial', 10)).pack(side='left')
        self.password_length_label = tk.Label(toggle_frame, text="Characters: 0",
                                              font=('Arial', 9), bg='#2c3e50', fg='#7f8c8d')
        self.password_length_label.pack(side='right')
        
        info_frame = tk.Frame(form_frame, bg='#34495e', relief='raised', bd=1)
        info_frame.pack(fill='x', pady=(0, 20))
        tk.Label(info_frame, text="Default: admin / admin123",
                 font=('Arial', 10), bg='#34495e', fg='#ecf0f1').pack(pady=5)
        
        button_frame = tk.Frame(form_frame, bg='#2c3e50')
        button_frame.pack(fill='x', pady=(10, 0))
        tk.Button(button_frame, text="Login", command=self.login,
                  bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                  padx=30, pady=10, relief='flat').pack(side='left', padx=(0, 10))
        tk.Button(button_frame, text="Cancel", command=self.cancel,
                  bg='#e74c3c', fg='white', font=('Arial', 12, 'bold'),
                  padx=30, pady=10, relief='flat').pack(side='left')
        
        self.root.bind('<Return>', lambda e: self.login())
        self.password_entry.focus()
    
    def toggle_password_visibility(self):
        self.password_entry.config(show="" if self.show_password_var.get() else "\u2022")
    
    def update_password_feedback(self, event=None):
        self.password_length_label.config(text=f"Characters: {len(self.password_entry.get())}")
    
    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        if self.db_manager.verify_user(username, password):
            self.success = True
            self.username = username
            self.root.destroy()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")
            self.password_entry.delete(0, tk.END)
            self.password_entry.focus()
            self.password_length_label.config(text="Characters: 0")
    
    def cancel(self):
        self.root.destroy()
    
    def show(self):
        self.root.mainloop()
        return self.success, self.username

# -------------------- Main Application --------------------
class EmotionDetectionSystem:
    def __init__(self, username):
        self.username = username
        self.db_manager = DatabaseManager()
        self.session_id = f"session_{int(time.time())}"
        
        # Core variables (vision)
        self.cap = None
        self.is_running = False
        self.is_recording = False
        self.current_emotions = []
        self.latest_frame = None
        self.frame_count = 0
        self.start_time = time.time()
        self.last_capture_time = 0
        self.capture_cooldown = 3.0  # seconds between auto-captures

        # Voice SER variables
        self.voice_running = False
        self.voice_thread = None
        self.voice_status = "Idle"
        self.voice_latest_text = ""   # overlay text
        self.voice_list_max = 20
        self.ser_pipeline = None      # cached HF pipeline (lazy)

        # Auto-refresh settings
        self.history_refresh_ms = 1500
        self._history_refresh_job = None

        # Setup main window
        self.root = tk.Tk()
        self.root.title(f"Emotion Detection System - Welcome {username}")
        self.root.geometry("1500x950")
        self.root.configure(bg='#2c3e50')
        
        self.setup_ui()
        self.start_display_thread()

        # Load initial data + start auto-refresh
        self.apply_filters()
        self._schedule_history_refresh()

    # ---------- VISUAL HELPERS ----------
    def _shade(self, hex_color, factor=0.9):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _add_hover(self, btn, base):
        hover = self._shade(base, 1.08)
        active = self._shade(base, 0.92)
        def on_e(_): btn.configure(bg=hover)
        def on_l(_): btn.configure(bg=base)
        def on_p(_): btn.configure(bg=active)
        def on_r(_): btn.configure(bg=hover)
        btn.bind("<Enter>", on_e)
        btn.bind("<Leave>", on_l)
        btn.bind("<ButtonPress-1>", on_p)
        btn.bind("<ButtonRelease-1>", on_r)

    def _add_tooltip(self, widget, text):
        tip = {"win": None}
        def show(_):
            if tip["win"] or not text:
                return
            x = widget.winfo_rootx() + widget.winfo_width()//2
            y = widget.winfo_rooty() + widget.winfo_height() + 8
            tip["win"] = tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(tw, text=text, bg="#000000", fg="white",
                           font=("Arial", 9), padx=8, pady=4)
            lbl.pack()
        def hide(_):
            if tip["win"]:
                tip["win"].destroy()
                tip["win"] = None
        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def _mk_btn(self, parent, text, command, color, tooltip=None, width=13):
        b = tk.Button(parent, text=text, command=command,
                      bg=color, fg="white", activebackground=self._shade(color, 1.05),
                      bd=0, padx=22, pady=12, width=width,
                      font=('Arial', 12, 'bold'), cursor="hand2",
                      highlightthickness=1, highlightbackground=self._shade(color, 0.8))
        self._add_hover(b, color)
        if tooltip: self._add_tooltip(b, tooltip)
        return b

    def _make_led(self, parent, label_text):
        wrap = tk.Frame(parent, bg="#2c3e50")
        c = tk.Canvas(wrap, width=14, height=14, bg="#2c3e50", highlightthickness=0)
        c.grid(row=0, column=0, padx=(0,6))
        dot = c.create_oval(2, 2, 12, 12, fill="#7f8c8d", outline="#7f8c8d")
        lbl = tk.Label(wrap, text=label_text, bg="#2c3e50", fg="#bdc3c7", font=("Arial", 10, "bold"))
        lbl.grid(row=0, column=1)
        return wrap, c, dot

    def _set_led(self, canvas, dot, on, color="#27ae60"):
        fill = color if on else "#7f8c8d"
        canvas.itemconfig(dot, fill=fill, outline=fill)

    def _disable_visually(self, btn, disabled=True, base_color="#7f8c8d"):
        if disabled:
            btn.config(state="disabled", bg=base_color, activebackground=base_color)
        else:
            btn.config(state="normal")

    def _set_webcam_state(self, running: bool):
        self._set_led(self.cam_led_canvas, self.cam_led_dot, running)
        if running:
            self._disable_visually(self.start_btn, True)
            self.stop_btn.config(state='normal', bg="#e74c3c")
            self.capture_btn.config(state='normal', bg="#f39c12")
            self.videocapture_btn.config(state='normal', bg="#3498db")
        else:
            self.start_btn.config(state='normal', bg="#27ae60")
            self._disable_visually(self.stop_btn, True)
            self._disable_visually(self.capture_btn, True)
            self._disable_visually(self.videocapture_btn, True)

    def _set_voice_state(self, running: bool, loading: bool=False):
        self._set_led(self.voice_led_canvas, self.voice_led_dot, running)
        if loading:
            self.voice_loader.pack(side='left', padx=8)
            self.voice_loader.start(8)
        else:
            try:
                self.voice_loader.stop()
                self.voice_loader.pack_forget()
            except Exception:
                pass
        if running:
            self._disable_visually(self.voice_start_btn, True)
            self.voice_stop_btn.config(state='normal', bg="#c0392b")
        else:
            self.voice_start_btn.config(state='normal', bg="#1abc9c")
            self._disable_visually(self.voice_stop_btn, True)

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg='#2c3e50', height=86)
        header.pack(fill='x', padx=15, pady=10)
        header.pack_propagate(False)
        
        # Title and user info (left)
        title_frame = tk.Frame(header, bg='#2c3e50')
        title_frame.pack(side='left', fill='y', padx=(0, 20))
        tk.Label(title_frame, text="Emotion Detection System", 
                 font=('Arial', 20, 'bold'), bg='#2c3e50', fg='white').pack(anchor='w')
        tk.Label(title_frame, text=f"User: {self.username} | Session: {self.session_id}", 
                 font=('Arial', 10), bg='#2c3e50', fg='#bdc3c7').pack(anchor='w')
        
        # Controls with horizontal scroll
        toolbar_wrap = tk.Frame(header, bg='#2c3e50')
        toolbar_wrap.pack(side='right', fill='both', expand=False)

        self.toolbar_canvas = tk.Canvas(toolbar_wrap, bg='#2c3e50', height=64,
                                        highlightthickness=0, bd=0)
        hscroll = ttk.Scrollbar(toolbar_wrap, orient='horizontal',
                                command=self.toolbar_canvas.xview)
        self.toolbar_canvas.configure(xscrollcommand=hscroll.set)
        self.toolbar_canvas.pack(side='top', fill='x')
        hscroll.pack(side='bottom', fill='x')

        controls = tk.Frame(self.toolbar_canvas, bg='#2c3e50')
        self.toolbar_canvas.create_window((0, 0), window=controls, anchor='nw')
        controls.bind("<Configure>", lambda e: self.toolbar_canvas.configure(scrollregion=self.toolbar_canvas.bbox('all')))

        # Palette
        CL_GREEN  = "#27ae60"
        CL_RED    = "#e74c3c"
        CL_ORANGE = "#f39c12"
        CL_BLUE   = "#3498db"
        CL_TEAL   = "#1abc9c"
        CL_DRED   = "#c0392b"
        CL_AZURE  = "#5dade2"
        CL_PURPLE = "#8e44ad"

        # Buttons
        self.start_btn   = self._mk_btn(controls, "Start Webcam",  self.start_detection,  CL_GREEN,  "Open camera and begin detection")
        self.stop_btn    = self._mk_btn(controls, "Stop Webcam",   self.stop_detection,   CL_RED,    "Release camera and stop detection")
        self.capture_btn = self._mk_btn(controls, "Capture Face",  self.manual_capture,   CL_ORANGE, "Save current detected faces")
        self.videocapture_btn = self._mk_btn(controls, "Capture Video", self.manual_video_capture, CL_BLUE, "Record 5s annotated clip")
        self.voice_start_btn  = self._mk_btn(controls, "Start Voice",   self.start_voice,  CL_TEAL,  "Begin VAD + speech emotion")
        self.voice_stop_btn   = self._mk_btn(controls, "Stop Voice",    self.stop_voice,   CL_DRED,  "Stop microphone listening")
        self.upload_img_btn   = self._mk_btn(controls, "Upload Image",  self.upload_image, CL_AZURE, "Analyze an image file (JPG/PNG)")
        self.upload_vid_btn   = self._mk_btn(controls, "Upload Video",  self.upload_video, CL_PURPLE,"Analyze a video file (MP4/AVI)")

        for w in (self.start_btn, self.stop_btn, self.capture_btn, self.videocapture_btn,
                  self.voice_start_btn, self.voice_stop_btn, self.upload_img_btn, self.upload_vid_btn):
            w.pack(side='left', padx=8, pady=4)

        # LEDs + loader for voice
        led_wrap = tk.Frame(controls, bg='#2c3e50')
        led_wrap.pack(side='left', padx=(12, 0))

        self.cam_led_wrap, self.cam_led_canvas, self.cam_led_dot = self._make_led(led_wrap, "Camera")
        self.cam_led_wrap.pack(side='left', padx=10)
        self.voice_led_wrap, self.voice_led_canvas, self.voice_led_dot = self._make_led(led_wrap, "Voice")
        self.voice_led_wrap.pack(side='left', padx=10)

        self.voice_loader = ttk.Progressbar(led_wrap, length=80, mode="indeterminate")

        # initial states
        self.stop_btn.config(state='disabled')
        self.capture_btn.config(state='disabled')
        self.videocapture_btn.config(state='disabled')
        self.voice_stop_btn.config(state='disabled')
        self._set_led(self.cam_led_canvas, self.cam_led_dot, False)
        self._set_led(self.voice_led_canvas, self.voice_led_dot, False)

        # Main content
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill='both', expand=True, padx=15, pady=5)
        
        # Left side - Camera and real-time detection
        left_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Camera header
        camera_header = tk.Frame(left_frame, bg='#34495e')
        camera_header.pack(fill='x', pady=10)
        tk.Label(camera_header, text="Live Feed / Uploaded Media", bg='#34495e', fg='white', 
                 font=('Arial', 16, 'bold')).pack(side='left', padx=15)
        self.detection_status = tk.StringVar(value="Idle")
        tk.Label(camera_header, textvariable=self.detection_status, bg='#34495e', fg='#f39c12', 
                 font=('Arial', 12, 'bold')).pack(side='right', padx=15)
        
        # Camera display
        self.camera_label = tk.Label(left_frame, text="Feed will appear here\n\nStart Webcam or Upload a File",
                                     bg='#2c3e50', fg='#bdc3c7', font=('Arial', 14),
                                     width=70, height=20)
        self.camera_label.pack(pady=15, padx=15, fill='both', expand=True)
        
        # Real-time detections list (faces)
        rt_frame = tk.Frame(left_frame, bg='#34495e')
        rt_frame.pack(fill='x', padx=15, pady=(0, 15))
        tk.Label(rt_frame, text="Recent Detections", bg='#34495e', fg='white',
                 font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
        self.live_detections = tk.Listbox(rt_frame, height=6, bg='#2c3e50', fg='#ecf0f1',
                                          font=('Consolas', 10), relief='flat')
        self.live_detections.pack(fill='x')

        # Voice detections list + status
        voice_box = tk.Frame(left_frame, bg='#34495e')
        voice_box.pack(fill='x', padx=15, pady=(0, 15))
        tk.Label(voice_box, text="Recent Voice Detections", bg='#34495e', fg='white',
                 font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 5))
        self.voice_detections = tk.Listbox(voice_box, height=5, bg='#2c3e50', fg='#ecf0f1',
                                           font=('Consolas', 10), relief='flat')
        self.voice_detections.pack(fill='x')
        self.voice_status_var = tk.StringVar(value="Voice: Idle")
        tk.Label(voice_box, textvariable=self.voice_status_var, bg='#34495e', fg='#bdc3c7',
                 font=('Arial', 10)).pack(anchor='w', pady=(6, 0))
        
        # Right side - Dashboard
        right_frame = tk.Frame(main_frame, bg='#34495e', relief='raised', bd=2, width=450)
        right_frame.pack(side='right', fill='y')
        right_frame.pack_propagate(False)
        
        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Filters tab
        filters_frame = tk.Frame(notebook, bg='#34495e')
        notebook.add(filters_frame, text="Filters & History")
        self.setup_filters_tab(filters_frame)
        
        # Face Gallery tab
        gallery_frame = tk.Frame(notebook, bg='#34495e')
        notebook.add(gallery_frame, text="Face Gallery")
        self.setup_gallery_tab(gallery_frame)
        
        # Export tab
        export_frame = tk.Frame(notebook, bg='#34495e')
        notebook.add(export_frame, text="Export")
        self.setup_export_tab(export_frame)
        
        # Status bar
        status_frame = tk.Frame(self.root, bg='#2c3e50', height=30)
        status_frame.pack(fill='x', padx=15, pady=5)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(status_frame, textvariable=self.status_var, bg='#2c3e50', fg='#95a5a6',
                 font=('Arial', 10)).pack(side='left', pady=5)
    
    def setup_filters_tab(self, parent):
        tk.Label(parent, text="From Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10, pady=(10, 0))
        self.start_date_entry = tk.Entry(parent, width=30)
        self.start_date_entry.pack(padx=10, pady=5)
        self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        
        tk.Label(parent, text="To Date (YYYY-MM-DD):", bg='#34495e', fg='white').pack(anchor='w', padx=10)
        self.end_date_entry = tk.Entry(parent, width=30)
        self.end_date_entry.pack(padx=10, pady=5)
        self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        tk.Label(parent, text="Emotion:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
        self.emotion_filter = ttk.Combobox(parent, values=["All", "happy", "sad", "angry", "fear", "surprise", "disgust", "neutral"], 
                                           state="readonly", width=27)
        self.emotion_filter.pack(padx=10, pady=5)
        self.emotion_filter.set("All")

        # NEW: capture type filter
        tk.Label(parent, text="Capture Type:", bg='#34495e', fg='white').pack(anchor='w', padx=10)
        self.capture_filter = ttk.Combobox(
            parent,
            values=["All", "auto", "manual", "voice"],
            state="readonly",
            width=27
        )
        self.capture_filter.pack(padx=10, pady=5)
        self.capture_filter.set("All")
        
        btn_frame = tk.Frame(parent, bg='#34495e')
        btn_frame.pack(fill='x', padx=10, pady=10)
        tk.Button(btn_frame, text="Apply Filters", command=self.apply_filters,
                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
        tk.Button(btn_frame, text="Clear Filters", command=self.clear_filters,
                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief='flat').pack(side='left')
        
        # Detection history
        history_frame = tk.LabelFrame(parent, text="Detection History", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
        history_frame.pack(fill='both', expand=True, padx=10, pady=10)
        columns = ("Time", "Emotion", "Confidence", "Type")
        self.detection_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)
        self.detection_tree.heading("Time", text="Timestamp")
        self.detection_tree.heading("Emotion", text="Emotion")
        self.detection_tree.heading("Confidence", text="Confidence")
        self.detection_tree.heading("Type", text="Capture")
        self.detection_tree.column("Time", width=120)
        self.detection_tree.column("Emotion", width=80)
        self.detection_tree.column("Confidence", width=80)
        self.detection_tree.column("Type", width=60)
        tree_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=self.detection_tree.yview)
        self.detection_tree.configure(yscrollcommand=tree_scroll.set)
        self.detection_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        tree_scroll.pack(side='right', fill='y', pady=10)
        self.detection_tree.bind('<Double-1>', self.view_face_image)
    
    def setup_gallery_tab(self, parent):
        gallery_controls = tk.Frame(parent, bg='#34495e')
        gallery_controls.pack(fill='x', padx=10, pady=10)
        tk.Button(gallery_controls, text="Refresh Gallery", command=self.refresh_gallery,
                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief='flat').pack(side='left', padx=(0, 5))
        tk.Button(gallery_controls, text="View Selected Face", command=self.view_selected_face,
                  bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
                  padx=15, relief='flat').pack(side='left')
        
        gallery_frame = tk.Frame(parent, bg='#34495e')
        gallery_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.gallery_canvas = tk.Canvas(gallery_frame, bg='#2c3e50', highlightthickness=0)
        gallery_scrollbar = ttk.Scrollbar(gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
        self.scrollable_gallery = tk.Frame(self.gallery_canvas, bg='#2c3e50')
        self.scrollable_gallery.bind("<Configure>", lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
        self.gallery_canvas.create_window((0, 0), window=self.scrollable_gallery, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=gallery_scrollbar.set)
        self.gallery_canvas.pack(side="left", fill="both", expand=True)
        gallery_scrollbar.pack(side="right", fill="y")
        self.face_thumbnails = []   # list of {"data": detection_tuple, ...}
    
    def setup_export_tab(self, parent):
        export_frame = tk.LabelFrame(parent, text="Export Options", bg='#34495e', fg='white', font=('Arial', 12, 'bold'))
        export_frame.pack(fill='x', padx=10, pady=10)
        tk.Button(export_frame, text="Export to CSV", command=self.export_csv,
                  bg='#16a085', fg='white', font=('Arial', 12, 'bold'),
                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        tk.Button(export_frame, text="Export to PDF Report", command=self.export_pdf,
                  bg='#8e44ad', fg='white', font=('Arial', 12, 'bold'),
                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        tk.Button(export_frame, text="Export Face Gallery", command=self.export_faces,
                  bg='#e67e22', fg='white', font=('Arial', 12, 'bold'),
                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)
        tk.Button(export_frame, text="Show Graphs (Pie + Line)", command=self.show_graphs,
                  bg='#3498db', fg='white', font=('Arial', 12, 'bold'),
                  padx=20, pady=10, relief='flat').pack(fill='x', padx=10, pady=5)

    # -------------------- Graphs (Pie + Multi-line Trend) --------------------
    def show_graphs(self):
        try:
            detections = [item['data'] for item in self.face_thumbnails]
            if not detections:
                messagebox.showinfo("Graphs", "No items in the Face Gallery to chart.")
                return

            from collections import Counter, defaultdict

            emotion_counts = Counter([d[1] for d in detections])

            timestamps = []
            for d in detections:
                try:
                    timestamps.append(datetime.fromisoformat(d[0]))
                except Exception:
                    continue
            if not timestamps:
                messagebox.showinfo("Graphs", "No valid timestamps in the Face Gallery.")
                return

            min_dt, max_dt = min(timestamps), max(timestamps)
            delta_days = (max_dt.date() - min_dt.date()).days
            group_by_hour = delta_days <= 2

            def bucket_key(dt: datetime) -> datetime:
                if group_by_hour:
                    return dt.replace(minute=0, second=0, microsecond=0)
                return datetime(dt.year, dt.month, dt.day)

            from collections import defaultdict
            per_emotion_counts = defaultdict(Counter)
            for ts, emo, *_ in detections:
                try:
                    dt = datetime.fromisoformat(ts)
                except Exception:
                    continue
                per_emotion_counts[emo][bucket_key(dt)] += 1

            all_buckets = sorted({b for c in per_emotion_counts.values() for b in c.keys()})
            if not all_buckets:
                messagebox.showinfo("Graphs", "No time buckets to plot.")
                return

            x_labels = [b.strftime("%Y-%m-%d %H:00") if group_by_hour else b.strftime("%Y-%m-%d")
                        for b in all_buckets]
            emotions = sorted(per_emotion_counts.keys())
            y_by_emotion = {
                emo: [per_emotion_counts[emo].get(b, 0) for b in all_buckets]
                for emo in emotions
            }

            win = tk.Toplevel(self.root)
            win.title("Emotion Analytics")
            win.configure(bg='#2c3e50')

            top_frame = tk.Frame(win, bg='#2c3e50')
            top_frame.pack(fill='both', expand=True, padx=10, pady=(10, 5))
            bottom_frame = tk.Frame(win, bg='#2c3e50')
            bottom_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))

            fig_pie = Figure(figsize=(4.8, 4.0), dpi=100)
            ax_pie = fig_pie.add_subplot(111)
            labels = list(emotion_counts.keys())
            sizes = [emotion_counts[k] for k in labels]
            if sum(sizes) == 0:
                labels, sizes = ["No Data"], [1]
            ax_pie.pie(sizes, labels=[s.upper() for s in labels], autopct='%1.1f%%', startangle=90)
            ax_pie.set_title("Emotion Distribution (Face Gallery)", fontsize=12)
            ax_pie.axis('equal')
            canvas_pie = FigureCanvasTkAgg(fig_pie, master=top_frame)
            canvas_pie.draw()
            canvas_pie.get_tk_widget().pack(fill='both', expand=True)

            fig_line = Figure(figsize=(7.2, 3.8), dpi=100)
            ax_line = fig_line.add_subplot(111)
            for emo in emotions:
                ax_line.plot(x_labels, y_by_emotion[emo], marker='o', label=emo.upper())
            ax_line.set_title("Detections per Emotion Over Time (Face Gallery)", fontsize=12)
            ax_line.set_xlabel("Time" if group_by_hour else "Date")
            ax_line.set_ylabel("Detections")
            ax_line.grid(True, linestyle='--', alpha=0.3)
            if len(x_labels) > 6:
                for label in ax_line.get_xticklabels():
                    label.set_rotation(30)
                    label.set_horizontalalignment('right')
            ax_line.legend(loc='upper left', ncol=2, fontsize=8)
            canvas_line = FigureCanvasTkAgg(fig_line, master=bottom_frame)
            canvas_line.draw()
            canvas_line.get_tk_widget().pack(fill='both', expand=True)

            win.update_idletasks()
            x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
            y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
            win.geometry(f'+{x}+{y}')

        except Exception as e:
            messagebox.showerror("Graphs Error", f"Could not render graphs: {e}")

    # -------------------- Capture / Display / Analysis (Vision) --------------------
    def start_display_thread(self):
        self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.display_thread.start()
    
    def start_detection(self):
        if self.is_running:
            self.stop_detection()
        try:
            self.cap = None
            for camera_idx in [0]:  # Use 0 for laptop camera
                cap = cv2.VideoCapture(camera_idx)
                if cap.isOpened():
                    self.cap = cap
                    break
                cap.release()
            if not self.cap or not self.cap.isOpened():
                messagebox.showerror("Camera Error", "Could not open camera. Please check your camera connection.")
                return
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            self.is_running = True
            self.start_time = time.time()
            self.frame_count = 0
            
            self._set_webcam_state(True)
            self.detection_status.set("Webcam running...")
            self.status_var.set("Webcam started - Auto-capturing emotions every 3 seconds")
            
            threading.Thread(target=self.detection_loop, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start detection: {str(e)}")
    
    def stop_detection(self):
        self.is_running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        
        self._set_webcam_state(False)
        self.detection_status.set("Idle")
        self.camera_label.config(image="", text="Feed will appear here\n\nStart Webcam or Upload a File")
        self.status_var.set("Ready")
    
    def manual_capture(self):
        if not self.is_running or self.latest_frame is None:
            messagebox.showwarning("Capture Error", "Please start detection first")
            return
        try:
            frame = self.latest_frame.copy()
            if self.current_emotions:
                for i, emotion_data in enumerate(self.current_emotions):
                    self.capture_emotion(emotion_data, frame.copy(), capture_type='manual', suffix=f"_face{i+1}")
                self.status_var.set(f"Manual capture completed - {len(self.current_emotions)} faces saved")
            else:
                messagebox.showinfo("Capture Info", "No faces detected in current frame")
        except Exception as e:
            messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")

    def manual_video_capture(self):
        if not self.is_running:
            messagebox.showwarning("Video Capture Error", "Please start the webcam first.")
            return
        if self.is_recording:
            messagebox.showwarning("Video Capture Error", "A recording is already in progress.")
            return
        threading.Thread(target=self._record_video_thread, daemon=True).start()

    def _record_video_thread(self):
        self.is_recording = True
        self.videocapture_btn.config(state='disabled')
        self.status_var.set("Recording video with annotations for 5 seconds...")
        duration = 5
        fps = 20.0
        
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width == 0 or height == 0:
            self.status_var.set("Error: Invalid frame dimensions from camera.")
            self.is_recording = False
            self.videocapture_btn.config(state='normal')
            messagebox.showerror("Recording Error", "Could not get valid frame dimensions.")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"videos/capture_{timestamp}_annotated.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
        if not out.isOpened():
            self.status_var.set("Error: Could not open video writer.")
            self.is_recording = False
            self.videocapture_btn.config(state='normal')
            messagebox.showerror("Recording Error", "Failed to initialize video recording.")
            return

        start_time = time.time()
        while time.time() - start_time < duration:
            if self.latest_frame is not None:
                annotated_frame = self.latest_frame.copy()
                if self.current_emotions:
                    for emotion_data in self.current_emotions:
                        try:
                            region = emotion_data['region']
                            x, y, w, h = region['x'], region['y'], region['w'], region['h']
                            emotion = emotion_data['dominant_emotion']
                            confidence = emotion_data['emotion'][emotion]
                            color = self.get_emotion_color(emotion)
                            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, 3)
                            label = f"{emotion.upper()}: {confidence:.1f}%"
                            cv2.putText(annotated_frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        except Exception:
                            continue
                if self.voice_latest_text:
                    cv2.putText(annotated_frame, self.voice_latest_text, (15, 35),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
                out.write(annotated_frame)
            time.sleep(1 / fps)
        out.release()
        self.is_recording = False
        if self.is_running:
            self.videocapture_btn.config(state='normal')
        self.status_var.set(f"Annotated video saved successfully as {filename}")
        messagebox.showinfo("Video Capture", f"Video with annotations saved to {filename}")
    
    def detection_loop(self):
        while self.is_running and self.cap:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
                frame = cv2.flip(frame, 1)
                self.latest_frame = frame.copy()
                self.frame_count += 1
                if self.frame_count % 10 == 0:
                    threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
                time.sleep(0.033)  # ~30 FPS
            except Exception:
                time.sleep(0.1)
    
    def analyze_emotion(self, frame):
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = DeepFace.analyze(
                img_path=rgb_frame,
                actions=['emotion'],
                detector_backend='opencv',
                enforce_detection=False,
                silent=True
            )
            self.current_emotions = results if isinstance(results, list) else [results]
            current_time = time.time()
            if current_time - self.last_capture_time >= self.capture_cooldown:
                for emotion_data in self.current_emotions:
                    try:
                        emotion = emotion_data['dominant_emotion']
                        confidence = emotion_data['emotion'][emotion]
                        if confidence > 60:
                            self.capture_emotion(emotion_data, frame.copy())
                            self.last_capture_time = current_time
                            break
                    except Exception:
                        continue
        except Exception:
            pass
    
    def upload_image(self):
        if self.is_running:
            self.stop_detection()
        filepath = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp")]
        )
        if not filepath:
            return
        try:
            self.status_var.set(f"Analyzing image: {os.path.basename(filepath)}...")
            self.root.update_idletasks()
            img = cv2.imread(filepath)
            if img is None:
                messagebox.showerror("Error", "Could not load the image file.")
                return

            results = DeepFace.analyze(img_path=img, actions=['emotion'], enforce_detection=False, silent=True)
            summary = ""
            faces = results if isinstance(results, list) else [results]
            for i, face in enumerate(faces):
                region = face['region']
                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                emotion = face['dominant_emotion']
                confidence = face['emotion'][emotion]
                color = self.get_emotion_color(emotion)
                cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
                label = f"{emotion.upper()}: {confidence:.1f}%"
                cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                summary += f"Face {i+1}: {emotion.capitalize()} ({confidence:.1f}%)\n"
            self.display_image(img)
            self.status_var.set("Image analysis complete.")
            messagebox.showinfo("Image Analysis Results", summary if summary else "No faces detected in the image.")
        except Exception as e:
            self.status_var.set("Error during image analysis.")
            messagebox.showerror("Analysis Error", f"Failed to analyze image: {e}")

    def upload_video(self):
        if self.is_running:
            self.stop_detection()
        filepath = filedialog.askopenfilename(
            title="Select a Video",
            filetypes=[("Video Files", "*.mp4 *.avi *.mov *.mkv")]
        )
        if not filepath:
            return
        self.cap = cv2.VideoCapture(filepath)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Could not open the video file.")
            self.is_running = False
            return

        self.is_running = True
        self.detection_status.set("Video playing...")
        self._set_webcam_state(True)
        threading.Thread(target=self.process_video_frames, daemon=True).start()
        
    def process_video_frames(self):
        frame_skip = 5
        frame_counter = 0
        while self.is_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break
            self.latest_frame = frame.copy()
            if frame_counter % frame_skip == 0:
                threading.Thread(target=self.analyze_emotion, args=(frame.copy(),), daemon=True).start()
            frame_counter += 1
            time.sleep(1 / 30)
        self.stop_detection()
    
    def display_image(self, frame):
        if frame is None or frame.size == 0:
            return
        try:
            if self.voice_latest_text:
                cv2.putText(frame, self.voice_latest_text, (15, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            label_w, label_h = self.camera_label.winfo_width(), self.camera_label.winfo_height()
            if label_w > 1 and label_h > 1:
                pil_image.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil_image)
            self.camera_label.configure(image=photo, text="")
            self.camera_label.image = photo
        except Exception as e:
            print(f"Error displaying image: {e}")

    def capture_emotion(self, emotion_data, frame, capture_type='auto', suffix=''):
        try:
            emotion = emotion_data['dominant_emotion']
            confidence = emotion_data['emotion'][emotion]
            timestamp = datetime.now()
            region = emotion_data['region']
            x, y, w, h = region['x'], region['y'], region['w'], region['h']
            padding = 20
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(frame.shape[1], x + w + padding)
            y2 = min(frame.shape[0], y + h + padding)
            face_crop = frame[y1:y2, x1:x2]
            color = self.get_emotion_color(emotion)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
            label = f"{emotion.upper()}: {confidence:.1f}%"
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            snapshot_filename = f"snapshots/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}.jpg"
            cv2.imwrite(snapshot_filename, frame)
            face_filename = None
            if os.path.exists("faces"):
                face_filename = f"faces/{timestamp.strftime('%Y%m%d_%H%M%S')}_{emotion}{suffix}_face.jpg"
                cv2.imwrite(face_filename, face_crop)
            region_json = json.dumps({
                'x': x, 'y': y, 'w': w, 'h': h,
                'padded': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
            })
            try:
                self.db_manager.save_detection(
                    timestamp.isoformat(), emotion, confidence, snapshot_filename,
                    face_filename, region_json, capture_type, "person1", self.session_id
                )
            except Exception as db_error:
                print(f"Database save error: {db_error}")
            detection_text = f"{timestamp.strftime('%H:%M:%S')} - {emotion.upper()}: {confidence:.1f}% [{capture_type.upper()}]"
            self.root.after(0, lambda: self.live_detections.insert(0, detection_text))
            if self.live_detections.size() > 20:
                self.root.after(0, lambda: self.live_detections.delete(tk.END))
            self.root.after(0, lambda: self.status_var.set(
                f"Captured {emotion.UPPER() if hasattr(emotion,'UPPER') else emotion.upper()}: {confidence:.1f}% - {timestamp.strftime('%H:%M:%S')} [{capture_type.upper()}]"
            ))
            self.root.after(1000, self.refresh_gallery)
        except Exception as e:
            print(f"Capture error: {e}")
    
    def refresh_gallery(self):
        try:
            for widget in self.scrollable_gallery.winfo_children():
                widget.destroy()
            self.face_thumbnails = []

            start_date = self.start_date_entry.get().strip()
            end_date = self.end_date_entry.get().strip()
            emotion = self.emotion_filter.get()
            cap_type = self.capture_filter.get() if hasattr(self, "capture_filter") else "All"

            start_iso = f"{start_date}T00:00:00" if start_date else None
            end_iso = f"{end_date}T23:59:59" if end_date else None

            detections = self.db_manager.get_detections(start_iso, end_iso, emotion, capture_type=cap_type, limit=50)

            row, col, max_cols = 0, 0, 3
            for detection in detections:
                timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                # Only show entries that actually have a face image (excludes voice)
                if face_crop_path and os.path.exists(face_crop_path):
                    try:
                        face_img = cv2.imread(face_crop_path)
                        face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                        face_img = cv2.resize(face_img, (100, 100))
                        pil_img = Image.fromarray(face_img)
                        photo = ImageTk.PhotoImage(pil_img)

                        thumb_frame = tk.Frame(self.scrollable_gallery, bg='#2c3e50', relief='ridge', bd=2)
                        thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

                        face_label = tk.Label(thumb_frame, image=photo, bg='#2c3e50')
                        face_label.pack(pady=5)
                        face_label.image = photo

                        dt = datetime.fromisoformat(timestamp)

                        confidence_float = 0.0
                        try:
                            confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
                            confidence_float = float(confidence_str)
                        except (ValueError, TypeError):
                            pass

                        emotion_text = f"{emotion_name.upper()}: {confidence_float:.1f}%"
                        time_text = dt.strftime('%m/%d %H:%M')
                        type_text = f"[{(capture_type or 'auto').upper()}]"

                        tk.Label(thumb_frame, text=emotion_text, bg='#2c3e50', fg='white',
                                 font=('Arial', 8, 'bold')).pack()
                        tk.Label(thumb_frame, text=time_text, bg='#2c3e50', fg='#bdc3c7',
                                 font=('Arial', 7)).pack()
                        tk.Label(thumb_frame, text=type_text, bg='#2c3e50', fg='#f39c12',
                                 font=('Arial', 7)).pack()

                        self.face_thumbnails.append({
                            'frame': thumb_frame,
                            'path': face_crop_path,
                            'snapshot_path': snapshot_path,
                            'data': detection
                        })

                        face_label.bind('<Button-1>', lambda e, path=face_crop_path: self.view_face_full(path))

                        col += 1
                        if col >= max_cols:
                            col = 0
                            row += 1
                    except Exception as e:
                        print(f"Thumbnail error: {e}")
                        continue

            self.scrollable_gallery.update_idletasks()
            self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
        except Exception as e:
            print(f"Gallery refresh error: {e}")
    
    def view_face_full(self, face_path):
        try:
            if os.path.exists(face_path):
                view_window = tk.Toplevel(self.root)
                view_window.title("Face View")
                view_window.configure(bg='#2c3e50')
                face_img = cv2.imread(face_path)
                face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                h, w = face_img.shape[:2]
                max_size = 400
                if max(h, w) > max_size:
                    scale = max_size / max(h, w)
                    new_w, new_h = int(w * scale), int(h * scale)
                    face_img = cv2.resize(face_img, (new_w, new_h))
                pil_img = Image.fromarray(face_img)
                photo = ImageTk.PhotoImage(pil_img)
                label = tk.Label(view_window, image=photo, bg='#2c3e50')
                label.pack(padx=20, pady=20)
                label.image = photo
                view_window.update_idletasks()
                x = (view_window.winfo_screenwidth() // 2) - (view_window.winfo_width() // 2)
                y = (view_window.winfo_screenheight() // 2) - (view_window.winfo_height() // 2)
                view_window.geometry(f'+{x}+{y}')
        except Exception as e:
            messagebox.showerror("View Error", f"Cannot view face: {str(e)}")
    
    def view_face_image(self, event):
        selection = self.detection_tree.selection()
        if selection:
            messagebox.showinfo("Info", "This feature requires linking tree items to the database. Please use the Face Gallery tab for now.")
    
    def view_selected_face(self):
        messagebox.showinfo("Info", "Click on any face thumbnail to view it in full size.")
    
    def update_display_loop(self):
        while True:
            try:
                if self.is_running and self.latest_frame is not None:
                    frame = self.latest_frame.copy()
                    if self.current_emotions:
                        for emotion_data in self.current_emotions:
                            try:
                                region = emotion_data['region']
                                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                                emotion = emotion_data['dominant_emotion']
                                confidence = emotion_data['emotion'][emotion]
                                color = self.get_emotion_color(emotion)
                                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
                                label = f"{emotion.upper()}: {confidence:.1f}%"
                                cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                            except Exception:
                                continue
                    self.display_image(frame)
                time.sleep(0.033)
            except Exception:
                time.sleep(0.1)
    
    def get_emotion_color(self, emotion):
        colors = {
            'happy': (0, 255, 0),      # Green
            'sad': (255, 100, 100),    # Light Blue
            'angry': (0, 0, 255),      # Red
            'fear': (255, 0, 255),     # Magenta
            'surprise': (0, 255, 255), # Yellow
            'disgust': (128, 0, 128),  # Purple
            'neutral': (128, 128, 128) # Gray
        }
        return colors.get(emotion.lower(), (255, 255, 255))
    
    # -------------------- Filtering and Auto-Refresh --------------------
    def _refresh_history_only(self):
        try:
            start_date = self.start_date_entry.get().strip()
            end_date = self.end_date_entry.get().strip()
            emotion = self.emotion_filter.get()
            cap_type = self.capture_filter.get() if hasattr(self, "capture_filter") else "All"

            if start_date:
                start_date = f"{start_date}T00:00:00"
            if end_date:
                end_date = f"{end_date}T23:59:59"

            detections = self.db_manager.get_detections(start_date, end_date, emotion, capture_type=cap_type)

            # Clear and refill
            self.detection_tree.delete(*self.detection_tree.get_children())
            for detection in detections:
                timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                confidence_float = 0.0
                try:
                    confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
                    confidence_float = float(confidence_str)
                except (ValueError, TypeError):
                    pass
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime('%m/%d %H:%M:%S')
                type_display = capture_type.upper() if capture_type else 'AUTO'
                self.detection_tree.insert('', 'end', values=(formatted_time, emotion_name.upper(), f"{confidence_float:.1f}%", type_display))
            self.status_var.set(f"Loaded {len(detections)} detections")
        except Exception as e:
            # Silent fail to avoid dialog spam during periodic refresh
            print(f"Auto-refresh error: {e}")

    def _schedule_history_refresh(self):
        if self._history_refresh_job is not None:
            self.root.after_cancel(self._history_refresh_job)
        def tick():
            if not self.root.winfo_exists():
                return
            self._refresh_history_only()
            self._history_refresh_job = self.root.after(self.history_refresh_ms, tick)
        self._history_refresh_job = self.root.after(self.history_refresh_ms, tick)

    def apply_filters(self):
        try:
            # Refresh history immediately
            self._refresh_history_only()
            # Refresh gallery on demand (not every 1.5s)
            self.refresh_gallery()
        except Exception as e:
            messagebox.showerror("Filter Error", f"Error applying filters: {str(e)}")
    
    def clear_filters(self):
        self.start_date_entry.delete(0, tk.END)
        self.start_date_entry.insert(0, (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        self.end_date_entry.delete(0, tk.END)
        self.end_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.emotion_filter.set("All")
        if hasattr(self, "capture_filter"):
            self.capture_filter.set("All")
        self.apply_filters()
    
    # -------------------- Exporting --------------------
    def export_csv(self):
        try:
            start_date = self.start_date_entry.get().strip()
            end_date = self.end_date_entry.get().strip()
            emotion = self.emotion_filter.get()
            cap_type = self.capture_filter.get() if hasattr(self, "capture_filter") else "All"
            if start_date:
                start_date = f"{start_date}T00:00:00"
            if end_date:
                end_date = f"{end_date}T23:59:59"
            detections = self.db_manager.get_detections(start_date, end_date, emotion, capture_type=cap_type)
            if not detections:
                messagebox.showinfo("Export", "No data to export")
                return
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile=f"emotion_detections_base64_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            if not filename:
                return
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Base64"])
                for detection in detections:
                    timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                    image_base64_string = "N/A"
                    confidence_float = 0.0
                    try:
                        confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
                        confidence_float = float(confidence_str)
                    except (ValueError, TypeError):
                        pass
                    try:
                        if snapshot_path and os.path.exists(snapshot_path):
                            image = cv2.imread(snapshot_path)
                            if image is not None and face_region:
                                region = json.loads(face_region)
                                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                                color = self.get_emotion_color(emotion_name)
                                cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)
                                label = f"{emotion_name.upper()}: {confidence_float:.1f}%"
                                cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                            _, buffer = cv2.imencode('.jpg', image)
                            image_base64_string = base64.b64encode(buffer).decode('utf-8')
                        else:
                            image_base64_string = "Snapshot not found"
                    except Exception:
                        image_base64_string = "Error encoding image"
                    writer.writerow([timestamp, emotion_name, f"{confidence_float:.1f}%", image_base64_string])
            messagebox.showinfo("Export", f"Data and embedded images exported successfully to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")
    
    def export_pdf(self):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
        except ImportError:
            messagebox.showerror("Export Error", "Please install reportlab: pip install reportlab")
            return
        try:
            start_date = self.start_date_entry.get().strip()
            end_date = self.end_date_entry.get().strip()
            emotion = self.emotion_filter.get()
            cap_type = self.capture_filter.get() if hasattr(self, "capture_filter") else "All"
            if start_date:
                start_date = f"{start_date}T00:00:00"
            if end_date:
                end_date = f"{end_date}T23:59:59"
            detections = self.db_manager.get_detections(start_date, end_date, emotion, capture_type=cap_type)
            if not detections:
                messagebox.showinfo("Export", "No data to export")
                return
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                initialfile=f"emotion_report_with_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            if not filename:
                return
            c = canvas.Canvas(filename, pagesize=A4)
            width, height = A4
            c.setFont("Helvetica-Bold", 20)
            c.drawString(inch, height - inch, "Emotion Detection Report")
            total = len(detections)
            emotion_counts = Counter([d[1] for d in detections])
            auto_count = sum(1 for d in detections if d[6] == 'auto')
            manual_count = sum(1 for d in detections if d[6] == 'manual')
            voice_count = sum(1 for d in detections if d[6] == 'voice')
            y_pos = height - inch * 1.5
            c.setFont("Helvetica-Bold", 12)
            c.drawString(inch, y_pos, f"Total Detections: {total}")
            c.drawString(inch, y_pos - 20, f"Auto Captures: {auto_count}")
            c.drawString(inch, y_pos - 40, f"Manual Captures: {manual_count}")
            c.drawString(inch, y_pos - 60, f"Voice Segments: {voice_count}")
            c.setFont("Helvetica-Bold", 12)
            c.drawString(inch * 4, y_pos, "Emotion Distribution:")
            c.setFont("Helvetica", 10)
            stat_y = y_pos - 20
            for emotion_name, count in emotion_counts.most_common():
                percentage = (count / total) * 100 if total > 0 else 0
                c.drawString(inch * 4, stat_y, f"{emotion_name.upper()}: {count} ({percentage:.1f}%)")
                stat_y -= 15
            y_pos -= 120
            c.setFont("Helvetica-Bold", 14)
            c.drawString(inch, y_pos, "Detection Log")
            y_pos -= 30
            for i, detection in enumerate(detections):
                if y_pos < inch * 2:
                    c.showPage()
                    y_pos = height - inch
                timestamp, emotion_name, confidence, snapshot_path, face_crop_path, face_region, capture_type, person_id = detection
                confidence_float = 0.0
                try:
                    confidence_str = confidence.decode('utf-8', errors='ignore') if isinstance(confidence, bytes) else str(confidence)
                    confidence_float = float(confidence_str)
                except (ValueError, TypeError):
                    pass
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                type_display = capture_type.upper() if capture_type else 'AUTO'
                c.setFont("Helvetica", 9)
                text = f"{i+1}. {formatted_time} | {emotion_name.upper()} | {confidence_float:.1f}% | {type_display}"
                c.drawString(inch, y_pos, text)
                y_pos -= 15
                if capture_type != 'voice' and face_crop_path and os.path.exists(face_crop_path):
                    try:
                        img_width = 1.5 * inch
                        img_height = 1.5 * inch
                        if y_pos < img_height + inch:
                            c.showPage()
                            y_pos = height - inch
                        c.drawImage(face_crop_path, inch, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
                        y_pos -= (img_height + 10)
                    except Exception as e:
                        c.drawString(inch + 5, y_pos, f"  (Error loading image: {e})")
                        y_pos -= 15
                else:
                    c.setFont("Helvetica-Oblique", 8)
                    c.drawString(inch + 5, y_pos, "  (No face image available)")
                    y_pos -= 15
            c.save()
            messagebox.showinfo("Export", f"Report with images exported successfully to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")
    
    def export_faces(self):
        try:
            import zipfile
            if not os.path.exists("faces"):
                messagebox.showinfo("Export", "No faces folder found")
                return
            face_files = [f for f in os.listdir("faces") if f.endswith('.jpg')]
            if not face_files:
                messagebox.showinfo("Export", "No face images to export")
                return
            filename = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip")],
                initialfile=f"face_gallery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )
            if not filename:
                return
            with zipfile.ZipFile(filename, 'w') as zipf:
                for face_file in face_files:
                    face_path = os.path.join("faces", face_file)
                    zipf.write(face_path, face_file)
            messagebox.showinfo("Export", f"Face gallery exported to {filename}\nTotal faces: {len(face_files)}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export faces: {str(e)}")

    # -------------------- Voice SER (VAD-gated) --------------------
    def start_voice(self):
        if self.voice_running:
            return
        try:
            import sounddevice as sd  # noqa
            import webrtcvad         # noqa
        except Exception as e:
            messagebox.showerror("Voice Error", f"Missing dependency: {e}\nInstall with: pip install sounddevice webrtcvad transformers torch")
            return

        # Clear old UI state for a clean session
        self.voice_detections.delete(0, tk.END)
        self.voice_latest_text = ""
        self.voice_status_var.set("Voice: Initializing…")

        self.voice_running = True
        self._set_voice_state(running=False, loading=True)
        self.voice_thread = threading.Thread(target=self._voice_worker, daemon=True)
        self.voice_thread.start()

    def stop_voice(self):
        if not self.voice_running:
            return
        self.voice_running = False
        self._set_voice_state(running=False, loading=False)
        self.voice_status_var.set("Voice: Stopped")
        self.voice_latest_text = ""

    def _voice_worker(self):
        import collections, queue
        import numpy as np
        import sounddevice as sd
        import webrtcvad
        from transformers import pipeline

        SR = 16000
        FRAME_MS = 30
        FRAME_SAMPLES = int(SR * FRAME_MS / 1000)
        AGGR = 2
        MIN_SEG_MS = 900      # shorter to catch brief phrases
        MAX_SEG_MS = 4000
        SILENCE_TAIL_MS = 400
        SMOOTH_N = 5

        def to_bytes_i16(x: np.ndarray) -> bytes:
            assert x.dtype == np.int16 and x.ndim == 1
            return x.tobytes()

        self.root.after(0, lambda: self.voice_status_var.set("Voice: Loading SER model..."))
        try:
            if self.ser_pipeline is None:
                self.ser_pipeline = pipeline("audio-classification", model="superb/wav2vec2-base-superb-er")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Voice Error", f"Failed to load SER model: {e}"))
            self.root.after(0, lambda: self._set_voice_state(running=False, loading=False))
            self.voice_running = False
            return

        self.root.after(0, lambda: self._set_voice_state(running=True, loading=False))
        self.root.after(0, lambda: self.voice_status_var.set("Voice: Listening (speak)…"))

        vad = webrtcvad.Vad(AGGR)
        audio_q: "queue.Queue[bytes]" = queue.Queue()
        window = collections.deque(maxlen=SMOOTH_N)

        def segmenter():
            ring = []
            voiced_ms = 0
            silence_ms = 0
            while True:
                frame = yield
                is_voiced = vad.is_speech(frame, SR)
                if is_voiced:
                    ring.append(frame)
                    voiced_ms += FRAME_MS
                    silence_ms = 0
                    if voiced_ms >= MAX_SEG_MS:
                        audio_q.put(b"".join(ring))
                        ring.clear(); voiced_ms = 0; silence_ms = 0
                else:
                    if ring:
                        silence_ms += FRAME_MS
                        should_flush = (voiced_ms >= MIN_SEG_MS and silence_ms >= SILENCE_TAIL_MS) or (voiced_ms >= MAX_SEG_MS)
                        if should_flush:
                            audio_q.put(b"".join(ring))
                            ring.clear(); voiced_ms = 0; silence_ms = 0

        seg = segmenter()
        next(seg)

        def on_audio(indata, frames, time_info, status):
            if not self.voice_running:
                return
            mono = indata[:, 0] if indata.ndim > 1 else indata
            i16 = np.clip(mono * 32768.0, -32768, 32767).astype(np.int16)
            start = 0
            while start + FRAME_SAMPLES <= len(i16):
                frame = i16[start:start+FRAME_SAMPLES]
                try:
                    seg.send(to_bytes_i16(frame))
                except StopIteration:
                    break
                start += FRAME_SAMPLES

        try:
            with sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                                blocksize=FRAME_SAMPLES, callback=on_audio):
                while self.voice_running:
                    try:
                        seg_bytes = audio_q.get(timeout=0.2)
                    except Exception:
                        continue
                    try:
                        seg_i16 = np.frombuffer(seg_bytes, dtype=np.int16)
                        seg_f32 = seg_i16.astype(np.float32) / 32768.0
                        preds = self.ser_pipeline({"array": seg_f32, "sampling_rate": SR}, top_k=4)
                        top = preds[0]
                        raw_label = top["label"].lower()
                        score_pct = float(top["score"]) * 100.0

                        window.append(raw_label)
                        smoothed = max(set(window), key=window.count)

                        overlay_text = f"VOICE: {raw_label.upper()} ({score_pct:.1f}%)"
                        self.voice_latest_text = overlay_text
                        ts = datetime.now()
                        log_line = f"{ts.strftime('%H:%M:%S')} - {raw_label.upper()}: {score_pct:.1f}% [VOICE]"
                        self.root.after(0, lambda s=log_line: self.voice_detections.insert(0, s))
                        if self.voice_detections.size() > self.voice_list_max:
                            self.root.after(0, lambda: self.voice_detections.delete(tk.END))
                        self.root.after(0, lambda: self.voice_status_var.set(f"Voice: {smoothed}"))

                        try:
                            fname = f"audio/voice_{ts.strftime('%Y%m%d_%H%M%S_%f')}.wav"
                            with wave.open(fname, "wb") as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(SR)
                                wf.writeframes(seg_bytes)
                            # Save into DB as capture_type='voice' so it appears in filters/history
                            self.db_manager.save_detection(
                                ts.isoformat(), raw_label, score_pct,
                                snapshot_path=fname,
                                face_crop_path=None, face_region=None,
                                capture_type='voice', person_id="voice", session_id=self.session_id
                            )
                        except Exception as e:
                            print(f"Voice save error: {e}")

                    except Exception as e:
                        print(f"Voice classify error: {e}")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Voice Error", f"Microphone/stream error: {e}"))

        self.voice_running = False
        self.root.after(0, lambda: self._set_voice_state(running=False, loading=False))
        self.voice_latest_text = ""

    # -------------------- Run / Close --------------------
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        if self.is_running:
            self.stop_detection()
        if self.voice_running:
            self.stop_voice()
            time.sleep(0.3)
        # Cancel auto-refresh timer if any
        if self._history_refresh_job is not None:
            try:
                self.root.after_cancel(self._history_refresh_job)
            except Exception:
                pass
        self.root.destroy()

# -------------------- Main Application Entry Point --------------------
def main():
    print("Starting Enhanced Emotion Detection System with Voice SER and Database Migration...")
    db_manager = DatabaseManager()
    login_window = LoginWindow(db_manager)
    success, username = login_window.show()
    if success:
        print(f"Login successful for user: {username}")
        app = EmotionDetectionSystem(username)
        app.run()
    else:
        print("Login cancelled or failed")

if __name__ == "__main__":
    main()
