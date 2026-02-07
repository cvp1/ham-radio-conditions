"""
Refactored Ham Radio Conditions - Main Application Class

This is a simplified, refactored version of the original HamRadioConditions class
that uses extracted data source and calculation modules.
"""

import os
import time
import math
from datetime import datetime
from typing import Dict, Optional, List
import logging
from dotenv import load_dotenv

# Import our refactored modules
from data_sources import SolarDataProvider, WeatherDataProvider, SpotsDataProvider, GeomagneticDataProvider, ActivationsDataProvider, ContestDataProvider
from calculations import MUFCalculator, PropagationCalculator, BandOptimizer, TimeAnalyzer
from utils.cache_manager import cache_get, cache_set, cache_clear
from utils.alerts import AlertsManager
from utils.geocoding import zip_to_coordinates, latlon_to_grid
from dxcc_data import get_dxcc_by_grid, grid_to_latlon as dxcc_grid_to_latlon

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Load environment variables
load_dotenv()


class HamRadioConditions:
    """Main class for ham radio conditions analysis."""
    
    def __init__(self, zip_code: Optional[str] = None):
        """Initialize the ham radio conditions system."""
        # Version information
        self.version = "2.1.0"
        self.build_date = "2024-12-19"
        self.changelog = {
            "2.1.0": {
                "date": "2024-12-19",
                "changes": [
                    "Refactored into modular architecture",
                    "Improved caching performance",
                    "Enhanced error handling"
                ]
            }
        }
        
        # Update checking
        self.last_update_check = 0
        self.update_check_interval = 3600  # 1 hour
        self.update_status = {
            'status': 'idle',
            'progress': 0,
            'message': ''
        }
        
        # Location setup
        self._setup_location(zip_code)
        
        # Initialize data providers
        self._initialize_data_providers()
        
        # Initialize calculators
        self._initialize_calculators()
        
        # Initialize state
        self._initialize_state()
        
        logger.info(f"HamRadioConditions initialized for {self.grid_square}")
    
    def _setup_location(self, zip_code: Optional[str]):
        """Setup location data from ZIP code."""
        if not zip_code:
            zip_code = "85630"  # Default to St. David, AZ

        # Convert ZIP to coordinates using geocoding
        location = zip_to_coordinates(zip_code)

        if location:
            self.zip_code = location['zip_code']
            self.lat = location['lat']
            self.lon = location['lon']
            self.grid_square = location['grid_square']
            self.timezone = location['timezone']
            self.city = location.get('city', 'Unknown')
            self.state = location.get('state', 'XX')
            self.location_source = location.get('source', 'unknown')
            logger.info(f"Location set to {self.city}, {self.state} ({self.grid_square})")
        else:
            # Fallback to defaults
            self.zip_code = zip_code
            self.lat = 31.8973
            self.lon = -110.2154
            self.grid_square = "DM41vv"
            self.timezone = "America/Phoenix"
            self.city = "St. David"
            self.state = "AZ"
            self.location_source = "fallback"
            logger.warning(f"Could not geocode ZIP {zip_code}, using defaults")

    def update_location(self, zip_code: str) -> Dict:
        """Update location from a new ZIP code."""
        old_zip = self.zip_code
        self._setup_location(zip_code)

        # Clear cached data since location changed
        cache_clear('conditions')
        cache_clear('weather')
        cache_clear('spots')

        # Reinitialize providers with new location
        self._initialize_data_providers()

        return {
            'success': True,
            'old_zip': old_zip,
            'new_zip': self.zip_code,
            'city': self.city,
            'state': self.state,
            'lat': self.lat,
            'lon': self.lon,
            'grid_square': self.grid_square,
            'timezone': self.timezone
        }
    
    def _initialize_data_providers(self):
        """Initialize data source providers."""
        self.solar_provider = SolarDataProvider()
        self.weather_provider = WeatherDataProvider(self.lat, self.lon)
        self.spots_provider = SpotsDataProvider(self.lat, self.lon, self.grid_square)
        self.geomagnetic_provider = GeomagneticDataProvider(self.lat, self.lon)
        self.activations_provider = ActivationsDataProvider()
        self.contest_provider = ContestDataProvider()
    
    def _initialize_calculators(self):
        """Initialize calculation utilities."""
        self.muf_calculator = MUFCalculator()
        self.propagation_calculator = PropagationCalculator()
        self.band_optimizer = BandOptimizer()
        self.time_analyzer = TimeAnalyzer()
        self.alerts_manager = AlertsManager()
    
    def _initialize_state(self):
        """Initialize application state."""
        self.callsign = os.getenv('CALLSIGN', 'N0CALL')
        self._prediction_confidence = {
            'solar_trend': 0.7,
            'propagation': 0.6,
            'band_quality': 0.5
        }
    
    def generate_report(self) -> Optional[Dict]:
        """Generate complete conditions report with caching."""
        try:
            # Try to get from cache first
            cached_report = cache_get('conditions', 'current')
            if cached_report:
                cached_report['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
                return cached_report
            
            # Generate new report
            report = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z'),
                'callsign': self.callsign,
                'location': {
                    'zip_code': self.zip_code,
                    'city': getattr(self, 'city', 'Unknown'),
                    'state': getattr(self, 'state', 'XX'),
                    'lat': self.lat,
                    'lon': self.lon,
                    'grid_square': self.grid_square,
                    'timezone': self.timezone
                },
                'solar_conditions': self.get_solar_conditions(),
                'weather_conditions': self.get_weather_conditions(),
                'band_conditions': self.get_band_conditions(),
                'propagation_summary': self.get_propagation_summary(),
                'live_activity': self.get_live_activity(),
                'activations': self.get_activations(),
                'contests': self.get_contests(),
                'alerts': self.get_alerts()
            }

            # Cache the report
            cache_set('conditions', 'current', report, max_age=600)  # 10 minutes
            logger.info("Generated and cached new conditions report")
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None
    
    def get_solar_conditions(self) -> Dict:
        """Get solar conditions from data provider."""
        return self.solar_provider.get_solar_conditions()
    
    def get_weather_conditions(self) -> Dict:
        """Get weather conditions from data provider."""
        return self.weather_provider.get_weather_conditions()
    
    def get_band_conditions(self) -> Dict:
        """Get band conditions using band optimizer."""
        try:
            solar_data = self.get_solar_conditions()
            weather_data = self.get_weather_conditions()
            time_data = self.time_analyzer.analyze_current_time(self.lat, self.timezone, self.lon)
            location_data = {'lat': self.lat, 'lon': self.lon}

            # Get MUF for band optimization
            muf_data = self.muf_calculator.calculate_muf(solar_data, location_data)
            muf = muf_data.get('muf', 15.0)

            return self.band_optimizer.optimize_bands(solar_data, weather_data, time_data, muf=muf)

        except Exception as e:
            logger.error(f"Error getting band conditions: {e}")
            return self._get_fallback_band_conditions()
    
    def get_propagation_summary(self) -> Dict:
        """Get propagation summary using calculators."""
        try:
            solar_data = self.get_solar_conditions()
            weather_data = self.get_weather_conditions()
            location_data = {
                'lat': self.lat,
                'lon': self.lon,
                'grid_square': self.grid_square
            }

            # Calculate MUF
            muf_data = self.muf_calculator.calculate_muf(solar_data, location_data)

            # Calculate propagation
            propagation_data = self.propagation_calculator.calculate_propagation(
                solar_data, weather_data, muf_data
            )

            # Get geomagnetic data
            geomagnetic_data = self.geomagnetic_provider.get_geomagnetic_coordinates()

            # Get time data for day/night status
            time_data = self.time_analyzer.analyze_current_time(self.lat, self.timezone, self.lon)

            # Format MUF as string for frontend compatibility
            muf_value = muf_data.get('muf', 15.0)
            muf_confidence = muf_data.get('confidence', 0.5)

            # Get solar cycle info
            solar_cycle_info = self._get_solar_cycle_info(solar_data)

            # Build band_conditions for frontend (day_rating / night_rating format)
            is_day = time_data.get('is_day', True)
            band_conditions_raw = self.get_band_conditions()
            band_conditions = {}
            raw_bands = band_conditions_raw.get('bands', band_conditions_raw) if isinstance(band_conditions_raw, dict) else {}
            for band_name, band_info in raw_bands.items():
                if isinstance(band_info, dict) and 'quality' in band_info:
                    quality = band_info['quality']
                    # Map quality to Good/Fair/Poor for ratings
                    rating = 'Good' if quality in ('Excellent', 'Very Good', 'Good') else quality
                    band_conditions[band_name] = {
                        'day_rating': rating if is_day else self._off_period_rating(rating),
                        'night_rating': rating if not is_day else self._off_period_rating(rating),
                    }

            return {
                'current_time': datetime.now().strftime('%I:%M %p %Z'),
                'day_night': 'Day' if is_day else 'Night',
                'propagation_parameters': {
                    'muf': f"{muf_value:.1f}",
                    'muf_source': muf_data.get('method', 'Traditional'),
                    'muf_confidence': f"{muf_confidence:.0%}" if muf_confidence >= 0.7 else f"{muf_confidence:.0%} ({muf_data.get('method', 'Estimated')})",
                    'quality': propagation_data.get('quality', 'Fair'),
                    'best_bands': propagation_data.get('best_bands', ['20m', '40m']),
                    'skip_distances': self._calculate_skip_distances(muf_value)
                },
                'band_conditions': band_conditions,
                'solar_cycle': solar_cycle_info,
                'geomagnetic_data': geomagnetic_data,
                'confidence': self._calculate_overall_confidence(muf_data, propagation_data)
            }

        except Exception as e:
            logger.error(f"Error generating propagation summary: {e}")
            return self._get_fallback_propagation_summary()
    
    def get_live_activity(self) -> Dict:
        """Get live activity from spots provider."""
        return self.spots_provider.get_live_activity()

    def get_activations(self) -> Dict:
        """Get POTA/SOTA activations."""
        try:
            return self.activations_provider.get_combined_activations()
        except Exception as e:
            logger.error(f"Error getting activations: {e}")
            return {'activations': [], 'total_count': 0, 'pota_count': 0, 'sota_count': 0, 'summary': {'total': 0, 'pota': 0, 'sota': 0}}

    def get_contests(self) -> Dict:
        """Get contest calendar data."""
        try:
            return self.contest_provider.get_contests()
        except Exception as e:
            logger.error(f"Error getting contests: {e}")
            return {'contests': [], 'active_count': 0, 'upcoming_count': 0}

    def get_alerts(self) -> list:
        """Get condition-based alerts."""
        try:
            solar_data = self.get_solar_conditions()
            time_data = self.time_analyzer.analyze_current_time(self.lat, self.timezone, self.lon)
            weather_data = self.get_weather_conditions()
            location_data = {'lat': self.lat, 'lon': self.lon}
            muf_data = self.muf_calculator.calculate_muf(solar_data, location_data)
            muf = muf_data.get('muf', 15.0)
            return self.alerts_manager.evaluate_conditions(solar_data, time_data, muf, weather_data)
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []

    def _calculate_overall_confidence(self, muf_data: Dict, propagation_data: Dict) -> float:
        """Calculate overall confidence in predictions."""
        muf_conf = muf_data.get('confidence', 0.5)
        prop_conf = propagation_data.get('confidence', 0.5)
        return (muf_conf + prop_conf) / 2

    def _calculate_skip_distances(self, muf: float) -> Dict:
        """Calculate skip distances per band based on MUF and F2 layer geometry."""
        EARTH_RADIUS = 6371  # km
        F2_HEIGHT = 300  # km, typical F2 layer height

        band_frequencies = {
            '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
            '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
            '10m': 28.0, '6m': 50.0
        }

        skip_distances = {}
        for band, freq in band_frequencies.items():
            if freq > muf:
                skip_distances[band] = 'No propagation'
                continue

            # Calculate skip distance using F2 layer reflection geometry
            # Critical angle: sin(ic) = freq / muf
            ratio = freq / muf
            if ratio >= 1.0:
                skip_distances[band] = 'No propagation'
                continue

            critical_angle = math.asin(ratio)

            # Skip distance = 2 * Earth_radius * arctan(cos(ic) * h / (R + h * sin(ic)))
            # Simplified: skip ≈ 2 * sqrt(2 * R * h) * cos(ic) for single hop
            skip_km = 2 * math.sqrt(2 * EARTH_RADIUS * F2_HEIGHT) * math.cos(critical_angle)
            max_single_hop = 2 * EARTH_RADIUS * math.acos(EARTH_RADIUS / (EARTH_RADIUS + F2_HEIGHT))

            skip_km = min(skip_km, max_single_hop)
            skip_distances[band] = f"{int(skip_km)} km"

        return skip_distances

    def _get_solar_cycle_info(self, solar_data: Dict) -> Dict:
        """Get solar cycle information derived from SFI."""
        try:
            # Extract SFI value
            sfi_str = str(solar_data.get('sfi', '100')).replace(' SFI', '').strip()
            sfi = float(sfi_str)
            sunspots = solar_data.get('sunspots', 'N/A')

            # Determine solar cycle phase based on SFI
            if sfi >= 150:
                phase = "Solar Maximum"
                prediction = "Excellent HF conditions expected across all bands"
                phase_description = "Peak solar activity with maximum ionization"
                cycle_position = "Peak (100%)"
            elif sfi >= 120:
                phase = "Rising Solar Maximum"
                prediction = "Very good HF conditions, optimal for 20m, 15m, 10m DX"
                phase_description = "Strong solar activity, F2 layer well developed"
                cycle_position = "Near Peak (85-95%)"
            elif sfi >= 100:
                phase = "Rising Phase"
                prediction = "Good HF conditions, favorable for 20m, 40m DX"
                phase_description = "Good solar activity, F2 layer active"
                cycle_position = "Rising (70-85%)"
            elif sfi >= 80:
                phase = "Early Rising Phase"
                prediction = "Fair conditions improving, focus on 40m, 80m"
                phase_description = "Moderate solar activity, F2 layer developing"
                cycle_position = "Early Rise (50-70%)"
            elif sfi >= 60:
                phase = "Solar Minimum"
                prediction = "Poor HF conditions, focus on lower bands (80m, 40m)"
                phase_description = "Low solar activity, limited F2 layer ionization"
                cycle_position = "Near Minimum (20-50%)"
            else:
                phase = "Deep Solar Minimum"
                prediction = "Very poor HF conditions, local contacts only"
                phase_description = "Minimal solar activity, F2 layer weak"
                cycle_position = "Minimum (0-20%)"

            # Determine SFI trend
            if sfi > 120:
                sfi_trend = "Strongly Rising"
                trend_description = "SFI > 120 indicates excellent solar activity"
            elif sfi > 100:
                sfi_trend = "Rising"
                trend_description = "SFI 100-120 shows very good conditions"
            elif sfi > 80:
                sfi_trend = "Stable"
                trend_description = "SFI 80-100 indicates stable conditions"
            else:
                sfi_trend = "Low"
                trend_description = "SFI < 80 shows reduced solar activity"

            return {
                'phase': phase,
                'prediction': prediction,
                'phase_description': phase_description,
                'cycle_position': cycle_position,
                'sfi_value': f"{sfi:.0f}",
                'sunspots': sunspots,
                'sfi_trend': sfi_trend,
                'trend_description': trend_description,
                'calculation_method': 'SFI-based solar cycle analysis'
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating solar cycle info: {e}")
            return {
                'phase': 'Unknown',
                'prediction': 'Unable to determine',
                'sfi_trend': 'Unknown'
            }
    
    @staticmethod
    def _off_period_rating(rating: str) -> str:
        """Downgrade a band rating for the off-period (day vs night)."""
        if rating in ('Excellent', 'Very Good', 'Good'):
            return 'Fair'
        return 'Poor'

    def _get_fallback_band_conditions(self) -> Dict:
        """Get fallback band conditions when calculation fails."""
        return {
            'bands': {
                '20m': {'quality': 'Good', 'notes': 'Primary band'},
                '40m': {'quality': 'Good', 'notes': 'Secondary band'},
                '80m': {'quality': 'Fair', 'notes': 'Night band'}
            },
            'confidence': 0.3,
            'source': 'Fallback'
        }
    
    def _get_fallback_propagation_summary(self) -> Dict:
        """Get fallback propagation summary when calculation fails."""
        return {
            'current_time': datetime.now().strftime('%I:%M %p %Z'),
            'day_night': 'Day',
            'propagation_parameters': {
                'muf': '15.0',
                'muf_source': 'Fallback',
                'muf_confidence': 'Low (Estimated)',
                'quality': 'Unknown',
                'best_bands': ['20m', '40m'],
                'skip_distances': {}
            },
            'solar_cycle': {
                'phase': 'Unknown',
                'prediction': 'Data unavailable',
                'sfi_trend': 'Unknown'
            },
            'confidence': 0.3,
            'source': 'Fallback'
        }
    
    def get_api_status(self) -> Dict:
        """Get status of external APIs and data sources."""
        status = {
            'timestamp': datetime.now().isoformat(),
            'apis': {},
            'data_collection': {
                'solar_conditions': 0, # Placeholder
                'propagation_quality': 0, # Placeholder
                'band_conditions': 0, # Placeholder
                'spots_activity': 0, # Placeholder
                'analysis_ready': True,
                'full_analysis_ready': True
            }
        }
        
        # Collect status from providers
        if hasattr(self.solar_provider, 'check_status'):
            solar_status = self.solar_provider.check_status()
            status['apis'].update(solar_status.get('sources', {}))
            
        if hasattr(self.spots_provider, 'check_status'):
            spots_status = self.spots_provider.check_status()
            status['apis'].update(spots_status.get('sources', {}))
            
        if hasattr(self.weather_provider, 'check_status'):
            weather_status = self.weather_provider.check_status()
            status['apis'].update(weather_status.get('sources', {}))
            
        return status

    def get_current_solar_conditions_debug(self) -> Dict:
        """Get debug information about solar conditions and MUF."""
        solar_data = self.get_solar_conditions()
        location_data = {'lat': self.lat, 'lon': self.lon}
        muf_data = self.muf_calculator.calculate_muf(solar_data, location_data)

        return {
            'solar_data': solar_data,
            'muf_calculation': {
                'muf': muf_data.get('muf'),
                'fof2': muf_data.get('fof2'),
                'method': muf_data.get('method'),
                'source': muf_data.get('source'),
                'station': muf_data.get('station'),
                'station_distance_km': muf_data.get('station_distance_km'),
                'confidence': muf_data.get('confidence'),
                'measurement_time': muf_data.get('measurement_time')
            },
            'timestamp': datetime.now().isoformat()
        }

    def get_location_debug_info(self) -> Dict:
        """Get debug information about location."""
        return {
            'lat': self.lat,
            'lon': self.lon,
            'grid': self.grid_square,
            'timestamp': datetime.now().isoformat()
        }

    @staticmethod
    def safe_json_serialize(obj):
        """Safely serialize an object to JSON."""
        import math

        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return "N/A"
            return obj
        elif isinstance(obj, dict):
            return {key: HamRadioConditions.safe_json_serialize(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [HamRadioConditions.safe_json_serialize(item) for item in obj]
        elif isinstance(obj, (int, str, bool, type(None))):
            return obj
        else:
            return str(obj)

    def get_version_info(self) -> Dict:
        """Get current version information."""
        return {
            'version': self.version,
            'build_date': self.build_date,
            'current_version': self.version,
            'latest_version': self.version,  # For now, same as current
            'update_available': False,
            'last_check': self.last_update_check
        }

    def check_for_updates(self, force_check: bool = False) -> Dict:
        """Check for available updates."""
        try:
            current_time = time.time()
            
            # Check if we should perform update check
            if (not force_check and 
                self.last_update_check and 
                current_time - self.last_update_check < self.update_check_interval):
                return self.get_version_info()
            
            self.last_update_check = current_time
            
            # Simulate update check (replace with actual logic if needed)
            return self.get_version_info()
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return self.get_version_info()

    def get_full_changelog(self) -> Dict:
        """Get complete changelog."""
        return self.changelog

    def mark_version_notified(self, version: str):
        """Mark a version as notified to the user."""
        # In a real app, this would store preference in DB
        pass

    def install_update(self, update_type: str = 'manual') -> Dict:
        """Install available updates."""
        self.update_status = {
            'status': 'installing',
            'progress': 0,
            'message': 'Starting update...'
        }
        return {'status': 'started', 'message': 'Update started'}

    def get_update_status(self) -> Dict:
        """Get current update installation status."""
        return self.update_status

    def print_report(self, report: Dict):
        """Print a formatted report."""
        if not report:
            print("❌ No report data available")
            return
        
        print("\n" + "="*60)
        print("📊 HAM RADIO CONDITIONS REPORT")
        print("="*60)
        
        # Solar conditions
        if 'solar_conditions' in report:
            solar = report['solar_conditions']
            print(f"☀️  Solar Flux: {solar.get('sfi', 'N/A')}")
            print(f"📡 K-Index: {solar.get('k_index', 'N/A')}")
            print(f"🌡️  A-Index: {solar.get('a_index', 'N/A')}")
        
        # Propagation summary
        if 'propagation_summary' in report:
            prop = report['propagation_summary']
            print(f"\n📈 MUF: {prop.get('muf', 'N/A')} MHz")
            print(f"🎯 Quality: {prop.get('propagation_quality', 'N/A')}")
            print(f"📻 Best Bands: {', '.join(prop.get('best_bands', []))}")
        
        print("="*60)


def main():
    """Main function for command-line usage."""
    print("🔧 Ham Radio Conditions - Refactored Version")
    print("=" * 60)
    
    # Get location from user
    zip_code = input("Enter your ZIP code (or press Enter for default): ").strip()
    if not zip_code:
        zip_code = "85630"  # Default to St. David, AZ
    
    print(f"📍 Location: {zip_code}")
    print("🔄 Initializing system...")
    
    # Create conditions instance
    hrc = HamRadioConditions(zip_code=zip_code)
    
    def update_report():
        """Update and display the report."""
        try:
            print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 60)
            
            # Generate report
            report = hrc.generate_report()
            
            if report:
                hrc.print_report(report)
            else:
                print("❌ Failed to generate report")
                
        except Exception as e:
            print(f"❌ Error updating report: {e}")
    
    # Generate initial report
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
