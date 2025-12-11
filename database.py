import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
import threading

class Database:
    """Thread-safe SQLite database handler for Nerd Master Bot"""
    
    _local = threading.local()
    
    def __init__(self, db_path: str = "nerd_master.db"):
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # User settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                ai_provider TEXT DEFAULT 'gemini',
                openai_model TEXT DEFAULT 'gpt-4o',
                gemini_model TEXT DEFAULT 'gemini-1.5-pro',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Chat history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                message_id INTEGER,
                role TEXT,
                content TEXT,
                ai_provider TEXT,
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Group settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_settings (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                ai_enabled BOOLEAN DEFAULT 1,
                ai_provider TEXT DEFAULT 'gemini',
                openai_model TEXT DEFAULT 'gpt-4o',
                gemini_model TEXT DEFAULT 'gemini-1.5-pro',
                welcome_enabled BOOLEAN DEFAULT 1,
                welcome_message TEXT,
                admin_only_ai BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Usage statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                ai_provider TEXT,
                model TEXT,
                tokens_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
    
    def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user settings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def set_user_settings(self, user_id: int, username: str = None, **kwargs):
        """Set or update user settings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        existing = self.get_user_settings(user_id)
        if existing:
            updates = []
            values = []
            for key, value in kwargs.items():
                updates.append(f"{key} = ?")
                values.append(value)
            updates.append("updated_at = ?")
            values.append(datetime.now())
            values.append(user_id)
            
            query = f"UPDATE user_settings SET {', '.join(updates)} WHERE user_id = ?"
            cursor.execute(query, values)
        else:
            columns = ['user_id', 'username'] + list(kwargs.keys())
            values = [user_id, username] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            
            query = f"INSERT INTO user_settings ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(query, values)
        
        conn.commit()
    
    def get_group_settings(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Get group settings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM group_settings WHERE chat_id = ?', (chat_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def set_group_settings(self, chat_id: int, chat_title: str = None, **kwargs):
        """Set or update group settings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        existing = self.get_group_settings(chat_id)
        if existing:
            updates = []
            values = []
            for key, value in kwargs.items():
                updates.append(f"{key} = ?")
                values.append(value)
            updates.append("updated_at = ?")
            values.append(datetime.now())
            values.append(chat_id)
            
            query = f"UPDATE group_settings SET {', '.join(updates)} WHERE chat_id = ?"
            cursor.execute(query, values)
        else:
            columns = ['chat_id', 'chat_title'] + list(kwargs.keys())
            values = [chat_id, chat_title] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            
            query = f"INSERT INTO group_settings ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(query, values)
        
        conn.commit()
    
    def add_chat_history(self, user_id: int, chat_id: int, message_id: int, 
                         role: str, content: str, ai_provider: str, model: str):
        """Add chat history entry"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_history (user_id, chat_id, message_id, role, content, ai_provider, model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, chat_id, message_id, role, content, ai_provider, model))
        conn.commit()
    
    def get_chat_history(self, chat_id: int, limit: int = 10) -> list:
        """Get recent chat history for context"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, content FROM chat_history 
            WHERE chat_id = ? 
            ORDER BY created_at DESC LIMIT ?
        ''', (chat_id, limit))
        rows = cursor.fetchall()
        return [{"role": row['role'], "content": row['content']} for row in reversed(rows)]
    
    def clear_chat_history(self, chat_id: int, user_id: int = None):
        """Clear chat history"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute('DELETE FROM chat_history WHERE chat_id = ? AND user_id = ?', 
                          (chat_id, user_id))
        else:
            cursor.execute('DELETE FROM chat_history WHERE chat_id = ?', (chat_id,))
        conn.commit()
    
    def add_usage_stat(self, user_id: int, chat_id: int, ai_provider: str, 
                       model: str, tokens_used: int):
        """Add usage statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO usage_stats (user_id, chat_id, ai_provider, model, tokens_used)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, chat_id, ai_provider, model, tokens_used))
        conn.commit()
    
    def get_usage_stats(self, user_id: int = None, chat_id: int = None) -> Dict[str, Any]:
        """Get usage statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        conditions = []
        values = []
        
        if user_id:
            conditions.append("user_id = ?")
            values.append(user_id)
        if chat_id:
            conditions.append("chat_id = ?")
            values.append(chat_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor.execute(f'''
            SELECT ai_provider, model, COUNT(*) as requests, SUM(tokens_used) as total_tokens
            FROM usage_stats WHERE {where_clause}
            GROUP BY ai_provider, model
        ''', values)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# Global database instance
db = Database()
