"""
Spots data provider for ham radio conditions.

Handles fetching and processing spot data from various sources:
- PSKReporter
- Reverse Beacon Network (RBN)
- WSPRNet
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class SpotsDataProvider:
    """Provider for spot data from multiple sources."""
    
    def __init__(self, lat: float, lon: float, grid_square: str):
        self.lat = lat
        self.lon = lon
        self.grid_square = grid_square
        self.cache_duration = 300  # 5 minutes
        
        # Data sources
        self.pskreporter_url = "https://retrieve.pskreporter.info/query"
        self.rbn_url = "https://www.reversebeacon.net/raw_data/"
        self.wsprnet_urls = [
            "https://wsprnet.org/drupal/wsprnet/spots.json",
            "https://wsprnet.org/drupal/wsprnet/spots.json?callback=?"
        ]
    
    def get_live_activity(self) -> Dict:
        """Get live activity data with timeout handling."""
        try:
            # Try to get from cache first
            cached_spots = cache_get('spots', f'live_activity_{self.grid_square}')
            if cached_spots:
                return cached_spots
            
            # Fetch new spots data
            spots_data = self._fetch_spots_with_timeout()
            if spots_data:
                cache_set('spots', f'live_activity_{self.grid_square}', spots_data, self.cache_duration)
                return spots_data
            else:
                return self._get_fallback_spots_data()
                
        except Exception as e:
            logger.error(f"Error getting live activity: {e}")
            return self._get_fallback_spots_data()
    
    def _fetch_spots_with_timeout(self) -> Optional[Dict]:
        """Fetch spots data with timeout handling."""
        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Submit all data source tasks
                futures = {
                    executor.submit(self._get_pskreporter_spots): 'pskreporter',
                    executor.submit(self._get_rbn_spots): 'rbn',
                    executor.submit(self._get_wsprnet_spots): 'wsprnet'
                }
                
                results = {}
                timeout = 5  # 5 second timeout
                
                for future in as_completed(futures, timeout=timeout):
                    source = futures[future]
                    try:
                        result = future.result(timeout=2)
                        if result:
                            results[source] = result
                    except Exception as e:
                        logger.debug(f"Error fetching {source} data: {e}")
                
                if results:
                    return self._combine_spots_data(results)
                    
        except Exception as e:
            logger.debug(f"Error in spots fetching: {e}")
        
        return None
    
    def _get_pskreporter_spots(self) -> Optional[Dict]:
        """Get PSKReporter spots via their API."""
        try:
            # PSKReporter requires API key for full access
            # Use public query endpoint for basic data
            params = {
                'flowStartSeconds': 900,  # Last 15 minutes
                'rronly': 1,
                'noactive': 1,
            }
            # Note: Full implementation requires API key
            # Return structure for when data is available
            return {
                'source': 'pskreporter',
                'spots': [],
                'count': 0,
                'status': 'api_key_required'
            }
        except Exception as e:
            logger.debug(f"Error fetching PSKReporter data: {e}")
            return None

    def _get_rbn_spots(self) -> Optional[Dict]:
        """Get RBN (Reverse Beacon Network) spots."""
        try:
            # RBN provides telnet stream, not REST API
            # For web apps, use their aggregated data or third-party APIs
            # DXWatch or similar can provide RBN data
            return {
                'source': 'rbn',
                'spots': [],
                'count': 0,
                'status': 'telnet_stream_not_implemented'
            }
        except Exception as e:
            logger.debug(f"Error fetching RBN data: {e}")
            return None

    def _get_wsprnet_spots(self) -> Optional[Dict]:
        """Get WSPRNet spots."""
        try:
            # Try to fetch from WSPRNet
            response = requests.get(
                "https://wsprnet.org/drupal/wsprnet/spots/json",
                timeout=5,
                headers={'User-Agent': 'ham-radio-conditions/1.0'}
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    spots = data if isinstance(data, list) else []
                    return {
                        'source': 'wsprnet',
                        'spots': spots[:50],  # Limit to 50 most recent
                        'count': len(spots),
                        'status': 'ok'
                    }
                except ValueError:
                    pass

            return {
                'source': 'wsprnet',
                'spots': [],
                'count': 0,
                'status': 'fetch_failed'
            }
        except requests.Timeout:
            logger.debug("WSPRNet request timed out")
            return {
                'source': 'wsprnet',
                'spots': [],
                'count': 0,
                'status': 'timeout'
            }
        except Exception as e:
            logger.debug(f"Error fetching WSPRNet data: {e}")
            return None
    
    def _combine_spots_data(self, results: Dict) -> Dict:
        """Combine spots data from multiple sources."""
        total_spots = 0
        all_spots = []
        source_status = {}

        for source, data in results.items():
            if data:
                count = data.get('count', 0)
                total_spots += count
                all_spots.extend(data.get('spots', []))
                source_status[source] = {
                    'count': count,
                    'status': data.get('status', 'unknown')
                }

        # Analyze spots for band/mode activity
        band_activity = self._analyze_band_activity(all_spots)
        mode_activity = self._analyze_mode_activity(all_spots)

        combined = {
            'timestamp': datetime.now().isoformat(),
            'sources': source_status,
            'total_spots': total_spots,
            'spots': all_spots[:100],  # Limit to 100 spots
            'band_activity': band_activity,
            'mode_activity': mode_activity,
            'active_bands': len(band_activity),
            'active_modes': len(mode_activity)
        }
        return combined

    def _analyze_band_activity(self, spots: list) -> Dict:
        """Analyze spots for band activity."""
        bands = {}
        for spot in spots:
            freq = spot.get('frequency', spot.get('freq', 0))
            if freq:
                band = self._freq_to_band(float(freq) if isinstance(freq, str) else freq)
                if band:
                    bands[band] = bands.get(band, 0) + 1
        return bands

    def _analyze_mode_activity(self, spots: list) -> Dict:
        """Analyze spots for mode activity."""
        modes = {}
        for spot in spots:
            mode = spot.get('mode', 'unknown')
            modes[mode] = modes.get(mode, 0) + 1
        return modes

    def _freq_to_band(self, freq_mhz: float) -> Optional[str]:
        """Convert frequency in MHz to band name."""
        if 1.8 <= freq_mhz <= 2.0:
            return '160m'
        elif 3.5 <= freq_mhz <= 4.0:
            return '80m'
        elif 7.0 <= freq_mhz <= 7.3:
            return '40m'
        elif 10.1 <= freq_mhz <= 10.15:
            return '30m'
        elif 14.0 <= freq_mhz <= 14.35:
            return '20m'
        elif 18.068 <= freq_mhz <= 18.168:
            return '17m'
        elif 21.0 <= freq_mhz <= 21.45:
            return '15m'
        elif 24.89 <= freq_mhz <= 24.99:
            return '12m'
        elif 28.0 <= freq_mhz <= 29.7:
            return '10m'
        elif 50.0 <= freq_mhz <= 54.0:
            return '6m'
        return None
    
    def _get_fallback_spots_data(self) -> Dict:
        """Get fallback spots data when primary sources fail."""
        return {
            'timestamp': datetime.now().isoformat(),
            'sources': ['fallback'],
            'total_spots': 0,
            'data': {'fallback': {'spots': [], 'count': 0}},
            'confidence': 0.3
        }
