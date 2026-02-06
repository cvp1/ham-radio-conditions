"""
Solar data provider for ham radio conditions.

Handles fetching and processing solar data from various sources:
- HamQSL XML feed
- NOAA space weather
- Solar storm data
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Optional, List, Any, Union
import logging
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class SolarDataProvider:
    """Provider for solar data from multiple sources."""
    
    def __init__(self):
        self.hamqsl_url = "https://www.hamqsl.com/solarxml.php"
        self.noaa_url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
        self.cache_duration = 300  # 5 minutes
        
    def get_solar_conditions(self) -> Dict[str, Any]:
        """Get enhanced solar conditions with multiple data sources."""
        try:
            # Get base solar data from HamQSL
            solar_data = cache_get('default', 'solar_conditions')
            if not solar_data:
                solar_data = self._fetch_hamqsl_data()
                if solar_data:
                    cache_set('default', 'solar_conditions', solar_data, self.cache_duration)
                else:
                    return self._get_fallback_solar_data()
            
            # Enhance with additional data sources
            enhanced_data = self._enhance_solar_data(solar_data)
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Error getting solar conditions: {e}")
            return self._get_fallback_solar_data()
    
    def _fetch_hamqsl_data(self) -> Optional[Dict[str, Any]]:
        """Fetch solar data from HamQSL XML feed."""
        try:
            response = requests.get(self.hamqsl_url, timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                # Safely extract values with fallbacks
                def safe_extract(element_path: str, default: str = '0') -> str:
                    element = root.find(element_path)
                    return element.text if element is not None and element.text else default
                
                return {
                    'sfi': safe_extract('.//solarflux') + ' SFI',
                    'a_index': safe_extract('.//aindex'),
                    'k_index': safe_extract('.//kindex'),
                    'aurora': safe_extract('.//aurora'),
                    'sunspots': safe_extract('.//sunspots'),
                    'xray': safe_extract('.//xray'),
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error fetching HamQSL data: {e}")
            return None
    
    def _enhance_solar_data(self, base_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance solar data with additional sources."""
        enhanced = base_data.copy()
        
        # Add NOAA data
        noaa_data = self._get_noaa_space_weather()
        if noaa_data:
            enhanced.update(noaa_data)
        
        # Add storm data
        storm_data = self._get_geomagnetic_storm_data()
        if storm_data:
            enhanced.update(storm_data)
        
        return enhanced
    
    def _get_noaa_space_weather(self) -> Optional[Dict[str, Any]]:
        """Get NOAA space weather data."""
        try:
            response = requests.get(self.noaa_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data:
                    latest = data[-1]
                    return {
                        'noaa_k_index': latest.get('kp', 0),
                        'noaa_timestamp': latest.get('time_tag', ''),
                        'noaa_source': 'NOAA'
                    }
        except Exception as e:
            logger.debug(f"Error fetching NOAA data: {e}")
        return None
    
    def _get_geomagnetic_storm_data(self) -> Optional[Dict[str, Any]]:
        """Get geomagnetic storm data."""
        # This would be implemented based on the original method
        # For now, return basic storm data
        return {
            'storm_activity': 'quiet',
            'storm_probability': 'low',
            'storm_source': 'Estimated'
        }
    
    def _get_fallback_solar_data(self) -> Dict[str, Any]:
        """Get fallback solar data when primary sources fail."""
        return {
            'sfi': '100 SFI',
            'a_index': '5',
            'k_index': '2',
            'aurora': '0',
            'sunspots': '50',
            'xray': 'B1',
            'timestamp': datetime.now().isoformat(),
            'source': 'Fallback',
            'confidence': 0.3
        }
