"""
API routes for Ham Radio Conditions app.
Provides RESTful endpoints for conditions data, spots, and QRZ lookups.
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Optional
from utils.logging_config import get_logger
from database import Database
from qrz_data import QRZLookup
from ham_radio_conditions import HamRadioConditions
from utils.cache_manager import cache_get, cache_set, cache_delete, get_cache_stats
import time
import threading

logger = get_logger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/conditions', methods=['GET'])
def get_conditions():
    """Get current ham radio conditions."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            ham_conditions = app.config.get('HAM_CONDITIONS')
            if not ham_conditions:
                return jsonify({'error': 'Ham conditions service not available'}), 503
            
            # Try to get from cache first
            cached_conditions = cache_get('conditions', 'current')
            if cached_conditions:
                logger.debug("Returning cached conditions")
                return jsonify(cached_conditions)
            
            # Generate new conditions
            conditions = ham_conditions.generate_report()
            if conditions:
                return jsonify(conditions)
            else:
                return jsonify({'error': 'Failed to generate conditions'}), 500
                
    except Exception as e:
        logger.error(f"Error getting conditions: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/spots', methods=['GET'])
def get_spots():
    """Get live spots data."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            ham_conditions = app.config.get('HAM_CONDITIONS')
            if not ham_conditions:
                return jsonify({'error': 'Ham conditions service not available'}), 503
            
            # Try to get from cache first
            cached_spots = cache_get('spots', 'current')
            if cached_spots:
                logger.debug("Returning cached spots")
                return jsonify(cached_spots)
            
            # Get fresh spots
            spots = ham_conditions.get_live_activity()
            if spots:
                return jsonify(spots)
            else:
                return jsonify({'error': 'Failed to get spots'}), 500
                
    except Exception as e:
        logger.error(f"Error getting spots: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/spots/history', methods=['GET'])
def get_spots_history():
    """Get spots history from database."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            database = app.config.get('DATABASE')
            if not database:
                return jsonify({'error': 'Database not available'}), 503
            
            # Get limit from query parameters
            limit = request.args.get('limit', 50, type=int)
            limit = min(limit, 100)  # Cap at 100
            
            spots = database.get_recent_spots(limit)
            return jsonify({
                'spots': spots,
                'total': len(spots),
                'limit': limit
            })
                
    except Exception as e:
        logger.error(f"Error getting spots history: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/spots/status', methods=['GET'])
def get_spots_status():
    """Get spots loading status."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            ham_conditions = app.config.get('HAM_CONDITIONS')
            if not ham_conditions:
                return jsonify({'error': 'Ham conditions service not available'}), 503
            
            # Check cache status
            cached_spots = cache_get('spots', 'current')
            status = {
                'cached': cached_spots is not None,
                'source': cached_spots.get('summary', {}).get('source', 'None') if cached_spots else 'None',
                'total_spots': cached_spots.get('summary', {}).get('total_spots', 0) if cached_spots else 0,
                'timestamp': time.time()
            }
            
            return jsonify(status)
                
    except Exception as e:
        logger.error(f"Error getting spots status: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/qrz/<callsign>', methods=['GET'])
def qrz_lookup(callsign):
    """Look up a callsign in QRZ database."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            database = app.config.get('DATABASE')
            qrz_lookup = app.config.get('QRZ_LOOKUP')
            
            if not database:
                return jsonify({'error': 'Database not available'}), 503
            
            # Check cache first
            cached_data = cache_get('qrz', callsign.upper())
            if cached_data:
                logger.debug(f"Returning cached QRZ data for {callsign}")
                return jsonify(cached_data)
            
            # If QRZ lookup is not available, return cached data only
            if not qrz_lookup:
                return jsonify({
                    'error': 'QRZ lookup not configured',
                    'callsign': callsign.upper(),
                    'cached_only': True
                }), 503
            
            # Perform QRZ lookup
            try:
                qrz_data = qrz_lookup.lookup_callsign(callsign)
                
                if qrz_data:
                    # Cache the result
                    cache_set('qrz', callsign.upper(), qrz_data, max_age=3600)  # 1 hour
                    
                    # Also store in database for persistence
                    database.store_qrz_cache(callsign.upper(), qrz_data)
                    
                    return jsonify(qrz_data)
                else:
                    return jsonify({
                        'error': 'Callsign not found',
                        'callsign': callsign.upper()
                    }), 404
                    
            except Exception as e:
                logger.error(f"QRZ lookup error for {callsign}: {e}")
                return jsonify({
                    'error': 'QRZ lookup failed',
                    'callsign': callsign.upper(),
                    'details': str(e)
                }), 500
                
    except Exception as e:
        logger.error(f"Error in QRZ lookup: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/weather', methods=['GET'])
def get_weather():
    """Get current weather conditions."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            ham_conditions = app.config.get('HAM_CONDITIONS')
            if not ham_conditions:
                return jsonify({'error': 'Ham conditions service not available'}), 503
            
            # Try to get from cache first
            cached_weather = cache_get('weather', 'current')
            if cached_weather:
                logger.debug("Returning cached weather")
                return jsonify(cached_weather)
            
            # Get fresh weather data
            weather = ham_conditions.get_weather_conditions()
            if weather:
                return jsonify(weather)
            else:
                return jsonify({'error': 'Failed to get weather data'}), 500
                
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/refresh', methods=['POST'])
def refresh_data():
    """Manually refresh all data."""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            ham_conditions = app.config.get('HAM_CONDITIONS')
            if not ham_conditions:
                return jsonify({'error': 'Ham conditions service not available'}), 503
            
            # Clear all caches to force refresh
            cache_delete('conditions', 'current')
            cache_delete('spots', 'current')
            cache_delete('weather', 'current')
            
            # Generate new conditions
            new_conditions = ham_conditions.generate_report()
            
            return jsonify({
                'message': 'Data refreshed successfully',
                'conditions_generated': bool(new_conditions),
                'timestamp': time.time()
            })
                
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/cache/stats', methods=['GET'])
def get_cache_statistics():
    """Get cache statistics."""
    try:
        stats = get_cache_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all caches."""
    try:
        # Get cache type from request body
        data = request.get_json() or {}
        cache_type = data.get('cache_type')
        
        if cache_type:
            cache_delete(cache_type, 'current')
            logger.info(f"Cleared {cache_type} cache")
            return jsonify({
                'message': f'{cache_type} cache cleared successfully',
                'cache_type': cache_type
            })
        else:
            # Clear all caches
            cache_delete('conditions', 'current')
            cache_delete('spots', 'current')
            cache_delete('weather', 'current')
            logger.info("Cleared all caches")
            return jsonify({
                'message': 'All caches cleared successfully'
            })
                
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/debug/update-cache', methods=['POST'])
def manual_update_cache():
    """Manually trigger a cache update for testing"""
    try:
        from app_factory import create_app_with_error_handling
        app = create_app_with_error_handling()
        
        with app.app_context():
            ham_conditions = app.config.get('HAM_CONDITIONS')
            if not ham_conditions:
                return jsonify({'error': 'Ham conditions service not available'}), 503
            
            # Clear existing cache
            cache_delete('conditions', 'current')
            
            # Generate new cache
            new_cache = ham_conditions.generate_report()
            
            # Update cache
            if new_cache:
                cache_set('conditions', 'current', new_cache, max_age=300)
            
            return jsonify({
                'message': 'Cache updated manually',
                'cache_generated': bool(new_cache),
                'timestamp': time.time()
            })
                
    except Exception as e:
        logger.error(f"Error in manual cache update: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/preferences', methods=['GET', 'POST'])
def user_preferences():
    """Handle user preferences"""
    try:
        db = current_app.config.get('DATABASE')
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500
        
        if request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            for key, value in data.items():
                db.store_user_preference(key, str(value))
            
            return jsonify({'message': 'Preferences saved successfully'})
        
        else:  # GET
            # Return all user preferences
            preferences = {}
            common_keys = ['default_band', 'default_mode', 'refresh_interval', 'theme']
            for key in common_keys:
                value = db.get_user_preference(key)
                if value:
                    preferences[key] = value
            
            return jsonify(preferences)
            
    except Exception as e:
        logger.error(f"Error handling preferences: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/database/stats')
def get_database_stats():
    """Get database statistics"""
    try:
        db = current_app.config.get('DATABASE')
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500
        
        stats = db.get_database_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/update-location', methods=['POST'])
def update_location():
    """Update user location for better propagation predictions"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = current_app.config.get('DATABASE')
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500
        
        # Handle both old zip_code format and new lat/lon format
        if 'zip_code' in data:
            # Old format - zip code
            zip_code = data['zip_code'].strip()
            if not zip_code:
                return jsonify({'error': 'ZIP code cannot be empty'}), 400
            
            # Store zip code in database
            db.store_user_preference('zip_code', zip_code)
            logger.info(f"Updated user location to ZIP code: {zip_code}")
            
            # Update ham conditions if available
            ham_conditions = current_app.config.get('HAM_CONDITIONS')
            if ham_conditions and hasattr(ham_conditions, 'update_location'):
                success = ham_conditions.update_location(zip_code)
                if success:
                    logger.info(f"Successfully updated ham conditions location to ZIP: {zip_code}")
                else:
                    logger.warning(f"Failed to update ham conditions location to ZIP: {zip_code}")
            else:
                logger.warning("Ham conditions service not available for location update")
            
            return jsonify({
                'success': True,
                'message': f'Location updated to ZIP code: {zip_code}',
                'zip_code': zip_code
            })
            
        elif 'latitude' in data and 'longitude' in data:
            # New format - latitude/longitude
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            
            if latitude is None or longitude is None:
                return jsonify({'error': 'Latitude and longitude are required'}), 400
            
            # Validate coordinates
            try:
                lat = float(latitude)
                lon = float(longitude)
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    return jsonify({'error': 'Invalid coordinates'}), 400
            except ValueError:
                return jsonify({'error': 'Invalid coordinate format'}), 400
            
            # Store location in database
            db.store_user_preference('latitude', str(lat))
            db.store_user_preference('longitude', str(lon))
            logger.info(f"Updated user location: {lat}, {lon}")
            
            # Update ham conditions if available
            ham_conditions = current_app.config.get('HAM_CONDITIONS')
            if ham_conditions:
                # For lat/lon, we need to update the instance directly
                ham_conditions.lat = lat
                ham_conditions.lon = lon
                ham_conditions.grid_square = ham_conditions.latlon_to_grid(lat, lon)
                ham_conditions.timezone = ham_conditions._get_timezone_from_coords(lat, lon)
                
                # Clear caches to force refresh with new location
                if hasattr(ham_conditions, 'clear_cache'):
                    ham_conditions.clear_cache()
                
                logger.info(f"Successfully updated ham conditions location to lat/lon: {lat}, {lon}")
            
            return jsonify({
                'success': True,
                'message': 'Location updated successfully',
                'latitude': lat,
                'longitude': lon
            })
        else:
            return jsonify({'error': 'Either zip_code or latitude/longitude are required'}), 400
        
    except Exception as e:
        logger.error(f"Error updating location: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/debug/ham-conditions')
def debug_ham_conditions():
    """Debug endpoint to check ham conditions service"""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({
                'error': 'Ham conditions not initialized',
                'config_keys': list(current_app.config.keys())
            }), 500
        
        # Test basic functionality
        status = ham_conditions.get_spots_status()
        
        return jsonify({
            'ham_conditions_type': type(ham_conditions).__name__,
            'status': status,
            'has_get_live_activity': hasattr(ham_conditions, 'get_live_activity'),
            'has_get_spots_status': hasattr(ham_conditions, 'get_spots_status'),
            'config_keys': list(current_app.config.keys())
        })
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc(),
            'config_keys': list(current_app.config.keys()) if current_app else []
        }), 500 