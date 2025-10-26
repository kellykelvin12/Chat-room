"""Create private_message table in the DB SQLAlchemy uses if it is missing.
Run: python scripts\create_private_message_table.py
"""
import sys
import pathlib
import os
import sqlite3

# Ensure project root on path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import app

uri = app.config.get('SQLALCHEMY_DATABASE_URI')
print('SQLALCHEMY_DATABASE_URI =', uri)

if uri and uri.startswith('sqlite:///'):
    db_path = uri.replace('sqlite:///', '')
else:
    db_path = 'gossip.db'

if not os.path.isabs(db_path):
    db_path = os.path.join(os.getcwd(), db_path)

print('Using DB file:', db_path)

# Connect
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check existing tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)

# Check if private_message exists
if 'private_message' not in tables:
    print('private_message not found. Creating table with is_read column...')
    create_sql = (
        "CREATE TABLE IF NOT EXISTS private_message ("
        "id TEXT PRIMARY KEY, "
        "chat_id TEXT, "
        "admin_id TEXT, "
        "user_id TEXT, "
        "content TEXT NOT NULL, "
        "image_path TEXT, "
        "voice_path TEXT, "
        "identity_revealed INTEGER DEFAULT 0, "
        "voice_type TEXT DEFAULT 'normal', "
        "is_read INTEGER DEFAULT 0, "
        "created_at DATETIME"
        ")"
    )
    try:
        cur.execute(create_sql)
        conn.commit()
        print('private_message table created.')
    except Exception as e:
        print('Failed to create table:', e)
else:
    print('private_message already exists; checking columns...')
    cur.execute("PRAGMA table_info(private_message)")
    cols = cur.fetchall()
    print('Columns:', cols)
    col_names = [c[1] for c in cols]
    if 'is_read' not in col_names:
        print('is_read missing; adding column...')
        try:
            cur.execute('ALTER TABLE private_message ADD COLUMN is_read INTEGER DEFAULT 0')
            conn.commit()
            print('is_read column added.')
        except Exception as e:
            print('Failed to add is_read column:', e)

cur.close()
conn.close()
print('Done. Restart Flask app to pick up the schema changes.')