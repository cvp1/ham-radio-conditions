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

setup_logging()
logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    logger.info("Initializing services...")
    
    init_database()
    logger.info("Database initialized")
    
    CORS(app)
    
    cache = Cache(app)
    
    services = initialize_services(app)
    
    register_blueprints(app)
    
    app.config['HAM_CONDITIONS'] = services['ham_conditions']
    app.config['TASK_MANAGER'] = services['task_manager']
    
    register_routes(app)
    
    configure_background_tasks(app, services)
    
    logger.info("Application created successfully")
    return app


def initialize_services(app):
    """Initialize all application services."""
    services = {}
    
    try:
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
        return str(obj)

def register_routes(app):
    """Register application routes."""
    @app.route('/')
    def index():
        """Render the main page with cached conditions data."""
        from flask import render_template
        from utils.cache_manager import cache_get
        
        ham_conditions = app.config.get('HAM_CONDITIONS')
        
        cached_conditions = cache_get('conditions', 'current')
        if cached_conditions:
            print("=== MAIN PAGE: Using cached conditions ===")
            safe_cached_conditions = safe_json_serialize(cached_conditions)
            print(f"=== MAIN PAGE: JSON safety check: Original size={len(str(cached_conditions))}, Safe size={len(str(safe_cached_conditions))} ===")
            return render_template('index.html', data=safe_cached_conditions)
        
        print("=== MAIN PAGE: Generating new conditions ===")
        new_conditions = ham_conditions.generate_report()
        if new_conditions:
            safe_new_conditions = safe_json_serialize(new_conditions)
            print(f"=== MAIN PAGE: JSON safety check: Original size={len(str(new_conditions))}, Safe size={len(str(safe_new_conditions))} ===")
            return render_template('index.html', data=safe_new_conditions)
        else:
            return render_template('index.html', data={})
    
    logger.info("Routes registered")


def configure_background_tasks(app, services):
    """Configure background tasks."""
    task_manager = services['task_manager']

    task_manager.add_task(
        'update_conditions',
        lambda: services['ham_conditions'].generate_report(),
        interval_seconds=300
    )

    # Snapshot conditions for the history chart.
    def store_conditions_snapshot():
        try:
            from database import get_database
            from utils.cache_manager import cache_get
            conditions = cache_get('conditions', 'current')
            if not conditions:
                return
            db = get_database()
            solar = conditions.get('solar_conditions', {})
            prop = conditions.get('propagation_summary', {})
            params = prop.get('propagation_parameters', {})
            muf_raw = params.get('muf', '0')
            muf = float(str(muf_raw).strip()) if muf_raw else 0.0
            sfi_raw = solar.get('sfi', '100')
            sfi = float(str(sfi_raw).replace(' SFI', '').strip()) if sfi_raw else 100.0
            k_raw = solar.get('k_index', '2')
            k_index = float(str(k_raw).strip()) if k_raw else 2.0
            a_raw = solar.get('a_index', '5')
            a_index = float(str(a_raw).strip()) if a_raw else 5.0
            quality = params.get('quality', 'Unknown')
            db.store_conditions_snapshot(muf, sfi, k_index, a_index, quality)
            logger.debug(f"Stored conditions snapshot: MUF={muf}, SFI={sfi}, K={k_index}")
        except Exception as e:
            logger.error(f"Error storing conditions snapshot: {e}")

    task_manager.add_task(
        'store_conditions_history',
        store_conditions_snapshot,
        interval_seconds=600
    )

    task_manager.start_all()

    logger.info("Background tasks configured and started")