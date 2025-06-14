from flask import Flask, render_template, jsonify
from ham_radio_conditions import HamRadioConditions
import os
from dotenv import load_dotenv
import threading
import time
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Get configuration from environment variables
ZIP_CODE = os.getenv('ZIP_CODE')
TEMP_UNIT = os.getenv('TEMP_UNIT', 'F')
CALLSIGN = os.getenv('CALLSIGN', 'N/A')

# Initialize HamRadioConditions with configured ZIP code
ham_conditions = HamRadioConditions(zip_code=ZIP_CODE)

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
    """Get live spots data."""
    try:
        spots_data = ham_conditions.get_live_activity()
        return jsonify(spots_data)
    except Exception as e:
        print(f"Error fetching spots: {e}")
        return jsonify({
            'spots': [],
            'summary': {
                'total_spots': 0,
                'active_bands': [],
                'active_modes': [],
                'active_dxcc': []
            }
        })

if __name__ == '__main__':
    app.run(debug=True) 