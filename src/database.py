import sqlite3
import os
import json
from datetime import datetime

class Database:
    def __init__(self, db_path="data/projects.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        
        # 1.Проекты
        cursor.execute('''CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_path TEXT NOT NULL,
            audio_path TEXT,
            last_opened TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
            created_date TIMESTAMP DEFAULT (DATETIME('now', 'localtime'))
        )''')
        
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'last_opened' not in columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN last_opened TIMESTAMP DEFAULT (DATETIME('now', 'localtime'))")
        
        if 'created_date' not in columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN created_date TIMESTAMP DEFAULT (DATETIME('now', 'localtime'))")
        
        # 2. Результаты анализа
        cursor.execute('''CREATE TABLE IF NOT EXISTS analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            analysis_date TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
            duration REAL,
            phonemes_json TEXT NOT NULL,
            text_transcript TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )''')
        
        # 3. Состояние поиска
        cursor.execute('''CREATE TABLE IF NOT EXISTS search_state (
            project_id INTEGER PRIMARY KEY,
            pattern TEXT,
            pattern_type TEXT,
            selected_exports TEXT,
            last_search TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )''')
        
        # 4. Настройки
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        self.conn.commit()
        self._init_default_settings()
    
    

    def _init_default_settings(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] == 0:
            default_settings = [
                ("projects_dir", os.path.expanduser("~/Documents/[ф]оноскоп")),
                ("auto_save", "1"),
                ("auto_analysis", "1"),
            ]
            for key, value in default_settings:
                cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
            self.conn.commit()
    
    def add_project(self, name, project_path, audio_path=None):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, project_path, audio_path, last_opened, created_date) VALUES (?, ?, ?, DATETIME('now', 'localtime'), DATETIME('now', 'localtime'))",
            (name, project_path, audio_path)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_project(self, project_id, audio_path=None):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE projects SET audio_path = ?, last_opened = DATETIME('now', 'localtime') WHERE id = ?",
            (audio_path, project_id)
        )
        self.conn.commit()
    
    def get_all_projects(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, name, project_path, audio_path, last_opened, created_date FROM projects ORDER BY last_opened DESC"
        )
        return cursor.fetchall()
    
    def get_project(self, project_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, name, project_path, audio_path FROM projects WHERE id = ?",
            (project_id,)
        )
        return cursor.fetchone()
    
    def delete_project(self, project_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()

    def update_project_path(self, project_id, new_path):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE projects SET project_path = ? WHERE id = ?",
            (new_path, project_id)
        )
        self.conn.commit()
    
    def save_analysis(self, project_id, phonemes_data, text_transcript="", duration=0):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM analysis WHERE project_id = ?", (project_id,))
        phonemes_json = json.dumps(phonemes_data, ensure_ascii=False)
        cursor.execute(
            "INSERT INTO analysis (project_id, duration, phonemes_json, text_transcript) VALUES (?, ?, ?, ?)",
            (project_id, duration, phonemes_json, text_transcript)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_analysis(self, project_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT duration, phonemes_json, text_transcript, analysis_date FROM analysis WHERE project_id = ? ORDER BY analysis_date DESC LIMIT 1",
            (project_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'duration': row['duration'],
                'phonemes': json.loads(row['phonemes_json']),
                'text_transcript': row['text_transcript'],
                'analysis_date': row['analysis_date']
            }
        return None
    
    def save_search_state(self, project_id, pattern, pattern_type, selected_exports=None):
        cursor = self.conn.cursor()
        selected_json = json.dumps(selected_exports) if selected_exports else None
        cursor.execute(
            "INSERT OR REPLACE INTO search_state (project_id, pattern, pattern_type, selected_exports, last_search) VALUES (?, ?, ?, ?, DATETIME('now', 'localtime'))",
            (project_id, pattern, pattern_type, selected_json)
        )
        self.conn.commit()
    
    def get_search_state(self, project_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT pattern, pattern_type, selected_exports FROM search_state WHERE project_id = ?",
            (project_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'pattern': row['pattern'],
                'pattern_type': row['pattern_type'],
                'selected_exports': json.loads(row['selected_exports']) if row['selected_exports'] else None
            }
        return None
    
    def get_setting(self, key, default=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default
    
    def set_setting(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()