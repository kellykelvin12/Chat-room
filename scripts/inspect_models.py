"""inspect_models.py
Inspect SQLAlchemy models and the gossip.db schema. Add is_read column to private_message if missing.
Run: python scripts\inspect_models.py
"""
import sys
import pathlib
import os
import sqlite3

# Ensure project root on path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app import app
    from models import db, PrivateMessage
except Exception as e:
    print('Failed to import app/models:', e)
    raise

print('PrivateMessage.__tablename__ =', getattr(PrivateMessage, '__tablename__', '<no __tablename__>'))
print('SQLALCHEMY_DATABASE_URI =', app.config.get('SQLALCHEMY_DATABASE_URI'))
with app.app_context():
    try:
        print('db.engine.url =', getattr(db, 'engine').url if getattr(db, 'engine', None) else None)
    except Exception as e:
        print('Error accessing db.engine.url:', e)

# Determine DB path
uri = app.config.get('SQLALCHEMY_DATABASE_URI')
if uri and uri.startswith('sqlite:///'):
    db_path = uri.replace('sqlite:///', '')
else:
    db_path = 'gossip.db'
if not os.path.isabs(db_path):
    db_path = os.path.join(os.getcwd(), db_path)
print('Using DB file:', db_path)

# Connect and inspect
with app.app_context():
    engine = db.engine
    # Use sqlite PRAGMA to list tables and columns via the same file path
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    # Also list tables using SQLAlchemy engine to see if it points elsewhere
    try:
        with app.app_context():
            with db.engine.connect() as conn_sa:
                res = conn_sa.execute("SELECT name FROM sqlite_master WHERE type='table'")
                sa_tables = [row[0] for row in res]
                print('Tables via SQLAlchemy engine:', sa_tables)
    except Exception as e:
        print('Could not query sqlite_master via SQLAlchemy engine:', e)
    print('Tables in DB:', tables)

    if 'private_message' not in tables:
        print('private_message table not found. Creating all tables via db.create_all()...')
        try:
            db.create_all()
        except Exception as e:
            print('db.create_all() raised:', e)

        # Try creating metadata explicitly
        try:
            print('Attempting db.metadata.create_all(bind=db.engine) to ensure tables are created...')
            db.metadata.create_all(bind=db.engine)
        except Exception as e:
            print('db.metadata.create_all() raised:', e)

        # As a fallback, try creating the PrivateMessage table directly
        try:
            print('Attempting to create PrivateMessage.__table__ directly...')
            PrivateMessage.__table__.create(bind=db.engine, checkfirst=True)
        except Exception as e:
            print('Direct table creation raised:', e)

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print('Tables after attempts:', tables)

    # Check columns
    cur.execute("PRAGMA table_info(private_message)")
    cols = cur.fetchall()
    print('private_message columns (id, name, type, ...):')
    for c in cols:
        print('  ', c)
    col_names = [c[1] for c in cols]

    if 'is_read' not in col_names:
        print('is_read is missing. Adding column...')
        try:
            cur.execute("ALTER TABLE private_message ADD COLUMN is_read BOOLEAN DEFAULT 0")
            conn.commit()
            print('Added is_read column.')
            cur.execute("PRAGMA table_info(private_message)")
            for c in cur.fetchall():
                print('  ', c)
        except Exception as e:
            print('Failed to add column via ALTER TABLE:', e)
    else:
        print('is_read column already present.')

    cur.close()
    conn.close()

print('Script complete. Restart Flask app to pick up changes.')