"""
API routes for Ham Radio Conditions app.
Contains all API endpoints for the application.
"""

from flask import Blueprint, jsonify, request, current_app
from typing import Optional
from utils.logging_config import get_logger
from database import Database
from qrz_data import QRZLookup
from ham_radio_conditions import HamRadioConditions

logger = get_logger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/spots')
def get_spots():
    """Get live spots data - async, non-blocking"""
    try:
        # Get ham_conditions from app context
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        db = current_app.config.get('DATABASE')
        
        logger.debug(f"Ham conditions object: {ham_conditions}")
        logger.debug(f"Database object: {db}")
        
        if not ham_conditions:
            logger.error("Ham conditions not initialized")
            return jsonify({'error': 'Ham conditions not initialized'}), 500
        
        # Get spots from ham conditions
        logger.debug("Calling ham_conditions.get_live_activity()")
        spots_data = ham_conditions.get_live_activity()
        logger.debug(f"Spots data received: {type(spots_data)}")
        
        # Store spots in database for persistence
        if spots_data and spots_data.get('spots') and db:
            try:
                db.store_spots(spots_data['spots'])
                logger.debug(f"Stored {len(spots_data['spots'])} spots in database")
            except Exception as db_error:
                logger.warning(f"Failed to store spots in database: {db_error}")
        
        return jsonify(spots_data)
        
    except Exception as e:
        logger.error(f"Error in spots route: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'spots': [],
            'summary': {'total_spots': 0, 'source': 'Error'},
            'error': str(e)
        }), 500


@api_bp.route('/spots/history')
def get_spots_history():
    """Get historical spots from database"""
    try:
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        
        db = current_app.config.get('DATABASE')
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500
        
        spots = db.get_recent_spots(hours=hours, limit=limit)
        summary = db.get_spots_summary(hours=hours)
        
        return jsonify({
            'spots': spots,
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"Error getting spots history: {e}")
        return jsonify({
            'spots': [],
            'summary': {'total_spots': 0, 'source': 'Database Error'},
            'error': str(e)
        }), 500


@api_bp.route('/spots/status')
def get_spots_status():
    """Get spots loading status"""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if ham_conditions:
            status = ham_conditions.get_spots_status()
            return jsonify(status)
        else:
            return jsonify({'error': 'Ham conditions not initialized'}), 500
    except Exception as e:
        logger.error(f"Error getting spots status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/qrz/<callsign>')
def get_qrz_info(callsign: str):
    """Get QRZ information for a callsign."""
    try:
        if not callsign:
            return jsonify({'error': 'Callsign is required'}), 400
        
        # Clean and validate callsign
        callsign = callsign.strip().upper()
        if not callsign:
            return jsonify({'error': 'Invalid callsign'}), 400

        db = current_app.config.get('DATABASE')
        qrz_lookup = current_app.config.get('QRZ_LOOKUP')
        
        if not db:
            return jsonify({'error': 'Database not initialized'}), 500
        
        if not qrz_lookup:
            return jsonify({'error': 'QRZ lookup service not available - credentials not configured'}), 503

        # Check cache first
        cached_data = db.get_qrz_cache(callsign)
        if cached_data:
            logger.debug(f"Returning cached QRZ data for {callsign}")
            return jsonify(cached_data)

        # Get QRZ data using the new formatted info method
        formatted_info = qrz_lookup.get_formatted_info(callsign)
        if formatted_info.startswith('Callsign not found'):
            return jsonify({'error': 'Callsign not found'}), 404
        elif formatted_info.startswith('Error retrieving'):
            return jsonify({'error': formatted_info}), 500

        # Get the raw data for additional fields
        qrz_data = qrz_lookup.lookup(callsign)
        if not qrz_data:
            return jsonify({'error': 'Callsign not found'}), 404

        # Add formatted info to the response
        qrz_data['formatted_info'] = formatted_info

        # Cache the result
        db.store_qrz_cache(callsign, qrz_data)

        return jsonify(qrz_data)
    except Exception as e:
        logger.error(f"Error fetching QRZ data: {e}")
        return jsonify({'error': str(e)}), 500


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
            if ham_conditions and hasattr(ham_conditions, 'zip_code'):
                ham_conditions.zip_code = zip_code
                # Clear cache to force refresh
                if hasattr(ham_conditions, '_conditions_cache'):
                    ham_conditions._conditions_cache = None
                if hasattr(ham_conditions, '_conditions_cache_time'):
                    ham_conditions._conditions_cache_time = None
            
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


@api_bp.route('/debug/update-cache', methods=['POST'])
def manual_update_cache():
    """Manually trigger a cache update for testing"""
    try:
        ham_conditions = current_app.config.get('HAM_CONDITIONS')
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions not initialized'}), 500
        
        # Clear existing cache
        if hasattr(ham_conditions, '_conditions_cache'):
            ham_conditions._conditions_cache = None
        if hasattr(ham_conditions, '_conditions_cache_time'):
            ham_conditions._conditions_cache_time = None
        
        # Generate new report
        import time
        start_time = time.time()
        new_cache = ham_conditions.generate_report()
        end_time = time.time()
        
        # Update cache
        ham_conditions._conditions_cache = new_cache
        ham_conditions._conditions_cache_time = time.time()
        
        return jsonify({
            'success': True,
            'message': 'Cache updated manually',
            'cache_generated': bool(new_cache),
            'generation_time': f"{end_time - start_time:.2f}s",
            'cache_time': ham_conditions._conditions_cache_time
        })
        
    except Exception as e:
        logger.error(f"Error in manual cache update: {e}")
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500 