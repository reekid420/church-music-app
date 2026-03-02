"""Application configuration."""

import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Config:
    """Default configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'church-bell-system-secret-key')

    # Directories
    MUSIC_DIR = os.path.join(BASE_DIR, 'music')
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DATABASE = os.path.join(BASE_DIR, 'data', 'church_bells.db')

    # Audio settings
    SUPPORTED_FORMATS = {'.mp3', '.flac'}
    DEFAULT_VOLUME = 80  # percent (0-100)

    # Server
    HOST = '0.0.0.0'
    PORT = 5000
