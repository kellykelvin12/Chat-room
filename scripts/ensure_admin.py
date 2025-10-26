import sys
sys.path.insert(0, r'c:/Users/vokek/OneDrive/Desktop/chat room 8 by deepseek')
from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(name='Administrator', class_name='Staff', username='admin', password=generate_password_hash('admin123'), email='admin@riverschool.edu.gh', status='approved', is_admin=True, admin_level=2)
        db.session.add(u)
        db.session.commit()
        print('Created admin with admin_level=2')
    else:
        print('Found admin: is_admin=', u.is_admin, 'admin_level=', u.admin_level)
        if not u.is_admin or u.admin_level < 2:
            u.is_admin = True
            u.admin_level = 2
            db.session.commit()
            print('Upgraded admin to admin_level=2')
        else:
            print('No changes required')
