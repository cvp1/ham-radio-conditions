"""
Configuration module for Ham Radio Conditions app.
Centralizes all configuration settings and environment variables.
"""

import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()


class Config:
    """Application configuration class."""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_ENV') == 'development'
    PORT = int(os.getenv('PORT', 5001))
    
    # Weather API Configuration
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
    ZIP_CODE = os.getenv('ZIP_CODE')
    TEMP_UNIT = os.getenv('TEMP_UNIT', 'F')
    
    # Ham Radio Configuration
    CALLSIGN = os.getenv('CALLSIGN', 'N/A')
    
    # QRZ XML Database API Configuration
    QRZ_USERNAME = os.getenv('QRZ_USERNAME')
    QRZ_PASSWORD = os.getenv('QRZ_PASSWORD')
    
    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/ham_radio.db')
    DATA_RETENTION_DAYS = int(os.getenv('DATA_RETENTION_DAYS', 7))
    
    # Cache Configuration
    CACHE_UPDATE_INTERVAL = int(os.getenv('CACHE_UPDATE_INTERVAL', 300))  # 5 minutes
    CLEANUP_INTERVAL = int(os.getenv('CLEANUP_INTERVAL', 3600))  # 1 hour
    
    # PWA Configuration
    PWA_NAME = "Ham Radio Conditions"
    PWA_SHORT_NAME = "Ham Radio"
    PWA_DESCRIPTION = "Real-time ham radio propagation conditions, solar weather, and live spots"
    PWA_THEME_COLOR = "#3B82F6"
    PWA_BACKGROUND_COLOR = "#111827"
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration values."""
        errors = []
        
        if not cls.OPENWEATHER_API_KEY:
            errors.append("OPENWEATHER_API_KEY is required")
        
        if not cls.ZIP_CODE:
            errors.append("ZIP_CODE is required")
        
        # QRZ credentials are optional - app will work without them
        if not cls.QRZ_USERNAME or not cls.QRZ_PASSWORD:
            print("Warning: QRZ_USERNAME and QRZ_PASSWORD not set - QRZ lookup functionality will be disabled")
        
        return errors
    
    @classmethod
    def get_database_url(cls) -> str:
        """Get database URL for SQLite."""
        return f"sqlite:///{cls.DATABASE_PATH}"
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production mode."""
        return not cls.DEBUG


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TEMP_UNIT = 'F'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
    @classmethod
    def validate(cls) -> list[str]:
        """Additional validation for production."""
        errors = super().validate()
        
        # Only warn about SECRET_KEY in production, don't fail
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            print("Warning: SECRET_KEY is using default value - consider setting a secure key in production")
        
        return errors


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DATABASE_PATH = ':memory:'  # Use in-memory database for tests


# Configuration mapping
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> Config:
    """Get configuration based on environment."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    return config_map.get(config_name, config_map['default']) 