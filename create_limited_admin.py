from models import db, User
from werkzeug.security import generate_password_hash
from app import app

with app.app_context():
    username = 'admin2'
    password = 'test1234'
    if User.query.filter_by(username=username).first():
        print('User already exists')
    else:
        user = User(
            name='Limited Admin',
            class_name='N/A',
            username=username,
            password=generate_password_hash(password),
            email='admin2@example.com',
            status='approved',
            is_admin=True,
            admin_level=1
        )
        db.session.add(user)
        db.session.commit()
        print('Limited admin user created: username=admin2, password=test1234')
