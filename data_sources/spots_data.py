"""
Spots data provider for ham radio conditions.

Handles fetching and processing spot data from various sources:
- PSKReporter
- Reverse Beacon Network (RBN)
- WSPRNet
"""

import requests
import xml.etree.ElementTree as ET
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
                timeout = 15  # 15 second timeout for all sources

                for future in as_completed(futures, timeout=timeout):
                    source = futures[future]
                    try:
                        result = future.result(timeout=5)
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
        """Get PSKReporter spots via their public query API."""
        try:
            params = {
                'flowStartSeconds': 900,  # Last 15 minutes
                'rronly': 1,
                'noactive': 1,
                'grid': self.grid_square[:4],
                'appcontact': 'ham-radio-conditions@github.com',
            }
            response = requests.get(
                self.pskreporter_url,
                params=params,
                timeout=10,
                headers={'User-Agent': 'ham-radio-conditions/1.0'}
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)
            spots = []
            # Find all receptionReport elements (handle potential XML namespaces)
            reports = root.findall('.//{*}receptionReport')
            if not reports:
                reports = root.findall('.//receptionReport')

            for report in reports[:50]:
                freq_hz = report.get('frequency', '0')
                try:
                    freq_mhz = float(freq_hz) / 1e6
                except (ValueError, TypeError):
                    freq_mhz = 0.0

                snr_val = report.get('sNR', '')
                try:
                    snr = int(snr_val)
                except (ValueError, TypeError):
                    snr = None

                # Extract timestamp from flowStartSeconds or senderDXCC
                spot_time = report.get('flowStartSeconds', '')
                if spot_time:
                    try:
                        spot_time = datetime.utcfromtimestamp(int(spot_time)).strftime('%Y-%m-%dT%H:%M:%SZ')
                    except (ValueError, TypeError, OSError):
                        spot_time = ''

                spot = {
                    'callsign': report.get('senderCallsign', ''),
                    'frequency': freq_mhz,
                    'mode': report.get('mode', ''),
                    'snr': snr,
                    'spotter': report.get('receiverCallsign', ''),
                    'time': spot_time,
                    'dxcc': report.get('senderDXCCCode', report.get('senderDXCC', '')),
                    'source': 'PSKReporter',
                    'comment': f"SNR: {snr}" if snr is not None else '',
                }
                spots.append(spot)

            return {
                'source': 'pskreporter',
                'spots': spots,
                'count': len(spots),
                'status': 'ok'
            }
        except Exception as e:
            logger.debug(f"Error fetching PSKReporter data: {e}")
            return None

    def _get_rbn_spots(self) -> Optional[Dict]:
        """Get RBN (Reverse Beacon Network) spots via HamQTH RBN API."""
        try:
            response = requests.get(
                'https://www.hamqth.com/rbn_data.php',
                params={
                    'data': 1,
                    'age': 900,  # Last 15 minutes
                    'order': 3,  # Sort by age
                },
                timeout=8,
                headers={
                    'User-Agent': 'ham-radio-conditions/1.0',
                    'Accept': 'application/json',
                }
            )
            response.raise_for_status()
            data = response.json()

            spots = []
            # HamQTH returns a dict with 'rbn' key containing spot list
            entries = data if isinstance(data, list) else data.get('rbn', data.get('spots', []))
            if isinstance(entries, dict):
                entries = list(entries.values()) if entries else []

            for entry in entries[:50]:
                snr_val = entry.get('snr', entry.get('db', ''))
                try:
                    snr = int(snr_val)
                except (ValueError, TypeError):
                    snr = None

                freq_val = entry.get('freq', entry.get('frequency', 0))
                try:
                    freq_mhz = float(freq_val) / 1000.0 if float(freq_val) > 1000 else float(freq_val)
                except (ValueError, TypeError):
                    freq_mhz = 0.0

                # Normalize RBN time (UTC) to ISO format
                rbn_time = entry.get('time', entry.get('ut', ''))
                if rbn_time and 'T' not in str(rbn_time):
                    # Bare HH:MM or HHMM — attach today's date and Z suffix
                    t = str(rbn_time).replace(':', '')
                    try:
                        hh, mm = int(t[:2]), int(t[2:4])
                        rbn_time = datetime.utcnow().strftime('%Y-%m-%d') + f'T{hh:02d}:{mm:02d}:00Z'
                    except (ValueError, IndexError):
                        pass

                spot = {
                    'callsign': entry.get('dx', entry.get('callsign', '')),
                    'frequency': freq_mhz,
                    'mode': entry.get('mode', entry.get('md', '')),
                    'snr': snr,
                    'spotter': entry.get('spotter', entry.get('de', '')),
                    'time': rbn_time,
                    'dxcc': entry.get('dxcc', ''),
                    'source': 'RBN',
                    'comment': f"{snr} dB" if snr is not None else '',
                }
                spots.append(spot)

            return {
                'source': 'rbn',
                'spots': spots,
                'count': len(spots),
                'status': 'ok'
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

        # Count unique DXCC entities
        dxcc_set = set()
        for spot in all_spots:
            dxcc = spot.get('dxcc', '')
            if dxcc:
                dxcc_set.add(str(dxcc))

        combined = {
            'timestamp': datetime.now().isoformat(),
            'sources': source_status,
            'total_spots': total_spots,
            'spots': all_spots[:100],  # Limit to 100 spots
            'band_activity': band_activity,
            'mode_activity': mode_activity,
            'active_bands': len(band_activity),
            'active_modes': len(mode_activity),
            'summary': {
                'total_spots': total_spots,
                'active_bands': len(band_activity),
                'active_modes': len(mode_activity),
                'active_dxcc': len(dxcc_set)
            }
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
