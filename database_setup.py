import os
import sqlite3
from datetime import datetime
from logger_config import log

# Configuration
DB_PATH = "jobs_detail.db"

# Connection
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

# Table Creation
def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL UNIQUE,
            category TEXT,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT,
            job_type TEXT,
            budget_amount REAL,
            hourly_min REAL,
            hourly_max REAL,
            contractor_tier INTEGER,
            duration TEXT,
            skills TEXT,
            published_time TEXT,
            created_time TEXT,
            first_seen_at TEXT DEFAULT (datetime('now')),
            discord_posted INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

def save_job(job_data):
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO jobs (
                job_id, category, title, description, url, job_type, budget_amount, 
                hourly_min, hourly_max, contractor_tier, duration, 
                skills, published_time, created_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_data.get('id'),
            job_data.get('category'),
            job_data.get('title'),
            job_data.get('description'),
            job_data.get('url'),
            job_data.get('job_type'),
            job_data.get('budget'),
            job_data.get('hourly_min'),
            job_data.get('hourly_max'),
            job_data.get('tier'),
            job_data.get('duration'),
            job_data.get('skills'),
            job_data.get('published_time'),
            job_data.get('created_time')
        ))
        conn.commit()
    except Exception as e:
        print(f"Database Save Error: {e}")
    finally:
        conn.close()



"""
# Initialize Database
create_tables()
log.info("✅ Database initialized and tables created.")
"""