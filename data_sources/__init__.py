"""
Data sources module for ham radio conditions.

This module contains classes for fetching data from various sources:
- Solar data (HamQSL, NOAA)
- Weather data
- Spot data (PSKReporter, RBN, WSPRNet)
- Geomagnetic data
"""

from .solar_data import SolarDataProvider
from .weather_data import WeatherDataProvider
from .spots_data import SpotsDataProvider
from .geomagnetic_data import GeomagneticDataProvider

__all__ = [
    'SolarDataProvider',
    'WeatherDataProvider', 
    'SpotsDataProvider',
    'GeomagneticDataProvider'
]
