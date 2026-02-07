"""
Weather data provider for ham radio conditions.

Handles fetching and processing weather data for propagation analysis.
"""

import requests
import os
from datetime import datetime
from typing import Dict, Optional, Tuple
import logging
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class WeatherDataProvider:
    """Provider for weather data."""
    
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        self.cache_duration = 1800  # 30 minutes
        
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
        """Fetch weather data from OpenWeather API."""
        api_key = os.environ.get('OPENWEATHER_API_KEY')
        if not api_key:
            logger.warning("OPENWEATHER_API_KEY not set, skipping weather fetch")
            return None

        temp_unit = os.environ.get('TEMP_UNIT', 'F')
        units = 'imperial' if temp_unit == 'F' else 'metric'

        try:
            response = requests.get(
                'https://api.openweathermap.org/data/2.5/weather',
                params={
                    'lat': self.lat,
                    'lon': self.lon,
                    'appid': api_key,
                    'units': units,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            return {
                'temperature': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'wind_direction': data['wind'].get('deg', 0),
                'visibility': data.get('visibility', 10000) / 1000,
                'cloud_cover': data['clouds']['all'],
                'conditions': data['weather'][0]['description'],
                'icon': data['weather'][0]['icon'],
                'temp_unit': 'F' if temp_unit == 'F' else 'C',
                'timestamp': datetime.now().isoformat(),
                'source': 'OpenWeather',
            }
        except Exception as e:
            logger.error(f"Error fetching weather data from OpenWeather: {e}")
            return None
    
    def _get_fallback_weather_data(self) -> Dict:
        """Get fallback weather data when primary sources fail."""
        return {
            'temperature': 20.0,
            'humidity': 50.0,
            'pressure': 1013.25,
            'wind_speed': 5.0,
            'wind_direction': 0,
            'visibility': 10.0,
            'cloud_cover': 0.0,
            'timestamp': datetime.now().isoformat(),
            'source': 'Fallback',
            'confidence': 0.3
        }
