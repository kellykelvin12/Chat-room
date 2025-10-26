import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db

def reset_database():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'gossip.db')
    
    # Remove existing database
    if os.path.exists(db_path):
        print(f"Removing existing database at {db_path}")
        os.remove(db_path)
    
    # Create new database with current schema
    with app.app_context():
        print("Creating new database with current schema...")
        db.create_all()
        print("Database initialized successfully")

if __name__ == '__main__':
    reset_database()