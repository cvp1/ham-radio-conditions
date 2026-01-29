"""
Weather data provider for ham radio conditions.

Handles fetching and processing weather data for propagation analysis.
"""

import os
import requests
from datetime import datetime
from typing import Dict, Optional, Any
import logging
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class WeatherDataProvider:
    """Provider for weather data from OpenWeatherMap API."""

    def __init__(self, lat: float, lon: float, api_key: Optional[str] = None, temp_unit: str = 'F'):
        self.lat = lat
        self.lon = lon
        self.api_key = api_key or os.getenv('OPENWEATHER_API_KEY')
        self.temp_unit = temp_unit or os.getenv('TEMP_UNIT', 'F')
        self.cache_duration = 1800  # 30 minutes
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def get_weather_conditions(self) -> Dict:
        """Get weather conditions with caching."""
        try:
            # Try to get from cache first
            cached_weather = cache_get('weather', f'conditions_{self.lat}_{self.lon}')
            if cached_weather:
                return cached_weather

            # Fetch new weather data
            weather_data = self._fetch_weather_data()
            if weather_data:
                cache_set('weather', f'conditions_{self.lat}_{self.lon}', weather_data, self.cache_duration)
                return weather_data
            else:
                return self._get_fallback_weather_data()

        except Exception as e:
            logger.error(f"Error getting weather conditions: {e}")
            return self._get_fallback_weather_data()

    def _fetch_weather_data(self) -> Optional[Dict]:
        """Fetch weather data from OpenWeatherMap API."""
        if not self.api_key:
            logger.warning("No OpenWeatherMap API key configured")
            return None

        try:
            # Use metric units from API, convert to Fahrenheit if needed
            params = {
                'lat': self.lat,
                'lon': self.lon,
                'appid': self.api_key,
                'units': 'metric'  # Get Celsius from API
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract and format weather data
            main = data.get('main', {})
            wind = data.get('wind', {})
            clouds = data.get('clouds', {})
            weather = data.get('weather', [{}])[0]

            # Temperature conversion if needed
            temp_celsius = main.get('temp', 20.0)
            if self.temp_unit.upper() == 'F':
                temperature = (temp_celsius * 9/5) + 32
            else:
                temperature = temp_celsius

            # Visibility is in meters, convert to km
            visibility_m = data.get('visibility', 10000)
            visibility_km = visibility_m / 1000

            # Extract location info
            city_name = data.get('name', 'Unknown')
            country_code = data.get('sys', {}).get('country', '')

            return {
                'temperature': round(temperature, 1),
                'temp_unit': self.temp_unit.upper(),
                'humidity': main.get('humidity', 50),
                'pressure': main.get('pressure', 1013.25),
                'wind_speed': round(wind.get('speed', 0) * 2.237, 1),  # m/s to mph
                'wind_direction': wind.get('deg', 0),
                'visibility': round(visibility_km, 1),
                'cloud_cover': clouds.get('all', 0),
                'condition': weather.get('main', 'Unknown'),
                'description': weather.get('description', ''),
                'icon': weather.get('icon', ''),
                'city': city_name,
                'state': country_code,  # OpenWeatherMap returns country code
                'location': city_name,  # Keep for backwards compatibility
                'timestamp': datetime.now().isoformat(),
                'source': 'OpenWeatherMap',
                'sunrise': datetime.fromtimestamp(data.get('sys', {}).get('sunrise', 0)).isoformat() if data.get('sys', {}).get('sunrise') else None,
                'sunset': datetime.fromtimestamp(data.get('sys', {}).get('sunset', 0)).isoformat() if data.get('sys', {}).get('sunset') else None
            }

        except requests.exceptions.Timeout:
            logger.error("OpenWeatherMap API request timed out")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"OpenWeatherMap API HTTP error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeatherMap API request error: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing OpenWeatherMap response: {e}")
            return None
    
    def _get_fallback_weather_data(self) -> Dict:
        """Get fallback weather data when primary sources fail."""
        return {
            'temperature': 72.0 if self.temp_unit.upper() == 'F' else 22.0,
            'temp_unit': self.temp_unit.upper(),
            'humidity': 50,
            'pressure': 1013.25,
            'wind_speed': 5.0,
            'wind_direction': 0,
            'visibility': 10.0,
            'cloud_cover': 0,
            'condition': 'Unknown',
            'description': 'Weather data unavailable',
            'city': 'Unknown',
            'state': '',
            'location': 'Unknown',
            'timestamp': datetime.now().isoformat(),
            'source': 'Fallback',
            'confidence': 0.3
        }

    def check_status(self) -> Dict[str, Any]:
        """Check status of weather data sources."""
        status = {
            'status': 'online',
            'sources': {}
        }

        if not self.api_key:
            status['status'] = 'error'
            status['sources']['openweathermap'] = {
                'status': 'error',
                'error': 'API key not configured'
            }
            return status

        # Check OpenWeatherMap API
        try:
            params = {
                'lat': self.lat,
                'lon': self.lon,
                'appid': self.api_key,
                'units': 'metric'
            }
            response = requests.get(self.base_url, params=params, timeout=5)
            status['sources']['openweathermap'] = {
                'status': 'online' if response.status_code == 200 else 'error',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            status['status'] = 'error'
            status['sources']['openweathermap'] = {
                'status': 'offline',
                'error': str(e)
            }

        return status
