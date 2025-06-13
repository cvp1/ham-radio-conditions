from flask import Flask, jsonify, render_template
from ham_radio_conditions import HamRadioConditions
import threading
import time
from datetime import datetime
import os

app = Flask(__name__)
reporter = HamRadioConditions(
    grid_square=os.getenv('GRID_SQUARE', 'DM41vv'),
    temp_unit=os.getenv('TEMP_UNIT', 'F')
)
current_data = {
    'timestamp': '',
    'location': '',
    'solar_conditions': {},
    'band_conditions': {},
    'weather_conditions': {}
}

def update_data():
    """Background task to update data every hour"""
    global current_data
    while True:
        try:
            report = reporter.generate_report()
            if report:
                current_data = report
                print(f"Data updated at {datetime.now()}")
            else:
                print(f"Failed to update data at {datetime.now()}")
        except Exception as e:
            print(f"Error updating data: {str(e)}")
        time.sleep(3600)  # Update every hour

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/conditions')
def get_conditions():
    global current_data
    try:
        # If data is empty or more than an hour old, fetch new data
        if not current_data.get('timestamp') or \
           (datetime.now() - datetime.fromisoformat(current_data['timestamp'])).total_seconds() > 3600:
            current_data = reporter.generate_report()
        return jsonify(current_data)
    except Exception as e:
        print(f"Error serving conditions: {str(e)}")
        return jsonify({
            'error': 'Failed to fetch conditions',
            'timestamp': datetime.now().isoformat(),
            'location': reporter.grid_square,
            'solar_conditions': {},
            'band_conditions': {},
            'weather_conditions': {}
        })

if __name__ == '__main__':
    # Generate initial data
    try:
        current_data = reporter.generate_report()
        print(f"Initial data fetched at {datetime.now()}")
    except Exception as e:
        print(f"Error fetching initial data: {str(e)}")
    
    # Start the background update thread
    update_thread = threading.Thread(target=update_data, daemon=True)
    update_thread.start()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=8087) 