import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image
import secrets

def allowed_file(filename, file_type='image'):
    """Check if file extension is allowed"""
    if file_type == 'image':
        allowed = current_app.config['ALLOWED_IMAGE_EXTENSIONS']
    else:  # voice
        allowed = current_app.config['ALLOWED_VOICE_EXTENSIONS']
    
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def save_image(file):
    """Save uploaded image and return filename"""
    if file and allowed_file(file.filename, 'image'):
        # Generate unique filename
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        # Ensure upload directory exists
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'images')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        
        # Open and optimize image
        image = Image.open(file)
        
        # Resize if too large (max 1200px width)
        if image.width > 1200:
            ratio = 1200 / image.width
            new_height = int(image.height * ratio)
            image = image.resize((1200, new_height), Image.Resampling.LANCZOS)
        
        # Save optimized image
        image.save(file_path, optimize=True, quality=85)
        
        return f"images/{filename}"
    return None

def save_voice(file):
    """Save uploaded voice file and return filename"""
    if file and allowed_file(file.filename, 'voice'):
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'voice')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return f"voice/{filename}"
    return None

def generate_voice_modification(audio_path, voice_type):
    """Placeholder for voice modification"""
    # In production, integrate with audio processing libraries
    voice_types = {
        'cartoon': 'high-pitched, animated',
        'deep': 'low-pitched, resonant', 
        'female': 'soft, higher-pitched',
        'robot': 'mechanical, synthesized'
    }
    return voice_types.get(voice_type, 'normal')

def format_timestamp(dt):
    """Format datetime for display"""
    return dt.strftime('%b %d, %Y %I:%M %p')