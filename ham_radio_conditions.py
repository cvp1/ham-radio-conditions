import os
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
from tabulate import tabulate
from dotenv import load_dotenv
import schedule
import time
import xml.etree.ElementTree as ET
import math
from dxcc_data import (
    get_dxcc_info,
    get_dxcc_by_name,
    get_dxcc_by_continent,
    get_dxcc_by_grid,
    get_nearby_dxcc,
    get_propagation_conditions
)
import telnetlib
import re
import socket
from typing import Dict
import pytz
import logging

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
        
        # If ZIP code is provided, get coordinates and grid square
        if zip_code:
            try:
                lat, lon = self.zip_to_latlon(zip_code)
                if lat and lon:
                    self.lat = lat
                    self.lon = lon
                    self.grid_square = self.latlon_to_grid(lat, lon)
                    # Get timezone from coordinates
                    self.timezone = self._get_timezone_from_coords(lat, lon)
            except Exception as e:
                print(f"Error initializing with ZIP code: {e}")

    def _get_timezone_from_coords(self, lat, lon):
        """Get timezone from coordinates using timezonefinder"""
        try:
            # Use a simple approximation based on longitude
            # Each 15 degrees of longitude represents roughly 1 hour
            hours_offset = round(lon / 15)
            if hours_offset >= 0:
                return pytz.timezone(f'Etc/GMT-{hours_offset}')
            else:
                return pytz.timezone(f'Etc/GMT+{abs(hours_offset)}')
        except Exception as e:
            print(f"Error getting timezone: {e}")
            return pytz.UTC

    def _calculate_sunrise_sunset(self):
        """Calculate sunrise and sunset times for the current location"""
        try:
            # Use a simple approximation for sunrise/sunset
            # This is a basic calculation and could be improved with more accurate algorithms
            now = datetime.now(self.timezone)
            sunrise = now.replace(hour=6, minute=0, second=0, microsecond=0)
            sunset = now.replace(hour=18, minute=0, second=0, microsecond=0)
            
            # Adjust for seasonal variations (simplified)
            day_of_year = now.timetuple().tm_yday
            seasonal_offset = math.sin((day_of_year - 80) * 2 * math.pi / 365) * 2  # 2 hours max variation
            
            sunrise = sunrise + timedelta(hours=seasonal_offset)
            sunset = sunset - timedelta(hours=seasonal_offset)
            
            return {
                'sunrise': sunrise.strftime('%I:%M %p'),
                'sunset': sunset.strftime('%I:%M %p'),
                'is_day': sunrise <= now <= sunset
            }
        except Exception as e:
            print(f"Error calculating sunrise/sunset: {e}")
            return {
                'sunrise': 'N/A',
                'sunset': 'N/A',
                'is_day': True
            }

    def get_propagation_summary(self):
        """Generate a comprehensive propagation summary"""
        try:
            # Get current time in local timezone
            now = datetime.now(self.timezone)
            current_time = now.strftime('%I:%M %p %Z')
            
            # Get sunrise/sunset information
            sun_info = self._calculate_sunrise_sunset()
            
            # Get solar conditions
            solar_data = self.get_solar_conditions()
            
            # Calculate MUF
            muf = self._calculate_muf(solar_data)
            
            # Determine best bands
            best_bands = self._determine_best_bands(solar_data, sun_info['is_day'])
            
            # Calculate propagation quality
            propagation_quality = self._calculate_propagation_quality(solar_data, sun_info['is_day'])
            
            # Get aurora conditions
            aurora_conditions = self._get_aurora_conditions(solar_data)
            
            # Get tropospheric conditions
            tropo_conditions = self._get_tropo_conditions()
            
            # Get band conditions
            band_conditions = self.get_band_conditions()
            
            return {
                'current_time': current_time,
                'day_night': 'Day' if sun_info['is_day'] else 'Night',
                'sunrise': sun_info['sunrise'],
                'sunset': sun_info['sunset'],
                'solar_conditions': {
                    'sfi': solar_data.get('sfi', 'N/A'),
                    'a_index': solar_data.get('a_index', 'N/A'),
                    'k_index': solar_data.get('k_index', 'N/A'),
                    'aurora': solar_data.get('aurora', 'N/A')
                },
                'muf': muf,
                'best_bands': best_bands,
                'propagation_quality': propagation_quality,
                'aurora_conditions': aurora_conditions,
                'tropo_conditions': tropo_conditions,
                'band_conditions': band_conditions
            }
        except Exception as e:
            logger.error(f"Error generating propagation summary: {e}")
            # Return a default structure instead of None
            return {
                'current_time': datetime.now(self.timezone).strftime('%I:%M %p %Z'),
                'day_night': 'Unknown',
                'sunrise': 'N/A',
                'sunset': 'N/A',
                'solar_conditions': {
                    'sfi': 'N/A',
                    'a_index': 'N/A',
                    'k_index': 'N/A',
                    'aurora': 'N/A'
                },
                'muf': 'N/A',
                'best_bands': ['Unknown'],
                'propagation_quality': 'Unknown',
                'aurora_conditions': 'Unknown',
                'tropo_conditions': 'Unknown',
                'band_conditions': {}
            }

    def grid_to_latlon(self, grid_square):
        """Convert Maidenhead grid square to latitude and longitude"""
        try:
            # Convert to uppercase and ensure we have at least 4 characters
            grid = grid_square.upper()[:4]
            
            # First two characters (A-R)
            lon = (ord(grid[0]) - ord('A')) * 20 - 180
            lat = (ord(grid[1]) - ord('A')) * 10 - 90
            
            # Next two characters (0-9)
            lon += (ord(grid[2]) - ord('0')) * 2
            lat += (ord(grid[3]) - ord('0'))
            
            # If we have 6 characters, add more precision
            if len(grid_square) >= 6:
                lon += (ord(grid_square[4].upper()) - ord('A')) * (2/24)
                lat += (ord(grid_square[5].upper()) - ord('A')) * (1/24)
            
            # Add half a grid square to center the coordinates
            lon += 1
            lat += 0.5
            
            return lat, lon
        except Exception as e:
            print(f"Error converting grid square {grid_square}: {e}")
            # Fallback to DM41vv coordinates (approximately 40.0°N, 105.0°W)
            return 40.0, -105.0

    def zip_to_latlon(self, zip_code):
        """Convert ZIP code to latitude and longitude using OpenWeather API"""
        if not self.openweather_api_key:
            print("OpenWeather API key not configured")
            return 40.0, -105.0  # Default to DM41vv coordinates

        try:
            url = f"http://api.openweathermap.org/geo/1.0/zip?zip={zip_code},US&appid={self.openweather_api_key}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return data['lat'], data['lon']
        except Exception as e:
            print(f"Error converting ZIP code {zip_code}: {e}")
            return 40.0, -105.0  # Default to DM41vv coordinates

    def latlon_to_grid(self, lat, lon):
        """Convert latitude and longitude to Maidenhead grid square"""
        try:
            # Normalize longitude to -180 to 180
            lon = ((lon + 180) % 360) - 180
            
            # Calculate first two characters (A-R)
            lon_field = int((lon + 180) / 20)
            lat_field = int((lat + 90) / 10)
            
            # Calculate next two characters (0-9)
            lon_square = int(((lon + 180) % 20) / 2)
            lat_square = int(((lat + 90) % 10))
            
            # Calculate last two characters (a-x)
            lon_sub = int((((lon + 180) % 20) % 2) * 12)
            lat_sub = int((((lat + 90) % 10) % 1) * 24)
            
            # Convert to characters
            grid = (
                chr(ord('A') + lon_field) +
                chr(ord('A') + lat_field) +
                str(lon_square) +
                str(lat_square) +
                chr(ord('a') + lon_sub) +
                chr(ord('a') + lat_sub)
            )
            
            return grid
        except Exception as e:
            print(f"Error converting lat/lon to grid square: {e}")
            return 'DM41vv'  # Default grid square

    def get_solar_conditions(self):
        """Fetch current solar conditions from HamQSL XML feed"""
        try:
            response = requests.get('http://www.hamqsl.com/solarxml.php')
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
            response = requests.get('http://www.hamqsl.com/solarxml.php')
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
            response = requests.get(url)
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
            response = requests.get(points_url, headers={'User-Agent': 'HamRadioConditions/1.0'})
            response.raise_for_status()
            grid_data = response.json()
            
            # Then get the forecast
            forecast_url = grid_data['properties']['forecast']
            response = requests.get(forecast_url, headers={'User-Agent': 'HamRadioConditions/1.0'})
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

    def get_weather_conditions(self):
        """Get weather conditions from OpenWeather or NWS"""
        # Try OpenWeather first
        weather_data = self.get_weather_from_openweather()
        
        # If OpenWeather fails, try NWS
        if not weather_data:
            weather_data = self.get_weather_from_nws()
        
        return weather_data

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
            
            # Get propagation conditions
            propagation = get_propagation_conditions(grid_square)
            
            return {
                'current': current_dxcc,
                'nearby': nearby_entities,
                'propagation': propagation
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
                'nearby': [],
                'propagation': {
                    'best_bands': [],
                    'best_times': [],
                    'best_directions': [],
                    'distance': 0
                }
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
        """Calculate Maximum Usable Frequency based on SFI and time of day."""
        try:
            # Basic MUF calculation
            base_muf = 15.0  # Base MUF in MHz
            
            # Adjust for SFI
            sfi = float(solar_data.get('sfi', '0').replace(' SFI', ''))
            sfi_factor = (sfi - 70) / 100  # Normalize SFI impact
            
            # Adjust for day/night
            sun_info = self._calculate_sunrise_sunset()
            time_factor = 1.5 if sun_info['is_day'] else 0.5
            
            # Calculate final MUF
            muf = base_muf * (1 + sfi_factor) * time_factor
            
            return max(3.5, min(muf, 30.0))  # Limit between 3.5 and 30 MHz
        except Exception as e:
            print(f"Error calculating MUF: {e}")
            return 15.0  # Default MUF

    def _determine_best_bands(self, solar_data, is_daytime):
        """Determine best bands based on current conditions."""
        try:
            best_bands = []
            
            # Define band frequencies
            bands = {
                '160m': 1.8,
                '80m': 3.5,
                '40m': 7.0,
                '20m': 14.0,
                '15m': 21.0,
                '10m': 28.0
            }
            
            # Add bands based on MUF
            for band, freq in bands.items():
                if freq <= self._calculate_muf(solar_data):
                    best_bands.append(band)
            
            # Prioritize bands based on time of day
            if is_daytime:
                best_bands = [b for b in best_bands if b in ['20m', '15m', '10m']]
            else:
                best_bands = [b for b in best_bands if b in ['160m', '80m', '40m']]
            
            return best_bands
        except Exception as e:
            print(f"Error determining best bands: {e}")
            return ['20m', '40m']  # Default bands

    def _calculate_propagation_quality(self, solar_data, is_daytime):
        """Calculate overall propagation quality score."""
        try:
            # Convert k_index to number
            k_index = solar_data.get('k_index', '0')
            k = float(k_index.replace('K-Index: ', ''))
            
            # Calculate quality score (0-100)
            sfi_score = min(100, (float(solar_data.get('sfi', '0').replace(' SFI', '')) - 70) * 5)  # SFI impact
            k_score = max(0, 100 - (k * 20))  # K-index impact
            
            # Combine scores
            quality = (sfi_score * 0.7 + k_score * 0.3)
            
            # Convert to descriptive rating
            if quality >= 80:
                return "Excellent"
            elif quality >= 60:
                return "Good"
            elif quality >= 40:
                return "Fair"
            else:
                return "Poor"
        except Exception as e:
            print(f"Error calculating propagation quality: {e}")
            return "Unknown"

    def _get_aurora_conditions(self, solar_data):
        """Get aurora conditions based on aurora level."""
        try:
            aurora_level = solar_data.get('aurora', '0')
            level = float(aurora_level.replace('Aurora: ', ''))
            if level >= 7:
                return "Strong aurora activity - HF propagation affected"
            elif level >= 5:
                return "Moderate aurora activity - Some HF bands affected"
            elif level >= 3:
                return "Light aurora activity - Minimal impact"
            else:
                return "No significant aurora activity"
        except Exception as e:
            print(f"Error getting aurora conditions: {e}")
            return "Unknown aurora conditions"

    def _get_tropo_conditions(self):
        """Get tropospheric conditions based on weather data"""
        try:
            weather = self.get_weather_conditions()
            if not weather:
                return "Unknown"
            
            # Simple tropospheric conditions based on weather
            if weather.get('clouds', 0) < 30:
                return "Excellent"
            elif weather.get('clouds', 0) < 70:
                return "Good"
            else:
                return "Poor"
        except Exception as e:
            logger.error(f"Error getting tropospheric conditions: {e}")
            return "Unknown"

    # NEW LIVE ACTIVITY METHODS ADDED HERE
    def get_live_activity(self):
        """Get live activity data from DXCluster spots"""
        try:
            print("🔍 Fetching live DX spots...")
            
            # Try multiple methods to get spots
            spots = self._get_dxsummit_spots() or self._get_dxwatch_spots() or self._get_telnet_spots()
            
            if not spots:
                print("⚠️ No spots available from any source")
                return {
                    'spots': [],
                    'summary': {
                        'total_spots': 0,
                        'active_bands': [],
                        'active_modes': [],
                        'active_dxcc': [],
                        'source': 'None - all sources failed'
                    }
                }
            
            # Process spots to get summary
            bands = set()
            modes = set()
            dxcc_entities = set()
            
            for spot in spots:
                if spot.get('band'):
                    bands.add(spot['band'])
                if spot.get('mode'):
                    modes.add(spot['mode'])
                if spot.get('dxcc'):
                    dxcc_entities.add(spot['dxcc'])
            
            summary = {
                'total_spots': len(spots),
                'active_bands': sorted(list(bands)),
                'active_modes': sorted(list(modes)),
                'active_dxcc': sorted(list(dxcc_entities))[:20],  # Limit to 20 for display
                'source': spots[0].get('source', 'Unknown') if spots else 'None'
            }
            
            print(f"✅ Retrieved {len(spots)} spots from {summary['source']}")
            
            return {
                'spots': spots[:50],  # Limit to 50 most recent spots
                'summary': summary
            }
            
        except Exception as e:
            print(f"❌ Error getting live activity: {e}")
            return {
                'spots': [],
                'summary': {
                    'total_spots': 0,
                    'active_bands': [],
                    'active_modes': [],
                    'active_dxcc': [],
                    'source': 'Error',
                    'error': str(e)
                }
            }
    
    def _get_dxsummit_spots(self):
        """Get spots from DXSummit.fi API"""
        try:
            print("📡 Trying DXSummit API...")
            
            url = "https://www.dxsummit.fi/api/v1/spots"
            params = {
                'limit': 50,
                'format': 'json'
            }
            
            headers = {
                'User-Agent': 'HamRadioConditions/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ DXSummit API error: {response.status_code}")
                return None
            
            data = response.json()
            
            if not isinstance(data, list):
                print(f"❌ DXSummit: Unexpected response format")
                return None
            
            spots = []
            for item in data:
                try:
                    spot = {
                        'timestamp': item.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        'callsign': item.get('dx', ''),
                        'frequency': str(item.get('freq', '')),
                        'spotter': item.get('de', ''),
                        'comment': item.get('comment', ''),
                        'mode': self._extract_mode_from_comment(item.get('comment', '')),
                        'band': self._freq_to_band(item.get('freq', 0)),
                        'dxcc': item.get('dxcc', ''),
                        'source': 'DXSummit'
                    }
                    spots.append(spot)
                except Exception as e:
                    print(f"⚠️ Error parsing DXSummit spot: {e}")
                    continue
            
            print(f"✅ DXSummit: Retrieved {len(spots)} spots")
            return spots
            
        except requests.exceptions.Timeout:
            print("⏰ DXSummit API timeout")
            return None
        except Exception as e:
            print(f"❌ DXSummit error: {e}")
            return None
    
    def _get_dxwatch_spots(self):
        """Get spots from DXWatch API"""
        try:
            print("📡 Trying DXWatch API...")
            
            url = "https://dxwatch.com/dxsd1/s.php"
            params = {
                't': 'dx',
                's': '0',
                'e': '50'
            }
            
            headers = {
                'User-Agent': 'HamRadioConditions/1.0',
                'Accept': 'text/plain'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ DXWatch API error: {response.status_code}")
                return None
            
            spots = []
            lines = response.text.strip().split('\n')
            
            for line in lines:
                try:
                    # Parse DXWatch format: freq dx spotter time comment
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    
                    freq = float(parts[0])
                    dx_call = parts[1]
                    spotter = parts[2]
                    time_str = parts[3]
                    comment = ' '.join(parts[4:]) if len(parts) > 4 else ''
                    
                    spot = {
                        'timestamp': time_str,
                        'callsign': dx_call,
                        'frequency': str(freq),
                        'spotter': spotter,
                        'comment': comment,
                        'mode': self._extract_mode_from_comment(comment),
                        'band': self._freq_to_band(freq),
                        'dxcc': '',
                        'source': 'DXWatch'
                    }
                    spots.append(spot)
                    
                except Exception as e:
                    print(f"⚠️ Error parsing DXWatch spot: {e}")
                    continue
            
            print(f"✅ DXWatch: Retrieved {len(spots)} spots")
            return spots
            
        except Exception as e:
            print(f"❌ DXWatch error: {e}")
            return None
    
    def _get_telnet_spots(self):
        """Get spots from DXCluster via telnet (fallback)"""
        try:
            print("📡 Trying DXCluster telnet...")
            
            # List of DXCluster nodes to try
            nodes = [
                ('dxc.nc7j.com', 23),
                ('cluster.w6cua.org', 23),
                ('w6yx.stanford.edu', 23)
            ]
            
            for host, port in nodes:
                try:
                    print(f"🔌 Connecting to {host}:{port}...")
                    
                    tn = telnetlib.Telnet(host, port, timeout=10)
                    
                    # Wait for login prompt
                    tn.read_until(b"login:", timeout=5)
                    tn.write(b"GUEST\n")
                    
                    # Send commands
                    tn.write(b"set/page 0\n")
                    tn.write(b"show/dx 30\n")
                    
                    # Read spots
                    spots_data = []
                    for _ in range(40):  # Read up to 40 lines
                        try:
                            line = tn.read_until(b"\n", timeout=2).decode('utf-8', errors='ignore').strip()
                            if not line or line.endswith('>'):
                                break
                            spots_data.append(line)
                        except:
                            break
                    
                    tn.close()
                    
                    # Parse spots
                    spots = []
                    for line in spots_data:
                        try:
                            # Parse DXCluster format: DX de CALL: freq DX info
                            match = re.match(r'DX de (\w+):\s+(\d+\.?\d*)\s+(\w+)\s+(.+)', line)
                            if match:
                                spotter, freq, dx_call, info = match.groups()
                                
                                spot = {
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'callsign': dx_call,
                                    'frequency': freq,
                                    'spotter': spotter,
                                    'comment': info,
                                    'mode': self._extract_mode_from_comment(info),
                                    'band': self._freq_to_band(float(freq)),
                                    'dxcc': '',
                                    'source': f'DXCluster-{host}'
                                }
                                spots.append(spot)
                        except Exception as e:
                            print(f"⚠️ Error parsing telnet spot: {e}")
                            continue
                    
                    if spots:
                        print(f"✅ DXCluster {host}: Retrieved {len(spots)} spots")
                        return spots
                    
                except Exception as e:
                    print(f"❌ Failed to connect to {host}: {e}")
                    continue
            
            print("❌ All DXCluster nodes failed")
            return None
            
        except Exception as e:
            print(f"❌ Telnet spots error: {e}")
            return None
    
    def _freq_to_band(self, freq):
        """Convert frequency to amateur radio band"""
        try:
            freq = float(freq)
            if 1800 <= freq <= 2000:
                return '160m'
            elif 3500 <= freq <= 4000:
                return '80m'
            elif 7000 <= freq <= 7300:
                return '40m'
            elif 10100 <= freq <= 10150:
                return '30m'
            elif 14000 <= freq <= 14350:
                return '20m'
            elif 18068 <= freq <= 18168:
                return '17m'
            elif 21000 <= freq <= 21450:
                return '15m'
            elif 24890 <= freq <= 24990:
                return '12m'
            elif 28000 <= freq <= 29700:
                return '10m'
            elif 50000 <= freq <= 54000:
                return '6m'
            elif 144000 <= freq <= 148000:
                return '2m'
            else:
                return 'Unknown'
        except:
            return 'Unknown'
    
    def _extract_mode_from_comment(self, comment):
        """Extract operating mode from spot comment"""
        if not comment:
            return 'Unknown'
        
        comment_upper = comment.upper()
        
        # Check for specific modes
        if 'FT8' in comment_upper:
            return 'FT8'
        elif 'FT4' in comment_upper:
            return 'FT4'
        elif 'CW' in comment_upper:
            return 'CW'
        elif any(mode in comment_upper for mode in ['SSB', 'LSB', 'USB', 'PHONE']):
            return 'SSB'
        elif 'RTTY' in comment_upper:
            return 'RTTY'
        elif 'PSK' in comment_upper:
            return 'PSK'
        elif 'JT65' in comment_upper:
            return 'JT65'
        elif 'JT9' in comment_upper:
            return 'JT9'
        elif 'MFSK' in comment_upper:
            return 'MFSK'
        elif 'OLIVIA' in comment_upper:
            return 'OLIVIA'
        elif 'CONTESTIA' in comment_upper:
            return 'CONTESTIA'
        elif any(mode in comment_upper for mode in ['DIGITAL', 'DATA']):
            return 'Digital'
        else:
            return 'Unknown'

    def generate_report(self):
        """Generate a comprehensive report of all conditions"""
        try:
            # Get current timestamp
            timestamp = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')
            
            # Get all condition data
            solar_conditions = self.get_solar_conditions()
            band_conditions = self.get_band_conditions()
            weather_conditions = self.get_weather_conditions()
            propagation_summary = self.get_propagation_summary()
            dxcc_conditions = self.get_dxcc_conditions(self.grid_square)
            
            # Add live activity data
            live_activity = self.get_live_activity()
            
            # Compile the report
            report = {
                'timestamp': timestamp,
                'location': f"{self.grid_square} ({self.lat:.4f}°N, {self.lon:.4f}°W)",
                'callsign': self.callsign,
                'solar_conditions': solar_conditions,
                'band_conditions': band_conditions,
                'weather_conditions': weather_conditions,
                'propagation_summary': propagation_summary,
                'dxcc_conditions': dxcc_conditions,
                'live_activity': live_activity
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            # Return a minimal report with error information
            return {
                'timestamp': datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z'),
                'location': f"{self.grid_square} ({self.lat:.4f}°N, {self.lon:.4f}°W)",
                'callsign': self.callsign,
                'error': str(e)
            }

    def print_report(self, report):
        """Print the report in a formatted table"""
        print("\n=== Ham Radio Conditions Report ===")
        print(f"Generated at: {report['timestamp']}")
        print(f"Location: {report['location']}\n")

        # Solar Conditions
        print("Solar Conditions:")
        solar_data = [[k, v] for k, v in report['solar_conditions'].items()]
        print(tabulate(solar_data, headers=['Parameter', 'Value'], tablefmt='grid'))
        print()

        # Band Conditions
        print("Band Conditions:")
        band_data = []
        for band, conditions in report['band_conditions'].items():
            if isinstance(conditions, dict):
                band_data.append([band, f"Day: {conditions.get('day', 'N/A')}", f"Night: {conditions.get('night', 'N/A')}"])
        print(tabulate(band_data, headers=['Band', 'Day Conditions', 'Night Conditions'], tablefmt='grid'))
        print()

        # Weather Conditions (only if available)
        if report['weather_conditions']:
            print(f"Weather Conditions (Source: {report['weather_conditions']['source']}):")
            weather_data = [[k, v] for k, v in report['weather_conditions'].items() if k != 'source']
            print(tabulate(weather_data, headers=['Parameter', 'Value'], tablefmt='grid'))
            print()
        else:
            print("Weather Conditions: Not available (both weather APIs failed)")
            print()

        # DXCC Conditions
        if report['dxcc_conditions']:
            print("DXCC Conditions:")
            dxcc = report['dxcc_conditions']
            
            if dxcc['current']:
                print(f"\nCurrent DXCC Entity: {dxcc['current']['name']}")
            
            if dxcc['nearby']:
                print("\nNearby DXCC Entities:")
                nearby_data = [[d['name'], d['continent'], d['itu_zone'], d['cq_zone']] 
                             for d in dxcc['nearby']]
                print(tabulate(nearby_data, 
                             headers=['Name', 'Continent', 'ITU Zone', 'CQ Zone'], 
                             tablefmt='grid'))
            
            if dxcc['propagation']:
                print("\nPropagation Conditions:")
                prop_data = [[k, v] for k, v in dxcc['propagation'].items()]
                print(tabulate(prop_data, headers=['Parameter', 'Value'], tablefmt='grid'))
            print()

        # Live Activity
        if report.get('live_activity'):
            print("\nLive Activity:")
            activity = report['live_activity']
            
            # Print summary
            print("\nActivity Summary:")
            summary = activity['summary']
            print(f"Total Spots: {summary['total_spots']}")
            print(f"Active Bands: {', '.join(summary['active_bands'])}")
            print(f"Active Modes: {', '.join(summary['active_modes'])}")
            print(f"Active DXCC Entities: {', '.join(summary['active_dxcc'])}")
            print(f"Source: {summary['source']}")
            
            # Print recent spots
            if activity['spots']:
                print("\nRecent Spots:")
                spots_data = []
                for spot in activity['spots'][:10]:  # Show last 10 spots
                    spots_data.append([
                        spot['callsign'],
                        spot['frequency'],
                        spot['mode'],
                        spot['band'],
                        spot['dxcc'],
                        spot['timestamp']
                    ])
                print(tabulate(spots_data, 
                             headers=['Callsign', 'Frequency', 'Mode', 'Band', 'DXCC', 'Time'],
                             tablefmt='grid'))
                print()
        else:
            print("\nLive Activity: Not available")
            print()


def main():
    reporter = HamRadioConditions()
    
    def update_report():
        report = reporter.generate_report()
        reporter.print_report(report)

    # Generate initial report
    update_report()

    # Schedule updates every hour
    schedule.every(1).hours.do(update_report)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()