"""
Application factory for Ham Radio Conditions app.
Creates and configures the Flask application with all its components.
"""

import os
import threading
import time
from flask import Flask, render_template
from config import get_config
from utils.logging_config import get_logger, setup_logging
from utils.background_tasks import setup_background_tasks, create_conditions_updater, create_database_cleanup
from routes.api import api_bp
from routes.pwa import pwa_bp
from database import Database
from qrz_data import QRZLookup
from ham_radio_conditions import HamRadioConditions

logger = get_logger(__name__)


def create_app(config_name: str = None) -> Flask:
    """
    Create and configure the Flask application.
    
    Args:
        config_name: Configuration name to use
    
    Returns:
        Configured Flask application
    """
    # Get configuration
    config = get_config(config_name)
    
    # Validate configuration
    errors = config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("Please check your environment variables and .env file")
        raise ValueError(f"Invalid configuration: {', '.join(errors)}")
    
    # Set up logging
    setup_logging('ham_radio_conditions', log_file='logs/ham_radio_conditions.log' if config.is_production() else None)
    
    # Create Flask app
    app = Flask(__name__, static_folder='static')
    app.config.from_object(config)
    
    # Initialize services
    services = initialize_services(config)
    
    # Store services in app config for access in routes
    app.config['DATABASE'] = services['database']
    app.config['HAM_CONDITIONS'] = services['ham_conditions']
    app.config['QRZ_LOOKUP'] = services['qrz_lookup']
    app.config['TASK_MANAGER'] = services['task_manager']
    
    # Register blueprints
    register_blueprints(app)
    
    # Register routes
    register_routes(app)
    
    # Set up background tasks
    setup_app_background_tasks(app, services)
    
    logger.info("Application created successfully")
    return app


def initialize_services(config) -> dict:
    """
    Initialize all application services.
    
    Args:
        config: Application configuration
    
    Returns:
        Dictionary of initialized services
    """
    logger.info("Initializing services...")
    
    # Initialize database
    database = Database()
    logger.info("Database initialized")
    
    # Load zip code from database if available, otherwise use environment variable
    stored_zip_code = database.get_user_preference('zip_code')
    if stored_zip_code:
        zip_code = stored_zip_code
        logger.info(f"Using stored ZIP code: {zip_code}")
    elif config.ZIP_CODE:
        zip_code = config.ZIP_CODE
        # Store the environment variable zip code in the database
        database.store_user_preference('zip_code', zip_code)
        logger.info(f"Stored environment ZIP code: {zip_code}")
    else:
        zip_code = None
        logger.warning("No ZIP code configured")
    
    # Initialize HamRadioConditions
    ham_conditions = HamRadioConditions(zip_code=zip_code)
    logger.info("HamRadioConditions initialized")
    
    # Initialize QRZ lookup (optional)
    qrz_lookup = None
    if config.QRZ_USERNAME and config.QRZ_PASSWORD:
        try:
            qrz_lookup = QRZLookup(config.QRZ_USERNAME, config.QRZ_PASSWORD)
            logger.info("QRZ lookup initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize QRZ lookup: {e}")
    else:
        logger.info("QRZ lookup not configured - QRZ functionality will be disabled")
    
    # Initialize task manager
    task_manager = setup_background_tasks(
        create_conditions_updater(ham_conditions, threading.Lock()),
        create_database_cleanup(database)
    )
    logger.info("Task manager initialized")
    
    return {
        'database': database,
        'ham_conditions': ham_conditions,
        'qrz_lookup': qrz_lookup,
        'task_manager': task_manager
    }


def register_blueprints(app: Flask) -> None:
    """
    Register Flask blueprints.
    
    Args:
        app: Flask application
    """
    app.register_blueprint(api_bp)
    app.register_blueprint(pwa_bp)
    logger.info("Blueprints registered")


def register_routes(app: Flask) -> None:
    """
    Register application routes.
    
    Args:
        app: Flask application
    """
    @app.route('/')
    def index():
        """Render the main page with cached conditions data."""
        ham_conditions = app.config.get('HAM_CONDITIONS')
        
        if ham_conditions._conditions_cache is None:
            # If no cache exists yet, generate conditions immediately
            with threading.Lock():
                ham_conditions._conditions_cache = ham_conditions.generate_report()
                ham_conditions._conditions_cache_time = time.time()
        
        return render_template('index.html', data=ham_conditions._conditions_cache)
    
    logger.info("Routes registered")


def setup_app_background_tasks(app: Flask, services: dict) -> None:
    """
    Set up background tasks for the application.
    
    Args:
        app: Flask application
        services: Dictionary of services
    """
    task_manager = services['task_manager']
    
    # Start background tasks
    task_manager.start_all()
    
    # Register cleanup on app shutdown
    @app.teardown_appcontext
    def cleanup(error):
        """Cleanup on application shutdown."""
        if error:
            logger.error(f"Application error: {error}")
        task_manager.stop_all()
    
    logger.info("Background tasks configured")


def create_app_with_error_handling(config_name: str = None) -> Flask:
    """
    Create application with error handling.
    
    Args:
        config_name: Configuration name to use
    
    Returns:
        Configured Flask application
    """
    try:
        return create_app(config_name)
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        raise 