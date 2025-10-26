"""ensure_db.py
Checks gossip.db schema and fixes private_message.is_read column.
Run from project root with the virtualenv active: python scripts\ensure_db.py
"""
import os
import sqlite3
from urllib.parse import urlparse

import sys
import pathlib

# Ensure project root is on sys.path so imports like 'app' succeed
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Attempt to import app and db
try:
    from app import app
    from models import db
except Exception as e:
    print('Error importing app/models:', e)
    print('sys.path:', sys.path[:5])
    raise

uri = app.config.get('SQLALCHEMY_DATABASE_URI')
print('SQLALCHEMY_DATABASE_URI =', uri)

# Determine sqlite file path
db_path = None
if uri and uri.startswith('sqlite:///'):
    db_path = uri.replace('sqlite:///', '')
elif uri and uri.startswith('sqlite://'):
    db_path = uri.replace('sqlite://', '')
else:
    # fallback: gossip.db in cwd
    db_path = 'gossip.db'

# Normalize path
if not os.path.isabs(db_path):
    db_path = os.path.join(os.getcwd(), db_path)

print('Using DB file:', db_path)

# Ensure directory exists
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

# Create tables if file or table missing
with app.app_context():
    # Connect sqlite directly to check schema
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(private_message)")
        cols = cur.fetchall()
        print('private_message columns:', cols)
        col_names = [c[1] for c in cols]
        if not cols:
            print('private_message table not found. Running db.create_all() to create all tables...')
            db.create_all()
            # Re-check
            cur.execute("PRAGMA table_info(private_message)")
            cols = cur.fetchall()
            print('After create_all, private_message columns:', cols)
        else:
            if 'is_read' not in col_names:
                print('is_read column missing; adding it now...')
                try:
                    cur.execute("ALTER TABLE private_message ADD COLUMN is_read BOOLEAN DEFAULT 0")
                    conn.commit()
                    print('is_read column added successfully.')
                except Exception as e:
                    print('Failed to add is_read column via ALTER TABLE:', e)
                    print('Attempting to recreate table by using SQLAlchemy db.create_all() (may not alter existing table)...')
                    db.create_all()
            else:
                print('is_read column already present.')
    finally:
        cur.close()
        conn.close()

print('Done. Restart your Flask app now.')