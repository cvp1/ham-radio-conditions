# Ham Radio Conditions Reporter

This application fetches real-time ham radio band conditions and environmental data to generate detailed reports. It provides up-to-the-minute information about:

- Solar conditions (SFI, A-index, K-index, X-ray, Sunspots, Flux)
- Band conditions for day and night
- Current weather conditions
- Detailed propogation report
- DXCC entity information and conditions
- Live spots from the PSK Network
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

# Flask Configuration
FLASK_APP=wsgi_dev.py
FLASK_ENV=development
```

3. Run the application:
```bash
python app.py
# or
python wsgi_dev.py
```

### Option 2: Docker Setup

1. Create a `.env` file with your configuration:
```bash
# Use the automated setup script
python create_env_template.py

# Or create manually with at least these required variables:
OPENWEATHER_API_KEY=your_weather_api_key
ZIP_CODE=your_zip_code
```

2. Build and run using Docker Compose:
```bash
# For newer Docker versions (recommended)
docker compose up --build

# For older Docker versions
docker-compose up --build
```

**Note:** Newer Docker versions use `docker compose` (with space), while older versions use `docker-compose` (with hyphen). The `test_docker.py` script will automatically detect which command to use.

**Required Environment Variables:**
- `OPENWEATHER_API_KEY` - Get from [OpenWeatherMap](https://openweathermap.org/api)
- `ZIP_CODE` - Your location for weather and propagation data

**Optional Environment Variables:**
- `QRZ_USERNAME` & `QRZ_PASSWORD` - For QRZ lookup functionality
- `CALLSIGN` - Your ham radio callsign
- `TEMP_UNIT` - Temperature unit (F or C)

The application will be available at http://localhost:8087

### Option 3: Automated Development Setup

1. Run the automated setup script:
```bash
python setup_dev.py
```

This will:
- Check Python version compatibility
- Create necessary directories
- Create a `.env` file with template values
- Install dependencies
- Run basic tests

## Features

- **Real-time propagation conditions** with solar flux, A-index, K-index, and MUF calculations
- **Live ham radio spots** from PSKReporter and Reverse Beacon Network
- **Weather integration** with current conditions and forecasts
- **DXCC information** with current location and nearby entities
- **Operating recommendations** based on current conditions
- **PWA support** for mobile and desktop installation
- **Caching system** for improved performance
- **Background task management** for data updates

## Database Features

- **Persistent SQLite database** for storing spots and user preferences
- **Automatic data retention** with configurable cleanup intervals
- **Historical spots data** with customizable time ranges
- **User preferences storage** for personalized settings

## Project Structure

```
ham-radio-conditions/
├── app.py                     # Main application entry point (development)
├── wsgi.py                    # WSGI entry point for production
├── wsgi_dev.py                # WSGI entry point for development
├── app_factory.py            # Application factory for creating Flask app
├── config.py                 # Configuration management
├── ham_radio_conditions.py  # Main propagation conditions logic
├── dxcc_data.py            # DXCC entity data and calculations
├── database.py             # Database operations and management
├── utils/
│   ├── background_tasks.py # Background task management
│   ├── cache_manager.py    # Caching system
│   └── logging_config.py   # Logging configuration
├── routes/
│   ├── api.py             # REST API endpoints
│   └── pwa.py             # PWA service worker routes
├── templates/
│   └── index.html         # Main application interface
└── static/
    ├── manifest.json      # PWA manifest
    ├── sw.js             # Service worker
    └── icons/            # PWA icons
```

## Data Sources

- HamQSL XML Feed (http://www.hamqsl.com/solarxml.php) for propagation and solar data
- OpenWeatherMap API for weather data
- PSK API https://pskreporter.info/pskmap.html for live spots
- DXCC database for entity information
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

## Update Frequency

- Propagation data: Updates every hour to respect the HamQSL feed's update frequency
- Live spots: Updates every 5 minutes
- Weather data: Updates on each request
- **Database cleanup: Runs every hour to maintain optimal performance**

## Database Configuration

The SQLite database is automatically created in the `data/` directory and includes:

- **Spots Table**: Stores all live spots with timestamps
- **User Preferences Table**: Stores user settings
- **Automatic Indexing**: Optimized queries for better performance
- **Data Retention**: Configurable cleanup of old data

## Docker Volume Persistence

When using Docker, the database is stored in a named volume (`ham_radio_data`) to ensure data persistence across container restarts and updates.

## API Endpoints

- `GET /api/conditions` - Get current propagation conditions
- `GET /api/spots` - Get live spots data
- `GET /api/weather` - Get current weather conditions
- `GET /api/cache/stats` - Get cache statistics
- `POST /api/cache/clear` - Clear specific or all caches 
