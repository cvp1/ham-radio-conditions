"""
Flask Application Factory
Creates and configures the Flask application with all necessary components.
"""

import os
import logging
from flask import Flask
from flask_caching import Cache
from flask_cors import CORS
from datetime import datetime
import pytz

from config import Config
from database import init_database
from ham_radio_conditions import HamRadioConditions
from utils.background_tasks import TaskManager
from utils.logging_config import setup_logging
from routes.api import api_bp
from routes.pwa import pwa_bp

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize logging
    logger.info("Initializing services...")
    
    # Initialize database
    init_database()
    logger.info("Database initialized")
    
    # Initialize CORS
    CORS(app)
    
    # Initialize cache
    cache = Cache(app)
    
    # Initialize services
    services = initialize_services(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Configure app with services
    app.config['HAM_CONDITIONS'] = services['ham_conditions']
    app.config['TASK_MANAGER'] = services['task_manager']
    
    # Register routes
    register_routes(app)
    
    # Configure background tasks
    configure_background_tasks(app, services)
    
    logger.info("Application created successfully")
    return app


def initialize_services(app):
    """Initialize all application services."""
    services = {}
    
    # Initialize HamRadioConditions
    try:
        # Get stored ZIP code from database or use default
        from database import get_stored_zip_code
        stored_zip = get_stored_zip_code()
        
        if stored_zip:
            logger.info(f"Using stored ZIP code: {stored_zip}")
            ham_conditions = HamRadioConditions(zip_code=stored_zip)
        else:
            ham_conditions = HamRadioConditions()
        
        services['ham_conditions'] = ham_conditions
        logger.info("HamRadioConditions initialized")
    except Exception as e:
        logger.error(f"Failed to initialize HamRadioConditions: {e}")
        raise
    
    # Initialize task manager
    try:
        task_manager = TaskManager()
        services['task_manager'] = task_manager
        logger.info("Task manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize task manager: {e}")
        raise
    
    return services


def register_blueprints(app):
    """Register Flask blueprints."""
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(pwa_bp)
    logger.info("Blueprints registered")


def safe_json_serialize(obj):
    """Safely serialize an object to JSON, handling NaN, inf, and other problematic values."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return "N/A"  # Use safe string instead of None
        return obj
    elif isinstance(obj, dict):
        return {key: safe_json_serialize(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    elif isinstance(obj, (int, str, bool, type(None))):
        return obj
    else:
        # Convert other types to string
        return str(obj)

def register_routes(app):
    """Register application routes."""
    @app.route('/')
    def index():
        """Render the main page with cached conditions data."""
        from flask import render_template
        from utils.cache_manager import cache_get
        
        ham_conditions = app.config.get('HAM_CONDITIONS')
        
        # Try to get cached conditions first
        cached_conditions = cache_get('conditions', 'current')
        if cached_conditions:
            print("=== MAIN PAGE: Using cached conditions ===")
            # Ensure JSON safety for template rendering
            safe_cached_conditions = safe_json_serialize(cached_conditions)
            print(f"=== MAIN PAGE: JSON safety check: Original size={len(str(cached_conditions))}, Safe size={len(str(safe_cached_conditions))} ===")
            return render_template('index.html', data=safe_cached_conditions)
        
        # Generate new conditions if not cached
        print("=== MAIN PAGE: Generating new conditions ===")
        new_conditions = ham_conditions.generate_report()
        if new_conditions:
            # Ensure JSON safety for template rendering
            safe_new_conditions = safe_json_serialize(new_conditions)
            print(f"=== MAIN PAGE: JSON safety check: Original size={len(str(new_conditions))}, Safe size={len(str(safe_new_conditions))} ===")
            return render_template('index.html', data=safe_new_conditions)
        else:
            # Return empty data if generation fails
            return render_template('index.html', data={})
    
    logger.info("Routes registered")


def configure_background_tasks(app, services):
    """Configure background tasks."""
    task_manager = services['task_manager']
    
    # Configure periodic tasks
    task_manager.add_task(
        'update_conditions',
        lambda: services['ham_conditions'].generate_report(),
        interval_seconds=300  # 5 minutes
    )
    
    logger.info("Background tasks configured") 