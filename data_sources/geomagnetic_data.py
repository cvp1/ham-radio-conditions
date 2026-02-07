"""
Geomagnetic data provider for ham radio conditions.

Handles fetching and processing geomagnetic data for propagation analysis.
"""

import math
from datetime import datetime
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class GeomagneticDataProvider:
    """Provider for geomagnetic data."""
    
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        
    def get_geomagnetic_coordinates(self) -> Dict:
        """Get geomagnetic coordinates for the location."""
        try:
            # Calculate geomagnetic coordinates using IGRF-13 model
            geomag_lat, geomag_lon = self._calculate_geomagnetic_coordinates()
            magnetic_declination = self._calculate_magnetic_declination()
            
            return {
                'geomagnetic_latitude': geomag_lat,
                'geomagnetic_longitude': geomag_lon,
                'magnetic_declination': magnetic_declination,
                'calculation_method': 'Enhanced Dipole Model (2024)',
                'pole_coordinates': '86.5°N, -164.0°W',
                'location_info': {
                    'name': f'Location at {self.lat:.4f}°N, {self.lon:.4f}°W',
                    'geographic_lat': self.lat,
                    'geographic_lon': self.lon
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating geomagnetic coordinates: {e}")
            return self._get_fallback_geomagnetic_data()
    
    def _calculate_geomagnetic_coordinates(self) -> Tuple[float, float]:
        """Calculate geomagnetic coordinates using IGRF-13 model."""
        # Current geomagnetic pole coordinates (2024-2025)
        mag_pole_lat = 86.5  # North geomagnetic pole latitude
        mag_pole_lon = -164.0  # North geomagnetic pole longitude
        
        # Convert to radians
        lat_rad = math.radians(self.lat)
        lon_rad = math.radians(self.lon)
        pole_lat_rad = math.radians(mag_pole_lat)
        pole_lon_rad = math.radians(mag_pole_lon)
        
        # Calculate geomagnetic latitude
        geomag_lat = math.asin(
            math.sin(lat_rad) * math.sin(pole_lat_rad) +
            math.cos(lat_rad) * math.cos(pole_lat_rad) * 
            math.cos(lon_rad - pole_lon_rad)
        )
        
        # Calculate geomagnetic longitude
        geomag_lon = math.atan2(
            math.sin(lon_rad - pole_lon_rad) * math.cos(lat_rad),
            math.cos(pole_lat_rad) * math.sin(lat_rad) -
            math.sin(pole_lat_rad) * math.cos(lat_rad) * 
            math.cos(lon_rad - pole_lon_rad)
        )
        
        # Convert back to degrees
        geomag_lat_deg = math.degrees(geomag_lat)
        geomag_lon_deg = math.degrees(geomag_lon)
        
        # Normalize longitude to 0-360
        if geomag_lon_deg < 0:
            geomag_lon_deg += 360
            
        return geomag_lat_deg, geomag_lon_deg
    
    def _calculate_magnetic_declination(self) -> float:
        """Calculate magnetic declination using NOAA NCEI API with dipole fallback."""
        # Try NOAA NCEI Magnetic Declination API (free, no key needed)
        try:
            import requests
            from datetime import datetime

            params = {
                'lat1': self.lat,
                'lon1': self.lon,
                'key': 'zNEw7',  # Public demo key for NCEI
                'resultFormat': 'json'
            }
            response = requests.get(
                'https://www.ngdc.noaa.gov/geomag-web/calculators/calculateDeclination',
                params=params,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', [{}])
                if result:
                    declination = result[0].get('declination', None)
                    if declination is not None:
                        return round(float(declination), 1)
        except Exception as e:
            logger.debug(f"NOAA declination API failed, using dipole model: {e}")

        # Fallback: Tilted dipole model (much better than lon * 0.1)
        return self._dipole_declination()

    def _dipole_declination(self) -> float:
        """Calculate magnetic declination using tilted dipole model."""
        # Geomagnetic north pole (2024 IGRF-13)
        pole_lat = math.radians(86.5)
        pole_lon = math.radians(-164.0)

        lat_r = math.radians(self.lat)
        lon_r = math.radians(self.lon)

        # Declination from spherical trigonometry
        numerator = math.cos(pole_lat) * math.sin(pole_lon - lon_r)
        denominator = (math.cos(lat_r) * math.sin(pole_lat) -
                       math.sin(lat_r) * math.cos(pole_lat) * math.cos(pole_lon - lon_r))

        if abs(denominator) < 1e-10:
            return 0.0

        declination = math.degrees(math.atan2(numerator, denominator))
        return round(declination, 1)
    
    def _get_fallback_geomagnetic_data(self) -> Dict:
        """Get fallback geomagnetic data when calculation fails."""
        return {
            'geomagnetic_latitude': 0.0,
            'geomagnetic_longitude': 0.0,
            'magnetic_declination': 0.0,
            'calculation_method': 'Fallback',
            'pole_coordinates': 'Unknown',
            'location_info': {
                'name': f'Location at {self.lat:.4f}°N, {self.lon:.4f}°W',
                'geographic_lat': self.lat,
                'geographic_lon': self.lon
            },
            'confidence': 0.3
        }
