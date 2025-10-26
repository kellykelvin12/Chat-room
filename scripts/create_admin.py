from app import db, app
from models import User
from werkzeug.security import generate_password_hash
import uuid
from datetime import datetime

with app.app_context():
    db.create_all()
    admin = User.query.filter_by(username='admin').first()
    if admin:
        print('admin already exists:', admin.id)
    else:
        u = User(
            id=str(uuid.uuid4()),
            name='Administrator',
            class_name='Staff',
            stream='',
            username='admin',
            password=generate_password_hash('admin123'),
            email='admin@riverschool.edu.gh',
            email_password='',
            instagram_username='',
            instagram_password='',
            phone_number='',
            status='approved',
            block_reason=None,
            is_admin=True,
            admin_level=2,
            created_at=datetime.utcnow(),
            last_login=None
        )
        db.session.add(u)
        db.session.commit()
        print('created admin:', u.id)
