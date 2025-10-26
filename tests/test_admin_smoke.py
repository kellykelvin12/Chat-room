import pytest
from app import app, db
from models import User
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


def create_user(username, is_admin=False, admin_level=0, status='approved'):
    user = User(
        name=username,
        class_name='Test',
        username=username,
        password=generate_password_hash('pass'),
        email=f'{username}@example.com',
        status=status,
        is_admin=is_admin,
        admin_level=admin_level
    )
    db.session.add(user)
    db.session.commit()
    return user


def login(client, username):
    return client.post('/login', data={'username': username, 'password': 'pass'}, follow_redirects=True)


def test_admin_access_levels(client):
    # Create users
    full_admin = create_user('fulladmin', is_admin=True, admin_level=2)
    limited_admin = create_user('limited', is_admin=True, admin_level=1)
    normal_user = create_user('normal', is_admin=False, admin_level=0)

    # Full admin should access /admin
    login(client, 'fulladmin')
    r = client.get('/admin')
    assert r.status_code == 200, f'Full admin could not access /admin: {r.status_code}'

    # Limited admin should be blocked from /admin
    client.get('/logout')
    login(client, 'limited')
    r = client.get('/admin', follow_redirects=False)
    assert r.status_code in (302, 403), f'Limited admin expected redirect or forbidden for /admin, got {r.status_code}'

    # Limited admin should access admin debug endpoint
    r = client.get('/admin/active_users_debug')
    assert r.status_code == 200, f'Limited admin could not access active_users_debug: {r.status_code}'

    # Normal user should be blocked from admin debug
    client.get('/logout')
    login(client, 'normal')
    r = client.get('/admin/active_users_debug', follow_redirects=False)
    assert r.status_code in (302, 403), f'Normal user should not access admin debug, got {r.status_code}'
