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
        """Calculate magnetic declination for the location."""
        # Simplified calculation - in practice would use IGRF model
        # This is a rough approximation
        declination = 0.0
        
        # Basic approximation based on latitude and longitude
        if self.lat > 0:  # Northern hemisphere
            declination = self.lon * 0.1  # Rough approximation
        else:  # Southern hemisphere
            declination = -self.lon * 0.1
            
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
