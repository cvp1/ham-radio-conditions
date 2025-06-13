# Ham Radio Conditions Reporter

This application fetches real-time ham radio band conditions and environmental data to generate detailed reports. It provides up-to-the-minute information about:

- Solar conditions (SFI, A-index, K-index, X-ray, Sunspots, Flux)
- Band conditions for day and night
- Current weather conditions
- DXCC entity information and conditions
- Live spots from the IARC network

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root and add your OpenWeatherMap API key and Maidenhead grid square:
```
WEATHER_API_KEY=your_weather_api_key
GRID_SQUARE=your_grid_square  # e.g., DM41vv
```

3. Run the application:
```bash
python ham_radio_conditions.py
```

## Features

- Real-time solar and geomagnetic data from HamQSL
- Detailed band condition forecasts for day and night
- Weather conditions
- Comprehensive propagation reports
- DXCC entity information with ITU and CQ zones
- Live spots from the IARC network
- Modern, responsive UI with real-time updates
- Hourly updates for propagation data
- 5-minute updates for live spots

## Data Sources

- HamQSL XML Feed (http://www.hamqsl.com/solarxml.php) for propagation and solar data
- OpenWeatherMap API for weather data
- IARC API (https://holycluster.iarc.org) for live spots
- DXCC database for entity information

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

## Update Frequency

- Propagation data: Updates every hour to respect the HamQSL feed's update frequency
- Live spots: Updates every 5 minutes
- Weather data: Updates on each request 