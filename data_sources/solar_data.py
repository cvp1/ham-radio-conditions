"""
Solar data provider for ham radio conditions.

Handles fetching and processing solar data from various sources:
- HamQSL XML feed
- NOAA space weather
- Solar storm data
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
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

        # Add solar flare data
        flare_data = self._get_solar_flare_data()
        if flare_data:
            enhanced.update(flare_data)

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
        """Get geomagnetic storm data from NOAA SWPC K-index forecast."""
        try:
            response = requests.get(
                "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json",
                timeout=8
            )
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 1:
                    # First row is header, get the most recent entry
                    latest = data[-1]
                    kp = float(latest[1])

                    # Classify storm level
                    if kp >= 8:
                        storm_level = 'Severe Storm (G4+)'
                    elif kp == 7:
                        storm_level = 'Strong Storm (G3)'
                    elif kp == 6:
                        storm_level = 'Moderate Storm (G2)'
                    elif kp == 5:
                        storm_level = 'Minor Storm (G1)'
                    elif kp == 4:
                        storm_level = 'Active'
                    else:
                        storm_level = 'Quiet'

                    # Determine storm probability
                    if kp >= 5:
                        probability = 'high'
                    elif kp >= 4:
                        probability = 'moderate'
                    else:
                        probability = 'low'

                    # Try to fetch active alert count (only last 24 hours)
                    storm_alerts = 0
                    try:
                        alerts_resp = requests.get(
                            "https://services.swpc.noaa.gov/products/alerts.json",
                            timeout=8
                        )
                        if alerts_resp.status_code == 200:
                            alerts_data = alerts_resp.json()
                            # Only count alerts from the last 24 hours
                            cutoff = datetime.now() - timedelta(hours=24)
                            for alert in alerts_data:
                                try:
                                    issue_time = alert.get('issue_datetime', '')
                                    if issue_time:
                                        alert_dt = datetime.fromisoformat(issue_time.replace('Z', '+00:00')).replace(tzinfo=None)
                                        if alert_dt >= cutoff:
                                            storm_alerts += 1
                                except (ValueError, TypeError):
                                    pass
                    except Exception:
                        storm_alerts = 0

                    return {
                        'storm_activity': storm_level,
                        'storm_kp': kp,
                        'storm_probability': probability,
                        'storm_alerts': storm_alerts,
                        'storm_source': 'NOAA SWPC'
                    }
        except Exception as e:
            logger.debug(f"Error fetching geomagnetic storm data: {e}")

        return {
            'storm_activity': 'quiet',
            'storm_probability': 'low',
            'storm_source': 'Estimated'
        }
    
    def _get_solar_flare_data(self) -> Optional[Dict[str, Any]]:
        """Get recent solar flare data from NASA DONKI API."""
        try:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            url = f"https://api.nasa.gov/DONKI/FLR?startDate={start_date}&api_key=DEMO_KEY"
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    latest = data[-1]
                    return {
                        'latest_flare_class': latest.get('classType', 'None'),
                        'latest_flare_time': latest.get('beginTime', 'N/A'),
                        'latest_flare_region': latest.get('sourceLocation', 'N/A'),
                        'flare_count_7d': len(data),
                        'flare_source': 'NASA DONKI'
                    }
                else:
                    return {
                        'latest_flare_class': 'None',
                        'latest_flare_time': 'N/A',
                        'latest_flare_region': 'N/A',
                        'flare_count_7d': 0,
                        'flare_source': 'NASA DONKI'
                    }
        except Exception as e:
            logger.debug(f"Error fetching solar flare data: {e}")
        return None

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
