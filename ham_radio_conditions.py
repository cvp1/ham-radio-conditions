import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import time
import xml.etree.ElementTree as ET
import math
from dxcc_data import (
    get_dxcc_by_grid,
    get_nearby_dxcc,
    grid_to_latlon
)
from typing import Dict, List, Optional
import pytz
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from utils.cache_manager import cache_get, cache_set, cache_delete
import json
import numpy as np
from collections import defaultdict, deque

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Load environment variables
load_dotenv()

class HamRadioConditions:
    def __init__(self, zip_code=None):
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        self.callsign = os.getenv('CALLSIGN', 'N/A')
        self.temp_unit = os.getenv('TEMP_UNIT', 'F')
        
        # Initialize with default values
        self.grid_square = 'DM41vv'  # Default to Los Angeles
        self.lat = 34.0522
        self.lon = -118.2437
        self.timezone = pytz.timezone('America/Los_Angeles')
        
        # Initialize thread pool executor for async operations
        self._executor = ThreadPoolExecutor(max_workers=2)
        
        # Historical data storage for trend analysis
        self._historical_data = {
            'solar_conditions': deque(maxlen=168),  # 7 days of hourly data
            'propagation_quality': deque(maxlen=168),
            'band_conditions': deque(maxlen=168),
            'spots_activity': deque(maxlen=168)
        }
        
        # Prediction confidence tracking
        self._prediction_confidence = {
            'solar_trend': 0.5,  # Start with 50% confidence
            'geomagnetic_stability': 0.5,
            'band_conditions': 0.5,
            'overall': 0.5
        }
        
        # Get ZIP code from environment or parameter
        env_zip_code = os.getenv('ZIP_CODE')
        if zip_code:
            target_zip = zip_code
        elif env_zip_code:
            target_zip = env_zip_code
        else:
            target_zip = None
        
        # If ZIP code is provided, try to get coordinates from weather API
        if target_zip and self.openweather_api_key:
            try:
                # Use OpenWeather API to get coordinates for the ZIP code
                url = "http://api.openweathermap.org/geo/1.0/zip"
                params = {
                    'zip': f"{target_zip},US",
                    'appid': self.openweather_api_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.lat = data['lat']
                    self.lon = data['lon']
                    self.grid_square = self.latlon_to_grid(self.lat, self.lon)
                    self.timezone = self._get_timezone_from_coords(self.lat, self.lon)
                    logger.info(f"Location set to ZIP {target_zip}: lat={self.lat}, lon={self.lon}, grid={self.grid_square}")
                else:
                    logger.warning(f"Could not get coordinates for ZIP {target_zip}, using defaults")
            except Exception as e:
                logger.error(f"Error getting coordinates for ZIP {target_zip}: {e}")
        
        # Start background spots loading
        self._start_background_spots_loading()

    def _start_background_spots_loading(self):
        """Start background thread to load spots without blocking"""
        def background_loader():
            """Background thread to continuously load spots"""
            while True:
                try:
                    self._load_spots_async()
                    time.sleep(600)  # Update every 10 minutes (production optimized)
                except Exception as e:
                    logger.error(f"Error in background spots loader: {e}")
                    time.sleep(120)  # Wait 2 minutes on error
        
        thread = threading.Thread(target=background_loader, daemon=True)
        thread.start()
        logger.info("Background spots loader started")

    def _load_spots_async(self):
        """Load spots asynchronously with timeout"""
        try:
            future = self._executor.submit(self._get_spots_with_timeout)
            spots = future.result(timeout=30)  # 30 second max
            
            if spots and spots.get('summary', {}).get('total_spots', 0) > 0:
                # Cache the spots data with production-optimized duration
                cache_set('spots', 'current', spots, max_age=300)  # 5 minutes
                logger.info(f"Loaded {spots['summary']['total_spots']} spots from {spots['summary']['source']}")
                
        except FuturesTimeoutError:
            logger.warning("Spots loading timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Error loading spots async: {e}")

    def _get_spots_with_timeout(self):
        """Get spots with timeout handling"""
        try:
            # Try PSKReporter first (fast)
            spots = self._get_pskreporter_spots_fast()
            if spots and spots.get('summary', {}).get('total_spots', 0) > 0:
                return spots
            
            # Fallback to test spots
            return self._get_test_spots()
            
        except Exception as e:
            logger.error(f"Error getting spots: {e}")
            return self._get_test_spots()

    def get_live_activity(self):
        """Get live activity data with caching."""
        # Try to get from cache first
        cached_spots = cache_get('spots', 'current')
        if cached_spots:
            return cached_spots
        
        # Get fresh spots data
        try:
            spots = self._get_spots_with_timeout()
            if spots:
                cache_set('spots', 'current', spots, max_age=300)  # 5 minutes
            return spots
        except Exception as e:
            logger.error(f"Error getting live activity: {e}")
            return None

    def get_live_activity_simple(self):
        """Get simplified live activity data."""
        spots = self.get_live_activity()
        if not spots:
            return None
        
        # Return simplified format
        return {
            'spots': spots.get('spots', [])[:10],  # Limit to 10 spots
            'summary': spots.get('summary', {}),
            'timestamp': datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
        }

    def generate_report(self):
        """Generate complete conditions report with caching."""
        # Try to get from cache first
        cached_report = cache_get('conditions', 'current')
        if cached_report:
            logger.debug("Returning cached conditions report")
            # Update the timestamp to current time even for cached data
            cached_report['timestamp'] = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
            return cached_report
        
        # Generate new report
        try:
            logger.debug("Generating new conditions report")
            report = {
                'timestamp': datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z'),
                'callsign': self.callsign,  # Add callsign to the report
                'solar_conditions': self.get_solar_conditions(),
                'weather_conditions': self.get_weather_conditions(),
                'band_conditions': self.get_band_conditions(),
                'dxcc_conditions': self.get_dxcc_conditions(self.grid_square),
                'propagation_summary': self.get_propagation_summary(),
                'live_activity': self.get_live_activity_simple()
            }
            
            # Cache the report with production-optimized duration
            cache_set('conditions', 'current', report, max_age=600)  # 10 minutes
            logger.info("Generated and cached new conditions report")
            
            return report
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None

    def get_weather_conditions(self):
        """Get weather conditions with caching."""
        # Try to get from cache first
        cached_weather = cache_get('weather', 'current')
        if cached_weather:
            return cached_weather
        
        # Get fresh weather data
        try:
            weather = self._get_weather_data()
            if weather:
                cache_set('weather', 'current', weather, max_age=900)  # 15 minutes
            return weather
        except Exception as e:
            logger.error(f"Error getting weather conditions: {e}")
            return None

    def _get_weather_data(self):
        """Get weather data from OpenWeather API."""
        if not self.openweather_api_key:
            return None
        
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': self.lat,
                'lon': self.lon,
                'appid': self.openweather_api_key,
                'units': 'imperial' if self.temp_unit == 'F' else 'metric'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Extract city and state from location name
                location_name = data.get('name', 'Unknown')
                city = location_name
                state = data.get('sys', {}).get('country', '')
                
                return {
                    'temperature': f"{data['main']['temp']:.1f}°{'F' if self.temp_unit == 'F' else 'C'}",
                    'humidity': f"{data['main']['humidity']}%",
                    'pressure': f"{data['main']['pressure']} hPa",
                    'description': data['weather'][0]['description'].title(),
                    'wind_speed': f"{data['wind']['speed']} {'mph' if self.temp_unit == 'F' else 'm/s'}",
                    'wind_direction': f"{data['wind'].get('deg', 0)}°",
                    'visibility': f"{data.get('visibility', 10000) / 1000:.1f} km",
                    'city': city,
                    'state': state,
                    'location': location_name,
                    'source': 'OpenWeather'
                }
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
        
        return None

    def clear_cache(self, cache_type=None):
        """Clear specific or all caches."""
        if cache_type:
            cache_delete(cache_type, 'current')
            logger.info(f"Cleared {cache_type} cache")
        else:
            # Clear all caches
            cache_delete('conditions', 'current')
            cache_delete('spots', 'current')
            cache_delete('weather', 'current')
            logger.info("Cleared all caches")

    def _get_pskreporter_spots_fast(self):
        """Fast PSKReporter spots with aggressive timeout"""
        try:
            url = "https://retrieve.pskreporter.info/query"
            params = {
                'since': '30',  # Last 30 minutes
                'limit': '20'   # Get 20 spots
            }
            headers = {
                'User-Agent': 'HamRadioConditions/1.0',
                'Accept': 'application/xml',
                'Connection': 'close'
            }
            
            # Use shorter timeout since we're in a background thread
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code != 200:
                return None
            
            # Parse XML response
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                return None
            
            # Find all receptionReport elements
            spots = []
            for report in root.findall('.//receptionReport')[:15]:  # Process fewer items for speed
                try:
                    # Extract data from XML attributes
                    raw_freq = report.get('frequency', 0)
                    
                    # Handle different frequency formats
                    try:
                        if isinstance(raw_freq, str):
                            # Remove any non-numeric characters except decimal point
                            raw_freq = ''.join(c for c in raw_freq if c.isdigit() or c == '.')
                        freq_hz = float(raw_freq)
                        freq_mhz = freq_hz / 1000000  # Convert Hz to MHz
                    except (ValueError, TypeError):
                        freq_hz = 0
                        freq_mhz = 0
                    
                    spot = {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # PSKReporter doesn't provide timestamp
                        'callsign': report.get('senderCallsign', ''),
                        'frequency': f"{freq_mhz:.6f}".rstrip('0').rstrip('.') if freq_mhz > 0 else '0',
                        'spotter': report.get('receiverCallsign', ''),
                        'comment': f"SNR: {report.get('sNR', 'N/A')}",
                        'mode': report.get('mode', 'Unknown'),
                        'dxcc': report.get('senderDXCC', ''),
                        'source': 'PSKReporter'
                    }
                    spots.append(spot)
                except Exception:
                    continue
            
            # Generate summary
            modes = set(s['mode'] for s in spots if s['mode'] != 'Unknown')
            dxcc_entities = set(s['dxcc'] for s in spots if s['dxcc'])
            return {
                'spots': spots,
                'summary': {
                    'total_spots': len(spots),
                    'active_modes': sorted(list(modes)),
                    'active_dxcc': sorted(list(dxcc_entities))[:10],
                    'source': 'PSKReporter'
                }
            }
            
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 503:
                    logger.info("PSKReporter service temporarily unavailable (503) - using fallback data")
                elif e.response.status_code == 429:
                    logger.info("PSKReporter rate limit exceeded (429) - using fallback data")
                else:
                    logger.info(f"PSKReporter HTTP error {e.response.status_code} - using fallback data")
            return None
        except Exception:
            return None

    def _get_test_spots(self):
        """Return test spots when real sources fail"""
        logger.info("Using test spots")
        
        # Generate some test spots
        test_spots = []
        test_callsigns = ['W1AW', 'K1ABC', 'N2XYZ', 'W3DEF', 'K4GHI']
        test_modes = ['FT8', 'CW', 'SSB', 'RTTY', 'PSK31']
        test_frequencies = ['7.074', '14.074', '21.074', '28.074', '3.574']
        
        for i in range(5):
            spot = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'callsign': test_callsigns[i],
                'frequency': test_frequencies[i],
                'mode': test_modes[i],
                'spotter': 'TEST',
                'comment': 'Test spot',
                'dxcc': 'USA',
                'source': 'Test'
            }
            test_spots.append(spot)
        
        return {
            'spots': test_spots,
            'summary': {
                'total_spots': len(test_spots),
                'active_modes': test_modes,
                'active_dxcc': ['USA'],
                'source': 'Test'
            }
        }

    def get_solar_conditions(self):
        """Get enhanced solar conditions with multiple data sources and trend analysis."""
        try:
            # Get base solar data from HamQSL
            solar_data = cache_get('default', 'solar_conditions')
            if not solar_data:
                # Fetch from HamQSL
                url = "https://www.hamqsl.com/solarxml.php"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    solar_data = {
                        'sfi': root.find('.//solarflux').text + ' SFI',
                        'a_index': root.find('.//aindex').text,
                        'k_index': root.find('.//kindex').text,
                        'aurora': root.find('.//aurora').text,
                        'sunspots': root.find('.//sunspots').text,
                        'xray': root.find('.//xray').text,
                        'timestamp': datetime.now().isoformat()
                    }
                    cache_set('default', 'solar_conditions', solar_data, 300)  # Cache for 5 minutes
                else:
                    return self._get_fallback_solar_data()
            
            # Enhance with additional data sources
            enhanced_data = self._enhance_solar_data(solar_data)
            
            # Store historical data for trend analysis
            self._historical_data['solar_conditions'].append(enhanced_data)
            
            # Update prediction confidence
            self._update_solar_confidence(enhanced_data)
            
            # Ensure confidence values are at least 0.3
            self._prediction_confidence['solar_trend'] = max(self._prediction_confidence['solar_trend'], 0.3)
            self._prediction_confidence['overall'] = max(self._prediction_confidence['overall'], 0.3)
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Error getting solar conditions: {e}")
            return self._get_fallback_solar_data()

    def _enhance_solar_data(self, base_data):
        """Enhance solar data with additional sources and analysis."""
        try:
            enhanced = base_data.copy()
            
            # Get additional data from NOAA Space Weather API (non-blocking)
            try:
                noaa_data = self._get_noaa_space_weather()
                if noaa_data:
                    enhanced.update(noaa_data)
            except Exception as e:
                logger.error(f"Error getting NOAA data: {e}")
            
            # Get geomagnetic storm data (non-blocking)
            try:
                storm_data = self._get_geomagnetic_storm_data()
                if storm_data:
                    enhanced.update(storm_data)
            except Exception as e:
                logger.error(f"Error getting storm data: {e}")
            
            # Add prediction confidence
            enhanced['prediction_confidence'] = self._prediction_confidence['solar_trend']
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Error enhancing solar data: {e}")
            return base_data

    def _get_noaa_space_weather(self):
        """Get additional space weather data from NOAA."""
        try:
            # NOAA Space Weather API endpoint
            url = "https://services.swpc.noaa.gov/json/solar_activity.json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'noaa_sfi': data.get('solar_flux', 'N/A'),
                    'noaa_a_index': data.get('a_index', 'N/A'),
                    'noaa_k_index': data.get('k_index', 'N/A'),
                    'geomagnetic_storm': data.get('geomagnetic_storm', 'None')
                }
        except Exception as e:
            logger.error(f"Error getting NOAA data: {e}")
        return None

    def _get_geomagnetic_storm_data(self):
        """Get geomagnetic storm information."""
        try:
            # Get K-index from current data without recursion
            k_index_str = self._get_current_k_index()
            k_index = self._safe_float_conversion(k_index_str)
            
            storm_level = 'None'
            if k_index >= 8:
                storm_level = 'Severe'
            elif k_index >= 6:
                storm_level = 'Strong'
            elif k_index >= 4:
                storm_level = 'Moderate'
            elif k_index >= 2:
                storm_level = 'Minor'
            
            return {
                'storm_level': storm_level,
                'storm_probability': self._calculate_storm_probability(k_index)
            }
        except Exception as e:
            logger.error(f"Error getting storm data: {e}")
            return None

    def _calculate_solar_trends(self):
        """Calculate solar activity trends from historical data."""
        try:
            if len(self._historical_data['solar_conditions']) < 2:
                return {'trend': 'Unknown', 'confidence': 0.0}
            
            # Get recent SFI values
            recent_data = list(self._historical_data['solar_conditions'])[-24:]  # Last 24 hours
            sfi_values = []
            
            for data in recent_data:
                sfi_str = data.get('sfi', '0 SFI')
                try:
                    sfi = float(sfi_str.replace(' SFI', ''))
                    sfi_values.append(sfi)
                except:
                    continue
            
            if len(sfi_values) < 2:
                return {'trend': 'Unknown', 'confidence': 0.0}
            
            # Calculate trend
            if len(sfi_values) >= 3:
                # Use linear regression for trend
                x = np.arange(len(sfi_values))
                y = np.array(sfi_values)
                slope = np.polyfit(x, y, 1)[0]
                
                if slope > 2:
                    trend = 'Rising'
                    confidence = min(abs(slope) / 10.0, 1.0)
                elif slope < -2:
                    trend = 'Falling'
                    confidence = min(abs(slope) / 10.0, 1.0)
                else:
                    trend = 'Stable'
                    confidence = 0.8
            else:
                # Simple comparison
                if sfi_values[-1] > sfi_values[0] + 5:
                    trend = 'Rising'
                    confidence = 0.6
                elif sfi_values[-1] < sfi_values[0] - 5:
                    trend = 'Falling'
                    confidence = 0.6
                else:
                    trend = 'Stable'
                    confidence = 0.7
            
            return {
                'trend': trend,
                'confidence': confidence,
                'change_24h': sfi_values[-1] - sfi_values[0] if len(sfi_values) > 1 else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating solar trends: {e}")
            return {'trend': 'Unknown', 'confidence': 0.0}

    def _update_solar_confidence(self, solar_data):
        """Update solar prediction confidence based on data quality and consistency."""
        try:
            confidence = 0.0
            
            # Check data completeness
            required_fields = ['sfi', 'a_index', 'k_index']
            completeness = sum(1 for field in required_fields if solar_data.get(field, 'N/A') != 'N/A') / len(required_fields)
            confidence += completeness * 0.3
            
            # Check data consistency
            if 'trends' in solar_data and solar_data['trends'].get('confidence', 0) > 0.5:
                confidence += 0.3
            
            # Check for recent updates
            if 'timestamp' in solar_data:
                try:
                    timestamp = datetime.fromisoformat(solar_data['timestamp'])
                    age_hours = (datetime.now() - timestamp).total_seconds() / 3600
                    if age_hours < 1:
                        confidence += 0.4
                    elif age_hours < 3:
                        confidence += 0.2
                except:
                    pass
            
            # Ensure minimum confidence
            confidence = max(confidence, 0.3)  # Minimum 30% confidence
            
            self._prediction_confidence['solar_trend'] = min(confidence, 1.0)
            
            # Update overall confidence
            self._prediction_confidence['overall'] = min(confidence * 0.8, 1.0)
            
        except Exception as e:
            logger.error(f"Error updating solar confidence: {e}")
            # Set default confidence values
            self._prediction_confidence['solar_trend'] = 0.5
            self._prediction_confidence['overall'] = 0.4

    def _calculate_storm_probability(self, k_index):
        """Calculate probability of geomagnetic storm in next 24 hours."""
        try:
            # Simple probability model based on K-index
            if k_index >= 6:
                return 0.8
            elif k_index >= 4:
                return 0.6
            elif k_index >= 2:
                return 0.3
            else:
                return 0.1
        except Exception as e:
            logger.error(f"Error calculating storm probability: {e}")
            return 0.0

    def _get_current_k_index(self):
        """Get current K-index value from cached solar data or return default."""
        try:
            # Try to get from cache first to avoid recursion
            solar_data = cache_get('default', 'solar_conditions')
            if solar_data and 'k_index' in solar_data:
                return solar_data.get('k_index', '0')
            else:
                # Return default if no cached data
                return '1'
        except Exception as e:
            logger.error(f"Error getting K-index: {e}")
            return '1'

    def _get_fallback_solar_data(self):
        """Return fallback solar data in case of API failures."""
        logger.warning("Using fallback solar data due to API failure.")
        return {
            'sfi': '100 SFI',  # Default reasonable value
            'a_index': '5',  # Default reasonable value
            'k_index': '1',  # Default reasonable value
            'aurora': 'None',
            'sunspots': '50',
            'xray': 'A0.0',
            'trends': {'trend': 'Unknown', 'confidence': 0.0, 'change_24h': 0},
            'prediction_confidence': 0.0
        }

    def _safe_float_conversion(self, value, default=0.0):
        """Safely convert a value to float, handling various formats."""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                # Remove common prefixes and suffixes
                cleaned = value.replace(' SFI', '').replace('A-Index: ', '').replace('K-Index: ', '')
                return float(cleaned)
            else:
                return default
        except (ValueError, TypeError):
            return default

    def _calculate_muf(self, solar_data):
        """Enhanced MUF calculation with multiple factors."""
        try:
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            a_index = self._safe_float_conversion(solar_data.get('a_index', '0'))
            
            # Base MUF calculation using solar flux
            if sfi >= 150:
                base_muf = 35
            elif sfi >= 120:
                base_muf = 28
            elif sfi >= 100:
                base_muf = 22
            elif sfi >= 80:
                base_muf = 18
            elif sfi >= 60:
                base_muf = 14
            else:
                base_muf = 10
            
            # Adjust for geomagnetic activity
            geomagnetic_factor = 1.0
            if k_index > 5:
                geomagnetic_factor = 0.6
            elif k_index > 3:
                geomagnetic_factor = 0.8
            elif k_index > 1:
                geomagnetic_factor = 0.9
            
            # Adjust for A-index
            a_factor = 1.0
            if a_index > 30:
                a_factor = 0.7
            elif a_index > 20:
                a_factor = 0.85
            elif a_index > 10:
                a_factor = 0.95
            
            # Calculate final MUF
            muf = base_muf * geomagnetic_factor * a_factor
            
            # Add confidence level based on data quality
            confidence = 0.8
            if sfi > 0 and k_index > 0 and a_index > 0:
                confidence = 0.9
            elif sfi > 0:
                confidence = 0.7
            
            return round(muf, 1)
            
        except Exception as e:
            logger.error(f"Error calculating MUF: {e}")
            return 15.0  # Default fallback

    def get_band_conditions(self):
        """Fetch band conditions from HamQSL XML feed"""
        try:
            response = requests.get('http://www.hamqsl.com/solarxml.php', timeout=10)
            root = ET.fromstring(response.content)
            
            # Find the band conditions
            bands = {}
            # Define the bands we want to check
            band_list = ['80m-40m', '30m-20m', '17m-15m', '12m-10m']
            
            # Initialize all bands with N/A
            for band_name in band_list:
                bands[band_name] = {'day': 'N/A', 'night': 'N/A'}
            
            # Find all band conditions
            calculated_conditions = root.find('.//calculatedconditions')
            if calculated_conditions is not None:
                for band in calculated_conditions.findall('band'):
                    band_name = band.get('name')
                    time = band.get('time')
                    condition = band.text.strip() if band.text else 'N/A'
                    
                    if band_name in bands and time in ['day', 'night']:
                        bands[band_name][time] = condition
            
            return bands
        except Exception as e:
            print(f"Error fetching band conditions: {e}")
            # Return default band structure with N/A values
            return {
                '80m-40m': {'day': 'N/A', 'night': 'N/A'},
                '30m-20m': {'day': 'N/A', 'night': 'N/A'},
                '17m-15m': {'day': 'N/A', 'night': 'N/A'},
                '12m-10m': {'day': 'N/A', 'night': 'N/A'}
            }

    def get_dxcc_conditions(self, grid_square: str) -> Dict:
        """
        Get DXCC conditions for the current location.
        
        Args:
            grid_square (str): The Maidenhead grid square
            
        Returns:
            dict: DXCC conditions including current entity and nearby entities
        """
        try:
            # Get current DXCC entity
            current_dxcc = get_dxcc_by_grid(grid_square)
            if not current_dxcc:
                # Calculate ITU and CQ zones based on grid square coordinates
                lat, lon = self.grid_to_latlon(grid_square)
                itu_zone = self._calculate_itu_zone(lat, lon)
                cq_zone = self._calculate_cq_zone(lat, lon)
                
                current_dxcc = {
                    'name': 'Unknown',
                    'continent': 'Unknown',
                    'itu_zone': str(itu_zone),
                    'cq_zone': str(cq_zone),
                    'prefixes': [],
                    'timezone': 'UTC'
                }
            else:
                # Calculate ITU and CQ zones based on grid square coordinates
                lat, lon = self.grid_to_latlon(grid_square)
                itu_zone = self._calculate_itu_zone(lat, lon)
                cq_zone = self._calculate_cq_zone(lat, lon)
                
                # Update current DXCC with calculated zones
                current_dxcc['itu_zone'] = str(itu_zone)
                current_dxcc['cq_zone'] = str(cq_zone)
            
            # Get nearby DXCC entities
            nearby_entities = get_nearby_dxcc(grid_square)
            
            return {
                'current': current_dxcc,
                'nearby': nearby_entities
            }
        except Exception as e:
            print(f"Error getting DXCC conditions: {str(e)}")
            return {
                'current': {
                    'name': 'Unknown',
                    'continent': 'Unknown',
                    'itu_zone': 'Unknown',
                    'cq_zone': 'Unknown',
                    'prefixes': [],
                    'timezone': 'UTC'
                },
                'nearby': []
            }

    def _calculate_itu_zone(self, lat: float, lon: float) -> int:
        """
        Calculate ITU zone based on latitude and longitude.
        
        Args:
            lat (float): Latitude in degrees
            lon (float): Longitude in degrees
            
        Returns:
            int: ITU zone number
        """
        # ITU zones are based on longitude, with zone 1 starting at 180°W
        # Each zone is 20° wide
        # Normalize longitude to -180 to 180
        lon = ((lon + 180) % 360) - 180
        # Calculate zone (1-90)
        itu_zone = int((lon + 180) / 20)
        if itu_zone == 0:
            itu_zone = 90
        return max(1, min(itu_zone, 90))  # Ensure zone is between 1 and 90

    def _calculate_cq_zone(self, lat: float, lon: float) -> int:
        """
        Calculate CQ zone based on latitude and longitude.
        
        Args:
            lat (float): Latitude in degrees
            lon (float): Longitude in degrees
            
        Returns:
            int: CQ zone number
        """
        # CQ zones are based on the official CQ zone map
        # Zone 1 starts at 180°W, 0°N
        # Each zone is 10° wide in longitude
        # Zones 1-18 are in the Northern Hemisphere
        # Zones 19-40 are in the Southern Hemisphere
        
        # Normalize longitude to -180 to 180
        lon = ((lon + 180) % 360) - 180
        # Calculate base zone (1-18 for Northern Hemisphere)
        base_zone = int((lon + 180) / 10)
        if base_zone == 0:
            base_zone = 18
        
        # Adjust for Southern Hemisphere
        if lat < 0:
            base_zone += 18
            
        # Ensure zone is between 1 and 40
        return max(1, min(base_zone, 40))

    def _determine_best_bands(self, solar_data, is_daytime):
        """Enhanced band determination with historical analysis and confidence scoring."""
        try:
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            
            # Get HamQSL band conditions for validation
            hamqsl_bands = self.get_band_conditions()
            band_conditions = self._convert_hamqsl_to_individual_bands(hamqsl_bands)
            
            # Enhanced band scoring system
            band_scores = {}
            
            # Define bands with their characteristics
            bands = {
                '160m': {'freq': 1.8, 'day_penalty': 0.3, 'night_bonus': 0.2},
                '80m': {'freq': 3.5, 'day_penalty': 0.2, 'night_bonus': 0.1},
                '40m': {'freq': 7.0, 'day_penalty': 0.1, 'night_bonus': 0.0},
                '30m': {'freq': 10.1, 'day_penalty': 0.0, 'night_bonus': 0.0},
                '20m': {'freq': 14.0, 'day_penalty': 0.0, 'night_bonus': 0.0},
                '17m': {'freq': 18.1, 'day_penalty': 0.0, 'night_bonus': 0.0},
                '15m': {'freq': 21.0, 'day_penalty': 0.0, 'night_bonus': 0.0},
                '12m': {'freq': 24.9, 'day_penalty': 0.0, 'night_bonus': 0.0},
                '10m': {'freq': 28.0, 'day_penalty': 0.0, 'night_bonus': 0.0},
                '6m': {'freq': 50.0, 'day_penalty': 0.0, 'night_bonus': 0.0}
            }
            
            for band_name, band_info in bands.items():
                score = 0
                freq = band_info['freq']
                
                # Base score based on solar flux and frequency
                if sfi >= 150:
                    # High solar flux - all bands good
                    if freq <= 30:
                        score = 90
                    else:
                        score = 85
                elif sfi >= 120:
                    # Good solar flux
                    if freq <= 21:
                        score = 85
                    elif freq <= 30:
                        score = 80
                    else:
                        score = 70
                elif sfi >= 100:
                    # Moderate solar flux
                    if freq <= 14:
                        score = 80
                    elif freq <= 21:
                        score = 75
                    elif freq <= 30:
                        score = 65
                    else:
                        score = 50
                elif sfi >= 80:
                    # Low solar flux
                    if freq <= 10:
                        score = 75
                    elif freq <= 14:
                        score = 70
                    elif freq <= 21:
                        score = 60
                    else:
                        score = 40
                else:
                    # Very low solar flux
                    if freq <= 7:
                        score = 70
                    elif freq <= 10:
                        score = 65
                    elif freq <= 14:
                        score = 55
                    else:
                        score = 30
                
                # Time of day adjustments
                if is_daytime:
                    score *= (1 - band_info['day_penalty'])
                else:
                    score *= (1 + band_info['night_bonus'])
                
                # Geomagnetic activity penalty
                if k_index > 4:
                    # High geomagnetic activity affects higher frequencies more
                    if freq > 14:
                        score *= 0.5
                    elif freq > 7:
                        score *= 0.7
                    else:
                        score *= 0.9
                
                # Cross-reference with HamQSL data if available
                if band_name in band_conditions:
                    hamqsl_rating = band_conditions[band_name]['day_rating'] if is_daytime else band_conditions[band_name]['night_rating']
                    if hamqsl_rating == 'Good':
                        score *= 1.2  # Boost score
                    elif hamqsl_rating == 'Poor':
                        score *= 0.7  # Reduce score
                
                band_scores[band_name] = score
            
            # Sort bands by score and return top performers
            sorted_bands = sorted(band_scores.items(), key=lambda x: x[1], reverse=True)
            best_bands = [band for band, score in sorted_bands if score >= 50]  # Only bands with decent scores
            
            # Store historical data
            self._historical_data['band_conditions'].append({
                'best_bands': best_bands,
                'band_scores': band_scores,
                'timestamp': datetime.now().isoformat()
            })
            
            return best_bands[:5]  # Return top 5 bands
            
        except Exception as e:
            logger.error(f"Error determining best bands: {e}")
            return ['20m', '40m', '80m']  # Default fallback

    def _calculate_propagation_quality(self, solar_data, is_daytime):
        """Calculate enhanced propagation quality with multiple factors and confidence scoring."""
        try:
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            a_index = self._safe_float_conversion(solar_data.get('a_index', '0'))
            
            # Enhanced quality scoring system
            quality_score = 0
            max_score = 100
            
            # Solar flux contribution (40% of total score)
            if sfi >= 150:
                quality_score += 40
            elif sfi >= 120:
                quality_score += 35
            elif sfi >= 100:
                quality_score += 30
            elif sfi >= 80:
                quality_score += 20
            elif sfi >= 60:
                quality_score += 10
            else:
                quality_score += 0
            
            # Geomagnetic activity penalty (30% of total score)
            geomagnetic_score = 30
            if k_index <= 1:
                geomagnetic_score = 30
            elif k_index <= 2:
                geomagnetic_score = 25
            elif k_index <= 3:
                geomagnetic_score = 20
            elif k_index <= 4:
                geomagnetic_score = 15
            elif k_index <= 5:
                geomagnetic_score = 10
            elif k_index <= 6:
                geomagnetic_score = 5
            else:
                geomagnetic_score = 0  # Severe geomagnetic storm
            
            quality_score += geomagnetic_score
            
            # A-index penalty (15% of total score)
            a_index_score = 15
            if a_index <= 10:
                a_index_score = 15
            elif a_index <= 20:
                a_index_score = 10
            elif a_index <= 30:
                a_index_score = 5
            else:
                a_index_score = 0
            
            quality_score += a_index_score
            
            # Time of day adjustment (10% of total score)
            time_score = 10
            if is_daytime:
                # Daytime generally better for HF, but depends on solar activity
                if sfi >= 100:
                    time_score = 10
                elif sfi >= 70:
                    time_score = 8
                else:
                    time_score = 5
            else:
                # Nighttime can be good for lower bands
                if sfi >= 120:
                    time_score = 8
                elif sfi >= 80:
                    time_score = 10
                else:
                    time_score = 7
            
            quality_score += time_score
            
            # Location-specific adjustments (5% of total score)
            location_score = 5
            if abs(self.lat) > 60:
                # High latitude - auroral effects
                if k_index > 3:
                    location_score = 0
                else:
                    location_score = 3
            elif abs(self.lat) < 30:
                # Low latitude - generally good
                location_score = 5
            else:
                # Mid-latitude
                location_score = 4
            
            quality_score += location_score
            
            # Normalize to percentage
            quality_percentage = (quality_score / max_score) * 100
            
            # Determine quality level with confidence
            if quality_percentage >= 80:
                quality = "Excellent"
                confidence = min(quality_percentage / 100, 0.95)
            elif quality_percentage >= 60:
                quality = "Good"
                confidence = min(quality_percentage / 80, 0.85)
            elif quality_percentage >= 40:
                quality = "Fair"
                confidence = min(quality_percentage / 60, 0.75)
            elif quality_percentage >= 20:
                quality = "Poor"
                confidence = min(quality_percentage / 40, 0.65)
            else:
                quality = "Very Poor"
                confidence = min(quality_percentage / 20, 0.55)
            
            # Store historical data
            self._historical_data['propagation_quality'].append({
                'quality': quality,
                'score': quality_percentage,
                'confidence': confidence,
                'timestamp': datetime.now().isoformat()
            })
            
            # Update overall confidence
            self._prediction_confidence['overall'] = confidence
            
            return quality
            
        except Exception as e:
            logger.error(f"Error calculating propagation quality: {e}")
            return "Unknown"

    def _get_aurora_conditions(self, solar_data):
        """Get aurora conditions based on solar data."""
        try:
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            a_index = self._safe_float_conversion(solar_data.get('a_index', '0'))
            
            # Determine aurora activity level
            if k_index >= 6:
                activity = "Strong"
                impact = "Severe HF degradation"
                affected_bands = "All HF bands"
                recommendation = "Avoid HF operation, use VHF/UHF for local contacts"
            elif k_index >= 4:
                activity = "Moderate"
                impact = "Significant HF degradation"
                affected_bands = "Higher HF bands (20m, 15m, 10m)"
                recommendation = "Focus on lower bands (80m, 40m)"
            elif k_index >= 2:
                activity = "Minor"
                impact = "Some HF degradation"
                affected_bands = "Higher HF bands"
                recommendation = "Monitor conditions, avoid higher bands"
            else:
                activity = "None"
                impact = "No auroral effects"
                affected_bands = "None"
                recommendation = "Normal HF operation"
            
            return {
                'activity': activity,
                'impact': impact,
                'affected_bands': affected_bands,
                'recommendation': recommendation,
                'k_index': k_index,
                'a_index': a_index
            }
        except Exception as e:
            logger.error(f"Error getting aurora conditions: {e}")
            return {
                'activity': 'Unknown',
                'impact': 'Unknown',
                'affected_bands': 'Unknown',
                'recommendation': 'Check solar conditions'
            }

    def _get_solar_cycle_info(self, solar_data):
        """Get solar cycle information and predictions."""
        try:
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            sunspots = solar_data.get('sunspots', '0')
            
            # Determine solar cycle phase
            if sfi >= 150:
                cycle_phase = "Solar Maximum"
                prediction = "Excellent HF conditions expected"
            elif sfi >= 100:
                cycle_phase = "Rising Solar Maximum"
                prediction = "Good HF conditions improving"
            elif sfi >= 70:
                cycle_phase = "Solar Minimum to Rising"
                prediction = "Fair conditions, improving"
            else:
                cycle_phase = "Solar Minimum"
                prediction = "Poor HF conditions, focus on lower bands"
            
            return {
                'phase': cycle_phase,
                'prediction': prediction,
                'sfi_trend': 'Rising' if sfi > 80 else 'Stable' if sfi > 60 else 'Declining'
            }
        except Exception as e:
            logger.error(f"Error getting solar cycle info: {e}")
            return {
                'phase': 'Unknown',
                'prediction': 'Unknown',
                'sfi_trend': 'Unknown'
            }

    def get_propagation_summary(self):
        """Generate a comprehensive propagation summary with detailed analysis."""
        try:
            # Get current time in local timezone
            now = datetime.now(self.timezone)
            current_time = now.strftime('%I:%M %p %Z')
            
            # Get sunrise/sunset information
            sun_info = self._calculate_sunrise_sunset()
            
            # Get solar conditions
            solar_data = self.get_solar_conditions()
            
            # Get HamQSL band conditions and convert to individual bands
            hamqsl_bands = self.get_band_conditions()
            band_conditions = self._convert_hamqsl_to_individual_bands(hamqsl_bands)
            
            # Calculate detailed propagation parameters
            muf = self._calculate_muf(solar_data)
            best_bands = self._determine_best_bands(solar_data, sun_info['is_day'])
            propagation_quality = self._calculate_propagation_quality(solar_data, sun_info['is_day'])
            aurora_conditions = self._get_aurora_conditions(solar_data)
            tropo_conditions = self._get_tropo_conditions()
            solar_cycle_info = self._get_solar_cycle_info(solar_data)
            
            # Calculate skip distances for best bands
            skip_distances = {}
            for band in best_bands[:3]:  # Top 3 bands
                if band in band_conditions:
                    freq = band_conditions[band]['freq']
                    skip_distances[band] = self._calculate_skip_distance(freq, sun_info['is_day'])
            
            # Get weather conditions for additional context
            weather_conditions = self.get_weather_conditions()
            
            # Determine operating recommendations
            recommendations = []
            recommendation_priorities = []
            
            # Extract solar data for recommendations
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            a_index = self._safe_float_conversion(solar_data.get('a_index', '0'))
            
            # Enhanced recommendation system with priority scoring
            def add_recommendation(rec, priority=1, confidence=0.8):
                recommendations.append(rec)
                recommendation_priorities.append((priority, confidence))
            
            # 1. Geomagnetic storm recommendations (highest priority)
            if k_index >= 6:
                add_recommendation("SEVERE GEOMAGNETIC STORM - Avoid HF operation, use VHF/UHF for local contacts", 10, 0.95)
            elif k_index >= 4:
                add_recommendation(f"Strong geomagnetic activity (K={k_index}) - Focus on lower bands (80m, 40m)", 9, 0.85)
            elif k_index >= 2:
                add_recommendation(f"Elevated geomagnetic activity (K={k_index}) - Monitor conditions, avoid higher bands", 8, 0.75)
            
            # 2. Solar flux-based recommendations
            if sfi >= 150:
                add_recommendation("Excellent solar flux - All HF bands should be open for DX", 7, 0.90)
            elif sfi >= 120:
                add_recommendation("Good solar flux - Favorable conditions for 20m, 15m, 10m DX", 7, 0.85)
            elif sfi >= 100:
                add_recommendation("Moderate solar flux - Focus on 20m, 40m for DX contacts", 6, 0.75)
            elif sfi >= 80:
                add_recommendation("Low solar flux - Limited HF conditions, focus on 40m, 80m", 6, 0.65)
            else:
                add_recommendation("Very low solar flux - Poor HF conditions, focus on local contacts", 5, 0.55)
            
            # 3. HamQSL band conditions based recommendations
            good_bands = []
            poor_bands = []
            for band_name, conditions in band_conditions.items():
                rating = conditions['day_rating'] if sun_info['is_day'] else conditions['night_rating']
                if rating == 'Good':
                    good_bands.append(band_name)
                elif rating == 'Poor':
                    poor_bands.append(band_name)
            
            if good_bands:
                time_context = "daytime" if sun_info['is_day'] else "nighttime"
                add_recommendation(f"HamQSL indicates good {time_context} conditions on: {', '.join(good_bands[:3])}", 8, 0.90)
            
            if poor_bands:
                time_context = "daytime" if sun_info['is_day'] else "nighttime"
                add_recommendation(f"HamQSL indicates poor {time_context} conditions on: {', '.join(poor_bands[:3])} - avoid these bands", 7, 0.85)
            
            # 4. MUF-based recommendations
            if muf < 10:
                add_recommendation(f"Low MUF ({muf} MHz) - Focus on 80m, 40m, and 30m for DX", 6, 0.80)
            elif muf > 25:
                add_recommendation(f"High MUF ({muf} MHz) - Excellent conditions for 20m, 15m, 10m DX", 7, 0.85)
            
            # 5. Solar cycle recommendations
            if solar_cycle_info['phase'] == 'Solar Maximum':
                add_recommendation("Solar Maximum phase - Excellent HF conditions across all bands", 6, 0.80)
            elif solar_cycle_info['phase'] == 'Solar Minimum':
                add_recommendation("Solar Minimum phase - Focus on lower bands (80m, 40m) for DX", 6, 0.75)
            
            # 6. Propagation quality recommendations
            if propagation_quality in ['Poor', 'Very Poor']:
                add_recommendation("Poor propagation conditions - Focus on local contacts and lower bands", 8, 0.75)
            elif propagation_quality in ['Excellent', 'Good']:
                add_recommendation("Excellent propagation conditions - Ideal for DX and long-distance contacts", 7, 0.85)
            
            # 7. Best bands recommendations
            if best_bands:
                time_context = "daytime" if sun_info['is_day'] else "nighttime"
                add_recommendation(f"Best {time_context} bands for DX: {', '.join(best_bands[:3])}", 6, 0.80)
            
            # 8. Time-specific recommendations
            if sun_info['is_day']:
                if sfi >= 100:
                    add_recommendation("Daytime with good solar flux - F2 layer active, optimal for 20m, 15m, 10m DX", 5, 0.85)
                else:
                    add_recommendation("Daytime with limited solar flux - Focus on 40m and lower bands", 5, 0.75)
            else:
                if sfi >= 80:
                    add_recommendation("Nighttime with decent solar flux - D layer absent, good for 80m, 40m DX", 5, 0.80)
                else:
                    add_recommendation("Nighttime with low solar flux - Focus on 80m and local contacts", 5, 0.70)
            
            # 9. Location-specific recommendations
            if abs(self.lat) > 60:
                add_recommendation("High latitude location - Monitor auroral conditions and geomagnetic activity", 6, 0.80)
            elif abs(self.lat) < 30:
                add_recommendation("Low latitude location - Generally favorable propagation conditions", 4, 0.75)
            
            # 10. Aurora-based recommendations
            if aurora_conditions['activity'] in ['Strong', 'Moderate']:
                add_recommendation(aurora_conditions['recommendation'], 8, 0.85)
            
            # 11. Tropospheric recommendations
            if tropo_conditions['condition'] in ['Excellent', 'Good']:
                add_recommendation(tropo_conditions['recommendation'], 5, 0.75)
            
            # 12. Trend-based recommendations
            if 'trends' in solar_data:
                trend = solar_data['trends'].get('trend', 'Unknown')
                confidence = solar_data['trends'].get('confidence', 0.0)
                if trend == 'Rising' and confidence > 0.6:
                    add_recommendation("Solar activity rising - Conditions improving, monitor higher bands", 5, confidence)
                elif trend == 'Falling' and confidence > 0.6:
                    add_recommendation("Solar activity declining - Conditions may worsen, focus on lower bands", 6, confidence)
            
            # 13. Outlook-coordinated recommendations (NEW)
            # Get the outlook first to coordinate recommendations
            hours_outlook = self._get_hours_outlook(solar_data, sun_info['is_day'])
            next_hours_prediction = self._predict_next_hours(solar_data, sun_info['is_day'])
            
            # Add outlook-based recommendations
            if hours_outlook and 'Improving' in hours_outlook:
                add_recommendation("Conditions expected to improve - Prepare for higher band openings", 6, 0.75)
            elif hours_outlook and 'worsen' in hours_outlook.lower():
                add_recommendation("Conditions may worsen - Focus on current good bands", 7, 0.70)
            
            # Add prediction-based recommendations
            if next_hours_prediction:
                if 'improving' in next_hours_prediction.lower():
                    add_recommendation("6-12 hour forecast: Conditions improving - Monitor 20m, 15m, 10m", 5, 0.70)
                elif 'worsen' in next_hours_prediction.lower():
                    add_recommendation("6-12 hour forecast: Conditions may decline - Focus on 40m, 80m", 6, 0.70)
                elif 'stable' in next_hours_prediction.lower():
                    add_recommendation("6-12 hour forecast: Conditions stable - Continue current operating strategy", 4, 0.75)
            
            # 14. Skip distance recommendations
            if skip_distances:
                best_skip = max(skip_distances.items(), key=lambda x: x[1])
                add_recommendation(f"Optimal skip distance on {best_skip[0]}: {best_skip[1]} km", 4, 0.70)
            
            # Sort recommendations by priority and confidence
            sorted_recommendations = sorted(zip(recommendations, recommendation_priorities), 
                                         key=lambda x: (x[1][0], x[1][1]), reverse=True)
            
            # Return top recommendations with confidence indicators
            final_recommendations = []
            for rec, (priority, confidence) in sorted_recommendations[:8]:  # Top 8 recommendations
                confidence_indicator = " (High)" if confidence >= 0.8 else " (Medium)" if confidence >= 0.6 else " (Low)"
                final_recommendations.append(rec + confidence_indicator)
            
            # Remove duplicates while preserving order
            unique_recommendations = list(dict.fromkeys(final_recommendations))
            recommendations = unique_recommendations[:6]  # Limit to top 6 recommendations
            
            # Get key propagation factors and outlook
            key_factors = self._get_key_propagation_factors(solar_data, sun_info['is_day'])
            hours_outlook = self._get_hours_outlook(solar_data, sun_info['is_day'])
            
            # Get enhanced predictions
            next_hours_prediction = self._predict_next_hours(solar_data, sun_info['is_day'])
            prediction_accuracy = self._calculate_prediction_accuracy()
            
            # Calculate overall confidence
            overall_confidence = (
                self._prediction_confidence['solar_trend'] * 0.3 +
                self._prediction_confidence['overall'] * 0.4 +
                prediction_accuracy * 0.3
            )
            
            return {
                'current_time': current_time,
                'day_night': 'Day' if sun_info['is_day'] else 'Night',
                'sunrise': sun_info['sunrise'],
                'sunset': sun_info['sunset'],
                'location': {
                    'grid': self.grid_square,
                    'latitude': round(self.lat, 2),
                    'longitude': round(self.lon, 2),
                    'timezone': str(self.timezone),
                    'location_name': self._get_location_name()
                },
                'solar_conditions': {
                    'sfi': solar_data.get('sfi', 'N/A'),
                    'a_index': solar_data.get('a_index', 'N/A'),
                    'k_index': solar_data.get('k_index', 'N/A'),
                    'aurora': solar_data.get('aurora', 'N/A'),
                    'sunspots': solar_data.get('sunspots', 'N/A'),
                    'xray': solar_data.get('xray', 'N/A'),
                    'prediction_confidence': solar_data.get('prediction_confidence', 0.0)
                },
                'solar_cycle': solar_cycle_info,
                'propagation_parameters': {
                    'muf': f"{muf} MHz",
                    'quality': propagation_quality,
                    'best_bands': best_bands,
                    'skip_distances': skip_distances,
                    'overall_confidence': round(overall_confidence, 2)
                },
                'band_conditions': band_conditions,
                'aurora_conditions': aurora_conditions,
                'tropo_conditions': tropo_conditions,
                'weather_context': {
                    'temperature': weather_conditions.get('temperature', 'N/A') if weather_conditions else 'N/A',
                    'humidity': weather_conditions.get('humidity', 'N/A') if weather_conditions else 'N/A',
                    'pressure': weather_conditions.get('pressure', 'N/A') if weather_conditions else 'N/A'
                },
                'recommendations': recommendations,
                'summary': {
                    'overall_condition': propagation_quality,
                    'primary_bands': best_bands[:3],
                    'key_factors': key_factors,
                    'next_hours_outlook': hours_outlook,
                    'enhanced_prediction': next_hours_prediction,
                    'prediction_accuracy': round(prediction_accuracy, 2),
                    'confidence_metrics': {
                        'solar_trend': round(self._prediction_confidence['solar_trend'], 2),
                        'overall': round(self._prediction_confidence['overall'], 2),
                        'prediction_accuracy': round(prediction_accuracy, 2)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error generating propagation summary: {e}")
            # Return a default structure instead of None
            return {
                'current_time': datetime.now(self.timezone).strftime('%I:%M %p %Z'),
                'day_night': 'Unknown',
                'sunrise': 'N/A',
                'sunset': 'N/A',
                'location': {
                    'grid': self.grid_square,
                    'latitude': round(self.lat, 2),
                    'longitude': round(self.lon, 2),
                    'timezone': str(self.timezone),
                    'location_name': self._get_location_name()
                },
                'solar_conditions': {
                    'sfi': 'N/A',
                    'a_index': 'N/A',
                    'k_index': 'N/A',
                    'aurora': 'N/A',
                    'sunspots': 'N/A',
                    'xray': 'N/A'
                },
                'solar_cycle': {
                    'phase': 'Unknown',
                    'prediction': 'Unknown',
                    'sfi_trend': 'Unknown'
                },
                'propagation_parameters': {
                    'muf': 'N/A',
                    'quality': 'Unknown',
                    'best_bands': ['Unknown'],
                    'skip_distances': {}
                },
                'band_conditions': {},
                'aurora_conditions': {
                    'activity': 'Unknown',
                    'impact': 'Unknown',
                    'affected_bands': 'Unknown',
                    'recommendation': 'Check solar conditions'
                },
                'tropo_conditions': {
                    'condition': 'Unknown',
                    'impact': 'Unknown',
                    'recommendation': 'Check weather data'
                },
                'weather_context': {
                    'temperature': 'N/A',
                    'humidity': 'N/A',
                    'pressure': 'N/A'
                },
                'recommendations': ['Check system status'],
                'summary': {
                    'overall_condition': 'Unknown',
                    'primary_bands': ['Unknown'],
                    'key_factors': ['Unknown'],
                    'next_hours_outlook': 'Unknown'
                }
            }

    def _calculate_sunrise_sunset(self):
        """Calculate sunrise and sunset times for the current location"""
        try:
            # Simple sunrise/sunset calculation based on latitude and time of year
            # This is a simplified version - for more accuracy, use a proper astronomical library
            now_local = datetime.now(self.timezone)
            today = now_local.date()
            
            # Approximate sunrise/sunset times based on latitude
            # These are rough estimates - in production, use a proper astronomical library
            if abs(self.lat) < 30:  # Tropical regions
                sunrise_hour = 6
                sunset_hour = 18
            elif abs(self.lat) < 45:  # Mid-latitudes
                sunrise_hour = 6
                sunset_hour = 18
            elif abs(self.lat) < 60:  # High latitudes
                sunrise_hour = 7
                sunset_hour = 17
            else:  # Polar regions
                sunrise_hour = 8
                sunset_hour = 16
            
            # Adjust for seasonal variations (simplified)
            day_of_year = today.timetuple().tm_yday
            if 80 <= day_of_year <= 265:  # Spring/Summer in Northern Hemisphere
                sunrise_hour -= 1
                sunset_hour += 1
            
            sunrise_time = now_local.replace(hour=sunrise_hour, minute=0, second=0, microsecond=0)
            sunset_time = now_local.replace(hour=sunset_hour, minute=0, second=0, microsecond=0)
            
            is_day = sunrise_time <= now_local <= sunset_time
            
            return {
                'sunrise': sunrise_time.strftime('%I:%M %p'),
                'sunset': sunset_time.strftime('%I:%M %p'),
                'is_day': is_day
            }
        except Exception as e:
            logger.error(f"Error calculating sunrise/sunset: {e}")
            return {
                'sunrise': 'N/A',
                'sunset': 'N/A',
                'is_day': True
            }

    def _get_key_propagation_factors(self, solar_data, is_daytime):
        """Get enhanced key factors affecting current propagation with confidence scoring."""
        try:
            factors = []
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            a_index = self._safe_float_conversion(solar_data.get('a_index', '0'))
            
            # Get HamQSL band conditions
            hamqsl_bands = self.get_band_conditions()
            band_conditions = self._convert_hamqsl_to_individual_bands(hamqsl_bands)
            
            # Enhanced factor analysis with confidence
            factor_confidence = {}
            
            # Solar flux factors (high confidence)
            if sfi >= 150:
                factors.append("High Solar Flux - excellent HF conditions across all bands")
                factor_confidence["solar_flux"] = 0.95
            elif sfi >= 120:
                factors.append("Good Solar Flux - favorable HF conditions")
                factor_confidence["solar_flux"] = 0.85
            elif sfi >= 100:
                factors.append("Moderate Solar Flux - decent HF conditions")
                factor_confidence["solar_flux"] = 0.75
            elif sfi >= 80:
                factors.append("Low Solar Flux - limited HF conditions")
                factor_confidence["solar_flux"] = 0.65
            else:
                factors.append("Very Low Solar Flux - poor HF conditions")
                factor_confidence["solar_flux"] = 0.55
            
            # Geomagnetic factors (high confidence)
            if k_index >= 6:
                factors.append(f"Severe Geomagnetic Storm (K={k_index}) - HF propagation severely degraded")
                factor_confidence["geomagnetic"] = 0.95
            elif k_index >= 4:
                factors.append(f"Strong Geomagnetic Activity (K={k_index}) - expect degraded HF propagation")
                factor_confidence["geomagnetic"] = 0.85
            elif k_index >= 2:
                factors.append(f"Elevated Geomagnetic Activity (K={k_index}) - some HF bands affected")
                factor_confidence["geomagnetic"] = 0.75
            else:
                factors.append("Quiet Geomagnetic Conditions - favorable for HF propagation")
                factor_confidence["geomagnetic"] = 0.85
            
            # A-index factors
            if a_index >= 30:
                factors.append(f"High A-index ({a_index}) - ionospheric instability")
                factor_confidence["a_index"] = 0.80
            elif a_index >= 20:
                factors.append(f"Elevated A-index ({a_index}) - moderate ionospheric effects")
                factor_confidence["a_index"] = 0.70
            else:
                factors.append("Low A-index - stable ionospheric conditions")
                factor_confidence["a_index"] = 0.80
            
            # Time-based factors
            if is_daytime:
                factors.append("Daytime - F2 layer active, optimal for 20m, 15m, 10m")
                factor_confidence["time"] = 0.90
            else:
                factors.append("Nighttime - D layer absent, E/F2 layers active, good for 80m, 40m")
                factor_confidence["time"] = 0.90
            
            # Location-based factors
            if abs(self.lat) > 60:
                factors.append("High latitude location - auroral zone effects")
                factor_confidence["location"] = 0.85
            elif abs(self.lat) < 30:
                factors.append("Low latitude - generally favorable propagation conditions")
                factor_confidence["location"] = 0.80
            else:
                factors.append("Mid-latitude - typical propagation conditions")
                factor_confidence["location"] = 0.75
            
            # HamQSL-based factors (high confidence when available)
            if band_conditions:
                good_bands = []
                poor_bands = []
                for band_name, conditions in band_conditions.items():
                    rating = conditions['day_rating'] if is_daytime else conditions['night_rating']
                    if rating == 'Good':
                        good_bands.append(band_name)
                    elif rating == 'Poor':
                        poor_bands.append(band_name)
                
                if good_bands:
                    factors.append(f"HamQSL indicates good conditions on: {', '.join(good_bands[:3])}")
                    factor_confidence["hamqsl_good"] = 0.90
                if poor_bands:
                    factors.append(f"HamQSL indicates poor conditions on: {', '.join(poor_bands[:3])}")
                    factor_confidence["hamqsl_poor"] = 0.90
            
            # Trend-based factors
            if 'trends' in solar_data:
                trend = solar_data['trends'].get('trend', 'Unknown')
                confidence = solar_data['trends'].get('confidence', 0.0)
                if trend != 'Unknown' and confidence > 0.6:
                    factors.append(f"Solar activity trending {trend.lower()} (confidence: {confidence:.1f})")
                    factor_confidence["trend"] = confidence
            
            # Calculate overall confidence
            if factor_confidence:
                avg_confidence = sum(factor_confidence.values()) / len(factor_confidence)
                self._prediction_confidence['overall'] = avg_confidence
            
            return factors if factors else ["Normal propagation conditions"]
            
        except Exception as e:
            logger.error(f"Error getting key factors: {e}")
            return ["Unknown conditions"]

    def _get_hours_outlook(self, solar_data, is_daytime):
        """Enhanced outlook for next few hours with comprehensive analysis and confidence scoring."""
        try:
            sfi = self._safe_float_conversion(solar_data.get('sfi', '0'))
            k_index = self._safe_float_conversion(solar_data.get('k_index', '0'))
            a_index = self._safe_float_conversion(solar_data.get('a_index', '0'))
            
            # Get current hour for time-based predictions
            current_hour = datetime.now(self.timezone).hour
            
            # Get HamQSL band conditions to inform the outlook
            hamqsl_bands = self.get_band_conditions()
            band_conditions = self._convert_hamqsl_to_individual_bands(hamqsl_bands)
            propagation_quality = self._calculate_propagation_quality(solar_data, is_daytime)
            
            # Enhanced outlook analysis
            outlook_components = []
            confidence_factors = []
            
            # 1. Geomagnetic storm conditions (highest priority)
            if k_index > 6:
                outlook_components.append("Severe geomagnetic storm")
                outlook_components.append("HF propagation severely degraded")
                outlook_components.append("Focus on VHF/UHF and local contacts")
                confidence_factors.append(0.95)
            elif k_index > 4 or a_index > 30:
                outlook_components.append("Geomagnetic storm conditions")
                outlook_components.append("Expect degraded HF propagation")
                outlook_components.append("Monitor conditions closely")
                confidence_factors.append(0.85)
            elif k_index > 2 or a_index > 20:
                outlook_components.append("Elevated geomagnetic activity")
                outlook_components.append("Some HF bands may be affected")
                outlook_components.append("Focus on lower bands")
                confidence_factors.append(0.75)
            else:
                outlook_components.append("Quiet geomagnetic conditions")
                outlook_components.append("Favorable for HF propagation")
                confidence_factors.append(0.80)
            
            # 2. Solar flux-based outlook
            if sfi >= 150:
                outlook_components.append("High solar flux")
                outlook_components.append("Excellent HF conditions expected")
                confidence_factors.append(0.90)
            elif sfi >= 120:
                outlook_components.append("Good solar flux")
                outlook_components.append("Favorable HF conditions")
                confidence_factors.append(0.85)
            elif sfi >= 100:
                outlook_components.append("Moderate solar flux")
                outlook_components.append("Decent HF conditions")
                confidence_factors.append(0.75)
            elif sfi >= 80:
                outlook_components.append("Low solar flux")
                outlook_components.append("Limited HF conditions")
                confidence_factors.append(0.65)
            else:
                outlook_components.append("Very low solar flux")
                outlook_components.append("Poor HF conditions")
                confidence_factors.append(0.55)
            
            # 3. HamQSL-based outlook
            if band_conditions:
                good_bands = 0
                fair_bands = 0
                poor_bands = 0
                
                for band_info in band_conditions.values():
                    rating = band_info['day_rating'] if is_daytime else band_info['night_rating']
                    if rating == 'Good':
                        good_bands += 1
                    elif rating == 'Fair':
                        fair_bands += 1
                    elif rating == 'Poor':
                        poor_bands += 1
                
                if good_bands >= 5:
                    outlook_components.append("Multiple bands showing good propagation")
                    outlook_components.append("Ideal for DX and long-distance contacts")
                    confidence_factors.append(0.90)
                elif good_bands >= 3:
                    outlook_components.append("Several bands available for operation")
                    outlook_components.append("Good for regional and DX contacts")
                    confidence_factors.append(0.80)
                elif good_bands >= 1:
                    outlook_components.append("Limited but usable bands available")
                    outlook_components.append("Focus on local and regional contacts")
                    confidence_factors.append(0.70)
                elif poor_bands >= 5:
                    outlook_components.append("Most bands degraded")
                    outlook_components.append("Focus on local contacts and VHF/UHF")
                    confidence_factors.append(0.75)
                else:
                    outlook_components.append("Mixed band conditions")
                    outlook_components.append("Check individual band ratings")
                    confidence_factors.append(0.65)
            
            # 4. Time-based outlook
            if is_daytime:
                if sfi >= 100:
                    outlook_components.append("Daytime with good solar flux")
                    outlook_components.append("Optimal for 20m, 15m, 10m DX")
                else:
                    outlook_components.append("Daytime with limited solar flux")
                    outlook_components.append("Focus on 40m and lower bands")
            else:
                if sfi >= 80:
                    outlook_components.append("Nighttime with decent solar flux")
                    outlook_components.append("Good for 80m, 40m DX")
                else:
                    outlook_components.append("Nighttime with low solar flux")
                    outlook_components.append("Focus on 80m and local contacts")
            
            confidence_factors.append(0.85)  # Time-based confidence
            
            # 5. Location-based outlook
            if abs(self.lat) > 60:
                outlook_components.append("High latitude location")
                outlook_components.append("Monitor auroral conditions")
                confidence_factors.append(0.80)
            elif abs(self.lat) < 30:
                outlook_components.append("Low latitude location")
                outlook_components.append("Generally favorable conditions")
                confidence_factors.append(0.85)
            else:
                outlook_components.append("Mid-latitude location")
                outlook_components.append("Typical propagation conditions")
                confidence_factors.append(0.80)
            
            # 6. Trend-based outlook
            if 'trends' in solar_data:
                trend = solar_data['trends'].get('trend', 'Unknown')
                change_24h = solar_data['trends'].get('change_24h', 0)
                if trend != 'Unknown' and abs(change_24h) > 5:
                    if trend == 'Rising':
                        outlook_components.append("Solar activity rising")
                        outlook_components.append("Conditions improving")
                    elif trend == 'Falling':
                        outlook_components.append("Solar activity declining")
                        outlook_components.append("Conditions may worsen")
                    confidence_factors.append(0.75)
            
            # 7. Recommendation-coordinated outlook (NEW)
            # Add outlook components that align with operating recommendations
            if sfi >= 120 and k_index <= 2:
                outlook_components.append("Excellent conditions for DX operation")
                outlook_components.append("All HF bands should be productive")
                confidence_factors.append(0.85)
            elif sfi >= 100 and k_index <= 3:
                outlook_components.append("Good conditions for regional and DX contacts")
                outlook_components.append("Focus on 20m, 40m for best results")
                confidence_factors.append(0.80)
            elif sfi < 80 or k_index >= 4:
                outlook_components.append("Challenging conditions for HF operation")
                outlook_components.append("Focus on local contacts and lower bands")
                confidence_factors.append(0.75)
            
            # 8. Time-based outlook coordination
            if is_daytime:
                if sfi >= 100:
                    outlook_components.append("Daytime F2 layer active - Optimal for 20m, 15m, 10m")
                else:
                    outlook_components.append("Daytime with limited solar flux - Focus on 40m and lower")
            else:
                if sfi >= 80:
                    outlook_components.append("Nighttime D layer absent - Good for 80m, 40m DX")
                else:
                    outlook_components.append("Nighttime with low solar flux - Focus on 80m and local")
            
            # Calculate overall confidence
            if confidence_factors:
                avg_confidence = sum(confidence_factors) / len(confidence_factors)
                confidence_level = "High" if avg_confidence >= 0.8 else "Medium" if avg_confidence >= 0.6 else "Low"
            else:
                avg_confidence = 0.7
                confidence_level = "Medium"
            
            # Create structured outlook data
            outlook_data = {
                'summary': " - ".join(outlook_components[:3]),  # First 3 components as summary
                'details': outlook_components[3:],  # Remaining components as details
                'confidence_level': confidence_level,
                'confidence_score': avg_confidence,
                'key_points': [
                    outlook_components[0] if outlook_components else "Unknown conditions",
                    outlook_components[1] if len(outlook_components) > 1 else "",
                    outlook_components[2] if len(outlook_components) > 2 else ""
                ],
                'time_context': "Daytime" if is_daytime else "Nighttime",
                'solar_flux_level': "High" if sfi >= 150 else "Good" if sfi >= 120 else "Moderate" if sfi >= 100 else "Low" if sfi >= 80 else "Very Low",
                'geomagnetic_status': "Storm" if k_index > 4 else "Elevated" if k_index > 2 else "Quiet"
            }
            
            # Return formatted string for backward compatibility
            outlook = " - ".join(outlook_components)
            outlook += f" (Confidence: {confidence_level})"
            
            return outlook
            
        except Exception as e:
            logger.error(f"Error getting outlook: {e}")
            return "Unknown outlook - check solar conditions"

    def _get_tropo_conditions(self):
        """Get detailed tropospheric conditions based on weather data."""
        try:
            weather = self.get_weather_conditions()
            if not weather:
                return {
                    'condition': 'Unknown',
                    'impact': 'Unknown',
                    'recommendation': 'Check weather data'
                }
            
            # Extract weather parameters
            temp = weather.get('temperature', '0°F')
            humidity = weather.get('humidity', '0%')
            pressure = weather.get('pressure', '1013 hPa')
            
            # Parse values
            try:
                temp_val = float(temp.replace('°F', '').replace('°C', ''))
                humidity_val = float(humidity.replace('%', ''))
                pressure_val = float(pressure.replace(' hPa', ''))
            except:
                temp_val = 70
                humidity_val = 50
                pressure_val = 1013
            
            # Calculate tropospheric ducting potential
            ducting_score = 0
            
            # Temperature inversion (common in morning/evening)
            hour = datetime.now(self.timezone).hour
            if 6 <= hour <= 9 or 17 <= hour <= 20:
                ducting_score += 20
            
            # Humidity factor
            if 40 <= humidity_val <= 80:
                ducting_score += 15
            elif humidity_val > 80:
                ducting_score += 10
            
            # Pressure factor
            if 1000 <= pressure_val <= 1020:
                ducting_score += 10
            
            # Determine condition
            if ducting_score >= 35:
                condition = "Excellent"
                impact = "Enhanced VHF/UHF propagation possible"
                recommendation = "Try 2m, 6m, and 70cm bands"
            elif ducting_score >= 25:
                condition = "Good"
                impact = "Some VHF enhancement possible"
                recommendation = "Monitor 2m and 6m for openings"
            elif ducting_score >= 15:
                condition = "Fair"
                impact = "Normal tropospheric conditions"
                recommendation = "Standard VHF operation"
            else:
                condition = "Poor"
                impact = "Limited tropospheric enhancement"
                recommendation = "Focus on HF bands"
            
            return {
                'condition': condition,
                'impact': impact,
                'recommendation': recommendation,
                'score': ducting_score
            }
        except Exception as e:
            logger.error(f"Error getting tropospheric conditions: {e}")
            return {
                'condition': 'Unknown',
                'impact': 'Unknown',
                'recommendation': 'Check weather data'
            }

    def _calculate_skip_distance(self, band_freq, is_daytime):
        """Calculate typical skip distance for a given band."""
        try:
            # Simplified skip distance calculation
            if band_freq <= 3.5:  # 80m and below
                return "500-1500 km"
            elif band_freq <= 7.0:  # 40m
                return "1000-3000 km"
            elif band_freq <= 14.0:  # 20m
                return "2000-8000 km"
            elif band_freq <= 21.0:  # 15m
                return "3000-12000 km"
            elif band_freq <= 28.0:  # 10m
                return "5000-15000 km"
            else:
                return "Variable"
        except Exception as e:
            logger.error(f"Error calculating skip distance: {e}")
            return "Unknown"

    def _get_location_name(self):
        """Get location name from weather data or return generic location."""
        try:
            # Try to get location from weather data first
            weather = self.get_weather_conditions()
            if weather and weather.get('city'):
                return f"{weather['city']}, {weather.get('state', '')}"
            
            # Fallback to generic location based on coordinates
            env_zip_code = os.getenv('ZIP_CODE')
            if env_zip_code:
                return f"ZIP {env_zip_code}"
            else:
                return f"Grid {self.grid_square}"
        except Exception as e:
            logger.error(f"Error getting location name: {e}")
            return "Unknown Location"

    def _convert_hamqsl_to_individual_bands(self, hamqsl_bands):
        """Convert HamQSL band groups to individual band conditions"""
        try:
            individual_bands = {}
            
            # Map HamQSL band groups to individual bands
            band_mapping = {
                '80m-40m': ['80m', '40m'],
                '30m-20m': ['30m', '20m'], 
                '17m-15m': ['17m', '15m'],
                '12m-10m': ['12m', '10m']
            }
            
            # Get current time to determine day/night
            sun_info = self._calculate_sunrise_sunset()
            is_daytime = sun_info['is_day']
            
            for group_name, group_data in hamqsl_bands.items():
                if group_name in band_mapping:
                    # Get the condition for current time (day/night)
                    condition = group_data['day'] if is_daytime else group_data['night']
                    
                    # Convert HamQSL condition to our rating system
                    if condition == 'Good':
                        rating = 'Good'
                    elif condition == 'Fair':
                        rating = 'Fair'
                    elif condition == 'Poor':
                        rating = 'Poor'
                    else:
                        rating = 'Fair'  # Default for N/A or unknown
                    
                    # Apply to individual bands in the group
                    for band_name in band_mapping[group_name]:
                        individual_bands[band_name] = {
                            'freq': self._get_band_frequency(band_name),
                            'day_rating': group_data['day'] if group_data['day'] != 'N/A' else 'Fair',
                            'night_rating': group_data['night'] if group_data['night'] != 'N/A' else 'Fair',
                            'notes': f'From HamQSL: {group_name}'
                        }
            
            # Add bands not covered by HamQSL with calculated conditions
            all_bands = ['160m', '80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
            solar_data = self.get_solar_conditions()
            
            for band_name in all_bands:
                if band_name not in individual_bands:
                    # Use calculated conditions for bands not in HamQSL
                    calculated = self._calculate_band_conditions_detailed(solar_data, is_daytime)
                    if band_name in calculated:
                        individual_bands[band_name] = calculated[band_name]
                        individual_bands[band_name]['notes'] += ' (Calculated)'
            
            return individual_bands
        except Exception as e:
            logger.error(f"Error converting HamQSL bands: {e}")
            # Fallback to calculated conditions
            solar_data = self.get_solar_conditions()
            sun_info = self._calculate_sunrise_sunset()
            return self._calculate_band_conditions_detailed(solar_data, sun_info['is_day'])

    def _get_band_frequency(self, band_name):
        """Get center frequency for a band"""
        frequencies = {
            '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
            '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
            '10m': 28.0, '6m': 50.0
        }
        return frequencies.get(band_name, 14.0)

    def _calculate_band_conditions_detailed(self, solar_data, is_daytime):
        """Calculate detailed conditions for each amateur band using only Good, Fair, Poor ratings."""
        try:
            muf = self._calculate_muf(solar_data)
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            k_index = float(solar_data.get('k_index', '0'))
            a_index = float(solar_data.get('a_index', '0'))
            
            bands = {
                '160m': {'freq': 1.8, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '80m': {'freq': 3.5, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '40m': {'freq': 7.0, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '30m': {'freq': 10.1, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '20m': {'freq': 14.0, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '17m': {'freq': 18.1, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '15m': {'freq': 21.0, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '12m': {'freq': 24.9, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '10m': {'freq': 28.0, 'day_rating': '', 'night_rating': '', 'notes': ''},
                '6m': {'freq': 50.0, 'day_rating': '', 'night_rating': '', 'notes': ''}
            }
            
            for band_name, band_info in bands.items():
                freq = band_info['freq']
                notes = []
                # MUF check
                if freq > muf:
                    band_info['day_rating'] = 'Poor'
                    band_info['night_rating'] = 'Poor'
                    notes.append(f"Above MUF ({muf:.1f} MHz)")
                else:
                    # SFI/K/A-index logic
                    for period, label in [('day_rating', True), ('night_rating', False)]:
                        # Start with Good if below MUF
                        rating = 'Good'
                        # SFI
                        if sfi < 70:
                            rating = 'Fair'
                            notes.append('Low SFI')
                        elif sfi < 90:
                            rating = 'Fair'
                        # K-index
                        if k_index > 6:
                            rating = 'Poor'
                            notes.append(f'Severe geomagnetic storm (K={k_index})')
                        elif k_index > 4:
                            rating = 'Poor'
                            notes.append(f'High K-index ({k_index})')
                        elif k_index > 2:
                            if rating != 'Poor':
                                rating = 'Fair'
                                notes.append(f'Elevated K-index ({k_index})')
                        # A-index
                        if a_index > 30:
                            rating = 'Poor'
                            notes.append(f'High A-index ({a_index})')
                        elif a_index > 20:
                            if rating != 'Poor':
                                rating = 'Fair'
                                notes.append(f'Elevated A-index ({a_index})')
                        # Time of day adjustments
                        if label:  # Day
                            if freq < 7:
                                rating = 'Poor'
                                notes.append('Daytime - lower bands poor')
                        else:  # Night
                            if freq > 21:
                                rating = 'Poor'
                                notes.append('Nighttime - higher bands poor')
                        band_info[period] = rating
                band_info['notes'] = '; '.join(notes) if notes else ''
            return bands
        except Exception as e:
            logger.error(f"Error calculating detailed band conditions: {e}")
            return {}

    def grid_to_latlon(self, grid_square: str) -> tuple:
        """Convert grid square to latitude and longitude."""
        try:
            return grid_to_latlon(grid_square)
        except Exception as e:
            logger.error(f"Error converting grid to lat/lon: {e}")
            return (0.0, 0.0)

    def latlon_to_grid(self, lat: float, lon: float) -> str:
        """Convert latitude and longitude to grid square."""
        try:
            # Simple grid square calculation
            # This is a simplified version - for more accurate results, use a proper library
            lon = lon + 180
            lat = lat + 90
            
            # Calculate grid square
            lon_field = int(lon / 20)
            lat_field = int(lat / 10)
            lon_square = int((lon % 20) / 2)
            lat_square = int((lat % 10) / 1)
            lon_sub = int(((lon % 20) % 2) / (2/24))
            lat_sub = int(((lat % 10) % 1) / (1/24))
            
            # Convert to characters
            lon_field_char = chr(ord('A') + lon_field)
            lat_field_char = chr(ord('A') + lat_field)
            lon_square_char = str(lon_square)
            lat_square_char = str(lat_square)
            lon_sub_char = chr(ord('a') + lon_sub)
            lat_sub_char = chr(ord('a') + lat_sub)
            
            return f"{lon_field_char}{lat_field_char}{lon_square_char}{lat_square_char}{lon_sub_char}{lat_sub_char}"
        except Exception as e:
            logger.error(f"Error converting lat/lon to grid: {e}")
            return "AA00aa"

    def update_location(self, zip_code: str) -> bool:
        """Update the location with a new ZIP code. Only allow ZIP from .env file."""
        try:
            env_zip_code = os.getenv('ZIP_CODE')
            if zip_code != env_zip_code:
                logger.error(f"Attempted to update location to ZIP {zip_code}, but only ZIP from .env is allowed.")
                return False
            
            if not self.openweather_api_key:
                logger.error("OpenWeather API key not available for geocoding")
                return False
            
            # Use OpenWeather API to get coordinates for the ZIP code
            url = "http://api.openweathermap.org/geo/1.0/zip"
            params = {
                'zip': f"{zip_code},US",
                'appid': self.openweather_api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.lat = data['lat']
                self.lon = data['lon']
                self.grid_square = self.latlon_to_grid(self.lat, self.lon)
                self.timezone = self._get_timezone_from_coords(self.lat, self.lon)
                self.clear_cache()
                logger.info(f"Location updated to ZIP {zip_code}: lat={self.lat}, lon={self.lon}, grid={self.grid_square}")
                return True
            else:
                logger.error(f"Failed to get coordinates for ZIP {zip_code}")
                return False
        except Exception as e:
            logger.error(f"Error updating location to ZIP {zip_code}: {e}")
            return False

    def _get_timezone_from_coords(self, lat: float, lon: float) -> pytz.timezone:
        """Get timezone from coordinates."""
        try:
            # This is a simplified version - in a real application, you'd use a timezone service
            # For now, return a default timezone based on longitude
            if lon < -100:
                return pytz.timezone('America/Los_Angeles')
            elif lon < -80:
                return pytz.timezone('America/New_York')
            else:
                return pytz.timezone('UTC')
        except Exception as e:
            logger.error(f"Error getting timezone from coordinates: {e}")
            return pytz.timezone('America/Los_Angeles')

    def get_spots_status(self):
        """Get status of spots loading and caching."""
        try:
            cached_spots = cache_get('spots', 'current')
            if cached_spots:
                return {
                    'loading': False,
                    'cached': True,
                    'source': cached_spots.get('summary', {}).get('source', 'Unknown'),
                    'cache_age': time.time() - cached_spots.get('_cache_time', time.time())
                }
            else:
                return {
                    'loading': True,
                    'cached': False,
                    'source': 'None',
                    'cache_age': None
                }
        except Exception as e:
            logger.error(f"Error getting spots status: {e}")
            return {
                'loading': False,
                'cached': False,
                'source': 'Error',
                'cache_age': None
            }

    def print_report(self, report):
        """Print a formatted report to console."""
        if not report:
            print("No report available")
            return
        
        print("\n" + "="*60)
        print("HAM RADIO CONDITIONS REPORT")
        print("="*60)
        print(f"Time: {report.get('timestamp', 'N/A')}")
        print(f"Location: {report.get('propagation_summary', {}).get('location', {}).get('location_name', 'N/A')}")
        
        # Solar conditions
        solar = report.get('solar_conditions', {})
        print(f"\nSOLAR CONDITIONS:")
        print(f"  SFI: {solar.get('sfi', 'N/A')}")
        print(f"  A-Index: {solar.get('a_index', 'N/A')}")
        print(f"  K-Index: {solar.get('k_index', 'N/A')}")
        print(f"  Sunspots: {solar.get('sunspots', 'N/A')}")
        
        # Weather conditions
        weather = report.get('weather_conditions', {})
        if weather:
            print(f"\nWEATHER CONDITIONS:")
            print(f"  Temperature: {weather.get('temperature', 'N/A')}")
            print(f"  Humidity: {weather.get('humidity', 'N/A')}")
            print(f"  Pressure: {weather.get('pressure', 'N/A')}")
        
        # Propagation summary
        prop = report.get('propagation_summary', {})
        if prop:
            print(f"\nPROPAGATION SUMMARY:")
            print(f"  Current Time: {prop.get('current_time', 'N/A')}")
            print(f"  Day/Night: {prop.get('day_night', 'N/A')}")
            print(f"  Sunrise: {prop.get('sunrise', 'N/A')}")
            print(f"  Sunset: {prop.get('sunset', 'N/A')}")
            print(f"  Overall Quality: {prop.get('propagation_parameters', {}).get('quality', 'N/A')}")
            print(f"  MUF: {prop.get('propagation_parameters', {}).get('muf', 'N/A')}")
            
            # Best bands
            best_bands = prop.get('propagation_parameters', {}).get('best_bands', [])
            if best_bands:
                print(f"  Best Bands: {', '.join(best_bands[:3])}")
        
        print("="*60)

    def _analyze_historical_patterns(self):
        """Analyze historical data patterns to improve predictions."""
        try:
            if len(self._historical_data['solar_conditions']) < 24:
                return {'pattern': 'Insufficient data', 'confidence': 0.0}
            
            # Get recent data for analysis
            recent_solar = list(self._historical_data['solar_conditions'])[-24:]  # Last 24 hours
            recent_quality = list(self._historical_data['propagation_quality'])[-24:]
            
            # Analyze solar flux trends
            sfi_values = []
            for data in recent_solar:
                sfi_str = data.get('sfi', '0 SFI')
                try:
                    sfi = float(sfi_str.replace(' SFI', ''))
                    sfi_values.append(sfi)
                except:
                    continue
            
            if len(sfi_values) < 12:
                return {'pattern': 'Insufficient solar data', 'confidence': 0.0}
            
            # Calculate trend strength
            x = np.arange(len(sfi_values))
            y = np.array(sfi_values)
            slope = np.polyfit(x, y, 1)[0]
            r_squared = np.corrcoef(x, y)[0, 1] ** 2
            
            # Analyze quality patterns
            quality_scores = []
            for data in recent_quality:
                if isinstance(data, dict) and 'score' in data:
                    quality_scores.append(data['score'])
                else:
                    quality_scores.append(50)  # Default score
            
            # Calculate quality trend
            if len(quality_scores) >= 12:
                quality_slope = np.polyfit(np.arange(len(quality_scores)), quality_scores, 1)[0]
            else:
                quality_slope = 0
            
            # Pattern classification
            if abs(slope) > 5 and r_squared > 0.7:
                if slope > 0:
                    pattern = "Strong rising trend"
                    confidence = min(abs(slope) / 10.0, 0.95)
                else:
                    pattern = "Strong falling trend"
                    confidence = min(abs(slope) / 10.0, 0.95)
            elif abs(slope) > 2 and r_squared > 0.5:
                if slope > 0:
                    pattern = "Moderate rising trend"
                    confidence = min(abs(slope) / 8.0, 0.85)
                else:
                    pattern = "Moderate falling trend"
                    confidence = min(abs(slope) / 8.0, 0.85)
            else:
                pattern = "Stable conditions"
                confidence = 0.8
            
            # Quality correlation
            if abs(quality_slope) > 5:
                if quality_slope > 0:
                    pattern += " with improving propagation"
                else:
                    pattern += " with degrading propagation"
            
            return {
                'pattern': pattern,
                'confidence': confidence,
                'slope': slope,
                'r_squared': r_squared,
                'quality_trend': quality_slope
            }
            
        except Exception as e:
            logger.error(f"Error analyzing historical patterns: {e}")
            return {'pattern': 'Analysis error', 'confidence': 0.0}

    def _predict_next_hours(self, solar_data, is_daytime):
        """Predict conditions for the next 6-12 hours."""
        try:
            # Get current conditions
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            k_index = float(solar_data.get('k_index', '0'))
            
            # Get historical patterns
            patterns = self._analyze_historical_patterns()
            
            # Base prediction
            predictions = []
            confidence = 0.7
            
            # Solar flux prediction
            if patterns['pattern'].startswith('Strong rising'):
                predictions.append("Solar flux likely to continue rising")
                predictions.append("Conditions improving over next 6-12 hours")
                confidence = min(confidence + 0.1, 0.9)
            elif patterns['pattern'].startswith('Strong falling'):
                predictions.append("Solar flux likely to continue falling")
                predictions.append("Conditions may worsen over next 6-12 hours")
                confidence = min(confidence + 0.1, 0.9)
            elif patterns['pattern'].startswith('Moderate rising'):
                predictions.append("Solar flux trending upward")
                predictions.append("Conditions likely to improve")
                confidence = min(confidence + 0.05, 0.85)
            elif patterns['pattern'].startswith('Moderate falling'):
                predictions.append("Solar flux trending downward")
                predictions.append("Conditions may decline")
                confidence = min(confidence + 0.05, 0.85)
            else:
                predictions.append("Solar flux stable")
                predictions.append("Conditions likely to remain similar")
            
            # Geomagnetic prediction
            if k_index >= 4:
                predictions.append("Geomagnetic activity may persist")
                predictions.append("Monitor for storm conditions")
                confidence = min(confidence - 0.1, 0.8)
            elif k_index <= 1:
                predictions.append("Quiet geomagnetic conditions expected")
                predictions.append("Favorable for HF propagation")
                confidence = min(confidence + 0.05, 0.85)
            
            # Time-based prediction
            current_hour = datetime.now(self.timezone).hour
            if is_daytime:
                if 6 <= current_hour <= 18:
                    predictions.append("Daytime conditions continuing")
                    if sfi >= 100:
                        predictions.append("Good conditions for 20m, 15m, 10m")
                    else:
                        predictions.append("Focus on 40m and lower bands")
                else:
                    predictions.append("Transitioning to nighttime")
                    predictions.append("D layer will disappear, good for 80m, 40m")
            else:
                if 18 <= current_hour or current_hour <= 6:
                    predictions.append("Nighttime conditions continuing")
                    predictions.append("Good for 80m, 40m DX")
                else:
                    predictions.append("Transitioning to daytime")
                    predictions.append("F2 layer becoming active")
            
            # 9. Recommendation-coordinated predictions (NEW)
            # Add predictions that align with operating recommendations
            if sfi >= 120 and k_index <= 2:
                predictions.append("Excellent propagation conditions expected to continue")
                predictions.append("Ideal for DX and long-distance contacts")
            elif sfi >= 100 and k_index <= 3:
                predictions.append("Good conditions likely to persist")
                predictions.append("Continue focus on 20m, 40m for DX")
            elif sfi < 80 or k_index >= 4:
                predictions.append("Challenging conditions may continue")
                predictions.append("Maintain focus on local contacts and lower bands")
            
            # Create structured prediction data
            prediction_data = {
                'summary': " - ".join(predictions[:2]),  # First 2 predictions as summary
                'details': predictions[2:],  # Remaining predictions as details
                'confidence_level': "High" if confidence >= 0.8 else "Medium" if confidence >= 0.6 else "Low",
                'confidence_score': confidence,
                'key_predictions': [
                    predictions[0] if predictions else "No predictions available",
                    predictions[1] if len(predictions) > 1 else "",
                    predictions[2] if len(predictions) > 2 else ""
                ],
                'timeframe': "6-12 hours",
                'trend_direction': "Improving" if any("improving" in p.lower() for p in predictions) else "Declining" if any("worsen" in p.lower() or "decline" in p.lower() for p in predictions) else "Stable"
            }
            
            # Return formatted string for backward compatibility
            prediction_text = " - ".join(predictions)
            confidence_level = "High" if confidence >= 0.8 else "Medium" if confidence >= 0.6 else "Low"
            
            return f"{prediction_text} (Confidence: {confidence_level})"
            
        except Exception as e:
            logger.error(f"Error predicting next hours: {e}")
            return "Unable to predict future conditions"

    def _calculate_prediction_accuracy(self):
        """Calculate accuracy of recent predictions vs actual outcomes."""
        try:
            # For now, provide a reasonable accuracy based on data quality
            # This is a simplified approach until we have more historical data
            
            # Check if we have recent solar data
            if len(self._historical_data['solar_conditions']) < 2:
                return 0.6  # Default accuracy when no historical data
            
            # Calculate accuracy based on data consistency
            recent_solar = list(self._historical_data['solar_conditions'])[-6:]  # Last 6 hours
            
            consistency_score = 0.0
            total_checks = 0
            
            for i in range(1, len(recent_solar)):
                try:
                    current_sfi = self._safe_float_conversion(recent_solar[i].get('sfi', '0'))
                    prev_sfi = self._safe_float_conversion(recent_solar[i-1].get('sfi', '0'))
                    
                    # Check if SFI values are consistent (not wildly different)
                    sfi_change = abs(current_sfi - prev_sfi)
                    if sfi_change <= 10:
                        consistency_score += 1.0
                    elif sfi_change <= 20:
                        consistency_score += 0.8
                    elif sfi_change <= 30:
                        consistency_score += 0.6
                    else:
                        consistency_score += 0.4
                    
                    total_checks += 1
                except:
                    continue
            
            if total_checks > 0:
                base_accuracy = consistency_score / total_checks
            else:
                base_accuracy = 0.7
            
            # Adjust based on confidence levels
            confidence_factor = self._prediction_confidence['solar_trend']
            
            # Final accuracy is a combination of consistency and confidence
            final_accuracy = (base_accuracy * 0.7) + (confidence_factor * 0.3)
            
            return min(max(final_accuracy, 0.3), 0.95)  # Between 30% and 95%
            
        except Exception as e:
            logger.error(f"Error calculating prediction accuracy: {e}")
            return 0.7  # Default accuracy


def main():
    """Main function for standalone testing"""
    print("🚀 Starting Ham Radio Conditions with Async Spots")
    
    reporter = HamRadioConditions()
    
    def update_report():
        report = reporter.generate_report()
        reporter.print_report(report)
        
        # Show spots status
        status = reporter.get_spots_status()
        print(f"\n📊 Spots Status:")
        print(f"   Loading: {status['loading']}")
        print(f"   Cached: {status['cached']}")
        print(f"   Source: {status['source']}")
        if status['cache_age']:
            print(f"   Cache Age: {status['cache_age']:.1f} seconds")

    # Generate initial report (won't hang on spots)
    print("📋 Generating initial report...")
    update_report()

    print("\n⏰ Running continuous updates. Press Ctrl+C to exit.")
    try:
        last_update = time.time()
        while True:
            current_time = time.time()
            # Update every hour
            if current_time - last_update >= 3600:  # 1 hour
                update_report()
                last_update = current_time
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")

if __name__ == "__main__":
    main()