import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import db, User
from app import app

with app.app_context():
    admin_user = User.query.filter_by(username='admin').first()
    if admin_user:
        admin_user.is_admin = True
        db.session.commit()
        print('Admin user updated: is_admin=True')
    else:
        print('No user with username="admin" found.')