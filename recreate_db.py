from app import app, db
import os

def recreate_db():
    # Remove existing database
    if os.path.exists('instance/gossip.db'):
        os.remove('instance/gossip.db')
    
    # Create new database with tables
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    recreate_db()