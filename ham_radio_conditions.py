import os
import requests
from datetime import datetime, timedelta
from tabulate import tabulate
from dotenv import load_dotenv
import schedule
import time
import xml.etree.ElementTree as ET
import math
from dxcc_data import (
    get_dxcc_by_grid,
    get_nearby_dxcc,
    grid_to_latlon
)
from typing import Dict
import pytz
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from astral import LocationInfo
from astral.sun import sun
from utils.cache_manager import cache_get, cache_set, cache_delete

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
        
        # Get ZIP code from environment or parameter
        env_zip_code = os.getenv('ZIP_CODE')
        if zip_code:
            target_zip = zip_code
        elif env_zip_code:
            target_zip = env_zip_code
        else:
            target_zip = None
        
        # If ZIP code is provided, get coordinates and grid square
        if target_zip:
            try:
                lat, lon = self.zip_to_latlon(target_zip)
                if lat and lon:
                    self.lat = lat
                    self.lon = lon
                    self.grid_square = self.latlon_to_grid(lat, lon)
                    # Get timezone from coordinates
                    self.timezone = self._get_timezone_from_coords(lat, lon)
                    logger.info(f"Location set to ZIP {target_zip}: lat={lat}, lon={lon}, grid={self.grid_square}")
            except Exception as e:
                logger.error(f"Error initializing with ZIP code {target_zip}: {e}")
        
        # Start background spots loading
        self._start_background_spots_loading()

    def _start_background_spots_loading(self):
        """Start background thread to load spots without blocking"""
        def background_loader():
            """Background thread to continuously load spots"""
            while True:
                try:
                    self._load_spots_async()
                    time.sleep(300)  # Update every 5 minutes
                except Exception as e:
                    logger.error(f"Error in background spots loader: {e}")
                    time.sleep(60)  # Wait 1 minute on error
        
        thread = threading.Thread(target=background_loader, daemon=True)
        thread.start()
        logger.info("Background spots loader started")

    def _load_spots_async(self):
        """Load spots asynchronously with timeout"""
        try:
            logger.debug("Starting async spots load")
            future = self._executor.submit(self._get_spots_with_timeout)
            spots = future.result(timeout=30)  # 30 second max
            
            if spots and spots.get('summary', {}).get('total_spots', 0) > 0:
                # Cache the spots data
                cache_set('spots', 'current', spots, max_age=120)  # 2 minutes
                logger.info(f"Loaded {spots['summary']['total_spots']} spots from {spots['summary']['source']}")
            else:
                logger.debug("No spots loaded")
                
        except FuturesTimeoutError:
            logger.warning("Spots loading timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Error loading spots async: {e}")

    def _get_spots_with_timeout(self):
        """Get spots with timeout handling (thread-safe)"""
        try:
            # Try PSKReporter first, then fall back to test spots
            spots = self._get_pskreporter_spots_fast() or self._get_test_spots()
            return spots
            
        except Exception as e:
            logger.error(f"Error getting spots with timeout: {e}")
            return self._get_test_spots()

    def get_live_activity(self):
        """Get live activity with caching."""
        # Try to get from cache first
        cached_spots = cache_get('spots', 'current')
        if cached_spots:
            return cached_spots
        
        # If not in cache, load synchronously
        try:
            spots = self._get_spots_with_timeout()
            if spots:
                cache_set('spots', 'current', spots, max_age=120)
            return spots
        except Exception as e:
            logger.error(f"Error getting live activity: {e}")
            return None

    def get_live_activity_simple(self):
        """Get simplified live activity."""
        activity = self.get_live_activity()
        if activity and 'summary' in activity:
            return activity['summary']
        return {'total_spots': 0, 'source': 'None'}

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
            
            # Cache the report
            cache_set('conditions', 'current', report, max_age=300)  # 5 minutes
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
                cache_set('weather', 'current', weather, max_age=600)  # 10 minutes
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
            logger.debug("Trying PSKReporter API (fast)")
            
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
                logger.debug(f"PSKReporter API error: {response.status_code}")
                return None
            
            # Parse XML response
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.debug(f"PSKReporter XML parse error: {e}")
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
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Error parsing frequency '{raw_freq}': {e}")
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
                except Exception as e:
                    logger.debug(f"Error parsing PSKReporter spot: {e}")
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
            logger.debug("PSKReporter API timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"PSKReporter request error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.debug(f"PSKReporter HTTP status: {e.response.status_code}")
                if e.response.status_code == 503:
                    logger.info("PSKReporter service temporarily unavailable (503) - using fallback data")
                elif e.response.status_code == 429:
                    logger.info("PSKReporter rate limit exceeded (429) - using fallback data")
                else:
                    logger.info(f"PSKReporter HTTP error {e.response.status_code} - using fallback data")
            return None
        except Exception as e:
            logger.debug(f"PSKReporter error: {e}")
            return None

    def _get_test_spots(self):
        """Return test spots when real sources fail"""
        logger.debug("Using test spots")
        return {
            'spots': [
                {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'callsign': 'W1AW',
                    'frequency': '14.205',
                    'mode': 'SSB',
                    'spotter': 'N0CVP',
                    'comment': 'ARRL HQ Station',
                    'dxcc': '291',
                    'source': 'Test'
                },
                {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'callsign': 'VE1ABC',
                    'frequency': '7.155',
                    'mode': 'CW',
                    'spotter': 'W1ABC',
                    'comment': 'Strong signal',
                    'dxcc': '1',
                    'source': 'Test'
                },
                {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'callsign': 'K1ABC',
                    'frequency': '3.8',
                    'mode': 'SSB',
                    'spotter': 'W2XYZ',
                    'comment': 'Evening net',
                    'dxcc': '291',
                    'source': 'Test'
                },
                {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'callsign': 'G4ABC',
                    'frequency': '28.5',
                    'mode': 'SSB',
                    'spotter': 'W3DEF',
                    'comment': 'DX contact',
                    'dxcc': '223',
                    'source': 'Test'
                }
            ],
            'summary': {
                'total_spots': 4,
                'active_bands': ['20m', '40m', '80m', '10m'],
                'active_modes': ['SSB', 'CW'],
                'active_dxcc': ['291', '1', '223'],
                'source': 'Test Data'
            }
        }

    def get_solar_conditions(self):
        """Fetch current solar conditions from HamQSL XML feed"""
        try:
            response = requests.get('http://www.hamqsl.com/solarxml.php', timeout=10)
            root = ET.fromstring(response.content)
            
            # Find the solardata element
            solar_data = root.find('solardata')
            if solar_data is not None:
                return {
                    'sfi': solar_data.find('solarflux').text.strip() if solar_data.find('solarflux') is not None else 'N/A',
                    'a_index': solar_data.find('aindex').text.strip() if solar_data.find('aindex') is not None else 'N/A',
                    'k_index': solar_data.find('kindex').text.strip() if solar_data.find('kindex') is not None else 'N/A',
                    'xray': solar_data.find('xray').text.strip() if solar_data.find('xray') is not None else 'N/A',
                    'sunspots': solar_data.find('sunspots').text.strip() if solar_data.find('sunspots') is not None else 'N/A',
                    'proton_flux': solar_data.find('protonflux').text.strip() if solar_data.find('protonflux') is not None else 'N/A',
                    'electron_flux': solar_data.find('electonflux').text.strip() if solar_data.find('electonflux') is not None else 'N/A',
                    'aurora': solar_data.find('aurora').text.strip() if solar_data.find('aurora') is not None else 'N/A',
                    'updated': solar_data.find('updated').text.strip() if solar_data.find('updated') is not None else 'N/A'
                }
            return {'sfi': 'N/A', 'a_index': 'N/A', 'k_index': 'N/A', 'xray': 'N/A', 
                   'sunspots': 'N/A', 'proton_flux': 'N/A', 'electron_flux': 'N/A',
                   'aurora': 'N/A', 'updated': 'N/A'}
        except Exception as e:
            print(f"Error fetching solar conditions: {e}")
            return {'sfi': 'N/A', 'a_index': 'N/A', 'k_index': 'N/A', 'xray': 'N/A', 
                   'sunspots': 'N/A', 'proton_flux': 'N/A', 'electron_flux': 'N/A',
                   'aurora': 'N/A', 'updated': 'N/A'}

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

    def convert_temp(self, temp_c):
        """Convert temperature from Celsius to the configured unit"""
        if self.temp_unit == 'F':
            return round((temp_c * 9/5) + 32, 1)
        return round(temp_c, 1)

    def get_weather_from_openweather(self):
        """Get weather data from OpenWeather API"""
        if not self.openweather_api_key:
            print("OpenWeather API key not configured")
            return None

        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?lat={self.lat}&lon={self.lon}&appid={self.openweather_api_key}&units=metric"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'temperature': f"{self.convert_temp(data['main']['temp'])}°{self.temp_unit}",
                'humidity': f"{data['main']['humidity']}%",
                'pressure': f"{data['main']['pressure']} hPa",
                'description': data['weather'][0]['description'].capitalize(),
                'city': data['name'],
                'state': data.get('sys', {}).get('country', ''),
                'source': 'OpenWeather'
            }
        except Exception as e:
            print(f"Error fetching weather from OpenWeather: {str(e)}")
            return None

    def get_weather_from_nws(self):
        """Get weather data from National Weather Service API"""
        try:
            # First, get the grid endpoint
            points_url = f"https://api.weather.gov/points/{self.lat},{self.lon}"
            response = requests.get(points_url, headers={'User-Agent': 'HamRadioConditions/1.0'}, timeout=10)
            response.raise_for_status()
            grid_data = response.json()
            
            # Then get the forecast
            forecast_url = grid_data['properties']['forecast']
            response = requests.get(forecast_url, headers={'User-Agent': 'HamRadioConditions/1.0'}, timeout=10)
            response.raise_for_status()
            forecast_data = response.json()
            
            current = forecast_data['properties']['periods'][0]
            return {
                'temperature': f"{current['temperature']}°{self.temp_unit}",
                'humidity': f"{current['relativeHumidity']['value']}%",
                'pressure': f"{current['pressure']['value']} hPa",
                'description': current['shortForecast'],
                'city': grid_data['properties']['relativeLocation']['properties']['city'],
                'state': grid_data['properties']['relativeLocation']['properties']['state'],
                'source': 'National Weather Service'
            }
        except Exception as e:
            print(f"Error fetching weather from NWS: {str(e)}")
            return None

    def get_itu_zone(self, lat, lon):
        """Calculate ITU zone from latitude and longitude"""
        # ITU zones are numbered from 1 to 90, with 1 starting at 180°W
        # Each zone is 20° wide
        itu_zone = int((lon + 180) / 20) + 1
        return str(itu_zone)

    def get_cq_zone(self, lat, lon):
        """Calculate CQ zone from latitude and longitude"""
        # CQ zones are numbered from 1 to 40, with 1 starting at 180°W
        # Each zone is 10° wide
        cq_zone = int((lon + 180) / 10) + 1
        return str(cq_zone)

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

    def _calculate_muf(self, solar_data):
        """Calculate Maximum Usable Frequency (MUF) based on solar conditions."""
        try:
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            
            # Base MUF calculation based on solar flux
            if sfi >= 150:
                base_muf = 25 + (sfi - 150) * 0.1  # High solar activity
            elif sfi >= 100:
                base_muf = 15 + (sfi - 100) * 0.2  # Moderate solar activity
            elif sfi >= 70:
                base_muf = 10 + (sfi - 70) * 0.17  # Low solar activity
            else:
                base_muf = 5 + sfi * 0.07  # Very low solar activity
            
            # Adjust for geomagnetic activity
            if k_index > 5:
                base_muf *= 0.5  # Severe geomagnetic storm
            elif k_index > 3:
                base_muf *= 0.7  # Moderate geomagnetic activity
            elif k_index > 1:
                base_muf *= 0.9  # Slight geomagnetic activity
            
            return round(max(3, min(50, base_muf)), 1)  # Clamp between 3-50 MHz
        except Exception as e:
            logger.error(f"Error calculating MUF: {e}")
            return 15.0  # Default fallback

    def _determine_best_bands(self, solar_data, is_daytime):
        """Determine the best bands for current conditions."""
        try:
            muf = self._calculate_muf(solar_data)
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            
            # Define band frequencies
            bands = {
                '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
                '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
                '10m': 28.0, '6m': 50.0
            }
            
            # Filter bands based on MUF
            available_bands = [band for band, freq in bands.items() if freq <= muf * 1.2]
            
            # Prioritize bands based on conditions
            if k_index > 4:
                # High geomagnetic activity - prefer lower bands
                priority_bands = ['80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
            elif is_daytime:
                # Daytime - prefer higher bands
                priority_bands = ['20m', '15m', '12m', '10m', '6m', '17m', '30m', '40m', '80m']
            else:
                # Nighttime - prefer lower bands
                priority_bands = ['80m', '40m', '30m', '20m', '17m', '15m', '12m', '10m', '6m']
            
            # Return available bands in priority order
            return [band for band in priority_bands if band in available_bands][:5]
        except Exception as e:
            logger.error(f"Error determining best bands: {e}")
            return ['20m', '40m', '80m']  # Default fallback

    def _calculate_propagation_quality(self, solar_data, is_daytime):
        """Calculate overall propagation quality."""
        try:
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            a_index = float(solar_data.get('a_index', '0').replace('A-Index: ', ''))
            
            # Base quality score
            quality_score = 0
            
            # Solar flux contribution
            if sfi >= 150:
                quality_score += 40
            elif sfi >= 120:
                quality_score += 30
            elif sfi >= 100:
                quality_score += 20
            elif sfi >= 80:
                quality_score += 10
            else:
                quality_score += 0
            
            # Geomagnetic activity penalty
            if k_index <= 1:
                quality_score += 20
            elif k_index <= 2:
                quality_score += 15
            elif k_index <= 3:
                quality_score += 10
            elif k_index <= 4:
                quality_score += 5
            else:
                quality_score -= 20
            
            # A-index penalty
            if a_index <= 10:
                quality_score += 10
            elif a_index <= 20:
                quality_score += 5
            elif a_index <= 30:
                quality_score += 0
            else:
                quality_score -= 15
            
            # Time of day adjustment
            if is_daytime:
                quality_score += 10  # Daytime generally better for HF
            
            # Determine quality level
            if quality_score >= 70:
                return "Excellent"
            elif quality_score >= 50:
                return "Good"
            elif quality_score >= 30:
                return "Fair"
            elif quality_score >= 10:
                return "Poor"
            else:
                return "Very Poor"
        except Exception as e:
            logger.error(f"Error calculating propagation quality: {e}")
            return "Unknown"

    def _get_aurora_conditions(self, solar_data):
        """Get aurora conditions and their impact on propagation."""
        try:
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            a_index = float(solar_data.get('a_index', '0').replace('A-Index: ', ''))
            
            # Determine aurora activity level
            if k_index >= 6 or a_index >= 50:
                activity = "Strong"
                impact = "Severe HF propagation degradation"
                affected_bands = "All HF bands severely affected"
                recommendation = "Focus on VHF/UHF and local contacts"
            elif k_index >= 4 or a_index >= 30:
                activity = "Moderate"
                impact = "Significant HF propagation degradation"
                affected_bands = "Higher HF bands (15m, 12m, 10m) affected"
                recommendation = "Monitor conditions, focus on lower bands"
            elif k_index >= 2 or a_index >= 15:
                activity = "Weak"
                impact = "Minor HF propagation effects"
                affected_bands = "Some higher bands may be affected"
                recommendation = "Monitor auroral conditions"
            else:
                activity = "None"
                impact = "No auroral effects on propagation"
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
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
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
            
            # HamQSL band conditions based recommendations
            good_bands = []
            poor_bands = []
            for band_name, conditions in band_conditions.items():
                rating = conditions['day_rating'] if sun_info['is_day'] else conditions['night_rating']
                if rating == 'Good':
                    good_bands.append(band_name)
                elif rating == 'Poor':
                    poor_bands.append(band_name)
            
            if good_bands:
                if sun_info['is_day']:
                    recommendations.append(f"Good daytime conditions on: {', '.join(good_bands[:3])}")
                else:
                    recommendations.append(f"Good nighttime conditions on: {', '.join(good_bands[:3])}")
            if poor_bands:
                if sun_info['is_day']:
                    recommendations.append(f"Poor daytime conditions on: {', '.join(poor_bands[:3])} - avoid these bands")
                else:
                    recommendations.append(f"Poor nighttime conditions on: {', '.join(poor_bands[:3])} - avoid these bands")
            
            # Aurora-based recommendations
            if aurora_conditions['activity'] in ['Strong', 'Moderate']:
                recommendations.append(aurora_conditions['recommendation'])
            
            # Tropospheric recommendations
            if tropo_conditions['condition'] in ['Excellent', 'Good']:
                recommendations.append(tropo_conditions['recommendation'])
            
            # MUF-based recommendations
            if muf < 10:
                recommendations.append(f"Low MUF ({muf} MHz) - focus on 80m, 40m, and 30m")
            elif muf > 25:
                recommendations.append(f"High MUF ({muf} MHz) - excellent conditions for 20m, 15m, 10m")
            
            # Solar cycle recommendations
            if solar_cycle_info['phase'] == 'Solar Maximum':
                recommendations.append("Solar Maximum - excellent HF conditions across all bands")
            elif solar_cycle_info['phase'] == 'Solar Minimum':
                recommendations.append("Solar Minimum - focus on lower bands (80m, 40m)")
            
            # Propagation quality recommendations
            if propagation_quality in ['Poor', 'Very Poor']:
                recommendations.append("Poor propagation - focus on local contacts and lower bands")
            elif propagation_quality in ['Excellent', 'Good']:
                recommendations.append("Excellent conditions for DX and long-distance contacts")
            
            # Best bands recommendations (now based on HamQSL data)
            if best_bands:
                if sun_info['is_day']:
                    recommendations.append(f"Best daytime bands: {', '.join(best_bands[:3])}")
                else:
                    recommendations.append(f"Best nighttime bands: {', '.join(best_bands[:3])}")
            
            # Time-specific recommendations
            if sun_info['is_day']:
                recommendations.append("Daytime - F2 layer active, focus on 20m, 15m, 10m for DX")
            else:
                recommendations.append("Nighttime - D layer absent, focus on 80m, 40m for DX")
            
            # Location-specific recommendations
            if abs(self.lat) > 60:
                recommendations.append("High latitude location - monitor auroral conditions")
            elif abs(self.lat) < 30:
                recommendations.append("Low latitude - generally good propagation conditions")
            
            # Remove duplicates and limit to most important
            unique_recommendations = list(dict.fromkeys(recommendations))
            recommendations = unique_recommendations[:6]  # Limit to top 6 recommendations
            
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
                    'xray': solar_data.get('xray', 'N/A')
                },
                'solar_cycle': solar_cycle_info,
                'propagation_parameters': {
                    'muf': f"{muf} MHz",
                    'quality': propagation_quality,
                    'best_bands': best_bands,
                    'skip_distances': skip_distances
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
                    'key_factors': self._get_key_propagation_factors(solar_data, sun_info['is_day']),
                    'next_hours_outlook': self._get_hours_outlook(solar_data, sun_info['is_day'])
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
            location = LocationInfo("Location", "Region", "US", self.lat, self.lon)
            now_local = datetime.now(self.timezone)
            today = now_local.date()
            tomorrow = today + timedelta(days=1)
            
            # Get today's sunrise and sunset
            sun_today = sun(location.observer, date=today)
            sunrise_local = sun_today['sunrise'].astimezone(self.timezone)
            sunset_today_local = sun_today['sunset'].astimezone(self.timezone)
            
            # Get tomorrow's sunset
            sun_tomorrow = sun(location.observer, date=tomorrow)
            sunset_tomorrow_local = sun_tomorrow['sunset'].astimezone(self.timezone)

            # Use the next sunset after now
            if sunset_today_local > now_local:
                sunset_local = sunset_today_local
            else:
                sunset_local = sunset_tomorrow_local

            return {
                'sunrise': sunrise_local.strftime('%I:%M %p'),
                'sunset': sunset_local.strftime('%I:%M %p'),
                'is_day': sunrise_local <= now_local <= sunset_local
            }
        except Exception as e:
            print(f"Error calculating sunrise/sunset: {e}")
            return {
                'sunrise': 'N/A',
                'sunset': 'N/A',
                'is_day': True
            }

    def _get_key_propagation_factors(self, solar_data, is_daytime):
        """Get key factors affecting current propagation using HamQSL data."""
        try:
            factors = []
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            a_index = float(solar_data.get('a_index', '0').replace('A-Index: ', ''))
            
            # Get HamQSL band conditions
            hamqsl_bands = self.get_band_conditions()
            band_conditions = self._convert_hamqsl_to_individual_bands(hamqsl_bands)
            
            # Count HamQSL band conditions
            good_bands = []
            poor_bands = []
            for band_name, conditions in band_conditions.items():
                rating = conditions['day_rating'] if is_daytime else conditions['night_rating']
                if rating == 'Good':
                    good_bands.append(band_name)
                elif rating == 'Poor':
                    poor_bands.append(band_name)
            
            # HamQSL-based factors
            if good_bands:
                factors.append(f"Good conditions on: {', '.join(good_bands[:3])}")
            if poor_bands:
                factors.append(f"Poor conditions on: {', '.join(poor_bands[:3])}")
            
            # Solar factors
            if sfi < 70:
                factors.append("Low Solar Flux - higher bands limited")
            elif sfi > 150:
                factors.append("High Solar Flux - excellent HF conditions")
            
            if k_index > 4:
                factors.append(f"High K-index ({k_index}) - geomagnetic disturbance")
            
            if a_index > 20:
                factors.append(f"High A-index ({a_index}) - ionospheric instability")
            
            if is_daytime:
                factors.append("Daytime - F2 layer active")
            else:
                factors.append("Nighttime - D layer absent, E/F2 layers active")
            
            if abs(self.lat) > 60:
                factors.append("High latitude - auroral zone effects")
            
            return factors if factors else ["Normal propagation conditions"]
        except Exception as e:
            print(f"Error getting key factors: {e}")
            return ["Unknown conditions"]

    def _get_hours_outlook(self, solar_data, is_daytime):
        """Get outlook for next few hours with comprehensive analysis using HamQSL data."""
        try:
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            a_index = float(solar_data.get('a_index', '0').replace('A-Index: ', ''))
            
            # Get current hour for time-based predictions
            current_hour = datetime.now(self.timezone).hour
            
            # Get HamQSL band conditions to inform the outlook
            hamqsl_bands = self.get_band_conditions()
            band_conditions = self._convert_hamqsl_to_individual_bands(hamqsl_bands)
            propagation_quality = self._calculate_propagation_quality(solar_data, is_daytime)
            
            # Count bands by condition from HamQSL data
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
            
            # Geomagnetic storm conditions (highest priority)
            if k_index > 6:
                return "Severe geomagnetic storm - HF propagation severely degraded, focus on VHF/UHF and local contacts"
            elif k_index > 4 or a_index > 30:
                return "Geomagnetic storm conditions - expect degraded HF propagation, monitor conditions closely"
            elif k_index > 2 or a_index > 20:
                return "Elevated geomagnetic activity - some HF bands may be affected, focus on lower bands"
            
            # HamQSL-based outlook
            if good_bands >= 5:
                if is_daytime:
                    return "Excellent daytime conditions - multiple bands showing good propagation, ideal for DX"
                else:
                    return "Excellent nighttime conditions - multiple bands showing good propagation, great for long-distance contacts"
            elif good_bands >= 3:
                if is_daytime:
                    return "Good daytime conditions - several bands available for operation, favorable for DX"
                else:
                    return "Good nighttime conditions - several bands available for operation, good for regional contacts"
            elif good_bands >= 1:
                if is_daytime:
                    return "Fair daytime conditions - limited but usable bands available, focus on local and regional"
                else:
                    return "Fair nighttime conditions - limited but usable bands available, focus on local contacts"
            elif poor_bands >= 5:
                if is_daytime:
                    return "Poor daytime conditions - most bands degraded, focus on local contacts and VHF/UHF"
                else:
                    return "Poor nighttime conditions - most bands degraded, focus on local contacts and VHF/UHF"
            else:
                if is_daytime:
                    return "Mixed daytime conditions - check individual band ratings for specific opportunities"
                else:
                    return "Mixed nighttime conditions - check individual band ratings for specific opportunities"
            
        except Exception as e:
            print(f"Error getting outlook: {e}")
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
        """Get a proper location name based on coordinates"""
        try:
            # Use weather data if available to get city name
            weather = self.get_weather_conditions()
            if weather and weather.get('city'):
                return f"{weather['city']}, {weather.get('state', 'AZ')}"
            
            # Fallback to approximate location based on coordinates
            if 31.5 <= self.lat <= 32.5 and -111.0 <= self.lon <= -109.0:
                return "St. David, AZ"
            elif 31.0 <= self.lat <= 32.0 and -111.5 <= self.lon <= -110.5:
                return "Tucson Area, AZ"
            elif 33.0 <= self.lat <= 34.0 and -112.5 <= self.lon <= -111.5:
                return "Phoenix Area, AZ"
            else:
                return f"Grid {self.grid_square}"
        except Exception as e:
            logger.error(f"Error getting location name: {e}")
            return f"Grid {self.grid_square}"

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
            k_index = float(solar_data.get('k_index', '0').replace('K-Index: ', ''))
            a_index = float(solar_data.get('a_index', '0').replace('A-Index: ', ''))
            
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

    def zip_to_latlon(self, zip_code: str) -> tuple:
        """Convert ZIP code to latitude and longitude using geocoding service."""
        try:
            # Try to use OpenCage Geocoding API if available
            opencage_api_key = os.getenv('OPENCAGE_API_KEY')
            if opencage_api_key:
                url = "https://api.opencagedata.com/geocode/v1/json"
                params = {
                    'q': f"{zip_code}, USA",
                    'key': opencage_api_key,
                    'limit': 1
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data['results']:
                        result = data['results'][0]
                        lat = result['geometry']['lat']
                        lon = result['geometry']['lng']
                        logger.info(f"Geocoded ZIP {zip_code} to lat={lat}, lon={lon}")
                        return (lat, lon)
            
            # Fallback: Use a simple ZIP code database for common US ZIP codes
            # This is a limited fallback - in production, you'd want a comprehensive database
            zip_coords = {
                '90210': (34.1030, -118.4105),  # Beverly Hills, CA
                '10001': (40.7505, -73.9965),   # New York, NY
                '20001': (38.9097, -77.0169),   # Washington, DC
                '33101': (25.7743, -80.1937),   # Miami, FL
                '60601': (41.8857, -87.6228),   # Chicago, IL
                '77001': (29.7604, -95.3698),   # Houston, TX
                '85001': (33.4484, -112.0740),  # Phoenix, AZ
                '98101': (47.6062, -122.3321),  # Seattle, WA
                '80201': (39.7392, -104.9903),  # Denver, CO
                '02101': (42.3601, -71.0589),   # Boston, MA
                '85630': (31.9686, -110.7856),  # Sierra Vista, AZ
                '85701': (32.2226, -110.9747),  # Tucson, AZ
                '85001': (33.4484, -112.0740),  # Phoenix, AZ
                '85201': (33.4152, -111.8315),  # Mesa, AZ
                '85301': (33.4353, -112.3576),  # Glendale, AZ
                '85364': (33.5387, -112.1860),  # Peoria, AZ
                '85381': (33.5722, -112.0891),  # Sun City, AZ
                '85382': (33.6389, -112.1429),  # Sun City West, AZ
                '85383': (33.6389, -112.1429),  # Surprise, AZ
                '85396': (33.6389, -112.1429),  # Youngtown, AZ
            }
            
            if zip_code in zip_coords:
                lat, lon = zip_coords[zip_code]
                logger.info(f"Using fallback coordinates for ZIP {zip_code}: lat={lat}, lon={lon}")
                return (lat, lon)
            
            # If no match found, return default coordinates
            logger.warning(f"ZIP code {zip_code} not found in database, using default coordinates")
            return (34.0522, -118.2437)  # Default to Los Angeles
            
        except Exception as e:
            logger.error(f"Error converting ZIP {zip_code} to lat/lon: {e}")
            return (34.0522, -118.2437)  # Default to Los Angeles

    def update_location(self, zip_code: str) -> bool:
        """Update the location with a new ZIP code."""
        try:
            lat, lon = self.zip_to_latlon(zip_code)
            if lat and lon:
                self.lat = lat
                self.lon = lon
                self.grid_square = self.latlon_to_grid(lat, lon)
                self.timezone = self._get_timezone_from_coords(lat, lon)
                
                # Clear caches to force refresh with new location
                self.clear_cache()
                
                logger.info(f"Location updated to ZIP {zip_code}: lat={lat}, lon={lon}, grid={self.grid_square}")
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

    # Schedule updates every hour
    schedule.every(1).hours.do(update_report)

    print("\n⏰ Scheduled hourly updates. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")

if __name__ == "__main__":
    main()