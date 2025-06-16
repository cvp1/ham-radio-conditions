# Ham Radio Conditions Reporter

This application fetches real-time ham radio band conditions and environmental data to generate detailed reports. It provides up-to-the-minute information about:

- Solar conditions (SFI, A-index, K-index, X-ray, Sunspots, Flux)
- Band conditions for day and night
- Current weather conditions
- DXCC entity information and conditions
- Live spots from the IARC network
- QRZ XML Database API integration for callsign information

## Setup

### Option 1: Local Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root and add your API keys and configuration:
```
# Weather API Configuration
OPENWEATHER_API_KEY=your_weather_api_key
ZIP_CODE=your_zip_code
TEMP_UNIT=F  # or C for Celsius

# Ham Radio Configuration
CALLSIGN=your_callsign

# QRZ XML Database API Configuration
QRZ_USERNAME=your_qrz_username  # Your QRZ.com login username
QRZ_PASSWORD=your_qrz_password  # Your QRZ.com login password

# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=production
```

3. Run the application:
```bash
python app.py
```

### Option 2: Docker Setup

1. Create a `.env` file as described above

2. Build and run using Docker Compose:
```bash
docker-compose up --build
```

The application will be available at http://localhost:8087

## Features

- Real-time solar and geomagnetic data from HamQSL
- Detailed band condition forecasts for day and night
- Weather conditions
- Comprehensive propagation reports
- DXCC entity information with ITU and CQ zones
- Live spots from the IARC network
- QRZ XML Database API integration with comprehensive callsign information:
  - Basic info (callsign, name, location)
  - License details (class, effective date, expiration)
  - Location data (country, state, county, grid)
  - DXCC and zone information
  - QSL information (manager, LoTW, eQSL)
  - IOTA and other awards
  - Contact information
- Modern, responsive UI with real-time updates
- Hourly updates for propagation data
- 5-minute updates for live spots

## Project Structure

- `app.py` - Main application entry point
- `ham_radio_conditions.py` - Core functionality for ham radio conditions
- `dxcc_data.py` - DXCC entity information handling
- `qrz_data.py` - QRZ XML Database API integration
- `templates/` - HTML templates for the web interface
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Docker Compose configuration

## Data Sources

- HamQSL XML Feed (http://www.hamqsl.com/solarxml.php) for propagation and solar data
- OpenWeatherMap API for weather data
- IARC API (https://holycluster.iarc.org) for live spots
- DXCC database for entity information
- QRZ XML Database API (https://xmldata.qrz.com) for callsign lookups

## UI Features

- Color-coded section icons for easy navigation
- Interactive hover effects
- Responsive layout optimized for all screen sizes
- Real-time updates for live spots
- Detailed DXCC information display
- Comprehensive spot information including:
  - Time
  - Callsign
  - Frequency
  - Mode
  - Band
  - DXCC entity
  - Comments
  - QRZ lookup integration with detailed callsign information:
    - Basic info display
    - License details
    - Location information
    - DXCC and zone data
    - QSL preferences
    - Awards and achievements
    - Contact information

## Update Frequency

- Propagation data: Updates every hour to respect the HamQSL feed's update frequency
- Live spots: Updates every 5 minutes
- Weather data: Updates on each request
- QRZ lookups: On-demand when viewing spot details or using the QRZ lookup feature

## QRZ Integration

The application uses the QRZ XML Database API to provide comprehensive callsign information. The integration includes:

- Authentication using QRZ.com login credentials
- Session management with automatic re-authentication
- Comprehensive data extraction including:
  - Basic operator information
  - License details
  - Location data
  - DXCC and zone information
  - QSL preferences
  - Awards and achievements
  - Contact information
- Error handling and retry logic
- Formatted display of all available information
- Automatic session expiration handling 