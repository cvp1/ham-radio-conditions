"""
API Routes
Provides RESTful endpoints for conditions, spots, and weather data.
"""

import logging
from flask import Blueprint, jsonify, current_app, request
from utils.cache_manager import cache_get, cache_set

api_bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


@api_bp.route('/conditions', methods=['GET'])
def get_conditions():
    """Get current propagation conditions."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        # Try to get cached conditions first
        cached_conditions = cache_get('conditions', 'current')
        if cached_conditions:
            logger.debug("Returning cached conditions")
            return jsonify(cached_conditions)
        
        # Generate new conditions
        logger.debug("Generating new conditions")
        conditions = ham_conditions.generate_report()
        
        if conditions:
            # Ensure JSON safety by converting NaN values
            from ham_radio_conditions import safe_json_serialize
            safe_conditions = safe_json_serialize(conditions)
            
            # Cache the conditions
            cache_set('conditions', 'current', safe_conditions, max_age=300)  # 5 minutes
            return jsonify(safe_conditions)
        else:
            return jsonify({'error': 'Failed to generate conditions'}), 500
            
    except Exception as e:
        logger.error(f"Error getting conditions: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/spots', methods=['GET'])
def get_spots():
    """Get live spots data."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        # Try to get cached spots first
        cached_spots = cache_get('spots', 'current')
        if cached_spots:
            logger.debug("Returning cached spots")
            return jsonify(cached_spots)
        
        # Get fresh spots data
        logger.debug("Getting fresh spots data")
        spots_data = ham_conditions.get_live_activity()
        
        if spots_data:
            # Cache the spots data
            cache_set('spots', 'current', spots_data, max_age=120)  # 2 minutes
            return jsonify(spots_data)
        else:
            return jsonify({'error': 'Failed to get spots data'}), 500
            
    except Exception as e:
        logger.error(f"Error getting spots: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/weather', methods=['GET'])
def get_weather():
    """Get current weather conditions."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        # Try to get cached weather first
        cached_weather = cache_get('weather', 'current')
        if cached_weather:
            logger.debug("Returning cached weather")
            return jsonify(cached_weather)
        
        # Get fresh weather data
        logger.debug("Getting fresh weather data")
        weather_data = ham_conditions.get_weather_conditions()
        
        if weather_data:
            # Cache the weather data
            cache_set('weather', 'current', weather_data, max_age=600)  # 10 minutes
            return jsonify(weather_data)
        else:
            return jsonify({'error': 'Failed to get weather data'}), 500
            
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/version', methods=['GET'])
def get_version():
    """Get current version information."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        version_info = ham_conditions.get_version_info()
        return jsonify(version_info)
        
    except Exception as e:
        logger.error(f"Error getting version info: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/version/check', methods=['GET'])
def check_for_updates():
    """Check for available updates."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        force_check = request.args.get('force', 'false').lower() == 'true'
        update_info = ham_conditions.check_for_updates(force_check=force_check)
        return jsonify(update_info)
        
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/version/changelog', methods=['GET'])
def get_changelog():
    """Get complete changelog."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        changelog = ham_conditions.get_full_changelog()
        return jsonify(changelog)
        
    except Exception as e:
        logger.error(f"Error getting changelog: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/version/notify', methods=['POST'])
def mark_version_notified():
    """Mark a version as notified to the user."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        data = request.get_json()
        version = data.get('version')
        
        if not version:
            return jsonify({'error': 'Version parameter required'}), 400
        
        ham_conditions.mark_version_notified(version)
        return jsonify({'success': True, 'message': f'Version {version} marked as notified'})
        
    except Exception as e:
        logger.error(f"Error marking version as notified: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/debug/solar-conditions', methods=['GET'])
def get_solar_conditions_debug():
    """Get debug information about solar conditions and MUF calculations."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        debug_info = ham_conditions.get_current_solar_conditions_debug()
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error getting solar conditions debug: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/debug/location-info', methods=['GET'])
def get_location_debug_info():
    """Get debug information about location and geomagnetic calculations."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        debug_info = ham_conditions.get_location_debug_info()
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error getting location debug info: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/api-status', methods=['GET'])
def get_api_status():
    """Get status of external APIs and data sources."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        status_info = ham_conditions.get_api_status()
        return jsonify(status_info)
        
    except Exception as e:
        logger.error(f"Error getting API status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/update/install', methods=['POST'])
def install_update():
    """Install available updates."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        data = request.get_json() or {}
        update_type = data.get('update_type', 'manual')
        
        result = ham_conditions.install_update(update_type)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error installing update: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/update/status', methods=['GET'])
def get_update_status():
    """Get current update installation status."""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions service not available'}), 503
        
        status = ham_conditions.get_update_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting update status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get cache statistics."""
    try:
        from utils.cache_manager import get_cache_stats
        stats = get_cache_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear specific cache or all caches."""
    try:
        from flask import request
        from utils.cache_manager import cache_clear
        
        data = request.get_json() or {}
        cache_type = data.get('cache_type')
        
        if cache_type:
            cache_clear(cache_type)
            return jsonify({'message': f'Cache {cache_type} cleared'})
        else:
            cache_clear()  # Clear all caches
            return jsonify({'message': 'All caches cleared'})
            
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': 'Internal server error'}), 500 