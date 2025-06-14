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
from flask import Flask, request, jsonify, render_template
import telnetlib
import re
import socket
from typing import Dict

# Load environment variables
load_dotenv()

class HamRadioConditions:
    def __init__(self, zip_code=None, temp_unit='F'):
        self.temp_unit = temp_unit.upper()  # Store as uppercase
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.callsign = os.getenv('CALLSIGN', 'N/A')
        
        # Get coordinates from ZIP code
        if zip_code:
            self.lat, self.lon = self.zip_to_latlon(zip_code)
            self.grid_square = self.latlon_to_grid(self.lat, self.lon)
        else:
            # Fallback to default location (DM41vv)
            self.grid_square = 'DM41vv'
            self.lat, self.lon = self.grid_to_latlon(self.grid_square)

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

    def _get_rbn_spots(self):
        """Get spots from Reverse Beacon Network."""
        try:
            print("Connecting to RBN...")
            # Connect to RBN
            tn = telnetlib.Telnet('telnet.reversebeacon.net', 7000, timeout=5)
            
            # Login as guest
            tn.read_until(b"login:", timeout=5)
            tn.write(b"guest\n")
            tn.read_until(b"password:", timeout=5)
            tn.write(b"guest\n")
            
            # Set page size and show spots
            tn.write(b"set/page 50\n")
            tn.write(b"show/dx\n")
            
            # Read response
            response = tn.read_until(b"\n", timeout=5).decode('utf-8', errors='ignore')
            spots_data = []
            
            # Read spots until we get a prompt or timeout
            while True:
                try:
                    line = tn.read_until(b"\n", timeout=2).decode('utf-8', errors='ignore')
                    if not line or '>' in line:
                        break
                    spots_data.append(line.strip())
                except (EOFError, ConnectionResetError):
                    break
            
            tn.close()
            
            # Process spots
            spots = []
            for spot in spots_data:
                # Parse spot data using regex
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (\d+\.\d+) (\w+) (\w+) (\w+) (.+)', spot)
                if match:
                    timestamp, callsign, freq, mode, band, dxcc, comment = match.groups()
                    spots.append({
                        'timestamp': timestamp,
                        'callsign': callsign,
                        'frequency': freq,
                        'mode': mode,
                        'band': band,
                        'dxcc': dxcc,
                        'comment': comment,
                        'source': 'RBN'
                    })
            
            if spots:
                print(f"Successfully fetched {len(spots)} spots from RBN")
                return spots
                
        except Exception as e:
            print(f"Error fetching RBN spots: {str(e)}")
        
        return []

    def get_live_activity(self):
        """Get live activity data from RBN."""
        try:
            # Try to get spots from RBN
            spots = self._get_rbn_spots()
            
            if not spots:
                print("No spots available from RBN")
                return {
                    'spots': [],
                    'summary': {
                        'total_spots': 0,
                        'active_bands': [],
                        'active_modes': [],
                        'active_dxcc': []
                    }
                }
            
            # Process spots to get summary
            bands = set()
            modes = set()
            dxcc_entities = set()
            
            for spot in spots:
                bands.add(spot['band'])
                modes.add(spot['mode'])
                dxcc_entities.add(spot['dxcc'])
            
            return {
                'spots': spots,
                'summary': {
                    'total_spots': len(spots),
                    'active_bands': sorted(list(bands)),
                    'active_modes': sorted(list(modes)),
                    'active_dxcc': sorted(list(dxcc_entities))
                }
            }
            
        except Exception as e:
            print(f"Error getting live activity: {e}")
            return {
                'spots': [],
                'summary': {
                    'total_spots': 0,
                    'active_bands': [],
                    'active_modes': [],
                    'active_dxcc': []
                }
            }

    def get_propagation_summary(self):
        """Generate a comprehensive propagation summary based on current conditions."""
        try:
            solar = self.get_solar_conditions()
            bands = self.get_band_conditions()
            
            # Get current time and calculate day/night status
            current_time = datetime.utcnow()
            sunrise, sunset = self._calculate_sunrise_sunset()
            is_daytime = sunrise <= current_time <= sunset
            
            # Calculate MUF (Maximum Usable Frequency)
            sfi = float(solar.get('sfi', '0').replace(' SFI', ''))
            muf = self._calculate_muf(sfi, is_daytime)
            
            # Determine best bands based on conditions
            best_bands = self._determine_best_bands(sfi, is_daytime, muf)
            
            # Get current band conditions
            current_band_conditions = {}
            for band, conditions in bands.items():
                current_band_conditions[band] = conditions['day'] if is_daytime else conditions['night']
            
            # Generate propagation summary
            summary = {
                'current_time': current_time.strftime('%H:%M UTC'),
                'day_night': 'Day' if is_daytime else 'Night',
                'sunrise': sunrise.strftime('%H:%M UTC'),
                'sunset': sunset.strftime('%H:%M UTC'),
                'solar_conditions': {
                    'sfi': solar.get('sfi', 'N/A'),
                    'a_index': solar.get('a_index', 'N/A'),
                    'k_index': solar.get('k_index', 'N/A'),
                    'aurora': solar.get('aurora', 'N/A')
                },
                'muf': f"{muf:.1f} MHz",
                'best_bands': best_bands,
                'band_conditions': current_band_conditions,
                'propagation_quality': self._calculate_propagation_quality(sfi, solar.get('k_index', '0')),
                'aurora_conditions': self._get_aurora_conditions(solar.get('aurora', '0')),
                'tropo_conditions': self._get_tropo_conditions(weather=self.get_weather_conditions())
            }
            
            return summary
        except Exception as e:
            print(f"Error generating propagation summary: {e}")
            return None

    def _calculate_sunrise_sunset(self):
        """Calculate sunrise and sunset times for the current location."""
        try:
            # Simple calculation based on latitude and time of year
            # This is a simplified version - in production, you'd want to use a proper astronomical library
            day_of_year = datetime.utcnow().timetuple().tm_yday
            lat_rad = math.radians(self.lat)
            
            # Approximate sunrise/sunset times
            sunrise_hour = 6 + (4 * math.sin(2 * math.pi * (day_of_year - 80) / 365))
            sunset_hour = 18 - (4 * math.sin(2 * math.pi * (day_of_year - 80) / 365))
            
            # Adjust for latitude
            sunrise_hour += (self.lat / 15) * 0.5
            sunset_hour += (self.lat / 15) * 0.5
            
            # Create datetime objects
            today = datetime.utcnow().date()
            sunrise = datetime.combine(today, datetime.min.time().replace(hour=int(sunrise_hour), minute=int((sunrise_hour % 1) * 60)))
            sunset = datetime.combine(today, datetime.min.time().replace(hour=int(sunset_hour), minute=int((sunset_hour % 1) * 60)))
            
            return sunrise, sunset
        except Exception as e:
            print(f"Error calculating sunrise/sunset: {e}")
            # Return default values
            return datetime.utcnow().replace(hour=6), datetime.utcnow().replace(hour=18)

    def _calculate_muf(self, sfi, is_daytime):
        """Calculate Maximum Usable Frequency based on SFI and time of day."""
        try:
            # Basic MUF calculation
            base_muf = 15.0  # Base MUF in MHz
            
            # Adjust for SFI
            sfi_factor = (sfi - 70) / 100  # Normalize SFI impact
            
            # Adjust for day/night
            time_factor = 1.5 if is_daytime else 0.5
            
            # Calculate final MUF
            muf = base_muf * (1 + sfi_factor) * time_factor
            
            return max(3.5, min(muf, 30.0))  # Limit between 3.5 and 30 MHz
        except Exception as e:
            print(f"Error calculating MUF: {e}")
            return 15.0  # Default MUF

    def _determine_best_bands(self, sfi, is_daytime, muf):
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
                if freq <= muf:
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

    def _calculate_propagation_quality(self, sfi, k_index):
        """Calculate overall propagation quality score."""
        try:
            # Convert k_index to number
            k = float(k_index.replace('K-Index: ', ''))
            
            # Calculate quality score (0-100)
            sfi_score = min(100, (sfi - 70) * 5)  # SFI impact
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

    def _get_aurora_conditions(self, aurora_level):
        """Get aurora conditions based on aurora level."""
        try:
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

    def _get_tropo_conditions(self, weather):
        """Get tropospheric conditions based on weather data."""
        if not weather:
            return "Weather data unavailable"
            
        try:
            # Check for favorable conditions
            temp = float(weather.get('temperature', '0').replace('°F', ''))
            humidity = float(weather.get('humidity', '0').replace('%', ''))
            
            if temp > 70 and humidity > 60:
                return "Favorable conditions for tropospheric propagation"
            elif temp > 60 and humidity > 50:
                return "Moderate conditions for tropospheric propagation"
            else:
                return "Poor conditions for tropospheric propagation"
        except Exception as e:
            print(f"Error getting tropo conditions: {e}")
            return "Unknown tropospheric conditions"

    def generate_report(self):
        """Generate a report of current conditions."""
        try:
            # Get all conditions
            solar = self.get_solar_conditions()
            bands = self.get_band_conditions()
            weather = self.get_weather_conditions()
            dxcc = self.get_dxcc_conditions(self.grid_square)
            propagation = self.get_propagation_summary()
            
            # Format location string
            location_str = f"{self.grid_square} ({self.lat:.4f}°N, {self.lon:.4f}°W)"
            if weather and 'city' in weather and 'state' in weather:
                location_str = f"{weather['city']}, {weather['state']} - {location_str}"
            
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'location': location_str,
                'callsign': self.callsign,
                'solar_conditions': solar,
                'band_conditions': bands,
                'weather_conditions': weather,
                'dxcc_conditions': dxcc,
                'propagation_summary': propagation
            }
        except Exception as e:
            print(f"Error generating report: {e}")
            return None

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
            
            # Print recent spots
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

app = Flask(__name__)

@app.route('/')
def index():
    reporter = HamRadioConditions()
    data = reporter.generate_report()
    return render_template('index.html', data=data)