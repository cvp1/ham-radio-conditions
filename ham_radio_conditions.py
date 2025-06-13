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
from dxcc_data import get_dxcc_info, get_dxcc_by_name, get_dxcc_by_continent, get_dxcc_by_grid
from flask import Flask, request, jsonify, render_template
import telnetlib
import re
import socket

# Load environment variables
load_dotenv()

class HamRadioConditions:
    def __init__(self, grid_square='DM41vv', temp_unit='F'):
        self.grid_square = grid_square
        self.temp_unit = temp_unit.upper()  # Store as uppercase
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
        self.lat, self.lon = self.grid_to_latlon(grid_square)
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.callsign = os.getenv('CALLSIGN', 'N/A')
        
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
            
            return lat, lon
        except Exception as e:
            print(f"Error converting grid square {grid_square}: {e}")
            # Fallback to DM41vv coordinates (approximately 40.0°N, 105.0°W)
            return 40.0, -105.0
        
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

    def get_dxcc_conditions(self):
        """Get DXCC information for the current location"""
        try:
            # Get the current DXCC entity based on the grid square
            current_dxcc = get_dxcc_by_grid(self.grid_square)
            
            # If we can't determine the current DXCC, use a default
            if not current_dxcc:
                current_dxcc = get_dxcc_info('110')  # Default to United States
            
            # Calculate actual ITU and CQ zones based on coordinates
            itu_zone = self.get_itu_zone(self.lat, self.lon)
            cq_zone = self.get_cq_zone(self.lat, self.lon)
            
            # Update the current DXCC with actual zones
            if current_dxcc:
                current_dxcc['itu_zone'] = itu_zone
                current_dxcc['cq_zone'] = cq_zone
            
            # Get nearby DXCC entities based on the current entity's continent
            nearby_dxcc = []
            if current_dxcc:
                # Get all entities in the same continent
                continent_entities = get_dxcc_by_continent(current_dxcc['continent'])
                # Filter out the current entity and limit to 5 nearby entities
                nearby_dxcc = [
                    entity for entity in continent_entities 
                    if entity.get('dxcc_number') != current_dxcc.get('dxcc_number')
                ][:5]
            
            # Filter out any None values from the nearby_dxcc list
            nearby_dxcc = [entity for entity in nearby_dxcc if entity is not None]
            
            return {
                'current_dxcc': current_dxcc,
                'nearby_dxcc': nearby_dxcc,
                'propagation_conditions': {
                    'best_bands': ['20m', '40m'],
                    'best_times': ['0000-0400 UTC', '1200-1600 UTC'],
                    'best_directions': ['Europe', 'Asia']
                }
            }
        except Exception as e:
            print(f"Error fetching DXCC conditions: {e}")
            return None

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

    def generate_report(self):
        """Generate a report of current conditions."""
        try:
            # Get solar conditions
            solar_conditions = self.get_solar_conditions()
            
            # Get band conditions
            band_conditions = self.get_band_conditions()
            
            # Get weather conditions
            weather_conditions = self.get_weather_conditions()
            
            # Get DXCC conditions
            dxcc_conditions = self.get_dxcc_conditions()
            
            # Generate timestamp
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            
            return {
                'timestamp': timestamp,
                'location': self.grid_square,
                'callsign': self.callsign,
                'solar_conditions': solar_conditions,
                'band_conditions': band_conditions,
                'weather_conditions': weather_conditions,
                'dxcc_conditions': dxcc_conditions
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
            
            if dxcc['current_dxcc']:
                print(f"\nCurrent DXCC Entity: {dxcc['current_dxcc']['name']}")
            
            if dxcc['nearby_dxcc']:
                print("\nNearby DXCC Entities:")
                nearby_data = [[d['name'], d['continent'], d['itu_zone'], d['cq_zone']] 
                             for d in dxcc['nearby_dxcc']]
                print(tabulate(nearby_data, 
                             headers=['Name', 'Continent', 'ITU Zone', 'CQ Zone'], 
                             tablefmt='grid'))
            
            if dxcc['propagation_conditions']:
                print("\nPropagation Conditions:")
                prop_data = [[k, v] for k, v in dxcc['propagation_conditions'].items()]
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