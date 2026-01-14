#!/usr/bin/env python3
"""
Medical Portfolio System with Enhanced Message Management
Complete system with read/unread tracking and reply management
"""

import os
import sys
import json
import sqlite3
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# Third-party imports
try:
    from flask import Flask, request, jsonify, send_from_directory, render_template_string
    from flask_cors import CORS
    from werkzeug.security import generate_password_hash, check_password_hash
    from werkzeug.utils import secure_filename
    import jwt
except ImportError as e:
    print("Missing dependencies. Installing required packages...")
    import subprocess
    
    packages = [
        "flask==2.3.3",
        "flask-cors==4.0.0",
        "werkzeug==2.3.7",
        "pyjwt==2.8.0",
        "python-dotenv==1.0.0"
    ]
    
    for package in packages:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    # Try imports again
    from flask import Flask, request, jsonify, send_from_directory, render_template_string
    from flask_cors import CORS
    from werkzeug.security import generate_password_hash, check_password_hash
    from werkzeug.utils import secure_filename
    import jwt

# ==================== DATABASE MODELS ====================

@dataclass
class Client:
    """Client/Contact submission model"""
    id: int = 0
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    project_type: str = ""
    message: str = ""
    status: str = "new"  # new, contacted, in_progress, completed, archived
    created_at: str = ""
    read_by_admin: bool = False
    admin_notes: str = ""
    replied_by_admin: bool = False
    reply_date: str = ""
    reply_content: str = ""
    reply_admin: str = ""
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'project_type': self.project_type,
            'message': self.message,
            'status': self.status,
            'created_at': self.created_at,
            'read_by_admin': self.read_by_admin,
            'admin_notes': self.admin_notes,
            'replied_by_admin': self.replied_by_admin,
            'reply_date': self.reply_date,
            'reply_content': self.reply_content,
            'reply_admin': self.reply_admin
        }

@dataclass
class WebsiteContent:
    """Website content storage model"""
    section: str = ""
    content: str = ""
    updated_at: str = ""
    
    def to_dict(self):
        return {
            'section': self.section,
            'content': self.content,
            'updated_at': self.updated_at
        }

@dataclass 
class AdminUser:
    """Admin user model"""
    id: int = 0
    username: str = ""
    password_hash: str = ""
    created_at: str = ""
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at
        }

# ==================== DATABASE MANAGER ====================

class DatabaseManager:
    """SQLite database manager with enhanced message tracking"""
    
    def __init__(self, db_path="medical_portfolio.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database with required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create clients table with enhanced columns
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                address TEXT,
                project_type TEXT,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                read_by_admin BOOLEAN DEFAULT 0,
                admin_notes TEXT DEFAULT '',
                replied_by_admin BOOLEAN DEFAULT 0,
                reply_date TEXT,
                reply_content TEXT DEFAULT '',
                reply_admin TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create website_content table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS website_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create admin_users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create email_templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                is_default BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create default admin if not exists
        cursor.execute("SELECT COUNT(*) FROM admin_users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            password_hash = generate_password_hash("admin9048")
            cursor.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                ('admin', password_hash)
            )
        
        # Insert default email templates
        default_templates = [
            ('initial_reply', 'Thank you for contacting Dr. Foscah Faith', 
             '''Dear {name},

Thank you for reaching out to me. I have received your message regarding {project_type}.

I will review your inquiry and get back to you within 24-48 hours.

Best regards,
Dr. Foscah Faith
Medical Consultant & Health Tech Specialist''', 1),
            
            ('follow_up', 'Follow-up on your inquiry', 
             '''Dear {name},

I wanted to follow up on your recent inquiry about {project_type}. 

{follow_up_text}

Please let me know if you have any further questions.

Best regards,
Dr. Foscah Faith''', 0),
            
            ('project_accepted', 'Project Discussion - Next Steps',
             '''Dear {name},

Thank you for your interest in working together on {project_type}.

I would like to schedule a call to discuss your project in more detail. Please let me know what times work best for you next week.

Looking forward to our conversation.

Best regards,
Dr. Foscah Faith''', 0)
        ]
        
        for name, subject, body, is_default in default_templates:
            cursor.execute('SELECT COUNT(*) FROM email_templates WHERE name = ?', (name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO email_templates (name, subject, body, is_default)
                    VALUES (?, ?, ?, ?)
                ''', (name, subject, body, is_default))
        
        # Insert default website content if not exists
        default_content = {
            'hero': json.dumps({
                'title': 'Medical expertise for digital health.',
                'text': 'I help health tech companies and healthcare organizations communicate clearly, build trust, and translate complex medical concepts into content that works.'
            }),
            'doctor': json.dumps({
                'name': 'Dr. Foscah Faith',
                'specialty': 'Medical Consultant & Health Tech Specialist'
            }),
            'contact_intro': 'I work with health tech companies, digital health platforms, healthcare organizations, and individual practitioners who need clear, accurate, and effective medical content.',
            'about_section': json.dumps({
                'title': 'From Clinical Training to Digital Health',
                'content': [
                    'I trained as a doctor because I wanted to help people make better health decisions. But I realized the biggest impact I could make wasn\'t in a single clinic—it was in how health information gets communicated at scale.',
                    'After completing medical school, I chose a different path: building a career at the intersection of medicine, technology, and communication. I work remotely with health tech startups, digital health platforms, and healthcare organizations to create content that\'s medically accurate, easy to understand, and built for real people.',
                    '<strong>What I bring:</strong> I understand clinical workflows, regulatory concerns, and how patients think. I also understand how digital products work, how content drives trust, and how to communicate with non-clinical teams.',
                    'I\'ve worked as a freelancer across platforms like Upwork and Fiverr, helping clients with everything from patient education to product documentation. I\'ve also built and operated my own businesses—from managing a short-term rental to running a cross-border shopping service—which taught me how to execute, iterate, and deliver on my own.',
                    '<strong>What I care about:</strong> Clarity over complexity. Execution over theory. Building things that work.',
                    'I\'m not a clinician anymore, and I\'m not a researcher. I\'m someone who knows medicine deeply enough to translate it into something useful for everyone else.'
                ]
            }),
            'services': json.dumps([
                {
                    'title': 'Medical & Healthcare Writing',
                    'description': 'Patient education content, condition explainers, treatment guides, health blog posts, and clinical summaries written for non-clinical audiences.',
                    'for': 'Telehealth platforms, wellness apps, healthtech startups, and healthcare providers building digital patient experiences.'
                },
                {
                    'title': 'Health Tech Content & Product Communication',
                    'description': 'Product explainers, feature documentation, onboarding content, help center articles, and internal clinical content for non-clinical teams.',
                    'for': 'Health tech founders, product managers, and marketing teams who need to explain complex features simply.'
                },
                {
                    'title': 'Clinical Accuracy Review',
                    'description': 'Review of existing health content for medical accuracy, safety, and compliance. Includes flagging errors, rewriting problematic sections, and creating content guidelines.',
                    'for': 'Apps, platforms, or publications releasing health-related content who need clinical oversight without hiring a full-time clinician.'
                },
                {
                    'title': 'Healthcare Education Content',
                    'description': 'Training materials, e-learning modules, clinical workflow documentation, and educational resources for patients, caregivers, or healthcare staff.',
                    'for': 'Healthcare organizations, EdTech platforms, and training programs that need accurate, accessible educational content.'
                }
            ])
        }
        
        for section, content in default_content.items():
            cursor.execute('SELECT COUNT(*) FROM website_content WHERE section = ?', (section,))
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO website_content (section, content)
                    VALUES (?, ?)
                ''', (section, content))
        
        conn.commit()
        conn.close()
    
    # Client operations
    def create_client(self, client_data: Dict) -> Tuple[bool, str, Optional[Client]]:
        """Create a new client submission"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO clients (name, email, phone, address, project_type, message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                client_data['name'],
                client_data['email'],
                client_data.get('phone', ''),
                client_data.get('address', ''),
                client_data.get('project_type', ''),
                client_data['message']
            ))
            
            client_id = cursor.lastrowid
            
            # Get the created client
            cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
            row = cursor.fetchone()
            
            conn.commit()
            conn.close()
            
            if row:
                client = self._row_to_client(row)
                return True, "Client created successfully", client
            
            return False, "Failed to create client", None
            
        except Exception as e:
            return False, str(e), None
    
    def _row_to_client(self, row) -> Client:
        """Convert a database row to Client object"""
        return Client(
            id=row['id'],
            name=row['name'],
            email=row['email'],
            phone=row['phone'] or '',
            address=row['address'] or '',
            project_type=row['project_type'] or '',
            message=row['message'],
            status=row['status'],
            created_at=row['created_at'],
            read_by_admin=bool(row['read_by_admin']),
            admin_notes=row['admin_notes'] or '',
            replied_by_admin=bool(row['replied_by_admin']),
            reply_date=row['reply_date'] or '',
            reply_content=row['reply_content'] or '',
            reply_admin=row['reply_admin'] or ''
        )
    
    def get_clients(self, filter_type: str = None) -> List[Client]:
        """Get clients with various filters"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM clients'
        params = []
        conditions = []
        
        if filter_type:
            if filter_type == 'unread':
                conditions.append('read_by_admin = 0')
            elif filter_type == 'read':
                conditions.append('read_by_admin = 1')
            elif filter_type == 'replied':
                conditions.append('replied_by_admin = 1')
            elif filter_type == 'not_replied':
                conditions.append('replied_by_admin = 0 AND read_by_admin = 1')
            elif filter_type in ['new', 'contacted', 'in_progress', 'completed', 'archived']:
                conditions.append('status = ?')
                params.append(filter_type)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        
        clients = []
        for row in cursor.fetchall():
            clients.append(self._row_to_client(row))
        
        conn.close()
        return clients
    
    def get_client(self, client_id: int) -> Optional[Client]:
        """Get a specific client by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return self._row_to_client(row)
        return None
    
    def update_client_status(self, client_id: int, status: str, admin_name: str = "") -> Tuple[bool, str]:
        """Update client status"""
        valid_statuses = ['new', 'contacted', 'in_progress', 'completed', 'archived']
        if status not in valid_statuses:
            return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Auto-mark as read when status changes
            cursor.execute('''
                UPDATE clients 
                SET status = ?, read_by_admin = 1 
                WHERE id = ?
            ''', (status, client_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Client not found"
            
            # Add admin note about status change
            if admin_name:
                cursor.execute('''
                    UPDATE clients 
                    SET admin_notes = admin_notes || ? 
                    WHERE id = ?
                ''', (f"\n\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Status changed to '{status}' by {admin_name}", client_id))
            
            conn.commit()
            conn.close()
            return True, "Status updated successfully"
            
        except Exception as e:
            return False, str(e)
    
    def mark_client_as_read(self, client_id: int, admin_notes: str = "", admin_name: str = "") -> Tuple[bool, str]:
        """Mark a client message as read by admin"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE clients 
                SET read_by_admin = 1,
                    admin_notes = CASE 
                        WHEN admin_notes = '' THEN ? 
                        ELSE admin_notes || ?
                    END
                WHERE id = ?
            ''', (admin_notes, f"\n\n{admin_notes}" if admin_notes else "", client_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Client not found"
            
            conn.commit()
            conn.close()
            return True, "Client marked as read"
            
        except Exception as e:
            return False, str(e)
    
    def mark_client_as_replied(self, client_id: int, reply_content: str, admin_name: str) -> Tuple[bool, str]:
        """Mark a client message as replied"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE clients 
                SET replied_by_admin = 1,
                    reply_date = ?,
                    reply_content = ?,
                    reply_admin = ?,
                    read_by_admin = 1
                WHERE id = ?
            ''', (datetime.now().isoformat(), reply_content, admin_name, client_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Client not found"
            
            conn.commit()
            conn.close()
            return True, "Client marked as replied"
            
        except Exception as e:
            return False, str(e)
    
    def update_reply(self, client_id: int, reply_content: str, admin_name: str) -> Tuple[bool, str]:
        """Update or add reply to client"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE clients 
                SET replied_by_admin = 1,
                    reply_date = ?,
                    reply_content = ?,
                    reply_admin = ?,
                    read_by_admin = 1
                WHERE id = ?
            ''', (datetime.now().isoformat(), reply_content, admin_name, client_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Client not found"
            
            conn.commit()
            conn.close()
            return True, "Reply updated successfully"
            
        except Exception as e:
            return False, str(e)
    
    def mark_all_as_read(self, admin_name: str = "") -> Tuple[bool, str]:
        """Mark all unread client messages as read"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE clients 
                SET read_by_admin = 1,
                    admin_notes = CASE 
                        WHEN admin_notes = '' THEN ? 
                        ELSE admin_notes || ?
                    END
                WHERE read_by_admin = 0
            ''', (
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Marked as read by {admin_name}" if admin_name else "Marked as read",
                f"\n\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Marked as read by {admin_name}" if admin_name else "\n\nMarked as read"
            ))
            
            updated_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            return True, f"Marked {updated_count} messages as read"
            
        except Exception as e:
            return False, str(e)
    
    def delete_client(self, client_id: int) -> Tuple[bool, str]:
        """Delete a client"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM clients WHERE id = ?', (client_id,))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Client not found"
            
            conn.commit()
            conn.close()
            return True, "Client deleted successfully"
            
        except Exception as e:
            return False, str(e)
    
    def get_message_counts(self) -> Dict[str, int]:
        """Get counts of different message types"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        counts = {}
        
        # Total messages
        cursor.execute('SELECT COUNT(*) FROM clients')
        counts['total'] = cursor.fetchone()[0]
        
        # Unread messages
        cursor.execute('SELECT COUNT(*) FROM clients WHERE read_by_admin = 0')
        counts['unread'] = cursor.fetchone()[0]
        
        # Read messages
        cursor.execute('SELECT COUNT(*) FROM clients WHERE read_by_admin = 1')
        counts['read'] = cursor.fetchone()[0]
        
        # Replied messages
        cursor.execute('SELECT COUNT(*) FROM clients WHERE replied_by_admin = 1')
        counts['replied'] = cursor.fetchone()[0]
        
        # Read but not replied
        cursor.execute('SELECT COUNT(*) FROM clients WHERE read_by_admin = 1 AND replied_by_admin = 0')
        counts['read_not_replied'] = cursor.fetchone()[0]
        
        # Status counts
        cursor.execute('SELECT status, COUNT(*) FROM clients GROUP BY status')
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        counts.update(status_counts)
        
        conn.close()
        return counts
    
    def get_recent_clients(self, limit: int = 50) -> List[Client]:
        """Get most recent client submissions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM clients ORDER BY created_at DESC LIMIT ?', (limit,))
        
        clients = []
        for row in cursor.fetchall():
            clients.append(self._row_to_client(row))
        
        conn.close()
        return clients
    
    # Website content operations
    def get_website_content(self) -> Dict[str, WebsiteContent]:
        """Get all website content"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT section, content, updated_at FROM website_content')
        
        content = {}
        for row in cursor.fetchall():
            content[row['section']] = WebsiteContent(
                section=row['section'],
                content=row['content'],
                updated_at=row['updated_at']
            )
        
        conn.close()
        return content
    
    def save_website_content(self, content_data: Dict[str, str]) -> Tuple[bool, str]:
        """Save website content"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            for section, content in content_data.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO website_content (section, content)
                    VALUES (?, ?)
                ''', (section, content))
            
            conn.commit()
            conn.close()
            return True, "Content saved successfully"
            
        except Exception as e:
            return False, str(e)
    
    # Email template operations
    def get_email_templates(self) -> List[Dict]:
        """Get all email templates"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, subject, body, is_default FROM email_templates ORDER BY name')
        
        templates = []
        for row in cursor.fetchall():
            templates.append({
                'id': row['id'],
                'name': row['name'],
                'subject': row['subject'],
                'body': row['body'],
                'is_default': bool(row['is_default'])
            })
        
        conn.close()
        return templates
    
    def get_email_template(self, template_id: int) -> Optional[Dict]:
        """Get specific email template"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name, subject, body, is_default FROM email_templates WHERE id = ?', (template_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'subject': row['subject'],
                'body': row['body'],
                'is_default': bool(row['is_default'])
            }
        return None
    
    def save_email_template(self, template_data: Dict) -> Tuple[bool, str]:
        """Save email template"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            template_id = template_data.get('id')
            
            if template_id:
                cursor.execute('''
                    UPDATE email_templates 
                    SET name = ?, subject = ?, body = ?
                    WHERE id = ?
                ''', (template_data['name'], template_data['subject'], template_data['body'], template_id))
            else:
                cursor.execute('''
                    INSERT INTO email_templates (name, subject, body)
                    VALUES (?, ?, ?)
                ''', (template_data['name'], template_data['subject'], template_data['body']))
            
            conn.commit()
            conn.close()
            return True, "Template saved successfully"
            
        except Exception as e:
            return False, str(e)
    
    def delete_email_template(self, template_id: int) -> Tuple[bool, str]:
        """Delete email template"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM email_templates WHERE id = ? AND is_default = 0', (template_id,))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Template not found or is default"
            
            conn.commit()
            conn.close()
            return True, "Template deleted successfully"
            
        except Exception as e:
            return False, str(e)
    
    # Admin user operations
    def authenticate_admin(self, username: str, password: str) -> Tuple[bool, str, Optional[AdminUser]]:
        """Authenticate admin user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM admin_users WHERE username = ?', (username,))
        row = cursor.fetchone()
        
        conn.close()
        
        if not row:
            return False, "Invalid credentials", None
        
        if not check_password_hash(row['password_hash'], password):
            return False, "Invalid credentials", None
        
        admin = AdminUser(
            id=row['id'],
            username=row['username'],
            password_hash=row['password_hash'],
            created_at=row['created_at']
        )
        
        return True, "Authentication successful", admin
    
    def change_admin_password(self, username: str, current_password: str, new_password: str) -> Tuple[bool, str]:
        """Change admin password"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT password_hash FROM admin_users WHERE username = ?', (username,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False, "User not found"
        
        if not check_password_hash(row['password_hash'], current_password):
            conn.close()
            return False, "Current password is incorrect"
        
        new_password_hash = generate_password_hash(new_password)
        cursor.execute('UPDATE admin_users SET password_hash = ? WHERE username = ?', 
                      (new_password_hash, username))
        
        conn.commit()
        conn.close()
        return True, "Password updated successfully"

# ==================== EMAIL MANAGER ====================

class EmailManager:
    """Email sending manager"""
    
    def __init__(self, smtp_server: str = None, smtp_port: int = None, 
                 username: str = None, password: str = None):
        self.smtp_server = smtp_server or "smtp.gmail.com"
        self.smtp_port = smtp_port or 587
        self.username = username
        self.password = password
        self.enabled = bool(username and password)
    
    def send_email(self, to_email: str, subject: str, body: str, from_name: str = "Dr. Foscah Faith") -> Tuple[bool, str]:
        """Send an email"""
        if not self.enabled:
            return False, "Email sending is not configured"
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{from_name} <{self.username}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            return True, "Email sent successfully"
            
        except Exception as e:
            return False, str(e)
    
    def send_template_email(self, to_email: str, template_body: str, client_data: Dict, 
                           from_name: str = "Dr. Foscah Faith") -> Tuple[bool, str]:
        """Send email using template with client data"""
        # Format template with client data
        formatted_body = template_body.format(
            name=client_data.get('name', ''),
            email=client_data.get('email', ''),
            project_type=client_data.get('project_type', 'your project'),
            message=client_data.get('message', ''),
            phone=client_data.get('phone', ''),
            address=client_data.get('address', '')
        )
        
        # Extract subject from template (first line)
        lines = formatted_body.strip().split('\n')
        subject = lines[0] if lines else "Message from Dr. Foscah Faith"
        
        return self.send_email(to_email, subject, formatted_body, from_name)

# ==================== AUTHENTICATION MANAGER ====================

class AuthManager:
    """JWT authentication manager"""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.algorithm = "HS256"
    
    def create_token(self, admin_data: Dict) -> str:
        """Create JWT token"""
        payload = {
            'admin': admin_data,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Tuple[bool, Any]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return True, payload.get('admin')
        except jwt.ExpiredSignatureError:
            return False, "Token has expired"
        except jwt.InvalidTokenError:
            return False, "Invalid token"
    
    def get_auth_header(self) -> Optional[str]:
        """Get authorization header from request"""
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]
        return None

# ==================== FLASK APPLICATION ====================

class MedicalPortfolioApp:
    """Main Flask application with enhanced message management"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = secrets.token_hex(32)
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
        
        # Enable CORS
        CORS(self.app)
        
        # Initialize managers
        self.db = DatabaseManager()
        self.auth = AuthManager(self.app.config['SECRET_KEY'])
        
        # Initialize email manager (configure via environment variables)
        self.email = EmailManager(
            username=os.environ.get('SMTP_USERNAME'),
            password=os.environ.get('SMTP_PASSWORD'),
            smtp_server=os.environ.get('SMTP_SERVER'),
            smtp_port=int(os.environ.get('SMTP_PORT', 587))
        )
        
        # Register routes
        self.register_routes()
        
        # Create static directory for uploaded files
        os.makedirs('static/uploads', exist_ok=True)
    
    def register_routes(self):
        """Register all application routes"""
        
        # ========== API ROUTES ==========
        
        # Health check
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'Medical Portfolio API',
                'features': ['read_tracking', 'reply_tracking', 'email_templates']
            })
        
        # Admin authentication
        @self.app.route('/api/admin/login', methods=['POST'])
        def admin_login():
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return jsonify({'error': 'Username and password required'}), 400
            
            success, message, admin = self.db.authenticate_admin(username, password)
            
            if not success:
                return jsonify({'error': message}), 401
            
            token = self.auth.create_token(admin.to_dict())
            
            return jsonify({
                'access_token': token,
                'admin': admin.to_dict(),
                'message': 'Login successful'
            })
        
        @self.app.route('/api/admin/change-password', methods=['POST'])
        def change_password():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            if not current_password or not new_password:
                return jsonify({'error': 'Both passwords are required'}), 400
            
            success, message = self.db.change_admin_password(
                admin_data['username'], 
                current_password, 
                new_password
            )
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({'message': message})
        
        # Client management
        @self.app.route('/api/clients', methods=['POST'])
        def create_client():
            data = request.get_json()
            
            # Validation
            required_fields = ['name', 'email', 'message']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'error': f'{field} is required'}), 400
            
            # Email validation
            if '@' not in data['email'] or '.' not in data['email']:
                return jsonify({'error': 'Please enter a valid email address'}), 400
            
            success, message, client = self.db.create_client(data)
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({
                'message': 'Thank you for your message! We will contact you soon.',
                'client': client.to_dict()
            }), 201
        
        # Get message counts
        @self.app.route('/api/admin/message-counts', methods=['GET'])
        def get_message_counts():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            counts = self.db.get_message_counts()
            return jsonify(counts)
        
        @self.app.route('/api/admin/clients', methods=['GET'])
        def get_clients():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            filter_type = request.args.get('filter', 'all')
            
            clients = self.db.get_clients(filter_type)
            
            return jsonify([client.to_dict() for client in clients])
        
        @self.app.route('/api/admin/clients/<int:client_id>', methods=['GET'])
        def get_client(client_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            client = self.db.get_client(client_id)
            if not client:
                return jsonify({'error': 'Client not found'}), 404
            
            return jsonify(client.to_dict())
        
        @self.app.route('/api/admin/clients/<int:client_id>/status', methods=['PUT'])
        def update_client_status(client_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            new_status = data.get('status')
            
            if not new_status:
                return jsonify({'error': 'Status is required'}), 400
            
            success, message = self.db.update_client_status(client_id, new_status, admin_data['username'])
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({'message': message})
        
        # Mark client as read
        @self.app.route('/api/admin/clients/<int:client_id>/read', methods=['PUT'])
        def mark_client_as_read(client_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            admin_notes = data.get('admin_notes', '')
            
            success, message = self.db.mark_client_as_read(client_id, admin_notes, admin_data['username'])
            
            if not success:
                return jsonify({'error': message}), 404
            
            return jsonify({'message': message})
        
        # Mark client as replied
        @self.app.route('/api/admin/clients/<int:client_id>/reply', methods=['PUT'])
        def mark_client_as_replied(client_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            reply_content = data.get('reply_content', '')
            
            if not reply_content:
                return jsonify({'error': 'Reply content is required'}), 400
            
            success, message = self.db.mark_client_as_replied(client_id, reply_content, admin_data['username'])
            
            if not success:
                return jsonify({'error': message}), 404
            
            return jsonify({'message': message})
        
        # Send email reply
        @self.app.route('/api/admin/clients/<int:client_id>/send-reply', methods=['POST'])
        def send_client_reply(client_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            reply_content = data.get('reply_content', '')
            template_id = data.get('template_id')
            
            if not reply_content:
                return jsonify({'error': 'Reply content is required'}), 400
            
            # Get client data
            client = self.db.get_client(client_id)
            if not client:
                return jsonify({'error': 'Client not found'}), 404
            
            # Send email
            if self.email.enabled:
                success, message = self.email.send_email(
                    client.email,
                    f"Re: Your inquiry to Dr. Foscah Faith",
                    reply_content
                )
                
                if not success:
                    return jsonify({'error': f'Failed to send email: {message}'}), 500
            else:
                # If email not configured, just save the reply
                pass
            
            # Mark as replied in database
            success, message = self.db.mark_client_as_replied(client_id, reply_content, admin_data['username'])
            
            if not success:
                return jsonify({'error': message}), 500
            
            return jsonify({
                'message': 'Reply sent successfully' if self.email.enabled else 'Reply saved (email not configured)',
                'email_sent': self.email.enabled
            })
        
        # Mark all as read
        @self.app.route('/api/admin/clients/mark-all-read', methods=['PUT'])
        def mark_all_as_read():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            success, message = self.db.mark_all_as_read(admin_data['username'])
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({'message': message})
        
        @self.app.route('/api/admin/clients/<int:client_id>', methods=['DELETE'])
        def delete_client(client_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            success, message = self.db.delete_client(client_id)
            
            if not success:
                return jsonify({'error': message}), 404
            
            return jsonify({'message': message})
        
        # Email templates
        @self.app.route('/api/admin/email-templates', methods=['GET'])
        def get_email_templates():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            templates = self.db.get_email_templates()
            return jsonify(templates)
        
        @self.app.route('/api/admin/email-templates/<int:template_id>', methods=['GET'])
        def get_email_template(template_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            template = self.db.get_email_template(template_id)
            if not template:
                return jsonify({'error': 'Template not found'}), 404
            
            return jsonify(template)
        
        @self.app.route('/api/admin/email-templates', methods=['POST'])
        def save_email_template():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            
            if not data.get('name') or not data.get('subject') or not data.get('body'):
                return jsonify({'error': 'Name, subject and body are required'}), 400
            
            success, message = self.db.save_email_template(data)
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({'message': message})
        
        @self.app.route('/api/admin/email-templates/<int:template_id>', methods=['DELETE'])
        def delete_email_template(template_id):
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            success, message = self.db.delete_email_template(template_id)
            
            if not success:
                return jsonify({'error': message}), 404
            
            return jsonify({'message': message})
        
        # Website content
        @self.app.route('/api/content', methods=['GET'])
        def get_content():
            content = self.db.get_website_content()
            content_dict = {}
            
            for section, content_obj in content.items():
                try:
                    content_dict[section] = json.loads(content_obj.content)
                except:
                    content_dict[section] = content_obj.content
            
            return jsonify(content_dict)
        
        @self.app.route('/api/admin/content', methods=['POST'])
        def save_content():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            data = request.get_json()
            
            if not isinstance(data, dict):
                return jsonify({'error': 'Content must be a JSON object'}), 400
            
            # Convert dict/list values to JSON strings
            content_to_save = {}
            for section, content in data.items():
                if isinstance(content, (dict, list)):
                    content_to_save[section] = json.dumps(content)
                else:
                    content_to_save[section] = str(content)
            
            success, message = self.db.save_website_content(content_to_save)
            
            if not success:
                return jsonify({'error': message}), 400
            
            return jsonify({'message': message})
        
        # File upload
        @self.app.route('/api/upload/photo', methods=['POST'])
        def upload_photo():
            token = self.auth.get_auth_header()
            if not token:
                return jsonify({'error': 'Authentication required'}), 401
            
            success, admin_data = self.auth.verify_token(token)
            if not success:
                return jsonify({'error': admin_data}), 401
            
            if 'photo' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['photo']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            if file:
                filename = secure_filename(f"doctor_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
                filepath = os.path.join('static/uploads', filename)
                file.save(filepath)
                
                # Return the URL for the uploaded file
                photo_url = f"/static/uploads/{filename}"
                return jsonify({
                    'message': 'Photo uploaded successfully',
                    'photo_url': photo_url
                })
        
        # ========== FRONTEND ROUTES ==========
        
        # Main website
        @self.app.route('/')
        @self.app.route('/<path:path>')
        def serve_frontend(path=''):
            """Serve the HTML frontend"""
            return render_template_string(HTML_TEMPLATE)
        
        # Static files
        @self.app.route('/static/<path:filename>')
        def serve_static(filename):
            return send_from_directory('static', filename)
    
    def run(self, host='0.0.0.0', port=5000, debug=True):
        """Run the Flask application"""
        print("\n" + "="*60)
        print("MEDICAL PORTFOLIO SYSTEM - ENHANCED MESSAGE MANAGEMENT")
        print("="*60)
        print("\nStarting server...")
        print(f"• Website URL: http://localhost:{port}")
        print(f"• API Base URL: http://localhost:{port}/api")
        print(f"• Health Check: http://localhost:{port}/api/health")
        print("\nADMIN ACCESS:")
        print("• Click on the doctor's name in top-left corner")
        print("• Username: admin")
        print("• Password: admin9048")
        print("\nNEW FEATURES:")
        print("• Track read/unread messages")
        print("• Track replied/not replied messages")
        print("• Email templates for quick replies")
        print("• Send email replies directly from admin panel")
        print("\n" + "="*60)
        
        self.app.run(host=host, port=port, debug=debug)

# ==================== HTML TEMPLATE ====================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical Portfolio | Dr. Foscah Faith</title>
    <style>
        /* Keep all your existing CSS styles here - they remain the same */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
            color: #2C3E50;
            line-height: 1.6;
            background: #F8FBFF;
        }
        
        /* Admin Panel */
        .admin-panel {
            position: fixed;
            top: 0;
            right: 0;
            width: 350px;
            background: #FFFFFF;
            padding: 1rem;
            border-left: 2px solid #3498db;
            border-bottom: 2px solid #3498db;
            z-index: 9999;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            max-height: 100vh;
            overflow-y: auto;
            box-shadow: -2px 2px 10px rgba(52, 152, 219, 0.1);
        }
        
        .admin-panel.open {
            transform: translateX(0);
        }
        
        /* Admin Name Tag in Header */
        .admin-name-tag {
            cursor: pointer;
            position: relative;
            display: inline-block;
            transition: all 0.3s;
            padding: 5px 15px;
            border-radius: 5px;
        }
        
        .admin-name-tag:hover {
            background: rgba(52, 152, 219, 0.1);
            transform: translateY(-2px);
        }
        
        .admin-name-tag.active {
            background: rgba(52, 152, 219, 0.15);
            box-shadow: 0 0 15px rgba(52, 152, 219, 0.2);
            border: 1px solid #3498db;
        }
        
        .admin-name-tag .admin-indicator {
            font-size: 0.7rem;
            color: #3498db;
            margin-left: 5px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        
        .admin-name-tag:hover .admin-indicator,
        .admin-name-tag.active .admin-indicator {
            opacity: 1;
        }
        
        .admin-name-tag .notification-badge {
            display: inline-block;
            width: 20px;
            height: 20px;
            background: #e74c3c;
            color: white;
            border-radius: 50%;
            margin-left: 8px;
            font-size: 0.7rem;
            line-height: 20px;
            text-align: center;
            font-weight: bold;
            vertical-align: middle;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        
        .admin-section {
            background: #F8FBFF;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 5px;
            border: 1px solid #D4E6F1;
        }
        
        .admin-section h3 {
            color: #3498db;
            margin-bottom: 1rem;
            font-size: 1.1rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .admin-section h3 .badge {
            background: #3498db;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8rem;
        }
        
        .admin-input, .admin-textarea, .admin-select {
            width: 100%;
            padding: 0.5rem;
            margin-bottom: 0.5rem;
            background: #FFFFFF;
            border: 1px solid #BDC3C7;
            border-radius: 4px;
            color: #2C3E50;
            font-family: inherit;
        }
        
        .admin-textarea {
            min-height: 80px;
            resize: vertical;
        }
        
        .admin-btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
            margin-top: 0.5rem;
            transition: background 0.3s;
        }
        
        .admin-btn:hover {
            background: #2980b9;
        }
        
        .admin-btn-secondary {
            background: #ECF0F1;
            color: #3498db;
        }
        
        .admin-btn-secondary:hover {
            background: #D5DBDB;
        }
        
        .admin-btn-success {
            background: #27ae60;
            color: white;
        }
        
        .admin-btn-success:hover {
            background: #219653;
        }
        
        .admin-btn-warning {
            background: #f39c12;
            color: white;
        }
        
        .admin-btn-warning:hover {
            background: #e67e22;
        }
        
        .admin-btn-danger {
            background: #e74c3c;
            color: white;
        }
        
        .admin-btn-danger:hover {
            background: #c0392b;
        }
        
        .admin-login {
            text-align: center;
        }
        
        .admin-status {
            background: #3498db;
            color: white;
            padding: 0.5rem;
            border-radius: 4px;
            margin-bottom: 1rem;
            font-size: 0.9rem;
            text-align: center;
            font-weight: bold;
        }
        
        /* Message stats grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .stat-box {
            background: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
            border: 1px solid #E1ECF4;
        }
        
        .stat-box .count {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .stat-box .label {
            font-size: 0.8rem;
            color: #7F8C8D;
        }
        
        .stat-box.unread .count {
            color: #e74c3c;
        }
        
        .stat-box.read .count {
            color: #3498db;
        }
        
        .stat-box.replied .count {
            color: #27ae60;
        }
        
        .stat-box.not-replied .count {
            color: #f39c12;
        }
        
        /* Quick filter buttons */
        .filter-buttons {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 5px;
            margin-bottom: 15px;
        }
        
        .filter-btn {
            padding: 8px;
            border: none;
            border-radius: 4px;
            background: #ECF0F1;
            color: #2C3E50;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s;
        }
        
        .filter-btn:hover {
            background: #D5DBDB;
        }
        
        .filter-btn.active {
            background: #3498db;
            color: white;
        }
        
        .filter-btn.unread {
            border-left: 3px solid #e74c3c;
        }
        
        .filter-btn.read {
            border-left: 3px solid #3498db;
        }
        
        .filter-btn.replied {
            border-left: 3px solid #27ae60;
        }
        
        .filter-btn.not-replied {
            border-left: 3px solid #f39c12;
        }
        
        /* Remove dotted outlines by default, only show in edit mode */
        .content-editable {
            padding: 2px;
            border-radius: 3px;
            transition: all 0.3s;
            cursor: default;
        }
        
        body.edit-mode .content-editable {
            outline: 2px dashed rgba(52, 152, 219, 0.3);
            cursor: text;
            background: rgba(52, 152, 219, 0.05);
        }
        
        body.edit-mode .content-editable:hover {
            outline: 2px dashed #3498db;
            background: rgba(52, 152, 219, 0.1);
        }
        
        /* Header */
        header {
            background: #FFFFFF;
            padding: 1.5rem 2rem;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
            position: sticky;
            top: 0;
            z-index: 100;
            border-bottom: 1px solid #E1ECF4;
        }
        
        nav {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.3rem;
            font-weight: 600;
            color: #3498db;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        nav ul {
            list-style: none;
            display: flex;
            gap: 2rem;
        }
        
        nav a {
            text-decoration: none;
            color: #2C3E50;
            font-weight: 500;
            transition: color 0.3s;
        }
        
        nav a:hover {
            color: #3498db;
        }
        
        /* Hero Section - ENHANCED LAYOUT */
        .hero {
            background: linear-gradient(135deg, #E8F4F8 0%, #FFFFFF 100%);
            color: #2C3E50;
            padding: 4rem 2rem;
            text-align: center;
            border-bottom: 1px solid #E1ECF4;
            position: relative;
            overflow: hidden;
        }
        
        .hero::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at 20% 50%, rgba(52, 152, 219, 0.05) 0%, transparent 50%);
            pointer-events: none;
        }
        
        .hero-content {
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }
        
        .hero h1 {
            font-size: 3.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            line-height: 1.2;
            color: #2C3E50;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
        }
        
        /* Doctor Info Container - Placed between title and description */
        .doctor-info-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin: 2rem auto 3rem;
            max-width: 800px;
            gap: 1.5rem;
        }
        
        .doctor-photo-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1.5rem;
        }
        
        .doctor-photo {
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: linear-gradient(135deg, #3498db 0%, #E8F4F8 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            border: 4px solid #3498db;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            cursor: pointer;
            position: relative;
            transition: all 0.3s ease;
        }
        
        .doctor-photo:hover {
            transform: scale(1.05);
            box-shadow: 0 15px 40px rgba(52, 152, 219, 0.2);
            border-color: #2980b9;
        }
        
        .doctor-photo img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .photo-placeholder {
            font-size: 3rem;
            font-weight: 600;
            color: white;
        }
        
        .doctor-details {
            text-align: center;
            padding: 0 1rem;
        }
        
        .doctor-name {
            color: #3498db;
            font-size: 2.2rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            line-height: 1.2;
        }
        
        .doctor-specialty {
            color: #5D6D7E;
            font-size: 1.3rem;
            font-weight: 500;
            margin-bottom: 1rem;
        }
        
        .doctor-divider {
            width: 100px;
            height: 3px;
            background: #3498db;
            margin: 1rem auto;
            border-radius: 2px;
            opacity: 0.7;
        }
        
        .hero p {
            font-size: 1.3rem;
            margin: 3rem auto 2.5rem;
            opacity: 0.95;
            line-height: 1.7;
            color: #5D6D7E;
            max-width: 800px;
        }
        
        .cta-buttons {
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 2rem;
        }
        
        .btn {
            padding: 0.9rem 2rem;
            font-size: 1rem;
            font-weight: 500;
            border-radius: 6px;
            text-decoration: none;
            transition: all 0.3s;
            cursor: pointer;
            border: none;
        }
        
        .btn-primary {
            background: #3498db;
            color: white;
        }
        
        .btn-primary:hover {
            background: #2980b9;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(52, 152, 219, 0.2);
        }
        
        .btn-secondary {
            background: transparent;
            color: #3498db;
            border: 2px solid #3498db;
        }
        
        .btn-secondary:hover {
            background: rgba(52, 152, 219, 0.1);
            color: #3498db;
        }
        
        /* Features Section */
        .features {
            padding: 5rem 2rem;
            background: #FFFFFF;
        }
        
        .features-container {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 3rem;
        }
        
        .feature-card {
            background: #FFFFFF;
            padding: 2.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border: 1px solid #E1ECF4;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        
        .feature-card h3 {
            color: #2C3E50;
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }
        
        .feature-card p {
            color: #5D6D7E;
            font-size: 1.05rem;
        }
        
        /* About Section */
        .about-preview {
            padding: 5rem 2rem;
            background: #F8FBFF;
            border-top: 1px solid #E1ECF4;
            border-bottom: 1px solid #E1ECF4;
        }
        
        .about-container {
            max-width: 900px;
            margin: 0 auto;
        }
        
        .about-container h2 {
            color: #2C3E50;
            font-size: 2.5rem;
            margin-bottom: 2rem;
            text-align: center;
        }
        
        .about-content {
            display: grid;
            grid-template-columns: 200px 1fr;
            gap: 3rem;
            align-items: start;
        }
        
        /* Updated Profile Photo - Now a proper photo space */
        .profile-photo {
            width: 200px;
            height: 200px;
            background: linear-gradient(135deg, #3498db 0%, #E8F4F8 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            border: 4px solid #3498db;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            cursor: pointer;
            position: relative;
            transition: all 0.3s ease;
        }
        
        .profile-photo:hover {
            transform: scale(1.03);
            box-shadow: 0 12px 30px rgba(52, 152, 219, 0.15);
            border-color: #2980b9;
        }
        
        .profile-photo img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .profile-photo .photo-placeholder {
            font-size: 3rem;
            font-weight: 600;
            color: white;
        }
        
        .about-text p {
            margin-bottom: 1.5rem;
            font-size: 1.05rem;
            color: #5D6D7E;
        }
        
        .about-text strong {
            color: #3498db;
        }
        
        /* Portfolio Section */
        .portfolio {
            padding: 5rem 2rem;
            background: #FFFFFF;
        }
        
        .portfolio-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .portfolio h2 {
            color: #2C3E50;
            font-size: 2.5rem;
            margin-bottom: 3rem;
            text-align: center;
        }
        
        .project-card {
            background: #FFFFFF;
            padding: 2.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border: 1px solid #E1ECF4;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .project-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        
        .project-card h3 {
            color: #2C3E50;
            font-size: 1.6rem;
            margin-bottom: 1.5rem;
        }
        
        .project-section {
            margin-bottom: 1.2rem;
        }
        
        .project-section strong {
            color: #3498db;
            display: block;
            margin-bottom: 0.5rem;
        }
        
        .project-section p {
            color: #5D6D7E;
            font-size: 1.05rem;
        }
        
        /* Services Section */
        .services {
            padding: 5rem 2rem;
            background: #F8FBFF;
            border-top: 1px solid #E1ECF4;
            border-bottom: 1px solid #E1ECF4;
        }
        
        .services-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .services h2 {
            color: #2C3E50;
            font-size: 2.5rem;
            margin-bottom: 1rem;
            text-align: center;
        }
        
        .services-intro {
            text-align: center;
            color: #5D6D7E;
            font-size: 1.1rem;
            margin-bottom: 3rem;
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .services-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 2rem;
        }
        
        .service-card {
            background: #FFFFFF;
            padding: 2rem;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            border: 1px solid #E1ECF4;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .service-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        
        .service-card h3 {
            color: #2C3E50;
            font-size: 1.4rem;
            margin-bottom: 1rem;
        }
        
        .service-detail {
            margin-bottom: 1rem;
            font-size: 0.95rem;
        }
        
        .service-detail strong {
            color: #2C3E50;
            display: block;
            margin-bottom: 0.3rem;
        }
        
        .service-detail p {
            color: #5D6D7E;
        }
        
        /* Contact Section */
        .contact {
            padding: 5rem 2rem;
            background: #F8FBFF;
        }
        
        .contact-container {
            max-width: 700px;
            margin: 0 auto;
        }
        
        .contact h2 {
            color: #2C3E50;
            font-size: 2.5rem;
            margin-bottom: 1rem;
            text-align: center;
        }
        
        .contact-intro {
            text-align: center;
            color: #5D6D7E;
            font-size: 1.1rem;
            margin-bottom: 3rem;
        }
        
        .contact-form {
            background: #FFFFFF;
            padding: 2.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            border: 1px solid #E1ECF4;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: #2C3E50;
            font-weight: 500;
        }
        
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 0.8rem;
            background: #FFFFFF;
            border: 1px solid #BDC3C7;
            border-radius: 6px;
            font-size: 1rem;
            font-family: inherit;
            color: #2C3E50;
        }
        
        .form-group textarea {
            min-height: 150px;
            resize: vertical;
        }
        
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #3498db;
            box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.1);
        }
        
        /* Footer */
        footer {
            background: #FFFFFF;
            color: #7F8C8D;
            padding: 3rem 2rem;
            text-align: center;
            border-top: 1px solid #E1ECF4;
        }
        
        .footer-content {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-bottom: 1.5rem;
        }
        
        .footer-links a {
            color: #2C3E50;
            text-decoration: none;
            opacity: 0.9;
            transition: color 0.3s;
        }
        
        .footer-links a:hover {
            opacity: 1;
            color: #3498db;
        }
        
        /* Smooth scrolling */
        html {
            scroll-behavior: smooth;
        }
        
        /* Modal Styles - ENHANCED for new features */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow-y: auto;
        }
        
        .modal-content {
            background: #FFFFFF;
            border-radius: 10px;
            border: 2px solid #3498db;
            color: #2C3E50;
            max-width: 1200px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        .modal-header {
            padding: 20px;
            border-bottom: 1px solid #E1ECF4;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #F8FBFF;
            border-radius: 10px 10px 0 0;
        }
        
        .modal-body {
            padding: 20px;
        }
        
        .client-list {
            max-height: 500px;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        
        .client-item {
            padding: 15px;
            border: 1px solid #E1ECF4;
            margin-bottom: 10px;
            border-radius: 5px;
            background: #FFFFFF;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .client-item:hover {
            background: #F8FBFF;
            border-color: #3498db;
        }
        
        .client-item.unread {
            background: #FFF8E1;
            border-left: 4px solid #f39c12;
        }
        
        .client-item.replied {
            border-left: 4px solid #27ae60;
        }
        
        .client-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .client-item-name {
            font-weight: bold;
            color: #2C3E50;
            font-size: 1.1rem;
        }
        
        .client-item-date {
            color: #7F8C8D;
            font-size: 0.9rem;
        }
        
        .client-item-message {
            color: #5D6D7E;
            margin-top: 5px;
            font-size: 0.95rem;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            display: inline-block;
            cursor: pointer;
        }
        
        .status-new { background: #f39c12; color: white; }
        .status-contacted { background: #3498db; color: white; }
        .status-in_progress { background: #9b59b6; color: white; }
        .status-completed { background: #27ae60; color: white; }
        .status-archived { background: #95a5a6; color: white; }
        
        .read-badge {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 5px;
        }
        
        .read-badge.unread {
            background: #e74c3c;
        }
        
        .read-badge.read {
            background: #3498db;
        }
        
        .read-badge.replied {
            background: #27ae60;
        }
        
        .client-detail-view {
            padding: 20px;
        }
        
        .client-detail-section {
            margin-bottom: 20px;
            padding: 15px;
            background: #F8FBFF;
            border-radius: 5px;
        }
        
        .client-detail-section h4 {
            color: #3498db;
            margin-bottom: 10px;
            border-bottom: 1px solid #E1ECF4;
            padding-bottom: 5px;
        }
        
        .client-detail-field {
            margin-bottom: 10px;
        }
        
        .client-detail-field strong {
            color: #2C3E50;
            display: block;
            margin-bottom: 5px;
        }
        
        .client-detail-field p {
            color: #5D6D7E;
            padding: 10px;
            background: white;
            border-radius: 4px;
            border: 1px solid #E1ECF4;
        }
        
        .client-actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        
        .mark-as-read-btn {
            background: #27ae60;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .mark-as-read-btn:hover {
            background: #219653;
        }
        
        .reply-btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .reply-btn:hover {
            background: #2980b9;
        }
        
        .reply-btn.replied {
            background: #27ae60;
        }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid #E1ECF4;
            margin-bottom: 20px;
            overflow-x: auto;
        }
        
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background: none;
            border: none;
            font-weight: 500;
            color: #7F8C8D;
            border-bottom: 2px solid transparent;
            transition: all 0.3s;
            white-space: nowrap;
        }
        
        .tab:hover {
            color: #3498db;
        }
        
        .tab.active {
            color: #3498db;
            border-bottom: 2px solid #3498db;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* Email template selector */
        .template-selector {
            margin-bottom: 15px;
        }
        
        .template-select {
            width: 100%;
            padding: 8px;
            border: 1px solid #BDC3C7;
            border-radius: 4px;
            background: white;
        }
        
        .reply-editor {
            width: 100%;
            min-height: 200px;
            padding: 10px;
            border: 1px solid #BDC3C7;
            border-radius: 4px;
            font-family: inherit;
            resize: vertical;
        }
        
        /* Loading spinner */
        .spinner {
            border: 3px solid rgba(52, 152, 219, 0.3);
            border-radius: 50%;
            border-top: 3px solid #3498db;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Notification */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            z-index: 10001;
            animation: slideIn 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            max-width: 400px;
        }
        
        .notification.success {
            background: #27ae60;
            border-left: 4px solid #219653;
        }
        
        .notification.error {
            background: #e74c3c;
            border-left: 4px solid #c0392b;
        }
        
        .notification.info {
            background: #3498db;
            border-left: 4px solid #2980b9;
        }
        
        .notification.warning {
            background: #f39c12;
            border-left: 4px solid #d35400;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        /* Scroll Animations */
        .fade-in {
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.8s ease, transform 0.8s ease;
        }
        
        .fade-in.visible {
            opacity: 1;
            transform: translateY(0);
        }
        
        /* Responsive Design */
        @media (max-width: 1024px) {
            .hero h1 {
                font-size: 3rem;
            }
            
            .doctor-name {
                font-size: 2rem;
            }
            
            .doctor-specialty {
                font-size: 1.2rem;
            }
        }
        
        @media (max-width: 768px) {
            .hero {
                padding: 3rem 1.5rem;
            }
            
            .hero h1 {
                font-size: 2.5rem;
            }
            
            .hero p {
                font-size: 1.1rem;
                margin: 2rem auto;
            }
            
            .doctor-info-container {
                margin: 1.5rem auto 2rem;
            }
            
            .doctor-photo {
                width: 150px;
                height: 150px;
            }
            
            .doctor-name {
                font-size: 1.8rem;
            }
            
            .doctor-specialty {
                font-size: 1.1rem;
            }
            
            .about-content {
                grid-template-columns: 1fr;
                text-align: center;
                gap: 2rem;
            }
            
            .profile-photo {
                margin: 0 auto;
                width: 180px;
                height: 180px;
            }
            
            nav ul {
                gap: 1rem;
                font-size: 0.9rem;
            }
            
            .footer-links {
                flex-wrap: wrap;
                gap: 1rem;
            }
            
            .cta-buttons {
                flex-direction: column;
                align-items: center;
            }
            
            .btn {
                width: 100%;
                max-width: 300px;
            }
            
            .admin-panel {
                width: 100%;
            }
            
            .admin-name-tag .admin-indicator {
                display: none;
            }
            
            .features-container {
                grid-template-columns: 1fr;
                gap: 2rem;
            }
            
            .feature-card {
                padding: 2rem;
            }
            
            .modal-content {
                width: 95%;
            }
            
            .client-actions {
                flex-direction: column;
            }
            
            .tabs {
                flex-direction: column;
            }
            
            .tab {
                width: 100%;
                text-align: left;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .filter-buttons {
                grid-template-columns: 1fr;
            }
        }
        
        @media (max-width: 480px) {
            .hero h1 {
                font-size: 2rem;
            }
            
            .doctor-name {
                font-size: 1.6rem;
            }
            
            .doctor-specialty {
                font-size: 1rem;
            }
            
            .doctor-photo {
                width: 120px;
                height: 120px;
            }
            
            .photo-placeholder {
                font-size: 2.5rem;
            }
            
            .hero p {
                font-size: 1rem;
            }
            
            header {
                padding: 1rem;
            }
            
            nav ul {
                gap: 0.8rem;
                font-size: 0.8rem;
            }
        }
    </style>
</head>
<body>
    <!-- Admin Panel -->
    <div class="admin-panel" id="adminPanel">
        <div class="admin-section admin-login" id="adminLogin">
            <h3>Admin Login</h3>
            <input type="text" id="adminUsername" class="admin-input" placeholder="Username" value="admin">
            <input type="password" id="adminPassword" class="admin-input" placeholder="Password" value="admin9048">
            <button class="admin-btn" onclick="loginAdmin()">Login</button>
            <p style="font-size: 0.8rem; color: #5D6D7E; margin-top: 10px; text-align: center;">
                Default: admin / admin9048<br>Change after first login!
            </p>
        </div>
        
        <div class="admin-section" id="adminControls" style="display: none;">
            <div class="admin-status" id="adminStatus">
                Admin Mode: Active
            </div>
            
            <!-- Message Stats -->
            <div class="admin-section">
                <h3>Message Stats</h3>
                <div class="stats-grid" id="messageStats">
                    <div class="stat-box unread">
                        <div class="count" id="unreadCount">0</div>
                        <div class="label">Unread</div>
                    </div>
                    <div class="stat-box read">
                        <div class="count" id="readCount">0</div>
                        <div class="label">Read</div>
                    </div>
                    <div class="stat-box replied">
                        <div class="count" id="repliedCount">0</div>
                        <div class="label">Replied</div>
                    </div>
                    <div class="stat-box not-replied">
                        <div class="count" id="notRepliedCount">0</div>
                        <div class="label">Not Replied</div>
                    </div>
                </div>
            </div>
            
            <!-- Quick Filters -->
            <div class="admin-section">
                <h3>Quick Filters</h3>
                <div class="filter-buttons">
                    <button class="filter-btn unread" onclick="loadClients('unread')">Unread Messages</button>
                    <button class="filter-btn read" onclick="loadClients('read')">Read Messages</button>
                    <button class="filter-btn replied" onclick="loadClients('replied')">Replied Messages</button>
                    <button class="filter-btn not-replied" onclick="loadClients('not_replied')">Not Replied</button>
                </div>
                <button class="admin-btn admin-btn-secondary" onclick="loadClients('all')">View All Messages</button>
                <button class="admin-btn" onclick="markAllAsRead()">Mark All as Read</button>
            </div>
            
            <h3>Quick Edit</h3>
            <button class="admin-btn admin-btn-secondary" onclick="toggleEditMode()">
                <span id="editModeText">Enable Edit Mode</span>
            </button>
            
            <h3>Email Templates</h3>
            <button class="admin-btn admin-btn-secondary" onclick="viewEmailTemplates()">Manage Templates</button>
            
            <h3>Save/Load</h3>
            <button class="admin-btn" onclick="saveContentToBackend()">Save All Changes</button>
            <button class="admin-btn admin-btn-secondary" onclick="loadContentFromBackend()">Load Content</button>
            
            <h3>Doctor Info</h3>
            <input type="text" id="editDoctorName" class="admin-input" placeholder="Doctor Name">
            <input type="text" id="editDoctorSpecialty" class="admin-input" placeholder="Specialty">
            <button class="admin-btn admin-btn-secondary" onclick="updateDoctorInfo()">Update Doctor Info</button>
            
            <h3>Hero Section</h3>
            <input type="text" id="editHeroTitle" class="admin-input" placeholder="Hero Title">
            <textarea id="editHeroText" class="admin-textarea" placeholder="Hero Description"></textarea>
            <button class="admin-btn admin-btn-secondary" onclick="updateHero()">Update Hero</button>
            
            <h3>Change Password</h3>
            <input type="password" id="currentPassword" class="admin-input" placeholder="Current Password">
            <input type="password" id="newPassword" class="admin-input" placeholder="New Password">
            <input type="password" id="confirmPassword" class="admin-input" placeholder="Confirm New Password">
            <button class="admin-btn admin-btn-secondary" onclick="changeAdminPassword()">Change Password</button>
            
            <h3>Upload Photos</h3>
            <input type="file" id="photoUpload" accept="image/*" style="display: none;" onchange="uploadPhoto('hero')">
            <button class="admin-btn admin-btn-secondary" onclick="document.getElementById('photoUpload').click()">Upload Profile Photo</button>
            
            <button class="admin-btn admin-btn-danger" onclick="logoutAdmin()" style="margin-top: 2rem;">Logout</button>
        </div>
    </div>

    <!-- Header with Admin Name Tag -->
    <header>
        <nav>
            <div class="admin-name-tag" id="adminNameTag" onclick="toggleAdminPanel()">
                <span class="logo">
                    <span id="doctorNameHeader">Dr. Foscah Faith</span>
                    <span id="notificationBadge" class="notification-badge" style="display: none;">0</span>
                </span>
                <span class="admin-indicator" id="adminIndicator">(Admin Panel)</span>
            </div>
            <ul>
                <li><a href="#home">Home</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#work">Work</a></li>
                <li><a href="#services">Services</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>

    <!-- HOME PAGE with New Layout -->
    <div id="home" class="section">
        <section class="hero">
            <div class="hero-content">
                <h1 id="heroTitle" class="content-editable fade-in">Medical expertise for digital health.</h1>
                
                <!-- Doctor Info Container - Between Title and Description -->
                <div class="doctor-info-container fade-in">
                    <div class="doctor-photo-container">
                        <div class="doctor-photo" onclick="triggerPhotoUpload('hero')">
                            <div class="photo-placeholder">MD</div>
                            <img id="doctorPhoto" src="" alt="Dr. Foscah Faith" style="display: none;">
                        </div>
                        <div class="doctor-details">
                            <h2 class="doctor-name content-editable" id="doctorNameDisplay">Dr. Foscah Faith</h2>
                            <div class="doctor-divider"></div>
                            <p class="doctor-specialty content-editable" id="doctorSpecialty">Medical Consultant & Health Tech Specialist</p>
                        </div>
                    </div>
                </div>
                
                <p id="heroText" class="content-editable fade-in">I help health tech companies and healthcare organizations communicate clearly, build trust, and translate complex medical concepts into content that works.</p>
                
                <div class="cta-buttons fade-in">
                    <a href="#work" class="btn btn-primary">View My Work</a>
                    <a href="#contact" class="btn btn-secondary">Let's Talk →</a>
                </div>
            </div>
        </section>

        <!-- Features Section -->
        <section class="features">
            <div class="features-container">
                <div class="feature-card fade-in">
                    <h3 class="content-editable">Medical Foundation</h3>
                    <p class="content-editable">Completed medical school with training in clinical decision-making and patient communication.</p>
                </div>
                <div class="feature-card fade-in">
                    <h3 class="content-editable">Digital Execution</h3>
                    <p class="content-editable">Experienced in freelance medical writing, healthcare content strategy, and building remote business operations.</p>
                </div>
                <div class="feature-card fade-in">
                    <h3 class="content-editable">Global & Remote</h3>
                    <p class="content-editable">Work with teams worldwide to deliver accurate, clear, and compliant healthcare content.</p>
                </div>
            </div>
        </section>
    </div>

    <!-- ABOUT PAGE -->
    <div id="about" class="section">
        <section class="about-preview">
            <div class="about-container">
                <h2 class="content-editable" id="aboutTitle">From Clinical Training to Digital Health</h2>
                <div class="about-content">
                    <!-- Updated Profile Photo - Now a proper photo space -->
                    <div class="profile-photo" onclick="triggerPhotoUpload('about')">
                        <div class="photo-placeholder">MD</div>
                        <img id="aboutPhoto" src="" alt="Profile Photo" style="display: none;">
                    </div>
                    <div class="about-text" id="aboutContent">
                        <!-- About content will be loaded dynamically -->
                    </div>
                </div>
            </div>
        </section>
    </div>

    <!-- WORK PAGE -->
    <div id="work" class="section">
        <section class="portfolio">
            <div class="portfolio-container">
                <h2 class="content-editable">Selected Work</h2>
                
                <div class="project-card fade-in">
                    <h3 class="content-editable">Patient Education Content for a Telemedicine Platform</h3>
                    
                    <div class="project-section">
                        <strong class="content-editable">The Challenge:</strong>
                        <p class="content-editable">A telehealth startup needed patient-facing content explaining common conditions and treatment options. Their existing content was too clinical and created confusion during consultations.</p>
                    </div>
                    
                    <div class="project-section">
                        <strong class="content-editable">What I Did:</strong>
                        <p class="content-editable">Rewrote 15+ condition explainers using plain language principles, structured for scannability, and optimized for mobile. Collaborated with their clinical and product teams to ensure medical accuracy and brand alignment.</p>
                    </div>
                    
                    <div class="project-section">
                        <strong class="content-editable">The Outcome:</strong>
                        <p class="content-editable">Increased patient engagement with pre-consultation materials by 40%, reduced in-session clarification time, and improved overall patient satisfaction scores.</p>
                    </div>
                </div>

                <div class="project-card fade-in">
                    <h3 class="content-editable">Medical Accuracy Review for a Health & Wellness App</h3>
                    
                    <div class="project-section">
                        <strong class="content-editable">The Challenge:</strong>
                        <p class="content-editable">A wellness app was preparing to launch a symptom checker feature but needed clinical oversight to ensure their content was safe, accurate, and appropriately scoped.</p>
                    </div>
                    
                    <div class="project-section">
                        <strong class="content-editable">What I Did:</strong>
                        <p class="content-editable">Reviewed 50+ symptom pathways, flagged clinical inaccuracies, rewrote ambiguous content, and created a medical content style guide for future updates.</p>
                    </div>
                    
                    <div class="project-section">
                        <strong class="content-editable">The Outcome:</strong>
                        <p class="content-editable">Launched on schedule with zero medical accuracy complaints in the first 6 months. The style guide became the foundation for their content team's workflow.</p>
                    </div>
                </div>

                <div class="project-card fade-in">
                    <h3 class="content-editable">Health Tech Explainer Series (Self-Initiated)</h3>
                    
                    <div class="project-section">
                        <strong class="content-editable">The Challenge:</strong>
                        <p class="content-editable">Many people in non-clinical roles struggle to understand how health tech regulations, clinical workflows, and patient behavior intersect.</p>
                    </div>
                    
                    <div class="project-section">
                        <strong class="content-editable">What I Did:</strong>
                        <p class="content-editable">Created a series of explainer articles breaking down topics like HIPAA compliance, FDA device classifications, and clinical validation in plain language for product managers and founders.</p>
                    </div>
                    
                    <div class="project-section">
                        <strong class="content-editable">The Outcome:</strong>
                        <p class="content-editable">Shared across LinkedIn and health tech communities. Used by startup founders to onboard non-clinical team members.</p>
                    </div>
                </div>
            </div>
        </section>
    </div>

    <!-- SERVICES PAGE -->
    <div id="services" class="section">
        <section class="services">
            <div class="services-container">
                <h2 class="content-editable">How I Can Help</h2>
                <p class="services-intro content-editable" id="servicesIntro">I work with health tech companies, digital health platforms, and healthcare organizations who need someone who understands both medicine and how to communicate it clearly. Here's how we can work together:</p>             
                <div class="services-grid" id="servicesGrid">
                    <!-- Services will be loaded dynamically -->
                </div>
            </div>
        </section>
    </div>

    <!-- CONTACT PAGE -->
    <div id="contact" class="section">
        <section class="contact">
            <div class="contact-container">
                <h2 class="content-editable">Let's Work Together</h2>
                <p class="contact-intro content-editable" id="contactIntro">I work with health tech companies, digital health platforms, healthcare organizations, and individual practitioners who need clear, accurate, and effective medical content.</p>
                
                <div class="contact-form">
                    <form id="contactForm">
                        <div class="form-group">
                            <label for="name">Name *</label>
                            <input type="text" id="name" name="name" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="email">Email *</label>
                            <input type="email" id="email" name="email" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="phone">Phone Number (Optional)</label>
                            <input type="tel" id="phone" name="phone" placeholder="+1 (123) 456-7890">
                        </div>
                        
                        <div class="form-group">
                            <label for="address">Address (Optional)</label>
                            <input type="text" id="address" name="address" placeholder="Street, City, Country">
                        </div>
                        
                        <div class="form-group">
                            <label for="project-type">Project Type</label>
                            <select id="project-type" name="project-type">
                                <option value="">Select a service</option>
                                <option value="medical-writing">Medical & Healthcare Writing</option>
                                <option value="health-tech">Health Tech Content</option>
                                <option value="accuracy-review">Clinical Accuracy Review</option>
                                <option value="education">Healthcare Education</option>
                                <option value="other">Other / Not Sure</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label for="message">Message *</label>
                            <textarea id="message" name="message" required placeholder="Tell me about your project..."></textarea>
                        </div>
                        
                        <button type="submit" class="btn btn-primary" style="width: 100%;">Send Message</button>
                    </form>
                </div>
            </div>
        </section>
    </div>

    <!-- Footer -->
    <footer>
        <div class="footer-content">
            <div class="footer-links">
                <a href="#home">Home</a>
                <a href="#about">About</a>
                <a href="#work">Work</a>
                <a href="#services">Services</a>
                <a href="#contact">Contact</a>
            </div>
            <p id="footerCopyright">&copy; 2025 Dr. Foscah Faith. All rights reserved.</p>
            <p style="margin-top: 1rem; opacity: 0.8;">Professional Medical Portfolio System</p>
        </div>
    </footer>

    <script>
        // ==================== CONFIGURATION ====================
        const API_BASE_URL = window.location.origin + '/api';
        let authToken = localStorage.getItem('authToken');
        let isAdmin = false;
        let editMode = false;
        let adminPanelOpen = false;
        let currentHeroPhotoUrl = '';
        let currentAboutPhotoUrl = '';
        let unreadCheckInterval = null;
        let currentAdmin = null;

        // ==================== INITIALIZATION ====================
        document.addEventListener('DOMContentLoaded', function() {
            checkAuthStatus();
            loadContentFromBackend();
            setupEventListeners();
            setupScrollAnimations();
            
            // Start checking for new messages if admin is logged in
            if (authToken) {
                startUnreadCheck();
            }
        });

        // ==================== EVENT LISTENERS ====================
        function setupEventListeners() {
            // Contact form submission
            document.getElementById('contactForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                await submitContactForm();
            });

            // Close admin panel when clicking outside
            document.addEventListener('click', function(event) {
                const adminPanel = document.getElementById('adminPanel');
                const adminNameTag = document.getElementById('adminNameTag');
                
                if (adminPanelOpen && 
                    !adminPanel.contains(event.target) && 
                    !adminNameTag.contains(event.target)) {
                    closeAdminPanel();
                }
            });

            // Smooth scrolling for navigation
            document.querySelectorAll('nav a, .footer-links a, .cta-buttons a').forEach(anchor => {
                anchor.addEventListener('click', function(e) {
                    e.preventDefault();
                    const targetId = this.getAttribute('href');
                    if (targetId.startsWith('#')) {
                        const targetElement = document.querySelector(targetId);
                        if (targetElement) {
                            window.scrollTo({
                                top: targetElement.offsetTop - 80,
                                behavior: 'smooth'
                            });
                        }
                    }
                });
            });

            // Escape key closes admin panel
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Escape' && adminPanelOpen) {
                    closeAdminPanel();
                }
            });
        }

        // ==================== SCROLL ANIMATIONS ====================
        function setupScrollAnimations() {
            const fadeElements = document.querySelectorAll('.fade-in');
            
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            });
            
            fadeElements.forEach(element => {
                observer.observe(element);
            });
        }

        // ==================== NOTIFICATION SYSTEM ====================
        function showNotification(message, type = 'info') {
            // Remove existing notifications
            document.querySelectorAll('.notification').forEach(n => n.remove());
            
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            
            document.body.appendChild(notification);
            
            // Auto-remove after 5 seconds
            setTimeout(() => {
                notification.style.animation = 'slideIn 0.3s ease reverse';
                setTimeout(() => notification.remove(), 300);
            }, 5000);
        }

        // ==================== ADMIN PANEL TOGGLE ====================
        function toggleAdminPanel() {
            if (adminPanelOpen) {
                closeAdminPanel();
            } else {
                openAdminPanel();
            }
        }

        function openAdminPanel() {
            const panel = document.getElementById('adminPanel');
            const nameTag = document.getElementById('adminNameTag');
            
            panel.classList.add('open');
            nameTag.classList.add('active');
            adminPanelOpen = true;
            
            // Load stats when panel opens
            if (isAdmin) {
                loadMessageStats();
            }
        }

        function closeAdminPanel() {
            const panel = document.getElementById('adminPanel');
            const nameTag = document.getElementById('adminNameTag');
            
            panel.classList.remove('open');
            nameTag.classList.remove('active');
            adminPanelOpen = false;
        }

        // ==================== AUTHENTICATION ====================
        async function loginAdmin() {
            const username = document.getElementById('adminUsername').value;
            const password = document.getElementById('adminPassword').value;
            
            if (!username || !password) {
                showNotification('Please enter username and password', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    authToken = data.access_token;
                    currentAdmin = data.admin;
                    localStorage.setItem('authToken', authToken);
                    isAdmin = true;
                    
                    // Update UI
                    document.getElementById('adminLogin').style.display = 'none';
                    document.getElementById('adminControls').style.display = 'block';
                    document.getElementById('adminStatus').textContent = `Admin Mode: ${currentAdmin.username}`;
                    
                    // Update name tag
                    updateAdminNameTag();
                    
                    // Load current values and stats
                    loadCurrentValues();
                    loadMessageStats();
                    
                    // Start checking for new messages
                    startUnreadCheck();
                    
                    showNotification('Admin login successful!', 'success');
                    
                } else {
                    showNotification(data.error || 'Login failed', 'error');
                }
            } catch (error) {
                console.error('Login error:', error);
                showNotification('Login failed. Check server connection.', 'error');
            }
        }

        function logoutAdmin() {
            authToken = null;
            currentAdmin = null;
            localStorage.removeItem('authToken');
            isAdmin = false;
            editMode = false;
            
            // Stop checking for new messages
            stopUnreadCheck();
            
            // Update UI
            document.getElementById('adminLogin').style.display = 'block';
            document.getElementById('adminControls').style.display = 'none';
            document.getElementById('adminUsername').value = 'admin';
            document.getElementById('adminPassword').value = 'admin9048';
            
            // Update name tag
            updateAdminNameTag();
            
            // Hide notification badge
            document.getElementById('notificationBadge').style.display = 'none';
            
            disableEditMode();
            showNotification('Logged out successfully', 'info');
        }

        async function checkAuthStatus() {
            if (!authToken) return;
            
            // For simplicity, assume token is valid if it exists
            isAdmin = true;
            
            if (isAdmin) {
                document.getElementById('adminLogin').style.display = 'none';
                document.getElementById('adminControls').style.display = 'block';
                document.getElementById('adminStatus').textContent = 'Admin Mode: Active';
                
                // Update name tag
                updateAdminNameTag();
                
                // Load stats and start checking for new messages
                loadMessageStats();
                startUnreadCheck();
            }
        }

        function updateAdminNameTag() {
            const nameTag = document.getElementById('adminNameTag');
            const notificationBadge = document.getElementById('notificationBadge');
            
            if (isAdmin) {
                nameTag.style.cursor = 'pointer';
                nameTag.title = 'Click to open admin panel';
            } else {
                nameTag.style.cursor = 'default';
                nameTag.title = '';
                notificationBadge.style.display = 'none';
            }
        }

        // ==================== MESSAGE STATS & TRACKING ====================
        function startUnreadCheck() {
            // Check immediately
            loadMessageStats();
            
            // Then check every 30 seconds
            unreadCheckInterval = setInterval(loadMessageStats, 30000);
        }

        function stopUnreadCheck() {
            if (unreadCheckInterval) {
                clearInterval(unreadCheckInterval);
                unreadCheckInterval = null;
            }
        }

        async function loadMessageStats() {
            if (!isAdmin) return;
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/message-counts`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const stats = await response.json();
                    updateMessageStats(stats);
                }
            } catch (error) {
                console.error('Failed to load message stats:', error);
            }
        }

        function updateMessageStats(stats) {
            // Update stats display
            document.getElementById('unreadCount').textContent = stats.unread || 0;
            document.getElementById('readCount').textContent = stats.read || 0;
            document.getElementById('repliedCount').textContent = stats.replied || 0;
            document.getElementById('notRepliedCount').textContent = stats.read_not_replied || 0;
            
            // Update notification badge
            const notificationBadge = document.getElementById('notificationBadge');
            if (stats.unread > 0) {
                notificationBadge.textContent = stats.unread;
                notificationBadge.style.display = 'inline-block';
                notificationBadge.style.animation = 'pulse 2s infinite';
            } else {
                notificationBadge.style.display = 'none';
                notificationBadge.style.animation = 'none';
            }
        }

        // ==================== CLIENT MANAGEMENT ====================
        async function loadClients(filter = 'all') {
            if (!isAdmin) {
                showNotification('Admin access required', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients?filter=${filter}`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const clients = await response.json();
                    
                    let title = 'All Messages';
                    if (filter === 'unread') title = 'Unread Messages';
                    else if (filter === 'read') title = 'Read Messages';
                    else if (filter === 'replied') title = 'Replied Messages';
                    else if (filter === 'not_replied') title = 'Read but Not Replied';
                    else if (filter === 'new') title = 'New Status Messages';
                    else if (filter === 'contacted') title = 'Contacted Status';
                    else if (filter === 'in_progress') title = 'In Progress';
                    else if (filter === 'completed') title = 'Completed';
                    else if (filter === 'archived') title = 'Archived';
                    
                    displayClientsModal(clients, title, filter);
                } else {
                    showNotification('Failed to load messages', 'error');
                }
            } catch (error) {
                console.error('Failed to load clients:', error);
                showNotification('Failed to load messages', 'error');
            }
        }

        function displayClientsModal(clients, title, filter) {
            let modalHTML = `
                <div class="modal-overlay">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3 style="color: #3498db; margin: 0;">${title} (${clients.length})</h3>
                            <button onclick="this.parentElement.parentElement.parentElement.remove()" style="background: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
                        </div>
                        <div class="modal-body">
            `;
            
            // Add filter buttons
            modalHTML += `
                <div style="margin-bottom: 20px;">
                    <div class="filter-buttons">
                        <button class="filter-btn ${filter === 'all' ? 'active' : ''}" onclick="loadClients('all')">All</button>
                        <button class="filter-btn unread ${filter === 'unread' ? 'active' : ''}" onclick="loadClients('unread')">Unread</button>
                        <button class="filter-btn read ${filter === 'read' ? 'active' : ''}" onclick="loadClients('read')">Read</button>
                        <button class="filter-btn replied ${filter === 'replied' ? 'active' : ''}" onclick="loadClients('replied')">Replied</button>
                        <button class="filter-btn not-replied ${filter === 'not_replied' ? 'active' : ''}" onclick="loadClients('not_replied')">Not Replied</button>
                    </div>
                </div>
            `;
            
            if (filter === 'unread' && clients.length > 0) {
                modalHTML += `
                    <div style="margin-bottom: 20px;">
                        <button onclick="markAllAsRead()" style="background: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold;">
                            Mark All as Read
                        </button>
                    </div>
                `;
            }
            
            if (clients.length === 0) {
                modalHTML += `
                    <div style="text-align: center; padding: 40px; color: #5D6D7E;">
                        <p style="font-size: 1.2rem; margin-bottom: 10px;">No messages found</p>
                        <p>No messages match the current filter.</p>
                    </div>
                `;
            } else {
                modalHTML += `
                    <div class="tabs">
                        <button class="tab active" onclick="switchTab('list', this)">List View</button>
                        <button class="tab" onclick="switchTab('details', this)">Details View</button>
                    </div>
                    
                    <div class="tab-content active" id="tab-list">
                        <div class="client-list">
                `;
                
                clients.forEach(client => {
                    const isUnread = client.read_by_admin === false;
                    const isReplied = client.replied_by_admin === true;
                    const date = new Date(client.created_at).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    
                    const messagePreview = client.message.length > 100 ? 
                        client.message.substring(0, 100) + '...' : client.message;
                    
                    const readBadgeClass = isUnread ? 'unread' : (isReplied ? 'replied' : 'read');
                    
                    modalHTML += `
                        <div class="client-item ${isUnread ? 'unread' : ''} ${isReplied ? 'replied' : ''}" onclick="viewClientDetails(${client.id})" data-client-id="${client.id}">
                            <div class="client-item-header">
                                <div class="client-item-name">
                                    <span class="read-badge ${readBadgeClass}"></span>
                                    ${escapeHtml(client.name)}
                                </div>
                                <div class="client-item-date">${date}</div>
                            </div>
                            <div class="client-item-message">${escapeHtml(messagePreview)}</div>
                            <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                                <span class="status-badge status-${client.status}">${client.status}</span>
                                ${isUnread ? '<span style="color: #f39c12; font-size: 0.8rem;">● NEW</span>' : ''}
                                ${isReplied ? '<span style="color: #27ae60; font-size: 0.8rem;">✓ REPLIED</span>' : ''}
                            </div>
                        </div>
                    `;
                });
                
                modalHTML += `
                        </div>
                    </div>
                    
                    <div class="tab-content" id="tab-details">
                        <div id="client-details-container" style="min-height: 400px; display: flex; align-items: center; justify-content: center; color: #7F8C8D;">
                            <p>Select a client from the list view to see details here</p>
                        </div>
                    </div>
                `;
            }
            
            modalHTML += `
                        </div>
                    </div>
                </div>
            `;
            
            // Remove any existing modals
            document.querySelectorAll('.modal-overlay').forEach(el => el.remove());
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            // Update active filter buttons
            updateFilterButtons(filter);
        }

        function updateFilterButtons(activeFilter) {
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.textContent.toLowerCase().includes(activeFilter) || 
                    (activeFilter === 'all' && btn.textContent === 'All')) {
                    btn.classList.add('active');
                }
            });
        }

        function switchTab(tabName, button) {
            // Update tabs
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            button.classList.add('active');
            
            // Update content
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            // If switching to details tab and no client is selected, show first client
            if (tabName === 'details') {
                const clientItems = document.querySelectorAll('.client-item');
                if (clientItems.length > 0 && !document.querySelector('.client-detail-view')) {
                    const firstClientId = clientItems[0].getAttribute('data-client-id');
                    viewClientDetails(parseInt(firstClientId));
                }
            }
        }

        async function viewClientDetails(clientId) {
            if (!isAdmin) return;
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const client = await response.json();
                    displayClientDetails(client);
                    
                    // Switch to details tab if we're in list view
                    const detailsTab = document.querySelector('#tab-details');
                    if (detailsTab && !detailsTab.classList.contains('active')) {
                        document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
                        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                        
                        const detailsTabButton = document.querySelector('.tab[onclick*="details"]');
                        if (detailsTabButton) {
                            detailsTabButton.classList.add('active');
                            detailsTab.classList.add('active');
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to load client details:', error);
                showNotification('Failed to load client details', 'error');
            }
        }

        function displayClientDetails(client) {
            const detailsContainer = document.getElementById('client-details-container') || 
                                   document.querySelector('.client-detail-view')?.parentElement;
            
            if (!detailsContainer) return;
            
            const date = new Date(client.created_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            const replyDate = client.reply_date ? 
                new Date(client.reply_date).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                }) : 'Not replied yet';
            
            const detailsHTML = `
                <div class="client-detail-view">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                        <h3 style="color: #3498db; margin: 0;">${escapeHtml(client.name)}</h3>
                        <span class="status-badge status-${client.status}" onclick="changeClientStatus(${client.id}, '${client.status}')">
                            ${client.status}
                        </span>
                    </div>
                    
                    <div class="client-detail-section">
                        <h4>Contact Information</h4>
                        <div class="client-detail-field">
                            <strong>Email:</strong>
                            <p><a href="mailto:${client.email}" style="color: #3498db;">${client.email}</a></p>
                        </div>
                        ${client.phone ? `
                        <div class="client-detail-field">
                            <strong>Phone:</strong>
                            <p><a href="tel:${client.phone}" style="color: #3498db;">${client.phone}</a></p>
                        </div>
                        ` : ''}
                        ${client.address ? `
                        <div class="client-detail-field">
                            <strong>Address:</strong>
                            <p>${escapeHtml(client.address)}</p>
                        </div>
                        ` : ''}
                        <div class="client-detail-field">
                            <strong>Project Type:</strong>
                            <p>${client.project_type || 'Not specified'}</p>
                        </div>
                    </div>
                    
                    <div class="client-detail-section">
                        <h4>Message</h4>
                        <div class="client-detail-field">
                            <p style="white-space: pre-wrap;">${escapeHtml(client.message)}</p>
                        </div>
                    </div>
                    
                    ${client.replied_by_admin ? `
                    <div class="client-detail-section">
                        <h4>Reply Information</h4>
                        <div class="client-detail-field">
                            <strong>Replied by:</strong>
                            <p>${client.reply_admin || 'Admin'}</p>
                        </div>
                        <div class="client-detail-field">
                            <strong>Reply Date:</strong>
                            <p>${replyDate}</p>
                        </div>
                        <div class="client-detail-field">
                            <strong>Reply Content:</strong>
                            <p style="white-space: pre-wrap;">${escapeHtml(client.reply_content)}</p>
                        </div>
                    </div>
                    ` : ''}
                    
                    ${client.admin_notes ? `
                    <div class="client-detail-section">
                        <h4>Admin Notes</h4>
                        <div class="client-detail-field">
                            <p style="white-space: pre-wrap;">${escapeHtml(client.admin_notes)}</p>
                        </div>
                    </div>
                    ` : ''}
                    
                    <div class="client-detail-section">
                        <h4>Submission Details</h4>
                        <div class="client-detail-field">
                            <strong>Submitted:</strong>
                            <p>${date}</p>
                        </div>
                        <div class="client-detail-field">
                            <strong>Read Status:</strong>
                            <p>${client.read_by_admin ? '✓ Read by admin' : '✗ Unread'}</p>
                        </div>
                        <div class="client-detail-field">
                            <strong>Reply Status:</strong>
                            <p>${client.replied_by_admin ? '✓ Replied by admin' : '✗ Not replied'}</p>
                        </div>
                    </div>
                    
                    <div class="client-actions">
                        ${!client.read_by_admin ? `
                        <button class="mark-as-read-btn" onclick="markClientAsRead(${client.id})">
                            Mark as Read
                        </button>
                        ` : ''}
                        <button class="reply-btn ${client.replied_by_admin ? 'replied' : ''}" onclick="sendReplyToClient(${client.id})">
                            ${client.replied_by_admin ? 'Edit Reply' : 'Send Reply'}
                        </button>
                        <button onclick="changeClientStatus(${client.id}, '${client.status}')" style="background: #3498db; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                            Change Status
                        </button>
                        <button onclick="deleteClient(${client.id})" style="background: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                            Delete
                        </button>
                        <button onclick="addAdminNotes(${client.id})" style="background: #f39c12; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
                            Add Notes
                        </button>
                    </div>
                </div>
            `;
            
            detailsContainer.innerHTML = detailsHTML;
        }

        async function markClientAsRead(clientId) {
            if (!isAdmin) return;
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}/read`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ admin_notes: '' })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification('Message marked as read', 'success');
                    
                    // Update the UI
                    const clientItem = document.querySelector(`.client-item[data-client-id="${clientId}"]`);
                    if (clientItem) {
                        clientItem.classList.remove('unread');
                        const newBadge = clientItem.querySelector('span[style*="color: #f39c12"]');
                        if (newBadge) newBadge.remove();
                    }
                    
                    // Update stats
                    loadMessageStats();
                    
                    // Refresh details if open
                    setTimeout(() => viewClientDetails(clientId), 500);
                } else {
                    showNotification(data.error || 'Failed to mark as read', 'error');
                }
            } catch (error) {
                console.error('Failed to mark client as read:', error);
                showNotification('Failed to mark as read', 'error');
            }
        }

        async function markAllAsRead() {
            if (!isAdmin) {
                showNotification('Admin access required', 'error');
                return;
            }
            
            if (!confirm('Mark all unread messages as read?')) {
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/mark-all-read`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification(data.message, 'success');
                    loadMessageStats();
                    
                    // Refresh any open client modal
                    const modal = document.querySelector('.modal-overlay');
                    if (modal) {
                        modal.remove();
                        loadClients('unread');
                    }
                } else {
                    showNotification(data.error || 'Failed to mark all as read', 'error');
                }
            } catch (error) {
                console.error('Failed to mark all as read:', error);
                showNotification('Failed to mark all as read', 'error');
            }
        }

        async function sendReplyToClient(clientId) {
            // First, get the client details
            const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });
            
            if (!response.ok) {
                showNotification('Failed to load client details', 'error');
                return;
            }
            
            const client = await response.json();
            
            // Create reply modal
            const modalHTML = `
                <div class="modal-overlay">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3 style="color: #3498db; margin: 0;">Send Reply to ${escapeHtml(client.name)}</h3>
                            <button onclick="this.parentElement.parentElement.parentElement.remove()" style="background: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
                        </div>
                        <div class="modal-body">
                            <div class="template-selector">
                                <select id="templateSelect" class="template-select" onchange="loadTemplate()">
                                    <option value="">Select a template...</option>
                                    <!-- Templates will be loaded here -->
                                </select>
                            </div>
                            <textarea id="replyContent" class="reply-editor" placeholder="Type your reply here...">${client.reply_content || ''}</textarea>
                            <div style="margin-top: 20px; display: flex; gap: 10px;">
                                <button onclick="sendReply(${clientId})" style="background: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold;">
                                    ${client.replied_by_admin ? 'Update Reply' : 'Send Reply'}
                                </button>
                                <button onclick="saveReplyOnly(${clientId})" style="background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer;">
                                    Save Only (No Email)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove any existing modals
            document.querySelectorAll('.modal-overlay').forEach(el => el.remove());
            document.body.insertAdjacentHTML('beforeend', modalHTML);
            
            // Load email templates
            await loadEmailTemplatesForSelect();
        }

        async function loadEmailTemplatesForSelect() {
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const templates = await response.json();
                    const select = document.getElementById('templateSelect');
                    
                    templates.forEach(template => {
                        const option = document.createElement('option');
                        option.value = template.id;
                        option.textContent = template.name + (template.is_default ? ' (Default)' : '');
                        select.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Failed to load templates:', error);
            }
        }

        async function loadTemplate() {
            const templateId = document.getElementById('templateSelect').value;
            if (!templateId) return;
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates/${templateId}`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const template = await response.json();
                    document.getElementById('replyContent').value = template.body;
                }
            } catch (error) {
                console.error('Failed to load template:', error);
            }
        }

        async function sendReply(clientId) {
            const replyContent = document.getElementById('replyContent').value;
            
            if (!replyContent.trim()) {
                showNotification('Reply content is required', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}/send-reply`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ reply_content: replyContent })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification(data.message, 'success');
                    
                    // Close the reply modal
                    document.querySelector('.modal-overlay')?.remove();
                    
                    // Refresh client details
                    setTimeout(() => viewClientDetails(clientId), 500);
                    
                    // Update stats
                    loadMessageStats();
                } else {
                    showNotification(data.error || 'Failed to send reply', 'error');
                }
            } catch (error) {
                console.error('Failed to send reply:', error);
                showNotification('Failed to send reply', 'error');
            }
        }

        async function saveReplyOnly(clientId) {
            const replyContent = document.getElementById('replyContent').value;
            
            if (!replyContent.trim()) {
                showNotification('Reply content is required', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}/reply`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ reply_content: replyContent })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification('Reply saved successfully', 'success');
                    
                    // Close the reply modal
                    document.querySelector('.modal-overlay')?.remove();
                    
                    // Refresh client details
                    setTimeout(() => viewClientDetails(clientId), 500);
                    
                    // Update stats
                    loadMessageStats();
                } else {
                    showNotification(data.error || 'Failed to save reply', 'error');
                }
            } catch (error) {
                console.error('Failed to save reply:', error);
                showNotification('Failed to save reply', 'error');
            }
        }

        function addAdminNotes(clientId) {
            const notes = prompt('Enter admin notes for this client:');
            if (notes === null) return; // User cancelled
            
            if (!isAdmin) return;
            
            fetch(`${API_BASE_URL}/admin/clients/${clientId}/read`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ admin_notes: notes })
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    showNotification('Notes added successfully', 'success');
                    setTimeout(() => viewClientDetails(clientId), 500);
                } else {
                    showNotification(data.error || 'Failed to add notes', 'error');
                }
            })
            .catch(error => {
                console.error('Failed to add notes:', error);
                showNotification('Failed to add notes', 'error');
            });
        }

        async function changeClientStatus(clientId, currentStatus) {
            if (!isAdmin) return;
            
            const statuses = ['new', 'contacted', 'in_progress', 'completed', 'archived'];
            const currentIndex = statuses.indexOf(currentStatus);
            const nextStatus = statuses[(currentIndex + 1) % statuses.length];
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}/status`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({ status: nextStatus })
                });
                
                if (response.ok) {
                    showNotification(`Status changed to ${nextStatus}`, 'success');
                    
                    // Refresh the client details
                    setTimeout(() => viewClientDetails(clientId), 500);
                }
            } catch (error) {
                console.error('Failed to update status:', error);
                showNotification('Failed to update status', 'error');
            }
        }

        async function deleteClient(clientId) {
            if (!isAdmin) return;
            
            if (!confirm('Are you sure you want to delete this client submission? This cannot be undone.')) {
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/clients/${clientId}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    showNotification('Client deleted successfully', 'success');
                    
                    // Remove from list
                    const clientItem = document.querySelector(`.client-item[data-client-id="${clientId}"]`);
                    if (clientItem) {
                        clientItem.remove();
                    }
                    
                    // Update stats
                    loadMessageStats();
                    
                    // If details view is showing this client, clear it
                    const detailsContainer = document.getElementById('client-details-container');
                    if (detailsContainer) {
                        detailsContainer.innerHTML = '<p>Client deleted. Select another client to view details.</p>';
                    }
                }
            } catch (error) {
                console.error('Failed to delete client:', error);
                showNotification('Failed to delete client', 'error');
            }
        }

        // ==================== EMAIL TEMPLATE MANAGEMENT ====================
        async function viewEmailTemplates() {
            if (!isAdmin) {
                showNotification('Admin access required', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const templates = await response.json();
                    displayEmailTemplatesModal(templates);
                } else {
                    showNotification('Failed to load email templates', 'error');
                }
            } catch (error) {
                console.error('Failed to load email templates:', error);
                showNotification('Failed to load email templates', 'error');
            }
        }

        function displayEmailTemplatesModal(templates) {
            let modalHTML = `
                <div class="modal-overlay">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3 style="color: #3498db; margin: 0;">Email Templates (${templates.length})</h3>
                            <button onclick="this.parentElement.parentElement.parentElement.remove()" style="background: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
                        </div>
                        <div class="modal-body">
                            <button onclick="createNewTemplate()" style="background: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-bottom: 20px; font-weight: bold;">
                                + Create New Template
                            </button>
                            <div class="client-list">
            `;
            
            if (templates.length === 0) {
                modalHTML += `
                    <div style="text-align: center; padding: 40px; color: #5D6D7E;">
                        <p style="font-size: 1.2rem; margin-bottom: 10px;">No templates found</p>
                        <p>Click "Create New Template" to add your first template.</p>
                    </div>
                `;
            } else {
                templates.forEach(template => {
                    modalHTML += `
                        <div class="client-item" onclick="editEmailTemplate(${template.id})">
                            <div class="client-item-header">
                                <div class="client-item-name">
                                    ${escapeHtml(template.name)} ${template.is_default ? '★' : ''}
                                </div>
                            </div>
                            <div class="client-item-message">${escapeHtml(template.subject)}</div>
                            <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                                <span style="color: #7F8C8D; font-size: 0.8rem;">
                                    ${template.is_default ? 'Default Template' : 'Custom Template'}
                                </span>
                                ${!template.is_default ? `
                                <button onclick="event.stopPropagation(); deleteEmailTemplate(${template.id})" style="background: #e74c3c; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
                                    Delete
                                </button>
                                ` : ''}
                            </div>
                        </div>
                    `;
                });
            }
            
            modalHTML += `
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove any existing modals
            document.querySelectorAll('.modal-overlay').forEach(el => el.remove());
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }

        function createNewTemplate() {
            const modalHTML = `
                <div class="modal-overlay">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h3 style="color: #3498db; margin: 0;">Create New Email Template</h3>
                            <button onclick="this.parentElement.parentElement.parentElement.remove()" style="background: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
                        </div>
                        <div class="modal-body">
                            <div style="margin-bottom: 15px;">
                                <input type="text" id="templateName" placeholder="Template Name" style="width: 100%; padding: 8px; border: 1px solid #BDC3C7; border-radius: 4px;">
                            </div>
                            <div style="margin-bottom: 15px;">
                                <input type="text" id="templateSubject" placeholder="Email Subject" style="width: 100%; padding: 8px; border: 1px solid #BDC3C7; border-radius: 4px;">
                            </div>
                            <textarea id="templateBody" placeholder="Email Body (use {name}, {email}, {project_type} for variables)" style="width: 100%; min-height: 300px; padding: 10px; border: 1px solid #BDC3C7; border-radius: 4px; font-family: inherit; resize: vertical;"></textarea>
                            <div style="margin-top: 20px;">
                                <button onclick="saveNewTemplate()" style="background: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold;">
                                    Save Template
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove any existing modals
            document.querySelectorAll('.modal-overlay').forEach(el => el.remove());
            document.body.insertAdjacentHTML('beforeend', modalHTML);
        }

        async function saveNewTemplate() {
            const name = document.getElementById('templateName').value;
            const subject = document.getElementById('templateSubject').value;
            const body = document.getElementById('templateBody').value;
            
            if (!name || !subject || !body) {
                showNotification('All fields are required', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ name, subject, body })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification('Template created successfully', 'success');
                    document.querySelector('.modal-overlay')?.remove();
                    viewEmailTemplates();
                } else {
                    showNotification(data.error || 'Failed to create template', 'error');
                }
            } catch (error) {
                console.error('Failed to create template:', error);
                showNotification('Failed to create template', 'error');
            }
        }

        async function editEmailTemplate(templateId) {
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates/${templateId}`, {
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    const template = await response.json();
                    
                    const modalHTML = `
                        <div class="modal-overlay">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h3 style="color: #3498db; margin: 0;">Edit Email Template</h3>
                                    <button onclick="this.parentElement.parentElement.parentElement.remove()" style="background: #e74c3c; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Close</button>
                                </div>
                                <div class="modal-body">
                                    <div style="margin-bottom: 15px;">
                                        <input type="text" id="editTemplateName" value="${escapeHtml(template.name)}" style="width: 100%; padding: 8px; border: 1px solid #BDC3C7; border-radius: 4px;" ${template.is_default ? 'disabled' : ''}>
                                    </div>
                                    <div style="margin-bottom: 15px;">
                                        <input type="text" id="editTemplateSubject" value="${escapeHtml(template.subject)}" style="width: 100%; padding: 8px; border: 1px solid #BDC3C7; border-radius: 4px;">
                                    </div>
                                    <textarea id="editTemplateBody" style="width: 100%; min-height: 300px; padding: 10px; border: 1px solid #BDC3C7; border-radius: 4px; font-family: inherit; resize: vertical;">${escapeHtml(template.body)}</textarea>
                                    <div style="margin-top: 20px;">
                                        <button onclick="updateTemplate(${template.id})" style="background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold;">
                                            Update Template
                                        </button>
                                        ${!template.is_default ? `
                                        <button onclick="deleteEmailTemplate(${template.id})" style="background: #e74c3c; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-left: 10px;">
                                            Delete Template
                                        </button>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    // Remove any existing modals
                    document.querySelectorAll('.modal-overlay').forEach(el => el.remove());
                    document.body.insertAdjacentHTML('beforeend', modalHTML);
                }
            } catch (error) {
                console.error('Failed to load template:', error);
                showNotification('Failed to load template', 'error');
            }
        }

        async function updateTemplate(templateId) {
            const name = document.getElementById('editTemplateName').value;
            const subject = document.getElementById('editTemplateSubject').value;
            const body = document.getElementById('editTemplateBody').value;
            
            if (!name || !subject || !body) {
                showNotification('All fields are required', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ id: templateId, name, subject, body })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification('Template updated successfully', 'success');
                    document.querySelector('.modal-overlay')?.remove();
                    viewEmailTemplates();
                } else {
                    showNotification(data.error || 'Failed to update template', 'error');
                }
            } catch (error) {
                console.error('Failed to update template:', error);
                showNotification('Failed to update template', 'error');
            }
        }

        async function deleteEmailTemplate(templateId) {
            if (!confirm('Are you sure you want to delete this template? This cannot be undone.')) {
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/email-templates/${templateId}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': `Bearer ${authToken}` }
                });
                
                if (response.ok) {
                    showNotification('Template deleted successfully', 'success');
                    document.querySelector('.modal-overlay')?.remove();
                    viewEmailTemplates();
                } else {
                    showNotification('Failed to delete template', 'error');
                }
            } catch (error) {
                console.error('Failed to delete template:', error);
                showNotification('Failed to delete template', 'error');
            }
        }

        // ==================== PASSWORD CHANGE ====================
        async function changeAdminPassword() {
            const currentPassword = document.getElementById('currentPassword').value;
            const newPassword = document.getElementById('newPassword').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            if (!currentPassword || !newPassword || !confirmPassword) {
                showNotification('All password fields are required', 'error');
                return;
            }
            
            if (newPassword !== confirmPassword) {
                showNotification('New passwords do not match', 'error');
                return;
            }
            
            if (newPassword.length < 6) {
                showNotification('New password must be at least 6 characters', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/change-password`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification('Password changed successfully!', 'success');
                    document.getElementById('currentPassword').value = '';
                    document.getElementById('newPassword').value = '';
                    document.getElementById('confirmPassword').value = '';
                } else {
                    showNotification(data.error || 'Failed to change password', 'error');
                }
            } catch (error) {
                console.error('Password change error:', error);
                showNotification('Failed to change password', 'error');
            }
        }

        // ==================== CONTENT MANAGEMENT ====================
        async function loadContentFromBackend() {
            try {
                const response = await fetch(`${API_BASE_URL}/content`);
                
                if (response.ok) {
                    const content = await response.json();
                    applyContentToPage(content);
                } else {
                    throw new Error('Failed to load content');
                }
            } catch (error) {
                console.error('Failed to load content:', error);
            }
        }

        function applyContentToPage(content) {
            // Hero section
            if (content.hero) {
                const heroData = content.hero;
                if (heroData.title) document.getElementById('heroTitle').textContent = heroData.title;
                if (heroData.text) document.getElementById('heroText').textContent = heroData.text;
            }
            
            // Doctor info
            if (content.doctor) {
                const doctorData = content.doctor;
                if (doctorData.name) {
                    document.getElementById('doctorNameHeader').textContent = doctorData.name;
                    document.getElementById('doctorNameDisplay').textContent = doctorData.name;
                    document.getElementById('footerCopyright').textContent = `© ${new Date().getFullYear()} ${doctorData.name}. All rights reserved.`;
                }
                if (doctorData.specialty) {
                    document.getElementById('doctorSpecialty').textContent = doctorData.specialty;
                }
            }
            
            // Contact intro
            if (content.contact_intro) {
                document.getElementById('contactIntro').textContent = content.contact_intro;
            }
            
            // Services intro
            if (content.services_intro) {
                document.getElementById('servicesIntro').textContent = content.services_intro;
            }
            
            // About section
            if (content.about_section) {
                const aboutData = content.about_section;
                if (aboutData.title) {
                    document.getElementById('aboutTitle').textContent = aboutData.title;
                }
                if (aboutData.content) {
                    const aboutContentDiv = document.getElementById('aboutContent');
                    aboutContentDiv.innerHTML = '';
                    aboutData.content.forEach(paragraph => {
                        const p = document.createElement('p');
                        p.className = 'content-editable';
                        p.innerHTML = paragraph;
                        aboutContentDiv.appendChild(p);
                    });
                }
            }
            
            // Services
            if (content.services) {
                const servicesGrid = document.getElementById('servicesGrid');
                servicesGrid.innerHTML = '';
                
                content.services.forEach(service => {
                    const serviceCard = document.createElement('div');
                    serviceCard.className = 'service-card fade-in';
                    serviceCard.innerHTML = `
                        <h3 class="content-editable">${service.title}</h3>
                        <div class="service-detail">
                            <strong class="content-editable">What it includes:</strong>
                            <p class="content-editable">${service.description}</p>
                        </div>
                        <div class="service-detail">
                            <strong class="content-editable">Who it's for:</strong>
                            <p class="content-editable">${service.for}</p>
                        </div>
                    `;
                    servicesGrid.appendChild(serviceCard);
                });
            }
        }

        async function saveContentToBackend() {
            if (!isAdmin) {
                showNotification('Admin access required', 'error');
                return;
            }
            
            // Collect all content
            const content = {
                hero: {
                    title: document.getElementById('heroTitle').textContent,
                    text: document.getElementById('heroText').textContent
                },
                doctor: {
                    name: document.getElementById('doctorNameDisplay').textContent,
                    specialty: document.getElementById('doctorSpecialty').textContent
                },
                contact_intro: document.getElementById('contactIntro').textContent,
                services_intro: document.getElementById('servicesIntro').textContent
            };
            
            // Collect about content
            const aboutParagraphs = Array.from(document.querySelectorAll('#aboutContent p')).map(p => p.innerHTML);
            content.about_section = {
                title: document.getElementById('aboutTitle').textContent,
                content: aboutParagraphs
            };
            
            // Collect services
            const services = [];
            document.querySelectorAll('.service-card').forEach(card => {
                const title = card.querySelector('h3').textContent;
                const description = card.querySelectorAll('p')[0].textContent;
                const forText = card.querySelectorAll('p')[1].textContent;
                services.push({ title, description, for: forText });
            });
            content.services = services;
            
            try {
                const response = await fetch(`${API_BASE_URL}/admin/content`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: JSON.stringify(content)
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification('Content saved successfully!', 'success');
                } else {
                    showNotification(data.error || 'Failed to save content', 'error');
                }
            } catch (error) {
                console.error('Save error:', error);
                showNotification('Failed to save content', 'error');
            }
        }

        // ==================== EDIT MODE FUNCTIONS ====================
        function toggleEditMode() {
            if (!isAdmin) {
                showNotification('Admin access required', 'error');
                return;
            }
            
            editMode = !editMode;
            
            if (editMode) {
                enableEditMode();
                document.getElementById('editModeText').textContent = 'Disable Edit Mode';
                showNotification('Edit mode enabled', 'info');
            } else {
                disableEditMode();
                document.getElementById('editModeText').textContent = 'Enable Edit Mode';
                showNotification('Edit mode disabled', 'info');
            }
        }

        function enableEditMode() {
            document.body.classList.add('edit-mode');
            const editableElements = document.querySelectorAll('.content-editable');
            editableElements.forEach(element => {
                element.contentEditable = true;
            });
        }

        function disableEditMode() {
            document.body.classList.remove('edit-mode');
            const editableElements = document.querySelectorAll('.content-editable');
            editableElements.forEach(element => {
                element.contentEditable = false;
            });
        }

        // ==================== ADMIN HELPER FUNCTIONS ====================
        function loadCurrentValues() {
            if (isAdmin) {
                document.getElementById('editDoctorName').value = document.getElementById('doctorNameDisplay').textContent;
                document.getElementById('editDoctorSpecialty').value = document.getElementById('doctorSpecialty').textContent;
                document.getElementById('editHeroTitle').value = document.getElementById('heroTitle').textContent;
                document.getElementById('editHeroText').value = document.getElementById('heroText').textContent;
                document.getElementById('editContactIntro').value = document.getElementById('contactIntro').textContent;
            }
        }

        function updateDoctorInfo() {
            if (!isAdmin) return;
            
            const name = document.getElementById('editDoctorName').value;
            const specialty = document.getElementById('editDoctorSpecialty').value;
            
            document.getElementById('doctorNameHeader').textContent = name;
            document.getElementById('doctorNameDisplay').textContent = name;
            document.getElementById('doctorSpecialty').textContent = specialty;
            document.getElementById('footerCopyright').textContent = `© ${new Date().getFullYear()} ${name}. All rights reserved.`;
            
            saveContentToBackend();
        }

        function updateHero() {
            if (!isAdmin) return;
            
            document.getElementById('heroTitle').textContent = document.getElementById('editHeroTitle').value;
            document.getElementById('heroText').textContent = document.getElementById('editHeroText').value;
            saveContentToBackend();
        }

        // ==================== PHOTO MANAGEMENT ====================
        function triggerPhotoUpload(type) {
            if (isAdmin) {
                if (type === 'hero') {
                    document.getElementById('photoUpload').click();
                }
            }
        }

        async function uploadPhoto(type) {
            if (!isAdmin) {
                showNotification('Admin access required', 'error');
                return;
            }
            
            const fileInput = type === 'hero' ? document.getElementById('photoUpload') : document.getElementById('aboutPhotoUpload');
            const file = fileInput.files[0];
            
            if (!file) {
                showNotification('No file selected', 'error');
                return;
            }
            
            if (!file.type.startsWith('image/')) {
                showNotification('Please select an image file', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('photo', file);
            
            try {
                const response = await fetch(`${API_BASE_URL}/upload/photo`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${authToken}`
                    },
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    if (type === 'hero') {
                        currentHeroPhotoUrl = data.photo_url;
                        updateHeroPhotoDisplay(currentHeroPhotoUrl);
                    } else {
                        currentAboutPhotoUrl = data.photo_url;
                        updateAboutPhotoDisplay(currentAboutPhotoUrl);
                    }
                    showNotification('Photo uploaded successfully!', 'success');
                } else {
                    showNotification(data.error || 'Failed to upload photo', 'error');
                }
            } catch (error) {
                console.error('Upload error:', error);
                showNotification('Failed to upload photo', 'error');
            }
            
            fileInput.value = '';
        }

        function updateHeroPhotoDisplay(photoUrl) {
            const doctorPhoto = document.getElementById('doctorPhoto');
            const placeholder = document.querySelector('.doctor-photo .photo-placeholder');
            
            if (photoUrl) {
                doctorPhoto.src = photoUrl;
                doctorPhoto.style.display = 'block';
                placeholder.style.display = 'none';
            } else {
                doctorPhoto.style.display = 'none';
                placeholder.style.display = 'flex';
            }
        }

        function updateAboutPhotoDisplay(photoUrl) {
            const aboutPhoto = document.getElementById('aboutPhoto');
            const placeholder = document.querySelector('.profile-photo .photo-placeholder');
            
            if (photoUrl) {
                aboutPhoto.src = photoUrl;
                aboutPhoto.style.display = 'block';
                placeholder.style.display = 'none';
            } else {
                aboutPhoto.style.display = 'none';
                placeholder.style.display = 'flex';
            }
        }

        // ==================== CONTACT FORM ====================
        async function submitContactForm() {
            const formData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                phone: document.getElementById('phone').value,
                address: document.getElementById('address').value,
                project_type: document.getElementById('project-type').value,
                message: document.getElementById('message').value
            };
            
            // Validation
            if (!formData.name || !formData.email || !formData.message) {
                showNotification('Please fill in all required fields', 'error');
                return;
            }
            
            if (!isValidEmail(formData.email)) {
                showNotification('Please enter a valid email address', 'error');
                return;
            }
            
            try {
                const response = await fetch(`${API_BASE_URL}/clients`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showNotification(`Thank you ${formData.name}! Your message has been sent.`, 'success');
                    document.getElementById('contactForm').reset();
                    
                    // Scroll to top
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                    
                    // If admin is logged in, update notification
                    if (isAdmin) {
                        setTimeout(() => {
                            loadMessageStats();
                        }, 1000);
                    }
                } else {
                    showNotification(data.error || 'Failed to submit form', 'error');
                }
            } catch (error) {
                console.error('Form submission error:', error);
                showNotification('Failed to submit form. Please try again.', 'error');
            }
        }

        // ==================== HELPER FUNCTIONS ====================
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function isValidEmail(email) {
            const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return re.test(email);
        }
    </script>
</body>
</html>
'''

# ==================== MAIN EXECUTION ====================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Medical Portfolio System')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Create and run the application
    app = MedicalPortfolioApp()
    app.run(host=args.host, port=args.port, debug=args.debug)