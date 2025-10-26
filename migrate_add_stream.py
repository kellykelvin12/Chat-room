"""
Migration script to add stream field to User model.
"""
from models import db
from flask import Flask
from sqlalchemy import text

def migrate():
    # Add stream column if it doesn't exist
    with db.engine.connect() as conn:
        conn.execute(text('ALTER TABLE user ADD COLUMN stream VARCHAR(50) NOT NULL DEFAULT "West"'))
        conn.commit()

if __name__ == '__main__':
    app = Flask(__name__)
    app.config.from_object('config.Config')
    db.init_app(app)
    with app.app_context():
        migrate()
        print("Migration complete.")