from flask import Flask, render_template, jsonify, request
from ham_radio_conditions import HamRadioConditions
import os
from dotenv import load_dotenv
import threading
import time
from datetime import datetime
from qrz_data import QRZLookup
from database import Database
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get configuration from environment variables
ZIP_CODE = os.getenv('ZIP_CODE')
TEMP_UNIT = os.getenv('TEMP_UNIT', 'F')
CALLSIGN = os.getenv('CALLSIGN', 'N/A')
QRZ_USERNAME = os.getenv('QRZ_USERNAME')
QRZ_PASSWORD = os.getenv('QRZ_PASSWORD')

# Initialize database
db = Database()

# Load zip code from database if available, otherwise use environment variable
stored_zip_code = db.get_user_preference('zip_code')
if stored_zip_code:
    ZIP_CODE = stored_zip_code
    logger.info(f"Using stored ZIP code: {ZIP_CODE}")
elif ZIP_CODE:
    # Store the environment variable zip code in the database
    db.store_user_preference('zip_code', ZIP_CODE)
    logger.info(f"Stored environment ZIP code: {ZIP_CODE}")

# Initialize HamRadioConditions with configured ZIP code
ham_conditions = HamRadioConditions(zip_code=ZIP_CODE)

# Initialize QRZ lookup
qrz_lookup = QRZLookup(QRZ_USERNAME, QRZ_PASSWORD)

# Cache for conditions data
_conditions_cache = None
_conditions_cache_time = None
_conditions_lock = threading.Lock()

def update_conditions_cache():
    """Update the conditions cache in the background."""
    global _conditions_cache, _conditions_cache_time
    while True:
        try:
            with _conditions_lock:
                _conditions_cache = ham_conditions.generate_report()
                _conditions_cache_time = time.time()
            time.sleep(300)  # Update every 5 minutes
        except Exception as e:
            print(f"Error updating conditions cache: {e}")
            time.sleep(60)  # Wait a minute before retrying

def cleanup_database():
    """Clean up old database data periodically."""
    while True:
        try:
            time.sleep(3600)  # Run every hour
            db.cleanup_old_data(days=7)  # Keep 7 days of data
        except Exception as e:
            logger.error(f"Error in database cleanup: {e}")

# Start background threads
conditions_thread = threading.Thread(target=update_conditions_cache, daemon=True)
conditions_thread.start()

cleanup_thread = threading.Thread(target=cleanup_database, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    """Render the main page with cached conditions data."""
    global _conditions_cache
    if _conditions_cache is None:
        # If no cache exists yet, generate conditions immediately
        with _conditions_lock:
            _conditions_cache = ham_conditions.generate_report()
            _conditions_cache_time = time.time()
    
    return render_template('index.html', data=_conditions_cache)

@app.route('/api/spots')
def get_spots():
    """Get live spots data - async, non-blocking"""
    try:
        if not ham_conditions:
            return jsonify({'error': 'Ham conditions not initialized'})
        
        # Get spots from ham conditions
        spots_data = ham_conditions.get_live_activity()
        
        # Store spots in database for persistence
        if spots_data.get('spots'):
            db.store_spots(spots_data['spots'])
        
        return jsonify(spots_data)
        
    except Exception as e:
        logger.error(f"Error in spots route: {e}")
        return jsonify({
            'spots': [],
            'summary': {'total_spots': 0, 'source': 'Error'},
            'error': str(e)
        })

@app.route('/api/spots/history')
def get_spots_history():
    """Get historical spots from database"""
    try:
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 100, type=int)
        
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
        })

@app.route('/api/spots/status')
def get_spots_status():
    """Get spots loading status"""
    try:
        if ham_conditions:
            status = ham_conditions.get_spots_status()
            return jsonify(status)
        else:
            return jsonify({'error': 'Ham conditions not initialized'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/qrz/<callsign>')
def get_qrz_info(callsign):
    """Get QRZ information for a callsign."""
    try:
        if not callsign:
            return jsonify({'error': 'Callsign is required'}), 400
        
        # Clean and validate callsign
        callsign = callsign.strip().upper()
        if not callsign:
            return jsonify({'error': 'Invalid callsign'}), 400

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
        print(f"Error fetching QRZ data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/preferences', methods=['GET', 'POST'])
def user_preferences():
    """Handle user preferences"""
    try:
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

@app.route('/api/database/stats')
def get_database_stats():
    """Get database statistics"""
    try:
        stats = db.get_database_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-location', methods=['POST'])
def update_location():
    """Update the location/zip code"""
    try:
        data = request.get_json()
        if not data or 'zip_code' not in data:
            return jsonify({'success': False, 'error': 'ZIP code is required'}), 400
        
        zip_code = data['zip_code'].strip()
        if not zip_code:
            return jsonify({'success': False, 'error': 'ZIP code cannot be empty'}), 400
        
        # Store the new zip code in the database
        db.store_user_preference('zip_code', zip_code)
        
        # Update the HamRadioConditions instance with the new zip code
        global ham_conditions
        ham_conditions = HamRadioConditions(zip_code=zip_code)
        
        # Clear the conditions cache to force a refresh
        global _conditions_cache, _conditions_cache_time
        with _conditions_lock:
            _conditions_cache = None
            _conditions_cache_time = None
        
        logger.info(f"Location updated to ZIP code: {zip_code}")
        return jsonify({'success': True, 'message': f'Location updated to {zip_code}'})
        
    except Exception as e:
        logger.error(f"Error updating location: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001) 