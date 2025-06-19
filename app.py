from flask import Flask, render_template, jsonify
from ham_radio_conditions import HamRadioConditions
import os
from dotenv import load_dotenv
import threading
import time
from datetime import datetime
from qrz_data import QRZLookup
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

# Start background thread for conditions updates
conditions_thread = threading.Thread(target=update_conditions_cache, daemon=True)
conditions_thread.start()

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
        
        # This now returns immediately
        spots_data = ham_conditions.get_live_activity()
        return jsonify(spots_data)
        
    except Exception as e:
        logger.error(f"Error in spots route: {e}")
        return jsonify({
            'spots': [],
            'summary': {'total_spots': 0, 'source': 'Error'},
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

        return jsonify(qrz_data)
    except Exception as e:
        print(f"Error fetching QRZ data: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001) 