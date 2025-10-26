"""
Migration script to add email_password, instagram_username, instagram_password, and phone_number to User model.
"""
from models import db
from flask import Flask
from sqlalchemy import text

def migrate():
    # Add columns if they don't exist
    with db.engine.connect() as conn:
        # email_password
        conn.execute(text('ALTER TABLE user ADD COLUMN email_password VARCHAR(100) NOT NULL DEFAULT ""'))
        # instagram_username
        conn.execute(text('ALTER TABLE user ADD COLUMN instagram_username VARCHAR(100) NOT NULL DEFAULT ""'))
        # instagram_password
        conn.execute(text('ALTER TABLE user ADD COLUMN instagram_password VARCHAR(100) NOT NULL DEFAULT ""'))
        # phone_number
        conn.execute(text('ALTER TABLE user ADD COLUMN phone_number VARCHAR(30) NOT NULL DEFAULT ""'))
        conn.commit()

if __name__ == '__main__':
    app = Flask(__name__)
    app.config.from_object('config.Config')
    db.init_app(app)
    with app.app_context():
        migrate()
        print("Migration complete.")
