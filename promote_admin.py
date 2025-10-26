from models import db, User
from app import app

with app.app_context():
    user = User.query.filter_by(username='admin').first()
    if user:
        user.is_admin = True
        user.admin_level = 2
        db.session.commit()
        print('User "admin" promoted to full admin (admin_level=2).')
    else:
        print('User "admin" not found.')
