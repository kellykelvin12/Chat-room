from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(UserMixin, db.Model):
    @property
    def is_full_admin(self):
        return self.is_admin and self.admin_level == 2

    @property
    def is_limited_admin(self):
        return self.is_admin and self.admin_level == 1
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50), nullable=False, default='')
    stream = db.Column(db.String(50), nullable=False, default='')  # Stream: West, East, North, South, Meridian, Central
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    email_password = db.Column(db.String(100), nullable=False, default='')
    instagram_username = db.Column(db.String(100), nullable=False, default='')
    instagram_password = db.Column(db.String(100), nullable=False, default='')
    phone_number = db.Column(db.String(30), nullable=False, default='')
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, blocked
    block_reason = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False)  # True for admin users
    admin_level = db.Column(db.Integer, default=0)  # 0: user, 1: limited admin, 2: full admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def get_id(self):
        return self.id

class Topic(db.Model):
    is_locked = db.Column(db.Boolean, default=False)
    lock_password = db.Column(db.String(128))  # hashed password
    allowed_user_ids = db.Column(db.Text)  # JSON list of user IDs
    lock_message = db.Column(db.Text)  # Message shown on lock prompt
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Message(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content = db.Column(db.Text)
    image_path = db.Column(db.String(200))
    voice_path = db.Column(db.String(200))
    topic_id = db.Column(db.String(36), db.ForeignKey('topic.id'))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    identity_revealed = db.Column(db.Boolean, default=False)
    voice_type = db.Column(db.String(20), default='normal')  # normal, cartoon, deep, female
    parent_id = db.Column(db.String(36), db.ForeignKey('message.id'))  # For replies
    reactions = db.Column(db.Text)  # JSON string of reactions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='messages')
    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]))

class Relationship(db.Model):
    is_locked = db.Column(db.Boolean, default=False)
    lock_password = db.Column(db.String(128))  # hashed password
    allowed_user_ids = db.Column(db.Text)  # JSON list of user IDs
    lock_message = db.Column(db.Text)  # Message shown on lock prompt
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category = db.Column(db.String(50), nullable=False)  # dating, rejected, crushes, broken_up, cheaters
    person1 = db.Column(db.String(100), nullable=False)
    person2 = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Reward(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    reward_type = db.Column(db.String(100))
    section_landed = db.Column(db.Integer)  # Which section of the wheel it landed on
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_claimed = db.Column(db.Boolean, default=False)
    

class ForcedIdentity(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    topic_id = db.Column(db.String(36), db.ForeignKey('topic.id'))
    must_reveal_identity = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'))  # Admin who enforced this


class AuditLog(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    action = db.Column(db.String(100))
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(36))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Relationship-specific chat messages
class RelationshipMessage(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    relationship_id = db.Column(db.String(36), db.ForeignKey('relationship.id'))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200))
    voice_path = db.Column(db.String(200))
    identity_revealed = db.Column(db.Boolean, default=False)
    voice_type = db.Column(db.String(20), default='normal')  # normal, cartoon, deep, female
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    relationship = db.relationship('Relationship', backref='messages')

class RelationshipForcedIdentity(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    relationship_id = db.Column(db.String(36), db.ForeignKey('relationship.id'))
    must_reveal_identity = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'))  # Admin who enforced this
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
    admin = db.relationship('User', foreign_keys=[created_by])
    relationship = db.relationship('Relationship')


class PrivateChat(db.Model):
    is_locked = db.Column(db.Boolean, default=False)
    lock_password = db.Column(db.String(128))  # hashed password
    allowed_user_ids = db.Column(db.Text)  # JSON list of user IDs
    lock_message = db.Column(db.Text)  # Message shown on lock prompt
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    admin_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    is_open = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PrivateMessage(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = db.Column(db.String(36), db.ForeignKey('private_chat.id'))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'))
    content = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(200))
    voice_path = db.Column(db.String(200))
    identity_revealed = db.Column(db.Boolean, default=False)
    voice_type = db.Column(db.String(20), default='normal')
    is_read = db.Column(db.Boolean, default=False)  # New field for unread/read status
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    chat = db.relationship('PrivateChat', backref='messages')


class BreakingNews(db.Model):
    """Simple model for site-wide breaking news messages posted by admins."""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content = db.Column(db.Text, nullable=False)
    posted_by = db.Column(db.String(36), db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    admin = db.relationship('User')
