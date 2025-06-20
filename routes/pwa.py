"""
PWA routes for Ham Radio Conditions app.
Handles PWA-specific routes like manifest, service worker, and offline page.
"""

from flask import Blueprint, send_from_directory, current_app
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Create blueprint
pwa_bp = Blueprint('pwa', __name__)


@pwa_bp.route('/manifest.json')
def manifest():
    """Serve the PWA manifest"""
    try:
        return send_from_directory(
            'static',
            'manifest.json',
            mimetype='application/manifest+json'
        )
    except Exception as e:
        logger.error(f"Error serving manifest: {e}")
        return {'error': 'Manifest not found'}, 404


@pwa_bp.route('/sw.js')
def service_worker():
    """Serve the service worker"""
    try:
        return send_from_directory(
            'static',
            'sw.js',
            mimetype='application/javascript'
        )
    except Exception as e:
        logger.error(f"Error serving service worker: {e}")
        return {'error': 'Service worker not found'}, 404


@pwa_bp.route('/offline.html')
def offline():
    """Serve the offline page"""
    try:
        return send_from_directory('static', 'offline.html')
    except Exception as e:
        logger.error(f"Error serving offline page: {e}")
        return {'error': 'Offline page not found'}, 404


@pwa_bp.route('/static/icons/<path:filename>')
def icons(filename):
    """Serve app icons"""
    try:
        return send_from_directory('static/icons', filename)
    except Exception as e:
        logger.error(f"Error serving icon {filename}: {e}")
        return {'error': 'Icon not found'}, 404 