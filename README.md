# Ham Radio Conditions Reporter

This application fetches real-time ham radio band conditions and environmental data to generate detailed reports. It provides up-to-the-minute information about:

- Solar conditions (SFI, A-index, K-index, X-ray, Sunspots, Flux)
- Band conditions for day and night
- Current weather conditions

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root and add your OpenWeatherMap API key:
```
WEATHER_API_KEY=your_weather_api_key
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
- Hourly updates

## Data Sources

- HamQSL XML Feed (http://www.hamqsl.com/solarxml.php) for propagation and solar data
- OpenWeatherMap API for weather data

## Update Frequency

The application updates the data every hour to respect the HamQSL feed's update frequency. 