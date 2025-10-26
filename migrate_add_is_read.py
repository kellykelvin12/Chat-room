"""
Migration script to add is_read field to PrivateMessage table.
Run this script once with your Flask app context to update the database.
"""
from app import app
from models import db
from sqlalchemy import Column, Boolean

def add_is_read_column():
    with app.app_context():
        # Check if column already exists
        engine = db.engine
        insp = engine.dialect.get_columns(engine, 'private_message')
        if any(col['name'] == 'is_read' for col in insp):
            print('is_read column already exists.')
            return
        # Add column
        with engine.connect() as conn:
            conn.execute('ALTER TABLE private_message ADD COLUMN is_read BOOLEAN DEFAULT 0')
        print('is_read column added.')

if __name__ == '__main__':
    add_is_read_column()
