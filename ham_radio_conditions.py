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

    def get_live_activity(self):
        """Fetch live activity data from multiple sources and combine results"""
        try:
            import telnetlib
            import re
            from datetime import datetime, timedelta
            
            # Cache key based on current time (rounded to nearest minute)
            cache_key = datetime.utcnow().replace(second=0, microsecond=0)
            
            # Check if we have cached data that's less than 5 minutes old
            if hasattr(self, '_spots_cache') and hasattr(self, '_spots_cache_time'):
                if (cache_key - self._spots_cache_time) < timedelta(minutes=5):
                    return self._spots_cache
            
            # Initialize sets for tracking unique spots
            all_spots = []
            active_bands = set()
            active_modes = set()
            active_dxcc = set()
            
            # Get spots from RBN
            rbn_spots = self._get_rbn_spots()
            if rbn_spots:
                all_spots.extend(rbn_spots)
            
            # Get spots from DX Cluster
            dx_spots = self._get_dxcluster_spots()
            if dx_spots:
                all_spots.extend(dx_spots)
            
            # Process all spots
            for spot in all_spots:
                active_bands.add(spot['band'])
                active_modes.add(spot['mode'])
                if spot.get('dxcc'):
                    active_dxcc.add(spot['dxcc'])
            
            # Sort spots by timestamp (most recent first)
            all_spots.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Limit to last 50 spots
            all_spots = all_spots[:50]
            
            # Create the response structure
            result = {
                'spots': all_spots,
                'summary': {
                    'total_spots': len(all_spots),
                    'active_bands': sorted(list(active_bands)),
                    'active_modes': sorted(list(active_modes)),
                    'active_dxcc': sorted(list(active_dxcc))
                }
            }
            
            # Cache the result
            self._spots_cache = result
            self._spots_cache_time = cache_key
            
            return result
            
        except Exception as e:
            print(f"Error fetching live activity: {e}")
            # Return cached data if available, otherwise return empty structure
            if hasattr(self, '_spots_cache'):
                return self._spots_cache
            return {
                'spots': [],
                'summary': {
                    'total_spots': 0,
                    'active_bands': [],
                    'active_modes': [],
                    'active_dxcc': []
                }
            }

    def _get_rbn_spots(self):
        """Fetch spots from Reverse Beacon Network"""
        try:
            import telnetlib
            import re
            from datetime import datetime
            
            # Connect to RBN
            tn = telnetlib.Telnet('telnet.reversebeacon.net', 7000, timeout=5)
            
            # Login process
            tn.read_until(b"login: ", timeout=5)
            tn.write(b"guest\n")
            tn.read_until(b"password: ", timeout=5)
            tn.write(b"\n")
            tn.read_until(b"Welcome to the Reverse Beacon Network", timeout=5)
            
            # Get recent spots
            tn.write(b"sh/dx on\n")
            response = tn.read_until(b"<CMD>", timeout=5).decode('utf-8', errors='ignore')
            tn.close()
            
            # Process spots
            spots = []
            spot_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) +(\d+\.\d+) +(\w+) +(\w+) +(\w+) +(.+)')
            
            for line in response.split('\n'):
                match = spot_pattern.search(line)
                if match:
                    try:
                        time_str, freq, mode, callsign, dxcc, comment = match.groups()
                        freq_float = float(freq)
                        
                        # Convert frequency to band
                        band = self._freq_to_band(freq_float)
                        
                        spot = {
                            'timestamp': time_str,
                            'callsign': callsign,
                            'frequency': freq,
                            'mode': mode,
                            'band': band,
                            'dxcc': dxcc,
                            'comment': comment.strip(),
                            'source': 'RBN'
                        }
                        spots.append(spot)
                    except Exception as spot_error:
                        print(f"Error processing RBN spot: {spot_error}")
                        continue
            
            return spots
            
        except Exception as e:
            print(f"Error fetching RBN spots: {e}")
            return []

    def _get_dxcluster_spots(self):
        """Get spots from DX Cluster servers with fallback."""
        # List of reliable public DX Cluster servers
        servers = [
            ('dxc.w1hkj.com', 7300),      # W1HKJ DX Cluster (US)
            ('dxc.ve7cc.net', 7300),      # VE7CC DX Cluster (Canada)
            ('dxc.kc4zvh.com', 7300),     # KC4ZVH DX Cluster (US)
            ('dxc.kc4zvh.com', 8000),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8001),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8002),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8003),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8004),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8005),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8006),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8007),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8008),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8009),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8010),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8011),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8012),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8013),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8014),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8015),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8016),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8017),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8018),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8019),     # KC4ZVH DX Cluster (alt port)
            ('dxc.kc4zvh.com', 8020),     # KC4ZVH DX Cluster (alt port)
        ]

        spots = []
        for host, port in servers:
            try:
                print(f"Trying DX Cluster server: {host}:{port}")
                # Connect to DX Cluster with a shorter timeout
                tn = telnetlib.Telnet(host, port, timeout=3)
                
                # Set page size and show DX spots
                tn.write(b"set/page 50\n")
                tn.write(b"show/dx\n")
                
                # Read response
                response = tn.read_until(b"\n", timeout=3).decode('utf-8', errors='ignore')
                spots_data = []
                
                # Read spots until we get a prompt or timeout
                while True:
                    try:
                        line = tn.read_until(b"\n", timeout=1).decode('utf-8', errors='ignore')
                        if not line or '>' in line:
                            break
                        spots_data.append(line.strip())
                    except (EOFError, ConnectionResetError):
                        break
                
                tn.close()
                
                # Process spots
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
                            'source': f'DX Cluster ({host})'
                        })
                
                if spots:
                    print(f"Successfully fetched {len(spots)} spots from {host}:{port}")
                    return spots
                    
            except (socket.gaierror, socket.timeout, ConnectionRefusedError) as e:
                print(f"Error connecting to {host}:{port}: {str(e)}")
                continue
            except Exception as e:
                print(f"Unexpected error with {host}:{port}: {str(e)}")
                continue
        
        print("All DX Cluster servers failed")
        return []

    def _freq_to_band(self, freq):
        """Convert frequency to band name"""
        if freq < 1.8:
            return '160m'
        elif freq < 3.5:
            return '80m'
        elif freq < 7.0:
            return '40m'
        elif freq < 10.1:
            return '30m'
        elif freq < 14.0:
            return '20m'
        elif freq < 18.068:
            return '17m'
        elif freq < 21.0:
            return '15m'
        elif freq < 24.89:
            return '12m'
        elif freq < 28.0:
            return '10m'
        elif freq < 50.0:
            return '6m'
        else:
            return 'VHF+'

    def generate_report(self):
        """Generate a comprehensive report of current conditions"""
        solar = self.get_solar_conditions()
        bands = self.get_band_conditions()
        weather = self.get_weather_conditions()
        dxcc = self.get_dxcc_conditions()
        live_activity = self.get_live_activity()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'location': self.grid_square,
            'callsign': self.callsign,
            'solar_conditions': solar,
            'band_conditions': bands,
            'weather_conditions': weather,
            'dxcc_conditions': dxcc,
            'live_activity': live_activity
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