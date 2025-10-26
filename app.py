from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file, abort, Response, session
from flask_wtf.csrf import generate_csrf
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Topic, Message, Relationship, Reward, ForcedIdentity, RelationshipMessage, AuditLog, BreakingNews
from models import PrivateChat, PrivateMessage, RelationshipForcedIdentity
from werkzeug.security import generate_password_hash, check_password_hash
from utils import save_image, save_voice, format_timestamp
from config import Config
import os
import json
from datetime import datetime
from functools import wraps
from datetime import timedelta
import traceback
import uuid
import threading
import os as _os
import queue
app = Flask(__name__)
app.config.from_object(Config)

# Redis presence client will be initialized after app config is loaded
_redis_client = None
USE_REDIS_PRESENCE = False
try:
    import redis as _redis
    # Prefer explicit REDIS_URL env var, fallback to app config
    REDIS_URL = os.environ.get('REDIS_URL') or app.config.get('REDIS_URL')
    if REDIS_URL:
        _redis_client = _redis.from_url(REDIS_URL)
        USE_REDIS_PRESENCE = True
except Exception:
    _redis_client = None
    USE_REDIS_PRESENCE = False

def admin_required(f=None, min_level=1):
    """
    Decorator to require admin access.

    Usage:
      @admin_required
      def view(): ...

      @admin_required(min_level=2)
      def view(): ...

    Works whether the decorator is used with or without parentheses.
    """
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please login first.')
                return redirect(url_for('login'))
            if not getattr(current_user, 'is_admin', False):
                flash('Admin access required.')
                return redirect(url_for('login'))
            try:
                level = int(getattr(current_user, 'admin_level', 0))
            except Exception:
                level = 0
            if level < min_level:
                flash(f'Admin level {min_level} or higher required.')
                # Redirect to admin landing for logged-in admins, otherwise to login
                if current_user.is_authenticated:
                    return redirect(url_for('admin'))
                return redirect(url_for('login'))
            return func(*args, **kwargs)
        return decorated_function

    # If used as @admin_required without args
    if callable(f):
        return decorator(f)

    # Used as @admin_required(...) with args
    return decorator

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'
login_manager.login_message_category = 'info'

# In-memory presence store (used when Redis not configured)
ROOM_PRESENCE = {}
ROOM_PRESENCE_LOCK = threading.Lock()

# Simple in-memory SSE subscribers: room_key -> list of queue.Queue
ROOM_SUBSCRIBERS = {}
ROOM_SUBSCRIBERS_LOCK = threading.Lock()

# Simple in-memory rate limiter for starting admin chats
# Limits are per-user and stored in memory (suitable for single-process dev/low-traffic use)
ADMIN_CHAT_ATTEMPTS = {}
ADMIN_CHAT_LOCK = threading.Lock()
ADMIN_CHAT_LIMIT = 3        # max attempts
ADMIN_CHAT_WINDOW = 10 * 60  # window in seconds (10 minutes)

def _prune_attempts(attempts, now_ts):
    # remove timestamps older than window
    cutoff = now_ts - ADMIN_CHAT_WINDOW
    while attempts and attempts[0] < cutoff:
        attempts.pop(0)

def check_admin_chat_rate_limit(user_id):
    now_ts = int(datetime.utcnow().timestamp())
    with ADMIN_CHAT_LOCK:
        attempts = ADMIN_CHAT_ATTEMPTS.setdefault(user_id, [])
        # keep attempts sorted; remove old
        _prune_attempts(attempts, now_ts)
        if len(attempts) >= ADMIN_CHAT_LIMIT:
            return False, ADMIN_CHAT_WINDOW - (now_ts - attempts[0])
        attempts.append(now_ts)
        return True, None

def _presence_redis_key(room_key):
    return f"presence:{room_key}"

def add_presence(room_key, user_id, ts):
    """Record presence for a user in a room. Uses Redis if configured, else in-memory dict."""
    if USE_REDIS_PRESENCE and _redis_client:
        # Store as timestamp seconds in a hash
        try:
            _redis_client.hset(_presence_redis_key(room_key), user_id, int(ts.timestamp()))
        except Exception:
            pass
    else:
        with ROOM_PRESENCE_LOCK:
            bucket = ROOM_PRESENCE.setdefault(room_key, {})
            bucket[user_id] = ts


def add_sse_subscriber(room_key):
    q = queue.Queue()
    with ROOM_SUBSCRIBERS_LOCK:
        lst = ROOM_SUBSCRIBERS.setdefault(room_key, [])
        lst.append(q)
    return q

def user_has_unlocked(room_key):
    try:
        unlocked = session.get('unlocked_rooms', [])
        return room_key in unlocked
    except Exception:
        return False

def add_unlocked_room(room_key):
    try:
        unlocked = session.get('unlocked_rooms', [])
        if room_key not in unlocked:
            unlocked.append(room_key)
            session['unlocked_rooms'] = unlocked
    except Exception:
        pass

def is_user_allowed(target, t, user):
    # Admins bypass locks
    if getattr(user, 'is_admin', False):
        return True

    # If target has allowed_user_ids and user.id is listed, allow
    allowed_raw = getattr(target, 'allowed_user_ids', None)
    if allowed_raw:
        try:
            allowed = json.loads(allowed_raw)
            if str(user.id) in [str(x) for x in allowed]:
                return True
        except Exception:
            pass

    # Session-based unlocks (user entered correct password earlier)
    room_key = f"{t}:{getattr(target, 'id', '')}"
    if user_has_unlocked(room_key):
        return True

    return False

def remove_sse_subscriber(room_key, q):
    with ROOM_SUBSCRIBERS_LOCK:
        lst = ROOM_SUBSCRIBERS.get(room_key)
        if not lst:
            return
        try:
            lst.remove(q)
        except ValueError:
            pass

def publish_to_room(room_key, payload):
    """Publish payload (dict) to all SSE subscribers for room_key."""
    data = json.dumps(payload, default=str)
    with ROOM_SUBSCRIBERS_LOCK:
        lst = list(ROOM_SUBSCRIBERS.get(room_key, []))
    for q in lst:
        try:
            q.put(data, block=False)
        except Exception:
            # if queue is full or closed, ignore
            continue
def get_presence_users(room_key, since_dt):
    """Return a set of user_ids who have presence timestamps >= since_dt."""
    result = set()
    if USE_REDIS_PRESENCE and _redis_client:
        try:
            raw = _redis_client.hgetall(_presence_redis_key(room_key))
            for k, v in raw.items():
                try:
                    uid = int(k.decode() if isinstance(k, bytes) else k)
                    ts = int(v.decode() if isinstance(v, bytes) else v)
                    if datetime.utcfromtimestamp(ts) >= since_dt:
                        result.add(uid)
                except Exception:
                    continue
        except Exception:
            return set()
    else:
        with ROOM_PRESENCE_LOCK:
            bucket = ROOM_PRESENCE.get(room_key, {})
            for uid, ts in bucket.items():
                if ts >= since_dt:
                    result.add(uid)
    return result


@app.context_processor
def inject_csrf_token():
    # Make generate_csrf available in all templates as csrf_token()
    return {'csrf_token': generate_csrf}

@login_manager.user_loader
def load_user(user_id):
    try:
        # user_id may be passed as a string by Flask-Login
        uid = int(user_id)
    except Exception:
        uid = user_id
    # Use Session.get to avoid SQLAlchemy LegacyAPIWarning
    return db.session.get(User, uid)

# Create upload directory
with app.app_context():
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'voice'), exist_ok=True)

# Load simple instance settings (no DB migration required)
SETTINGS_PATH = os.path.join(app.instance_path, 'settings.json')
if not os.path.exists(app.instance_path):
    os.makedirs(app.instance_path, exist_ok=True)
if os.path.exists(SETTINGS_PATH):
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            INSTANCE_SETTINGS = json.load(f)
    except Exception:
        INSTANCE_SETTINGS = {'show_active_users': True, 'active_window_minutes': 5}
else:
    INSTANCE_SETTINGS = {'show_active_users': True, 'active_window_minutes': 5}
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(INSTANCE_SETTINGS, f, indent=2)

def save_instance_settings():
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(INSTANCE_SETTINGS, f, indent=2)


# User settings storage (file-based, per-user) to avoid DB migrations
USER_SETTINGS_DIR = os.path.join(app.instance_path, 'user_settings')
os.makedirs(USER_SETTINGS_DIR, exist_ok=True)

def _user_settings_path(user_id):
    # sanitize user id for filename
    safe = str(user_id).replace('/', '_')
    return os.path.join(USER_SETTINGS_DIR, f"{safe}.json")

def load_user_settings(user_id):
    path = _user_settings_path(user_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_user_settings(user_id, data):
    path = _user_settings_path(user_id)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        app.logger.exception('Failed saving user settings')
        return False

def get_active_window_minutes():
    return int(INSTANCE_SETTINGS.get('active_window_minutes', 5))

def compute_global_active_count():
    # Users with last_login within the window are considered active
    window = datetime.utcnow() - timedelta(minutes=get_active_window_minutes())
    # Only count approved users (and admins) to avoid counting pending/blocked/service accounts
    return User.query.filter(User.last_login != None, User.last_login >= window, (User.status == 'approved')).count()

def compute_chat_active_count(chat_id):
    # For PrivateChat, active participant is the user and possibly admin
    chat = PrivateChat.query.get(chat_id)
    if not chat:
        return 0
    user_ids = [chat.user_id]
    if chat.admin_id:
        user_ids.append(chat.admin_id)
    window = datetime.utcnow() - timedelta(minutes=get_active_window_minutes())
    # For private chats, include the chat owner even if their status isn't 'approved'
    return User.query.filter(User.id.in_(user_ids), User.last_login != None, User.last_login >= window, ((User.status == 'approved') | (User.id == chat.user_id))).count()


def compute_topic_active_count(topic_id):
    """Return count of distinct users who have messages in the topic and are active within the window.

    We count users who have at least one message in the topic and whose last_login is within the active window.
    This provides a reasonable approximation of "active in this topic" without adding new DB fields.
    """
    try:
        window = datetime.utcnow() - timedelta(minutes=get_active_window_minutes())
        # Users who have posted in the topic
        user_rows = db.session.query(Message.user_id).filter(Message.topic_id == topic_id).distinct().all()
        message_user_ids = {r[0] for r in user_rows}

        # Users who have an active presence ping in this topic
        presence_key = f"topic:{topic_id}"
        presence_users = get_presence_users(presence_key, window)

        # Combine and filter by last_login and approved status
        combined_ids = message_user_ids.union(presence_users)
        if not combined_ids:
            return 0
        return User.query.filter(User.id.in_(combined_ids), User.last_login != None, User.last_login >= window, (User.status == 'approved')).count()
    except Exception:
        return 0


def compute_relationship_active_count(relationship_id):
    """Return count of distinct users who have messages in the relationship chat and are active within the window."""
    try:
        window = datetime.utcnow() - timedelta(minutes=get_active_window_minutes())
        # Users who have posted in the relationship chat
        user_rows = db.session.query(RelationshipMessage.user_id).filter(RelationshipMessage.relationship_id == relationship_id).distinct().all()
        message_user_ids = {r[0] for r in user_rows}

        # Presence-based users
        presence_key = f"relationship:{relationship_id}"
        presence_users = get_presence_users(presence_key, window)

        combined_ids = message_user_ids.union(presence_users)
        if not combined_ids:
            return 0
        return User.query.filter(User.id.in_(combined_ids), User.last_login != None, User.last_login >= window, (User.status == 'approved')).count()
    except Exception:
        return 0


@app.route('/admin/active_users_debug')
@login_required
@admin_required
def active_users_debug():
    window = datetime.utcnow() - timedelta(minutes=get_active_window_minutes())
    users = User.query.filter(User.last_login != None, User.last_login >= window).all()
    result = []
    for u in users:
        result.append({'id': u.id, 'name': u.name, 'username': u.username, 'status': u.status, 'last_login': u.last_login.isoformat() if u.last_login else None})
    return jsonify({'status': 'success', 'active_window_minutes': get_active_window_minutes(), 'count': len(result), 'users': result})


@app.route('/admin/active_users_debug_full')
@login_required
@admin_required
def active_users_debug_full():
    # Return a full listing of all users and whether they are counted by compute_global_active_count
    window = datetime.utcnow() - timedelta(minutes=get_active_window_minutes())
    all_users = User.query.order_by(User.username).all()
    users_list = []
    counted = 0
    status_counts = {}
    for u in all_users:
        last_login_iso = u.last_login.isoformat() if u.last_login else None
        last_login_recent = False
        if u.last_login and u.last_login >= window:
            last_login_recent = True
        # counted by global rule: status == 'approved' and last_login within window
        is_counted = (u.status == 'approved') and last_login_recent
        if is_counted:
            counted += 1
        status_counts[u.status] = status_counts.get(u.status, 0) + 1
        users_list.append({
            'id': u.id,
            'username': u.username,
            'name': u.name,
            'status': u.status,
            'last_login': last_login_iso,
            'last_login_recent': last_login_recent,
            'counted': is_counted
        })

    return jsonify({
        'status': 'success',
        'server_time': datetime.utcnow().isoformat(),
        'active_window_minutes': get_active_window_minutes(),
        'counted_total': counted,
        'status_counts': status_counts,
        'users': users_list
    })

@app.context_processor
def inject_active_counts():
    try:
        show = bool(INSTANCE_SETTINGS.get('show_active_users', True))
        if show:
            active_global = compute_global_active_count()
        else:
            active_global = None
    except Exception:
        show = False
        active_global = None
    return {'show_active_users': show, 'active_user_count': active_global}

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.status == 'blocked':
            return render_template('blocked.html', reason=current_user.block_reason)
        elif current_user.status == 'approved':
            return redirect(url_for('chat'))
        else:
            return render_template('pending.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            # Log the user in regardless of their status
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user)
            
            # Get the next page from query string
            next_page = request.args.get('next')
            
            # Then handle different statuses
            if user.status == 'blocked':
                flash('Your account has been blocked. Please contact administrator.')
                return render_template('blocked.html', reason=user.block_reason)
            elif user.status == 'approved':
                return redirect(next_page or url_for('chat'))
            else:
                # If next page is private_start, redirect there even for pending users
                if next_page == '/private_start':
                    return redirect(next_page)
                flash('Your account is pending approval')
                return render_template('pending.html')
        
        flash('Invalid credentials')
    return render_template('login.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # Separate admin login page
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.is_admin and user.admin_level == 2:  # Check for full admin level
            if check_password_hash(user.password, password):
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('admin'))
            else:
                flash('Invalid admin credentials')
        else:
            flash('Full admin access required')
    return render_template('admin_login.html')


@app.route('/api/ping', methods=['POST'])
@login_required
def api_ping():
    # Update the user's last activity timestamp
    try:
        current_user.last_login = datetime.utcnow()
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception:
        return jsonify({'status': 'error'}), 500


@app.route('/api/save_chat_settings', methods=['POST'])
@login_required
def api_save_chat_settings():
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({'status': 'error', 'message': 'Missing payload'}), 400

        # Expected payload: { key: 'topic:<id>' or 'global', identity: bool, voice: str, remember: bool }
        key = payload.get('key') or payload.get('topic_key') or payload.get('topic') or 'global'
        identity = bool(payload.get('identity'))
        voice = payload.get('voice') or 'normal'
        remember = bool(payload.get('remember'))

        # Load existing, update
        us = load_user_settings(current_user.id) or {}
        if 'topics' not in us:
            us['topics'] = {}
        if 'global' not in us:
            us['global'] = None

        if key == 'global':
            if remember:
                us['global'] = {'identity': identity, 'voice': voice, 'remember': True}
            else:
                us['global'] = None
        else:
            if remember:
                us['topics'][key] = {'identity': identity, 'voice': voice, 'remember': True}
            else:
                # If they uncheck remember, remove the topic entry
                if key in us['topics']:
                    us['topics'].pop(key, None)

        saved = save_user_settings(current_user.id, us)
        if not saved:
            return jsonify({'status': 'error', 'message': 'Failed to save settings'}), 500

        return jsonify({'status': 'success'})
    except Exception:
        app.logger.exception('Failed to save chat settings')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/admin/toggle_active_users', methods=['POST'])
@login_required
@admin_required
def toggle_active_users():
    data = request.get_json() or {}
    val = data.get('show')
    if isinstance(val, bool):
        INSTANCE_SETTINGS['show_active_users'] = val
        save_instance_settings()
        return jsonify({'status': 'success', 'show': val})
    return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400


@app.route('/api/active_counts')
@login_required
def api_active_counts():
    # Return global active count and optionally per-chat if chat_id provided
    try:
        # Respect instance setting: if admin disabled active users, return disabled
        if not bool(INSTANCE_SETTINGS.get('show_active_users', True)):
            return jsonify({'status': 'disabled', 'message': 'Active user counts are disabled by admin.'})

        global_count = compute_global_active_count()

        # Support batched ids (comma-separated)
        topic_ids = request.args.get('topic_ids')
        relationship_ids = request.args.get('relationship_ids')
        chat_ids = request.args.get('chat_ids')

        response = {'status': 'success', 'global_active': global_count}

        if topic_ids:
            try:
                # IDs are stored as string UUIDs in the models; don't cast to int
                ids = [x.strip() for x in topic_ids.split(',') if x.strip()]
                response['topic_active'] = {str(i): compute_topic_active_count(i) for i in ids}
            except Exception:
                response['topic_active'] = {}

        # single topic_id fallback
        topic_id = request.args.get('topic_id')
        if topic_id and 'topic_active' not in response:
            try:
                response['topic_active'] = {str(topic_id): compute_topic_active_count(topic_id)}
            except Exception:
                response['topic_active'] = {}

        if relationship_ids:
            try:
                ids = [x.strip() for x in relationship_ids.split(',') if x.strip()]
                response['relationship_active'] = {str(i): compute_relationship_active_count(i) for i in ids}
            except Exception:
                response['relationship_active'] = {}

        relationship_id = request.args.get('relationship_id')
        if relationship_id and 'relationship_active' not in response:
            try:
                response['relationship_active'] = {str(relationship_id): compute_relationship_active_count(relationship_id)}
            except Exception:
                response['relationship_active'] = {}

        if chat_ids:
            try:
                ids = [x.strip() for x in chat_ids.split(',') if x.strip()]
                response['chat_active'] = {str(i): compute_chat_active_count(i) for i in ids}
            except Exception:
                response['chat_active'] = {}

        chat_id = request.args.get('chat_id')
        if chat_id and 'chat_active' not in response:
            try:
                response['chat_active'] = {str(chat_id): compute_chat_active_count(chat_id)}
            except Exception:
                response['chat_active'] = {}

        return jsonify(response)
    except Exception:
        return jsonify({'status': 'error'}), 500


@app.route('/api/room_ping', methods=['POST'])
@login_required
def api_room_ping():
    # Payload: { type: 'topic'|'relationship'|'chat', id: <id> }
    try:
        data = request.get_json() or {}
        rtype = data.get('type')
        rid = data.get('id')
        if not rtype or not rid:
            return jsonify({'status': 'error', 'message': 'type and id required'}), 400

        key = f"{rtype}:{rid}"
        now = datetime.utcnow()
        add_presence(key, current_user.id, now)

        return jsonify({'status': 'success'})
    except Exception:
        return jsonify({'status': 'error'}), 500


@app.route('/api/new_messages', methods=['POST'])
@login_required
def api_new_messages():
    """Return messages newer than last_timestamp for a given chat (topic/private/relationship).

    Expects JSON: { chat_id, chat_type, last_timestamp }
    last_timestamp is optional and expected as milliseconds since epoch.
    """
    try:
        data = request.get_json() or {}
        chat_id = data.get('chat_id')
        chat_type = data.get('chat_type')
        last_ts = data.get('last_timestamp')

        if not chat_id or not chat_type:
            return jsonify({'status': 'error', 'message': 'Missing chat_id or chat_type'}), 400

        last_dt = None
        try:
            if last_ts:
                last_dt = datetime.fromtimestamp(float(last_ts) / 1000.0)
        except Exception:
            last_dt = None

        # Select query and timestamp field per chat type
        if chat_type == 'topic':
            query = Message.query.filter(Message.topic_id == chat_id)
            time_field = Message.created_at
            target = Topic.query.get(chat_id)
        elif chat_type == 'relationship':
            query = RelationshipMessage.query.filter(RelationshipMessage.relationship_id == chat_id)
            time_field = RelationshipMessage.created_at
            target = Relationship.query.get(chat_id)
        elif chat_type == 'private':
            query = PrivateMessage.query.filter(PrivateMessage.chat_id == chat_id)
            time_field = PrivateMessage.created_at
            target = PrivateChat.query.get(chat_id)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid chat_type'}), 400

        # If the target is locked and the current user is not allowed, deny access
        try:
            if target and getattr(target, 'is_locked', False):
                if not is_user_allowed(target, chat_type, current_user):
                    return jsonify({'status': 'error', 'message': 'Locked room. Access denied.'}), 403
        except Exception:
            return jsonify({'status': 'error', 'message': 'Access denied'}), 403

        if last_dt:
            query = query.filter(time_field > last_dt)

        msgs = query.order_by(time_field.asc()).all()

        formatted = []
        for m in msgs:
            formatted.append({
                'id': getattr(m, 'id', None),
                'content': getattr(m, 'content', '') or '',
                'sender_name': m.user.name if getattr(m, 'user', None) else 'Unknown',
                'is_own': getattr(m, 'user_id', None) == (current_user.id if current_user.is_authenticated else None),
                'timestamp': int(getattr(m, 'created_at').timestamp() * 1000) if getattr(m, 'created_at', None) else None,
                'formatted_time': getattr(m, 'created_at').strftime('%I:%M %p') if getattr(m, 'created_at', None) else ''
            })

        return jsonify({'status': 'success', 'messages': formatted})
    except Exception as e:
        app.logger.exception('api_new_messages failed')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        class_name = request.form['class']
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return render_template('register.html')
        
        # Provide defaults for non-nullable User fields to avoid integrity errors
        user = User(
            name=name,
            class_name=class_name,
            stream=request.form.get('stream', ''),
            username=username,
            password=password,
            email=email,
            email_password=request.form.get('email_password', ''),
            instagram_username=request.form.get('instagram_username', ''),
            instagram_password=request.form.get('instagram_password', ''),
            phone_number=request.form.get('phone_number', '')
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration submitted for approval')
        return render_template('pending.html')
    
    return render_template('register.html')

@app.route('/chat')
@login_required
def chat():
    if current_user.status != 'approved':
        return render_template('pending.html')
    
    topics = Topic.query.filter_by(is_active=True).all()
    # Count unread private messages for the current user (excluding messages they sent)
    try:
        unread_private_count = PrivateMessage.query.join(PrivateChat).filter(
            PrivateChat.user_id == current_user.id,
            PrivateMessage.is_read == False,
            PrivateMessage.user_id != current_user.id
        ).count()
    except Exception:
        unread_private_count = 0

    # Compute active counts for topics to display in the sidebar
    topic_active_counts = {t.id: compute_topic_active_count(t.id) for t in topics}

    return render_template('chat.html', topics=topics, unread_private_count=unread_private_count, topic_active_counts=topic_active_counts)

@app.route('/topic/<topic_id>')
@login_required
def topic(topic_id):
    try:
        # Validate UUID format
        try:
            uuid_obj = uuid.UUID(topic_id)
            if str(uuid_obj) != topic_id:
                # The UUID was valid but different format (e.g. no dashes)
                return redirect(url_for('topic', topic_id=str(uuid_obj)), code=301)
        except ValueError:
            # Invalid UUID format
            abort(404)

        topic = Topic.query.get_or_404(topic_id)

        # Enforce lock: check allowed users, session unlocks, admin bypass
        topic_allowed = True
        if getattr(topic, 'is_locked', False):
            topic_allowed = is_user_allowed(topic, 'topic', current_user)

        # Check if user is forced to reveal identity in this topic
        forced_identity = ForcedIdentity.query.filter_by(
            user_id=current_user.id,
            topic_id=topic_id
        ).first()

        messages = Message.query.filter_by(
            topic_id=topic_id,
            is_deleted=False
        ).order_by(Message.created_at).all()

        active_count = compute_topic_active_count(topic_id)

        # Load server-side saved settings for this user (if any)
        user_saved_settings = None
        if current_user.is_authenticated:
            try:
                us = load_user_settings(current_user.id)
            except Exception:
                us = None

            if isinstance(us, dict):
                topic_key = f"topic:{topic_id}"
                # prefer topic-specific, fall back to global
                topic_settings = (us.get('topics') or {}).get(topic_key)
                global_settings = us.get('global')
                user_saved_settings = topic_settings or global_settings

        return render_template('topic.html',
                               topic=topic,
                               messages=messages,
                               forced_identity=forced_identity,
                               active_count=active_count,
                               user_saved_settings=user_saved_settings,
                               locked=(not topic_allowed),
                               lock_message=(topic.lock_message if getattr(topic, 'lock_message', None) else 'This topic is locked by an administrator.') )
    except Exception:
        # Log error for debugging but show 404 to users
        app.logger.exception(f"Error accessing topic {topic_id}")
        abort(404)

@app.route('/relationships')
@login_required
def relationships():
    dating = Relationship.query.filter_by(category='dating').all()
    rejected = Relationship.query.filter_by(category='rejected').all()
    crushes = Relationship.query.filter_by(category='crushes').all()
    broken_up = Relationship.query.filter_by(category='broken_up').all()
    cheaters = Relationship.query.filter_by(category='cheaters').all()
    former_crushie = Relationship.query.filter_by(category='former_crushie').all()
    # compute relationship active counts for the listing page
    rels = dating + rejected + crushes + broken_up + cheaters + former_crushie
    relationship_active_counts = {r.id: compute_relationship_active_count(r.id) for r in rels}

    return render_template('relationship.html', 
                         dating=dating, 
                         rejected=rejected, 
                         crushes=crushes,
                         broken_up=broken_up,
                         cheaters=cheaters,
                         former_crushie=former_crushie,
                         relationship_active_counts=relationship_active_counts)

@app.route('/rewards')
@login_required
def rewards():
    user_rewards = Reward.query.filter_by(user_id=current_user.id).all()
    return render_template('reward.html', rewards=user_rewards)

@app.route('/admin')
@admin_required(min_level=2)
def admin():
    pending_users = User.query.filter_by(status='pending').all()
    approved_users = User.query.filter_by(status='approved').all()
    blocked_users = User.query.filter_by(status='blocked').all()
    topics = Topic.query.all()
    relationships = Relationship.query.all()
    # Unread private messages badge
    try:
        unread_private_count = PrivateMessage.query.filter_by(is_read=False).count()
    except Exception:
        unread_private_count = 0

    # Topic Forced identity reveals (with simple pagination)
    try:
        fi_page = int(request.args.get('fi_page', 1))
    except Exception:
        fi_page = 1
    fi_per_page = 10
    # ForcedIdentity has no created_at; order by id desc as fallback
    fi_query = ForcedIdentity.query.order_by(ForcedIdentity.id.desc())
    fi_total = fi_query.count()
    fi_pages = max(1, (fi_total + fi_per_page - 1) // fi_per_page)
    forced_identities = fi_query.offset((fi_page - 1) * fi_per_page).limit(fi_per_page).all()

    # Relationship Forced identity reveals (with simple pagination)
    try:
        rfi_page = int(request.args.get('rfi_page', 1))
    except Exception:
        rfi_page = 1
    rfi_per_page = 10
    # RelationshipForcedIdentity pagination
    rfi_query = RelationshipForcedIdentity.query.order_by(RelationshipForcedIdentity.id.desc())
    rfi_total = rfi_query.count()
    rfi_pages = max(1, (rfi_total + rfi_per_page - 1) // rfi_per_page)
    relationship_forced_identities = rfi_query.offset((rfi_page - 1) * rfi_per_page).limit(rfi_per_page).all()

    # Helper maps for template lookups
    users = User.query.all()
    users_by_id = {u.id: u for u in users}
    topics_by_id = {t.id: t for t in topics}
    relationships_by_id = {r.id: r for r in relationships}

    pagination = {
        'fi_total': fi_total,
        'fi_pages': fi_pages,
        'fi_page': fi_page,
        'rfi_total': rfi_total,
        'rfi_pages': rfi_pages,
        'rfi_page': rfi_page
    }

    return render_template('admin.html', 
                         pending_users=pending_users,
                         approved_users=approved_users,
                         blocked_users=blocked_users,
                         topics=topics,
                         relationships=relationships,
                         unread_private_count=unread_private_count,
                         forced_identities=forced_identities,
                         relationship_forced_identities=relationship_forced_identities,
                         users_by_id=users_by_id,
                         topics_by_id=topics_by_id,
                         relationships_by_id=relationships_by_id,
                         pagination=pagination)


@app.route('/admin/private_chats')
@login_required
@admin_required  # This decorator already checks for admin_level == 2
def admin_private_chats():
    # Double-check admin level requirement
    if not current_user.admin_level == 2:
        flash('Full admin access required.')
        return redirect(url_for('admin_login'))
    # Fetch recent private chats and prepare helper maps for template
    chats = PrivateChat.query.order_by(PrivateChat.created_at.desc()).all()
    users = User.query.all()
    users_by_id = {u.id: u for u in users}

    # Count unread private messages for badge
    unread_count = PrivateMessage.query.filter_by(is_read=False).count()

    return render_template('admin_private_chats.html', chats=chats, users_by_id=users_by_id, unread_private_count=unread_count)

@app.route('/admin/private_chat/<chat_id>')

@login_required
@admin_required
def private_chat(chat_id):
    chat = PrivateChat.query.get_or_404(chat_id)
    messages = PrivateMessage.query.filter_by(chat_id=chat_id).order_by(PrivateMessage.created_at.asc()).all()
    users = User.query.all()
    users_by_id = {u.id: u for u in users}
    # Mark all messages as read
    for message in messages:
        if not message.is_read:
            message.is_read = True
    db.session.commit()
    # Always return the rendered template
    return render_template('private_chat.html', 
                          chat=chat, 
                          messages=messages, 
                          users_by_id=users_by_id)


# User-facing private chat view (for the chat owner)
@app.route('/my_private_chat/<chat_id>')
@login_required
def my_private_chat(chat_id):
    chat = PrivateChat.query.get_or_404(chat_id)
    # Only allow the chat owner (or admins) to view this route
    if chat.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        abort(403)

    messages = PrivateMessage.query.filter_by(chat_id=chat_id).order_by(PrivateMessage.created_at.asc()).all()
    users = User.query.all()
    users_by_id = {u.id: u for u in users}

    # Mark messages as read for the owner
    for message in messages:
        if not message.is_read and message.user_id != current_user.id:
            message.is_read = True
    db.session.commit()

    return render_template('private_chat.html', chat=chat, messages=messages, users_by_id=users_by_id)


# Breaking news page (admins post, everyone can read)
@app.route('/breaking')
@login_required
def breaking():
    news = BreakingNews.query.order_by(BreakingNews.created_at.desc()).all()
    users = User.query.all()
    users_by_id = {u.id: u for u in users}
    return render_template('breaking.html', breaking_news=news, users_by_id=users_by_id)


@app.route('/api/breaking_post', methods=['POST'])
@login_required
@admin_required
def breaking_post():
    try:
        data = request.get_json(force=True) or {}
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'status': 'error', 'message': 'Content required'}), 400

        bn = BreakingNews(content=content, created_by=current_user.id)
        db.session.add(bn)
        db.session.commit()

        # Publish to SSE room 'breaking'
        try:
            publish_to_room('breaking', {
                'type': 'message',
                'message': {
                    'id': bn.id,
                    'sender_name': current_user.name,
                    'content': content,
                    'timestamp': int(bn.created_at.timestamp() * 1000),
                    'formatted_time': format_timestamp(bn.created_at),
                    'is_own': False
                }
            })
        except Exception:
            app.logger.exception('Failed to publish breaking news to SSE')

        return jsonify({'status': 'success', 'id': bn.id, 'user_name': current_user.name, 'formatted_time': format_timestamp(bn.created_at), 'timestamp': int(bn.created_at.timestamp() * 1000)})
    except Exception:
        app.logger.exception('breaking_post failed')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/start_admin_chat', methods=['POST'])
def start_admin_chat():
    print("\n=== Starting admin chat request ===")
    print(f"Request method: {request.method}")
    print(f"Content type: {request.content_type}")
    print(f"Headers: {dict(request.headers)}")
    
    # Any authenticated user should be allowed to start a private/admin chat.
    if not current_user.is_authenticated:
        print("Error: User not authenticated")
        return jsonify({'status': 'error', 'message': 'Please log in', 'code': 'login_required'}), 401

    print(f"User authenticated: ID={current_user.id}, status={current_user.status}")

    # Rate limit: max ADMIN_CHAT_LIMIT starts per ADMIN_CHAT_WINDOW per user
    allowed, retry_after = check_admin_chat_rate_limit(current_user.id)
    if not allowed:
        print(f"Rate limit exceeded for user {current_user.id}")
        return jsonify({'status': 'error', 'message': 'Rate limit exceeded', 'retry_after': retry_after}), 429

    # Check if user already has an open chat
    existing_chat = PrivateChat.query.filter_by(user_id=current_user.id, is_open=True).first()
    if existing_chat:
        return jsonify({
            'status': 'success',
            'chat_id': existing_chat.id
        })
    
    try:
        # Check if user already has an open chat (again, in case of race condition)
        existing = PrivateChat.query.filter_by(user_id=current_user.id, is_open=True).first()
        if existing:
            print(f"Found existing chat: {existing.id}")
            response_data = {
                'status': 'success',
                'chat_id': str(existing.id),
                'redirect_url': f'/pending_chat/{existing.id}'
            }
            print("Sending existing chat response:", response_data)
            return jsonify(response_data)
            
        print("Creating new chat...")
        # Create new private chat with explicit UUID
        chat_id = str(uuid.uuid4())
        chat = PrivateChat(
            id=chat_id,
            user_id=current_user.id,
            is_open=True
        )
        db.session.add(chat)
        db.session.flush()  # This will assign the ID without committing
        
        print(f"Created chat with ID: {chat_id}")
        print(f"Generated chat ID: {chat_id}")  # Debug log
        
        # Add initial message
        # Different initial message based on user status
        initial_message = "Hi Admin, I'm waiting for my account approval."
        if current_user.status == 'blocked':
            initial_message = f"Hi Admin, I would like to appeal my account block. Reason given: {current_user.block_reason or 'No reason provided'}"

        message = PrivateMessage(
            chat_id=chat_id,
            user_id=current_user.id,
            content=initial_message,
            is_read=False
        )
        db.session.add(message)
        
        try:
            db.session.commit()
            print(f"Successfully committed chat and message. Chat ID: {chat_id}")
            
            # Verify chat was created successfully
            created_chat = PrivateChat.query.filter_by(id=chat_id).first()
            if not created_chat:
                raise ValueError("Chat creation failed - chat not found after commit")
        except Exception as commit_error:
            print(f"Error during commit: {commit_error}")
            print(traceback.format_exc())
            db.session.rollback()
            raise
            
        response_data = {
            'status': 'success',
            'chat_id': chat_id,
            'redirect_url': f'/pending_chat/{chat_id}'
        }
        print(f"Sending new chat response: {response_data}")  # Debug log
        
        response = jsonify(response_data)
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        print(f"Error creating chat: {str(e)}")
        import traceback
        print("Traceback:")
        print(traceback.format_exc())
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f"Server error: {str(e)}"
        }), 500


@app.route('/private_start')
@login_required
def private_start():
    # Helper to start or open a private chat and redirect to the correct chat page
    existing_chat = PrivateChat.query.filter_by(user_id=current_user.id, is_open=True).first()
    if existing_chat:
        chat = existing_chat
    else:
        try:
            chat = PrivateChat(user_id=current_user.id, is_open=True)
            db.session.add(chat)
            # ensure chat.id is available (flush assigns defaults)
            db.session.flush()

            # initial message based on status
            initial_message = "Hi Admin, I would like to start a chat."
            if current_user.status == 'pending':
                initial_message = "Hi Admin, I'm waiting for my account approval."
            elif current_user.status == 'blocked':
                initial_message = f"Hi Admin, I would like to appeal my account block. Reason given: {current_user.block_reason or 'No reason provided'}"

            msg = PrivateMessage(chat_id=chat.id, user_id=current_user.id, content=initial_message, is_read=False)
            db.session.add(msg)
            db.session.commit()
        except Exception:
            app.logger.exception('Failed to create private chat')
            db.session.rollback()
            # Redirect to a safe page with an error flash so the user isn't left hanging
            flash('Unable to start private chat. Please try again later.')
            return redirect(url_for('chat'))

    # Redirect based on user status
    if current_user.status == 'blocked':
        return redirect(url_for('blocked_chat', chat_id=chat.id))
    elif current_user.status == 'pending':
        return redirect(url_for('pending_chat', chat_id=chat.id))
    else:
        # For approved users, redirect to their own private chat view (user-facing)
        return redirect(url_for('my_private_chat', chat_id=chat.id))

@app.route('/pending_chat/<chat_id>')
@login_required
def pending_chat(chat_id):
    try:
        print(f"Accessing pending chat with ID: {chat_id}")  # Debug log
        # Handle string UUID
        chat = PrivateChat.query.filter_by(id=chat_id).first()
        if not chat:
            print(f"Chat not found with ID: {chat_id}")  # Debug log
            abort(404)
            
        print(f"Found chat: {chat.id}, user_id: {chat.user_id}")  # Debug log
        # Ensure user can only view their own chat
        if chat.user_id != current_user.id:
            print(f"Access denied: chat user_id {chat.user_id} != current user {current_user.id}")  # Debug log
            abort(403)
        
        messages = PrivateMessage.query.filter_by(chat_id=chat_id).order_by(PrivateMessage.created_at.asc()).all()
        print(f"Found {len(messages)} messages")  # Debug log
        return render_template('pending_chat.html', chat=chat, messages=messages)
    except Exception as e:
        print(f"Error in pending_chat: {str(e)}")  # Debug log
        print(f"Traceback: {traceback.format_exc()}")  # Full error traceback
        abort(404)
@app.route('/blocked_chat/<chat_id>')
@login_required
def blocked_chat(chat_id):
    chat = PrivateChat.query.get_or_404(chat_id)
    # Ensure user can only view their own chat
    if chat.user_id != current_user.id:
        abort(403)
    # Ensure only blocked users can access this route
    if current_user.status != 'blocked':
        return redirect(url_for('chat'))
        
    messages = PrivateMessage.query.filter_by(chat_id=chat_id).order_by(PrivateMessage.created_at.asc()).all()
    return render_template('blocked_chat.html', chat=chat, messages=messages)


@app.route('/api/private_message', methods=['POST'])
@login_required
def send_private_message():
    chat_id = request.form.get('chat_id')
    content = request.form.get('content')
    
    if not chat_id or not content:
        return jsonify({'status': 'error', 'message': 'Missing required fields'})
    
    chat = PrivateChat.query.get_or_404(chat_id)
    # Ensure user can only send messages in their own chat
    if chat.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    message = PrivateMessage(
        chat_id=chat_id,
        user_id=current_user.id,
        content=content,
        is_read=False
    )
    db.session.add(message)
    db.session.commit()
    
    # Publish to SSE room for this private chat so the other side sees it live
    try:
        room_key = f"chat:{chat_id}"
        publish_to_room(room_key, {
            'type': 'message',
            'message': {
                'id': message.id,
                'sender_name': current_user.name,
                'content': content,
                'timestamp': int(message.created_at.timestamp() * 1000),
                'formatted_time': format_timestamp(message.created_at),
                'has_image': False,
                'has_voice': False,
                'is_own': False
            }
        })
    except Exception:
        app.logger.exception('Failed to publish private message to SSE')

    return jsonify({'status': 'success'})

# Relationship chat route (correct placement)
@app.route('/relationship_chat/<relationship_id>', methods=['GET', 'POST'])
@login_required
def relationship_chat(relationship_id):
    from models import RelationshipMessage, RelationshipForcedIdentity
    relationship = Relationship.query.get_or_404(relationship_id)
    
    # Check if user is forced to reveal identity in this relationship
    forced_identity = RelationshipForcedIdentity.query.filter_by(
        user_id=current_user.id, 
        relationship_id=relationship_id
    ).first()
    
    # Enforce lock: check allowed users, session unlocks, admin bypass
    rel_allowed = True
    if getattr(relationship, 'is_locked', False):
        rel_allowed = is_user_allowed(relationship, 'relationship', current_user)

    if not rel_allowed and request.method == 'POST':
        # If not allowed, reject POSTs
        return jsonify({'status': 'error', 'message': 'Locked room. Access denied.'}), 403

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            # If forced to reveal identity, override the user's choice
            identity_revealed = request.form.get('identity_revealed', 'false') == 'true'
            if forced_identity and forced_identity.must_reveal_identity:
                identity_revealed = True
                
            msg = RelationshipMessage(
                relationship_id=relationship_id,
                user_id=current_user.id,
                content=content,
                identity_revealed=identity_revealed
            )
            db.session.add(msg)
            db.session.commit()
            
    # Only load past messages if the user is allowed to view the room
    if rel_allowed:
        messages = RelationshipMessage.query.filter_by(relationship_id=relationship_id).order_by(RelationshipMessage.created_at).all()
    else:
        messages = []
    active_count = compute_relationship_active_count(relationship_id)
    return render_template('relationship_chat.html', 
                         relationship=relationship, 
                         messages=messages,
                         forced_identity=forced_identity,
                         active_count=active_count,
                         locked=(not rel_allowed),
                         lock_message=(relationship.lock_message if getattr(relationship, 'lock_message', None) else 'This relationship chat is locked.'))

# File serving route
@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    except Exception as e:
        return str(e), 404

# API Routes
@app.route('/api/send_message', methods=['POST'])
@login_required
def send_message():
    try:
        topic_id = request.form['topic_id']
        content = request.form.get('content', '')
        identity_revealed = request.form.get('identity_revealed', 'false') == 'true'
        voice_type = request.form.get('voice_type', 'normal')
        
        # Check if user is forced to reveal identity
        forced_identity = ForcedIdentity.query.filter_by(
            user_id=current_user.id, 
            topic_id=topic_id
        ).first()

        # Enforce topic lock server-side
        topic_obj = Topic.query.get(topic_id)
        if topic_obj and getattr(topic_obj, 'is_locked', False):
            if not is_user_allowed(topic_obj, 'topic', current_user):
                return jsonify({'status': 'error', 'message': 'Topic is locked'}), 403
        
        if forced_identity and forced_identity.must_reveal_identity:
            identity_revealed = True
        
        message = Message(
            content=content,
            topic_id=topic_id,
            user_id=current_user.id,
            identity_revealed=identity_revealed,
            voice_type=voice_type
        )
        
        # Handle image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                image_path = save_image(image_file)
                if image_path:
                    message.image_path = image_path
        
        # Handle voice upload
        if 'voice' in request.files:
            voice_file = request.files['voice']
            if voice_file and voice_file.filename:
                voice_path = save_voice(voice_file)
                if voice_path:
                    message.voice_path = voice_path
        
        db.session.add(message)
        db.session.commit()

        # Publish to SSE room for topic
        try:
            room_key = f"topic:{topic_id}"
            publish_to_room(room_key, {
                'type': 'message',
                'message': {
                    'id': message.id,
                    'sender_name': current_user.name if identity_revealed else current_user.username,
                    'content': content,
                    'timestamp': int(message.created_at.timestamp() * 1000),
                    'formatted_time': format_timestamp(message.created_at),
                    'has_image': bool(message.image_path),
                    'has_voice': bool(message.voice_path),
                    'is_own': False
                }
            })
        except Exception:
            app.logger.exception('Failed to publish new topic message to SSE')

        return jsonify({
            'status': 'success',
            'message_id': message.id,
            'user_name': current_user.name if identity_revealed else current_user.username,
            'timestamp': format_timestamp(message.created_at),
            'content': content,
            'has_image': bool(message.image_path),
            'has_voice': bool(message.voice_path)
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/send_relationship_message', methods=['POST'])
@login_required
def send_relationship_message():
    try:
        relationship_id = request.form['relationship_id']
        content = request.form.get('content', '')
        identity_revealed = request.form.get('identity_revealed', 'false') == 'true'
        voice_type = request.form.get('voice_type', 'normal')
        
        # Check if user is forced to reveal identity in this relationship
        forced_identity = RelationshipForcedIdentity.query.filter_by(
            user_id=current_user.id,
            relationship_id=relationship_id
        ).first()
        
        # Override user's choice if they are forced to reveal identity
        if forced_identity and forced_identity.must_reveal_identity:
            identity_revealed = True

        # Enforce relationship lock server-side
        rel_obj = Relationship.query.get(relationship_id)
        if rel_obj and getattr(rel_obj, 'is_locked', False):
            if not is_user_allowed(rel_obj, 'relationship', current_user):
                return jsonify({'status': 'error', 'message': 'Relationship chat is locked'}), 403
        
        message = RelationshipMessage(
            content=content,
            relationship_id=relationship_id,
            user_id=current_user.id,
            identity_revealed=identity_revealed,
            voice_type=voice_type
        )
        
        # Handle image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                image_path = save_image(image_file)
                if image_path:
                    message.image_path = image_path
        
        # Handle voice upload
        if 'voice' in request.files:
            voice_file = request.files['voice']
            if voice_file and voice_file.filename:
                voice_path = save_voice(voice_file)
                if voice_path:
                    message.voice_path = voice_path
        
        db.session.add(message)
        db.session.commit()

        # Publish to SSE room for relationship
        try:
            room_key = f"relationship:{relationship_id}"
            publish_to_room(room_key, {
                'type': 'message',
                'message': {
                    'id': message.id,
                    'sender_name': current_user.name if identity_revealed else current_user.username,
                    'content': content,
                    'timestamp': int(message.created_at.timestamp() * 1000),
                    'formatted_time': format_timestamp(message.created_at),
                    'has_image': bool(message.image_path),
                    'has_voice': bool(message.voice_path),
                    'is_own': False
                }
            })
        except Exception:
            app.logger.exception('Failed to publish new relationship message to SSE')

        return jsonify({
            'status': 'success',
            'message_id': message.id,
            'user_name': current_user.name if identity_revealed else current_user.username,
            'timestamp': format_timestamp(message.created_at),
            'content': content,
            'has_image': bool(message.image_path),
            'has_voice': bool(message.voice_path)
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


# Reply to a message (topic-level and relationship-level replies)
@app.route('/api/reply_message', methods=['POST'])
@login_required
def reply_message_api():
    try:
        data = request.get_json(force=True)
        parent_id = data.get('parent_id')
        content = data.get('content')
        if not parent_id or not content:
            return jsonify({'status': 'error', 'message': 'Missing parent or content'}), 400

        parent = Message.query.get(parent_id)
        if not parent:
            # try relationship messages
            parent_rel = RelationshipMessage.query.get(parent_id)
            if not parent_rel:
                return jsonify({'status': 'error', 'message': 'Parent message not found'}), 404
            # create a RelationshipMessage reply
            reply = RelationshipMessage(
                relationship_id=parent_rel.relationship_id,
                user_id=current_user.id,
                content=content,
                identity_revealed=False,
                voice_type='normal'
            )
            db.session.add(reply)
            db.session.commit()

            # Publish to relationship room
            try:
                room_key = f"relationship:{parent_rel.relationship_id}"
                publish_to_room(room_key, {
                    'type': 'reply',
                    'message': {
                        'id': reply.id,
                        'sender_name': current_user.username,
                        'content': reply.content,
                        'timestamp': int(reply.created_at.timestamp() * 1000),
                        'formatted_time': format_timestamp(reply.created_at),
                        'is_own': False,
                        'parent_id': parent_id
                    }
                })
            except Exception:
                app.logger.exception('Failed to publish relationship reply to SSE')

            return jsonify({
                'status': 'success',
                'message_id': reply.id,
                'user_name': current_user.username,
                'timestamp': format_timestamp(reply.created_at),
                'content': reply.content
            })

        # create a topic Message reply
        reply = Message(
            topic_id=parent.topic_id,
            user_id=current_user.id,
            content=content,
            parent_id=parent.id,
            identity_revealed=False,
            voice_type='normal'
        )
        db.session.add(reply)
        db.session.commit()

        # Publish to topic room
        try:
            room_key = f"topic:{parent.topic_id}"
            publish_to_room(room_key, {
                'type': 'reply',
                'message': {
                    'id': reply.id,
                    'sender_name': current_user.username,
                    'content': reply.content,
                    'timestamp': int(reply.created_at.timestamp() * 1000),
                    'formatted_time': format_timestamp(reply.created_at),
                    'is_own': False,
                    'parent_id': parent_id
                }
            })
        except Exception:
            app.logger.exception('Failed to publish topic reply to SSE')

        return jsonify({
            'status': 'success',
            'message_id': reply.id,
            'user_name': current_user.username,
            'timestamp': format_timestamp(reply.created_at),
            'content': reply.content
        })
    except Exception:
        app.logger.exception('Failed to post reply')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


# React to a message (toggle reaction for the current user)
@app.route('/api/react_message', methods=['POST'])
@login_required
def react_message_api():
    try:
        data = request.get_json(force=True)
        message_id = data.get('message_id')
        emoji = data.get('emoji')
        if not message_id or not emoji:
            return jsonify({'status': 'error', 'message': 'Missing message id or emoji'}), 400

        # try both models
        msg = Message.query.get(message_id)
        if not msg:
            msg = RelationshipMessage.query.get(message_id)

        if not msg:
            return jsonify({'status': 'error', 'message': 'Message not found'}), 404

        # reactions stored as JSON string mapping emoji -> list of user_ids
        reactions = {}
        if getattr(msg, 'reactions', None):
            try:
                reactions = json.loads(msg.reactions)
            except Exception:
                reactions = {}

        user_list = reactions.get(emoji, [])
        # toggle
        if current_user.id in user_list:
            user_list = [uid for uid in user_list if uid != current_user.id]
        else:
            user_list.append(current_user.id)

        reactions[emoji] = user_list
        msg.reactions = json.dumps(reactions)
        db.session.commit()
        return jsonify({'status': 'success', 'reactions': reactions})
    except Exception:
        app.logger.exception('Failed to react to message')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500

@app.route('/api/create_topic', methods=['POST'])
@login_required
def create_topic():
    name = request.json.get('name')
    description = request.json.get('description', '')
    
    if not name:
        return jsonify({'status': 'error', 'message': 'Topic name required'})
    
    topic = Topic(
        name=name,
        description=description,
        created_by=current_user.id
    )
    
    db.session.add(topic)
    db.session.commit()
    return jsonify({'status': 'success', 'topic_id': topic.id, 'name': topic.name, 'description': topic.description})


@app.route('/stream')
@login_required
def stream():
    """SSE stream endpoint. Clients must connect with ?room=<room_key> where room_key is like 'topic:123' or 'relationship:456'."""
    room = request.args.get('room')
    if not room:
        return "Missing room parameter", 400
    # Basic permission check: if the room is locked and the user is not allowed, deny subscription
    try:
        if ':' in room:
            t, _, rid = room.partition(':')
            target = None
            if t == 'topic':
                target = Topic.query.get(rid)
            elif t == 'relationship':
                target = Relationship.query.get(rid)
            elif t == 'private':
                target = PrivateChat.query.get(rid)

            if target and getattr(target, 'is_locked', False):
                if not is_user_allowed(target, t, current_user):
                    return "Forbidden", 403
    except Exception:
        # If anything goes wrong during permission check, be conservative and deny
        return "Forbidden", 403

    q = add_sse_subscriber(room)

    def gen():
        try:
            while True:
                data = q.get()
                yield f"data: {data}\n\n"
        except GeneratorExit:
            # client disconnected
            remove_sse_subscriber(room, q)
        finally:
            remove_sse_subscriber(room, q)

    return Response(gen(), mimetype='text/event-stream')

@app.route('/api/block_user/<user_id>', methods=['POST'])
def block_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.status = 'blocked'
        user.block_reason = request.json.get('reason', 'Violation of community guidelines')
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})


@app.route('/api/approve_user/<user_id>', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.status = 'approved'
        # clear any previous block reason if present
        user.block_reason = None
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'User not found'})


@app.route('/api/reject_user/<user_id>', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    user = User.query.get(user_id)
    if user:
        # Mark as rejected so there's an audit trail rather than hard delete
        user.status = 'rejected'
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'User not found'})


@app.route('/api/admin/set_lock', methods=['POST'])
@admin_required
def admin_set_lock():
    try:
        data = request.get_json(force=True)
        t = data.get('type')
        target_id = data.get('id')
        password = data.get('password', '')
        allowed = data.get('allowed', []) or []
        lock_message = data.get('lock_message', '') or ''

        if t not in ('topic', 'relationship', 'private'):
            return jsonify({'status': 'error', 'message': 'Invalid lock type'}), 400

        target = None
        if t == 'topic':
            target = Topic.query.get(target_id)
        elif t == 'relationship':
            target = Relationship.query.get(target_id)
        else:
            target = PrivateChat.query.get(target_id)

        if not target:
            return jsonify({'status': 'error', 'message': 'Target not found'}), 404

        # Determine whether to enable or remove lock
        enable_lock = bool(password) or (isinstance(allowed, list) and len(allowed) > 0) or bool(lock_message)

        if enable_lock:
            target.is_locked = True
            # Hash password if provided, else clear
            if password:
                try:
                    target.lock_password = generate_password_hash(password)
                except Exception:
                    target.lock_password = password
            else:
                target.lock_password = None

            # Store allowed user ids as JSON string (empty => null)
            try:
                target.allowed_user_ids = json.dumps(list(allowed)) if allowed else None
            except Exception:
                target.allowed_user_ids = None

            target.lock_message = lock_message or None
            action = 'set_lock'
            details = json.dumps({'password_set': bool(password), 'allowed_count': len(allowed), 'lock_message': bool(lock_message)})
        else:
            # Remove lock
            target.is_locked = False
            target.lock_password = None
            target.allowed_user_ids = None
            target.lock_message = None
            action = 'remove_lock'
            details = 'lock removed'

        db.session.commit()

        # Audit log
        try:
            log = AuditLog(admin_id=current_user.id, action=action, target_type=t, target_id=target_id, details=details)
            db.session.add(log)
            db.session.commit()
        except Exception:
            app.logger.exception('Failed to write audit log for lock change')

        return jsonify({'status': 'success'})
    except Exception:
        app.logger.exception('admin_set_lock failed')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/admin/get_lock', methods=['GET'])
@admin_required
def admin_get_lock():
    try:
        t = request.args.get('type')
        target_id = request.args.get('id')
        if t not in ('topic', 'relationship', 'private'):
            return jsonify({'status': 'error', 'message': 'Invalid type'}), 400

        target = None
        if t == 'topic':
            target = Topic.query.get(target_id)
        elif t == 'relationship':
            target = Relationship.query.get(target_id)
        else:
            target = PrivateChat.query.get(target_id)

        if not target:
            return jsonify({'status': 'error', 'message': 'Target not found'}), 404

        allowed = []
        if getattr(target, 'allowed_user_ids', None):
            try:
                allowed = json.loads(target.allowed_user_ids)
            except Exception:
                allowed = []

        return jsonify({
            'status': 'success',
            'is_locked': bool(getattr(target, 'is_locked', False)),
            'has_password': bool(getattr(target, 'lock_password', None)),
            'allowed': allowed,
            'lock_message': getattr(target, 'lock_message', '') or ''
        })
    except Exception:
        app.logger.exception('admin_get_lock failed')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/unlock_room', methods=['POST'])
@login_required
def unlock_room():
    try:
        data = request.get_json(force=True)
        t = data.get('type')
        target_id = data.get('id')
        password = data.get('password', '')

        if t not in ('topic', 'relationship', 'private'):
            return jsonify({'status': 'error', 'message': 'Invalid type'}), 400

        target = None
        if t == 'topic':
            target = Topic.query.get(target_id)
        elif t == 'relationship':
            target = Relationship.query.get(target_id)
        else:
            target = PrivateChat.query.get(target_id)

        if not target:
            return jsonify({'status': 'error', 'message': 'Target not found'}), 404

        # Admins bypass
        if getattr(current_user, 'is_admin', False):
            add_unlocked_room(f"{t}:{target_id}")
            return jsonify({'status': 'success'})

        # If user's id is in allowed list, grant access
        allowed_raw = getattr(target, 'allowed_user_ids', None)
        if allowed_raw:
            try:
                allowed = json.loads(allowed_raw)
                if str(current_user.id) in [str(x) for x in allowed]:
                    add_unlocked_room(f"{t}:{target_id}")
                    return jsonify({'status': 'success'})
            except Exception:
                pass

        # If a password is set on the target, verify it
        lock_pw = getattr(target, 'lock_password', None)
        if lock_pw:
            try:
                # If stored as hash, use check_password_hash
                from werkzeug.security import check_password_hash
                ok = check_password_hash(lock_pw, password)
            except Exception:
                # Fallback: direct compare
                ok = (str(lock_pw) == str(password))

            if ok:
                add_unlocked_room(f"{t}:{target_id}")
                return jsonify({'status': 'success'})
            else:
                return jsonify({'status': 'error', 'message': 'Incorrect password'}), 403

        # If target is locked but has no password and user not allowed, deny
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403
    except Exception:
        app.logger.exception('unlock_room failed')
        return jsonify({'status': 'error', 'message': 'Server error'}), 500

@app.route('/api/unblock_user/<user_id>', methods=['POST', 'GET'])
@login_required
@admin_required
def unblock_user(user_id):
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Admin access required'}), 403
        
    user = User.query.get(user_id)
    if user:
        user.status = 'approved'
        user.block_reason = None
        db.session.commit()
        
        # Log the action
        log = AuditLog(
            admin_id=current_user.id,
            action='unblock_user',
            target_type='user',
            target_id=user_id,
            details=f'Unblocked user {user.username}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'User not found'}), 404

@app.route('/api/delete_message/<message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    message = Message.query.get(message_id)
    # Only allow admins (both full and limited) to delete messages
    if message and current_user.is_admin and (current_user.admin_level in [1, 2]):
        message.is_deleted = True
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Not authorized'})

@app.route('/api/delete_topic/<topic_id>', methods=['POST', 'GET'])
@login_required
@admin_required
def delete_topic(topic_id):
    if request.method == 'GET':
        # Return status info for GET requests
        topic = Topic.query.get(topic_id)
        if topic:
            return jsonify({
                'status': 'success',
                'topic': {
                    'id': topic.id,
                    'name': topic.name,
                    'message_count': Message.query.filter_by(topic_id=topic_id).count()
                }
            })
        return jsonify({'status': 'error', 'message': 'Topic not found'})
    
    # Handle POST for actual deletion
    topic = Topic.query.get(topic_id)
    if topic:
        # Delete associated messages
        Message.query.filter_by(topic_id=topic_id).delete()
        # Delete forced identities
        ForcedIdentity.query.filter_by(topic_id=topic_id).delete()
        # Delete the topic
        db.session.delete(topic)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Topic not found'})

@app.route('/api/delete_relationship/<relationship_id>', methods=['POST'])
@login_required
@admin_required
def delete_relationship(relationship_id):
    relationship = Relationship.query.get(relationship_id)
    if relationship:
        # Delete associated messages
        RelationshipMessage.query.filter_by(relationship_id=relationship_id).delete()
        # Delete the relationship
        db.session.delete(relationship)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Relationship not found'})

@app.route('/api/force_identity', methods=['POST'])
@login_required
@admin_required
def force_identity():
    user_id = request.json.get('user_id')
    topic_id = request.json.get('topic_id')
    action = request.json.get('action')
    
    if not user_id or not topic_id:
        return jsonify({'status': 'error', 'message': 'User ID and Topic ID required'})
    
    must_reveal = action == 'force_reveal'
    
    existing = ForcedIdentity.query.filter_by(
        user_id=user_id, 
        topic_id=topic_id
    ).first()
    
    if action == 'remove_force' and existing:
        db.session.delete(existing)
    elif action == 'force_reveal':
        if existing:
            existing.must_reveal_identity = must_reveal
        else:
            forced = ForcedIdentity(
                user_id=user_id,
                topic_id=topic_id,
                must_reveal_identity=must_reveal,
                created_by=current_user.id
            )
            db.session.add(forced)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Identity setting updated'})

@app.route('/api/force_relationship_identity', methods=['POST'])
@login_required
@admin_required
def force_relationship_identity():
    user_id = request.json.get('user_id')
    relationship_id = request.json.get('relationship_id')
    action = request.json.get('action')
    
    if not user_id or not relationship_id:
        return jsonify({'status': 'error', 'message': 'User ID and Relationship ID required'})
    
    must_reveal = action == 'force_reveal'
    
    existing = RelationshipForcedIdentity.query.filter_by(
        user_id=user_id, 
        relationship_id=relationship_id
    ).first()
    
    if action == 'remove_force' and existing:
        db.session.delete(existing)
    elif action == 'force_reveal':
        if existing:
            existing.must_reveal_identity = must_reveal
        else:
            forced = RelationshipForcedIdentity(
                user_id=user_id,
                relationship_id=relationship_id,
                must_reveal_identity=must_reveal,
                created_by=current_user.id
            )
            db.session.add(forced)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Identity setting updated'})

@app.route('/api/add_relationship', methods=['POST'])
@login_required
def add_relationship():
    try:
        category = request.json.get('category')
        person1 = request.json.get('person1')
        person2 = request.json.get('person2', '')
        description = request.json.get('description', '')
        
        if not category or not person1:
            return jsonify({'status': 'error', 'message': 'Category and person1 are required'})
        
        relationship = Relationship(
            category=category,
            person1=person1,
            person2=person2,
            description=description,
            created_by=current_user.id
        )
        
        db.session.add(relationship)
        db.session.commit()
        
        return jsonify({'status': 'success', 'relationship_id': relationship.id})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/add_reward', methods=['POST'])
@login_required
def add_reward():
    try:
        reward_type = request.json.get('reward_type')
        
        if not reward_type:
            return jsonify({'status': 'error', 'message': 'Reward type is required'})
        
        reward = Reward(
            user_id=current_user.id,
            reward_type=reward_type
        )
        
        db.session.add(reward)
        db.session.commit()
        
        return jsonify({'status': 'success', 'reward_id': reward.id})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/claim_reward/<reward_id>', methods=['POST'])
@login_required
def claim_reward(reward_id):
    try:
        reward = Reward.query.get(reward_id)
        if reward and reward.user_id == current_user.id:
            reward.is_claimed = True
            db.session.commit()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Reward not found or unauthorized'})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/user_rewards')
@login_required
def user_rewards():
    try:
        rewards = Reward.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            'status': 'success',
            'rewards': [{
                'id': r.id,
                'reward_type': r.reward_type,
                'awarded_at': r.awarded_at.isoformat(),
                'is_claimed': r.is_claimed
            } for r in rewards]
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/user_points')
@login_required
def user_points():
    try:
        # Calculate points based on user activity
        message_count = Message.query.filter_by(user_id=current_user.id).count()
        points = message_count * 5  # 5 points per message
        
        # Add bonus points for media uploads
        media_messages = Message.query.filter(
            Message.user_id == current_user.id,
            (Message.image_path != None) | (Message.voice_path != None)
        ).count()
        points += media_messages * 10  # 10 points per media upload
        
        # Daily login bonus (simplified)
        if current_user.last_login and current_user.last_login.date() == datetime.utcnow().date():
            points += 20  # 20 points for daily login
        
        return jsonify({
            'status': 'success',
            'points': points,
            'message_count': message_count,
            'media_count': media_messages
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})



@app.route('/api/get_topic_messages/<topic_id>')
@login_required
def get_topic_messages(topic_id):
    try:
        messages = Message.query.filter_by(
            topic_id=topic_id, 
            is_deleted=False
        ).order_by(Message.created_at).all()
        
        messages_data = []
        for message in messages:
            messages_data.append({
                'id': message.id,
                'content': message.content,
                'user_name': message.user.name if message.identity_revealed else message.user.username,
                'username': message.user.username,
                'identity_revealed': message.identity_revealed,
                'image_path': message.image_path,
                'voice_path': message.voice_path,
                'voice_type': message.voice_type,
                'timestamp': format_timestamp(message.created_at),
                'is_own_message': message.user_id == current_user.id
            })
        
        return jsonify({
            'status': 'success',
            'messages': messages_data
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/get_users')
@login_required
@admin_required
def get_users():
    try:
        # Get all users except the current admin
        users = User.query.filter(User.id != current_user.id).all()
        relationship_id = request.args.get('relationship_id')
        
        result = []
        for user in users:
            # Check if user is forced to reveal identity in this relationship
            force_reveal = False
            if relationship_id:
                forced = RelationshipForcedIdentity.query.filter_by(
                    user_id=user.id,
                    relationship_id=relationship_id
                ).first()
                if forced:
                    force_reveal = forced.must_reveal_identity
            
            result.append({
                'id': user.id,
                'name': user.name,
                'username': user.username,
                'force_reveal': force_reveal
            })
        
        return jsonify({
            'status': 'success',
            'users': result
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_user_stats')
@login_required
def get_user_stats():
    try:
        total_messages = Message.query.filter_by(user_id=current_user.id).count()
        total_topics = Topic.query.filter_by(created_by=current_user.id).count()
        total_relationships = Relationship.query.filter_by(created_by=current_user.id).count()
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_messages': total_messages,
                'topics_created': total_topics,
                'relationships_added': total_relationships,
                'join_date': current_user.created_at.strftime('%B %d, %Y')
            }
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create admin user if not exists
        admin_user = User.query.filter_by(username='adminkelly').first()
        if not admin_user:
            admin_user = User(
                name='Administrator',
                class_name='Staff',
                username='adminkelly',
                password=generate_password_hash('samira'),
                email='admin@riverschool.edu.gh',
                status='approved',
                is_admin=True,  # Set admin flag
                admin_level=2   # Full admin
            )
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created: username='adminkelly', password='samira', admin_level=2")
        else:
            # If admin exists but doesn't have full admin level, upgrade them
            try:
                if getattr(admin_user, 'is_admin', False) and getattr(admin_user, 'admin_level', 0) < 2:
                    admin_user.admin_level = 2
                    db.session.commit()
                    print("Existing admin upgraded to admin_level=2")
            except Exception:
                db.session.rollback()
    
    app.run(debug=True, host='0.0.0.0', port=5000)