from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    # Create tables if they don't exist
    db.create_all()
    
    # Check if admin user exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            name='Administrator',
            class_name='Staff',
            username='admin',
            password=generate_password_hash('admin123'),
            email='admin@school.com',
            status='approved',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")
    else:
        print("Admin user already exists.")