import os

class Config:
    SECRET_KEY = 'athi-river-gossip-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///gossip.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Allowed extensions
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    ALLOWED_VOICE_EXTENSIONS = {'mp3', 'wav', 'ogg'}