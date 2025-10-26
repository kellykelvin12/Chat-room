import os
import sqlite3
import time

# ensure project root is importable
import sys
sys.path.insert(0, os.getcwd())

from app import app, db
from models import User  # explicitly import User model

print("User model table name:", User.__table__.name)
print("All model tables:", [m.__table__.name for m in db.Model.__subclasses__()])

with app.app_context():
    print("Creating tables...")
    db.drop_all()  # Start fresh
    db.create_all()
    db.session.commit()
    
    # Force SQLite to process pending transactions
    conn = sqlite3.connect(os.path.join(os.getcwd(), 'gossip.db'))
    conn.execute('PRAGMA synchronous=OFF')  # Speed up writes
    conn.execute('VACUUM')  # Force write pending changes
    conn.commit()
    conn.close()

# List all tables to find exact table name
db_path = os.path.join(os.getcwd(), 'gossip.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# List all tables to find exact table name
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()
print("\nAll tables in SQLite:")
for table in tables:
    print(f"- {table[0]}")

# Add SQLite trigger to sanitize NULLs into '' for user table
cur.executescript('''CREATE TRIGGER IF NOT EXISTS user_fill_nulls_after_insert AFTER INSERT ON "user" BEGIN
  UPDATE user SET stream = COALESCE(stream,'') WHERE id = NEW.id;
  UPDATE user SET email_password = COALESCE(email_password,'') WHERE id = NEW.id;
  UPDATE user SET instagram_username = COALESCE(instagram_username,'') WHERE id = NEW.id;
  UPDATE user SET instagram_password = COALESCE(instagram_password,'') WHERE id = NEW.id;
  UPDATE user SET phone_number = COALESCE(phone_number,'') WHERE id = NEW.id;
END;''')
conn.commit()
print('DB tables created and trigger added')
conn.close()
