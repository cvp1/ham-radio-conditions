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
            logger.debug("Using cached conditions for main page")
            return render_template('index.html', data=cached_conditions)
        
        # Generate new conditions if not cached
        logger.debug("Generating new conditions for main page")
        new_conditions = ham_conditions.generate_report()
        if new_conditions:
            return render_template('index.html', data=new_conditions)
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