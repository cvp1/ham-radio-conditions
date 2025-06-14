from flask import Flask, render_template, jsonify
from ham_radio_conditions import HamRadioConditions
import os
from dotenv import load_dotenv
import threading
import time
from datetime import datetime
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get configuration from environment variables
ZIP_CODE = os.getenv('ZIP_CODE')
TEMP_UNIT = os.getenv('TEMP_UNIT', 'F')
CALLSIGN = os.getenv('CALLSIGN', 'N/A')

# Initialize HamRadioConditions with configured ZIP code
ham_conditions = HamRadioConditions(zip_code=ZIP_CODE)

# Initialize cache variables
_conditions_cache = None
_conditions_cache_time = 0
_conditions_lock = threading.Lock()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

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
    """Render the main page."""
    global _conditions_cache, _conditions_cache_time
    try:
        with _conditions_lock:
            if _conditions_cache is None:
                _conditions_cache = ham_conditions.generate_report()
                _conditions_cache_time = time.time()
            
            # Get current time
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Calculate cache age
            cache_age = int(time.time() - _conditions_cache_time)
            
            # Log the data being sent to the template
            logger.info(f"Sending data to template: {_conditions_cache}")
            
            return render_template('index.html',
                                data=_conditions_cache,
                                current_time=current_time,
                                cache_age=cache_age)
    except Exception as e:
        logger.error(f"Error rendering index: {e}")
        return render_template('index.html', 
                             data={'error': str(e)},
                             current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             cache_age=0)

@app.route('/api/spots')
def get_spots():
    """Get live spots data."""
    try:
        logger.info("Fetching spots from PSK Reporter...")
        spots_data = ham_conditions.get_live_activity()
        logger.info(f"Received spots data: {spots_data}")
        return jsonify(spots_data)
    except Exception as e:
        logger.error(f"Error fetching spots: {e}")
        logger.exception("Full traceback:")
        return jsonify({
            'spots': [],
            'summary': {
                'total_spots': 0,
                'active_bands': [],
                'active_modes': [],
                'active_dxcc': []
            }
        })

@app.route('/api/query_spots', methods=['POST'])
def query_spots():
    """Manually query spots from PSK Reporter."""
    try:
        logger.info("Manual spot query requested")
        spots_data = ham_conditions.get_live_activity()
        logger.info(f"Received spots data: {spots_data}")
        return jsonify(spots_data)
    except Exception as e:
        logger.error(f"Error fetching spots: {e}")
        logger.exception("Full traceback:")
        return jsonify({
            'error': str(e),
            'spots': [],
            'summary': {
                'total_spots': 0,
                'active_bands': [],
                'active_modes': [],
                'active_dxcc': []
            }
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 