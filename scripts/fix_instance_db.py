"""fix_instance_db.py
Ensure the `private_message` table with `is_read` exists in the DB that SQLAlchemy actually uses (db.engine.url).
Run: python scripts\fix_instance_db.py
"""
import sys
import pathlib
import os
import sqlite3
from urllib.parse import urlparse

# Ensure project root on path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app import app
    from models import db
except Exception as e:
    print('Failed to import app/models:', e)
    raise

with app.app_context():
    # Prefer using db.engine.url if available
    engine_url = None
    try:
        engine_url = db.engine.url
        print('db.engine.url =', engine_url)
    except Exception as e:
        print('Could not access db.engine.url:', e)

    db_path = None
    if engine_url is not None:
        # engine_url may be a URL object; convert to string
        s = str(engine_url)
        if s.startswith('sqlite:///'):
            db_path = s.replace('sqlite:///', '')
        elif s.startswith('sqlite://'):
            db_path = s.replace('sqlite://', '')
        else:
            db_path = 'gossip.db'
    else:
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI')
        if db_path and db_path.startswith('sqlite:///'):
            db_path = db_path.replace('sqlite:///', '')
        else:
            db_path = 'gossip.db'

    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)

    print('Target DB file:', db_path)
    print('Exists:', os.path.exists(db_path))

    # Connect and inspect
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print('Tables in DB:', tables)

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
            print('private_message table created in', db_path)
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
                print('is_read column added to', db_path)
            except Exception as e:
                print('Failed to add is_read column:', e)

    cur.close()
    conn.close()

print('Done. Restart Flask app.')