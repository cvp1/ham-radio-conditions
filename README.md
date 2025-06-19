# Ham Radio Conditions Reporter

This application fetches real-time ham radio band conditions and environmental data to generate detailed reports. It provides up-to-the-minute information about:

- Solar conditions (SFI, A-index, K-index, X-ray, Sunspots, Flux)
- Band conditions for day and night
- Current weather conditions
- Detailed propogation report
- DXCC entity information and conditions
- Live spots from the PSK Network
- QRZ XML Database API integration for callsign information
- **Persistent SQLite database for storing spots, QRZ cache, and user preferences**
- **Progressive Web App (PWA) with offline support and install capability**

## PWA Features

This application is now a full Progressive Web App (PWA) with the following features:

### Installation
- **Install to Home Screen**: Users can install the app on their mobile devices and desktop
- **App-like Experience**: Runs in standalone mode without browser UI
- **Automatic Updates**: Service worker handles app updates seamlessly

### Offline Functionality
- **Offline Support**: App works offline with cached data
- **Smart Caching**: Static files and API responses are cached for offline use
- **Offline Page**: Custom offline page when no cached content is available
- **Background Sync**: Data updates automatically when connection is restored

### Performance
- **Fast Loading**: Critical resources are cached for instant loading
- **Network Optimization**: Network-first strategy for API calls with cache fallback
- **Background Updates**: Data refreshes in the background

### User Experience
- **Install Prompt**: Automatic install prompt for eligible users
- **Update Notifications**: Notifies users when new versions are available
- **Responsive Design**: Optimized for all screen sizes and orientations
- **Safe Area Support**: Proper handling of device notches and home indicators

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

# Flask Configuration #
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
- Detailed propogation summary and recommendations
- Weather conditions
- Comprehensive propagation reports
- DXCC entity information with ITU and CQ zones
- Live spots from the PSK Network
- **Persistent SQLite database with automatic data retention**
- **Historical spots data with customizable time ranges**
- **QRZ lookup caching for improved performance**
- **User preferences storage**
- QRZ XML Database API integration with comprehensive callsign information:
  - Basic info (callsign, name, location)
  - License details (class, effective date, expiration)
  - Location data (country, state, county, grid)
  - DXCC and zone information
  - QSL information (manager, LoTW, eQSL)
  - IOTA and other awards
  - Contact information
- Modern, responsive UI with real-time updates

## Database Features

The application now uses SQLite for persistent storage with the following capabilities:

### Data Storage
- **Spots History**: All live spots are automatically stored in the database
- **QRZ Cache**: QRZ lookups are cached to reduce API calls and improve performance
- **User Preferences**: User settings and preferences are stored persistently

### Data Management
- **Automatic Cleanup**: Old data is automatically cleaned up (7 days retention by default)
- **Database Statistics**: View database size and record counts via API
- **Historical Queries**: Query spots data with customizable time ranges

### API Endpoints
- `GET /api/spots/history?hours=24&limit=100` - Get historical spots
- `GET /api/preferences` - Get user preferences
- `POST /api/preferences` - Save user preferences
- `GET /api/database/stats` - Get database statistics

## Project Structure

- `app.py` - Main application entry point
- `ham_radio_conditions.py` - Core functionality for ham radio conditions
- `dxcc_data.py` - DXCC entity information handling
- `qrz_data.py` - QRZ XML Database API integration
- `database.py` - SQLite database management and operations
- `templates/` - HTML templates for the web interface
- `static/` - Static files for PWA functionality
  - `manifest.json` - PWA manifest file
  - `sw.js` - Service worker for offline functionality
  - `offline.html` - Offline page
  - `icons/` - App icons for various sizes
- `data/` - SQLite database files (created automatically)
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Docker Compose configuration

## Data Sources

- HamQSL XML Feed (http://www.hamqsl.com/solarxml.php) for propagation and solar data
- OpenWeatherMap API for weather data
- PSK API https://pskreporter.info/pskmap.html for live spots
- DXCC database for entity information
- QRZ XML Database API (https://xmldata.qrz.com) for callsign lookups
- **SQLite database for persistent local storage**

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
- **Database cleanup: Runs every hour to maintain optimal performance**

## QRZ Integration

The application uses the QRZ XML Database API to provide comprehensive callsign information. The integration includes:

- Authentication using QRZ.com login credentials
- Session management with automatic re-authentication
- **Caching of lookup results in SQLite database for improved performance**
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

## Database Configuration

The SQLite database is automatically created in the `data/` directory and includes:

- **Spots Table**: Stores all live spots with timestamps
- **QRZ Cache Table**: Caches QRZ lookup results
- **User Preferences Table**: Stores user settings
- **Automatic Indexing**: Optimized queries for better performance
- **Data Retention**: Configurable cleanup of old data

## Docker Volume Persistence

When using Docker, the database is stored in a named volume (`ham_radio_data`) to ensure data persistence across container restarts and updates. 
