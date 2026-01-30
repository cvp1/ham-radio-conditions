"""
Spots data provider for ham radio conditions.

Handles fetching and processing spot data from various sources:
- PSKReporter
- Reverse Beacon Network (RBN)
- WSPRNet
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        self.wsprnet_url = "https://www.wsprnet.org/olddb"
    
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
        """Get PSKReporter spots - returns XML which we parse."""
        try:
            from bs4 import BeautifulSoup

            # PSKReporter API - get recent spots (last 15 minutes)
            params = {
                'flowStartSeconds': 900,  # Last 15 minutes
            }

            response = requests.get(self.pskreporter_url, params=params, timeout=8)

            if response.status_code != 200:
                logger.debug(f"PSKReporter returned status {response.status_code}")
                return None

            # Parse XML response
            soup = BeautifulSoup(response.text, 'lxml-xml')
            reports = soup.find_all('receptionReport')
            spots = []

            for report in reports[:100]:  # Limit to 100 spots
                try:
                    freq_hz = float(report.get('frequency', 0))
                    spot = {
                        'callsign': report.get('senderCallsign', ''),
                        'frequency': round(freq_hz / 1000000, 6),  # Convert Hz to MHz
                        'mode': report.get('mode', 'Unknown'),
                        'snr': int(report.get('sNR', 0)) if report.get('sNR') else 0,
                        'spotter': report.get('receiverCallsign', ''),
                        'spotter_grid': report.get('receiverLocator', ''),
                        'sender_grid': report.get('senderLocator', ''),
                        'dxcc': report.get('senderDXCC', ''),
                        'timestamp': report.get('flowStartSeconds', ''),
                        'source': 'PSKReporter'
                    }
                    if spot['callsign'] and spot['frequency'] > 0:
                        spots.append(spot)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Error parsing PSKReporter spot: {e}")
                    continue

            return {
                'spots': spots,
                'count': len(spots),
                'source': 'PSKReporter'
            }

        except ImportError:
            logger.debug("BeautifulSoup or lxml not available for PSKReporter XML parsing")
            return None
        except requests.exceptions.Timeout:
            logger.debug("PSKReporter request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"PSKReporter request error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error fetching PSKReporter data: {e}")
            return None

    def _get_rbn_spots(self) -> Optional[Dict]:
        """Get Reverse Beacon Network spots.

        Note: RBN's web API at /raw_data/ is for historical data downloads only.
        Live spots require telnet connection to telnet.reversebeacon.net:7000.
        For now, we rely on PSKReporter which includes many of the same digital mode spots.
        """
        # RBN web interface doesn't provide a simple live spots API
        # The raw_data page is for downloading historical ZIP files
        # Live access requires telnet connection which is more complex
        logger.debug("RBN spots skipped - requires telnet connection for live data")
        return None

    def _get_wsprnet_spots(self) -> Optional[Dict]:
        """Get WSPRNet spots from the olddb HTML interface."""
        try:
            from bs4 import BeautifulSoup

            # WSPRNet olddb endpoint returns HTML with spot data
            url = 'https://www.wsprnet.org/olddb'
            params = {
                'mode': 'html',
                'band': 'all',
                'limit': '100'
            }

            response = requests.get(url, params=params, timeout=8)

            if response.status_code != 200:
                logger.debug(f"WSPRNet returned status {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            spots = []

            # Find the spots table (third table on the page)
            tables = soup.find_all('table')
            if len(tables) < 3:
                logger.debug("WSPRNet spots table not found")
                return None

            spot_table = tables[2]
            rows = spot_table.find_all('tr')

            # Skip header rows (first 2 rows), parse data rows
            for row in rows[2:]:
                try:
                    cells = row.find_all('td')
                    if len(cells) >= 10:
                        # Columns: Date, Call, Frequency, SNR, Drift, Grid, dBm, W, by (reporter), loc (reporter grid), km
                        freq_str = cells[2].get_text(strip=True)
                        snr_str = cells[3].get_text(strip=True)
                        drift_str = cells[4].get_text(strip=True)
                        power_str = cells[7].get_text(strip=True) if len(cells) > 7 else '0'
                        distance_str = cells[10].get_text(strip=True) if len(cells) > 10 else '0'

                        spot = {
                            'callsign': cells[1].get_text(strip=True),
                            'frequency': float(freq_str) if freq_str else 0,
                            'mode': 'WSPR',
                            'snr': int(snr_str) if snr_str and snr_str.lstrip('-').isdigit() else 0,
                            'drift': int(drift_str) if drift_str and drift_str.lstrip('-').isdigit() else 0,
                            'sender_grid': cells[5].get_text(strip=True),
                            'power_dbm': cells[6].get_text(strip=True) if len(cells) > 6 else '',
                            'power_w': power_str,
                            'spotter': cells[8].get_text(strip=True) if len(cells) > 8 else '',
                            'spotter_grid': cells[9].get_text(strip=True) if len(cells) > 9 else '',
                            'distance_km': int(distance_str) if distance_str and distance_str.isdigit() else 0,
                            'timestamp': cells[0].get_text(strip=True),
                            'source': 'WSPRNet'
                        }
                        if spot['callsign'] and spot['frequency'] > 0:
                            spots.append(spot)
                except (ValueError, IndexError, AttributeError) as e:
                    logger.debug(f"Error parsing WSPRNet row: {e}")
                    continue

            return {
                'spots': spots,
                'count': len(spots),
                'source': 'WSPRNet'
            }

        except ImportError:
            logger.debug("BeautifulSoup not available for WSPRNet parsing")
            return None
        except requests.exceptions.Timeout:
            logger.debug("WSPRNet request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"WSPRNet request error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error fetching WSPRNet data: {e}")
            return None
    
    def _combine_spots_data(self, results: Dict) -> Dict:
        """Combine spots data from multiple sources with band activity analysis."""
        # Collect all spots
        all_spots = []
        for source_name, source_data in results.items():
            spots = source_data.get('spots', [])
            all_spots.extend(spots)

        # Analyze band activity
        band_activity = self._analyze_band_activity(all_spots)

        # Mode breakdown
        mode_counts = {}
        for spot in all_spots:
            mode = spot.get('mode', 'Unknown')
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

        # Count unique DXCC entities
        dxcc_set = set()
        for spot in all_spots:
            dxcc = spot.get('dxcc', '')
            if dxcc:
                dxcc_set.add(dxcc)

        # Count active bands (bands with spots)
        active_bands = sum(1 for band_data in band_activity.values() if band_data.get('count', 0) > 0)

        # Create summary for frontend
        summary = {
            'total_spots': len(all_spots),
            'active_bands': active_bands,
            'active_modes': len(mode_counts),
            'active_dxcc': len(dxcc_set)
        }

        combined = {
            'timestamp': datetime.now().isoformat(),
            'sources': list(results.keys()),
            'source_counts': {name: data.get('count', 0) for name, data in results.items()},
            'total_spots': len(all_spots),
            'summary': summary,
            'spots': sorted(all_spots, key=lambda x: x.get('frequency', 0), reverse=True)[:100],
            'band_activity': band_activity,
            'mode_breakdown': mode_counts,
            'confidence': 0.8 if len(results) >= 2 else 0.6
        }
        return combined

    def _analyze_band_activity(self, spots: List[Dict]) -> Dict:
        """Analyze spot activity by band."""
        # Band frequency ranges in MHz
        bands = {
            '160m': (1.8, 2.0),
            '80m': (3.5, 4.0),
            '60m': (5.3, 5.4),
            '40m': (7.0, 7.3),
            '30m': (10.1, 10.15),
            '20m': (14.0, 14.35),
            '17m': (18.068, 18.168),
            '15m': (21.0, 21.45),
            '12m': (24.89, 24.99),
            '10m': (28.0, 29.7),
            '6m': (50.0, 54.0)
        }

        activity = {}
        for band_name, (low, high) in bands.items():
            band_spots = [s for s in spots if low <= s.get('frequency', 0) <= high]
            if band_spots:
                avg_snr = sum(s.get('snr', 0) for s in band_spots) / len(band_spots)
                activity[band_name] = {
                    'count': len(band_spots),
                    'avg_snr': round(avg_snr, 1),
                    'modes': list(set(s.get('mode', 'Unknown') for s in band_spots))
                }
            else:
                activity[band_name] = {'count': 0, 'avg_snr': 0, 'modes': []}

        return activity
    
    def _get_fallback_spots_data(self) -> Dict:
        """Get fallback spots data when primary sources fail."""
        return {
            'timestamp': datetime.now().isoformat(),
            'sources': ['fallback'],
            'total_spots': 0,
            'summary': {
                'total_spots': 0,
                'active_bands': 0,
                'active_modes': 0,
                'active_dxcc': 0
            },
            'spots': [],
            'band_activity': {},
            'mode_breakdown': {},
            'confidence': 0.3
        }

    def check_status(self) -> Dict[str, Any]:
        """Check status of spots data sources."""
        status = {
            'status': 'online',
            'sources': {}
        }

        # Check PSKReporter
        try:
            response = requests.get(self.pskreporter_url, params={'flowStartSeconds': 60}, timeout=5)
            status['sources']['pskreporter'] = {
                'status': 'online' if response.status_code == 200 else 'error',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            status['sources']['pskreporter'] = {
                'status': 'offline',
                'error': str(e)
            }

        # Check WSPRNet
        try:
            response = requests.get(self.wsprnet_url, params={'mode': 'html', 'limit': '1'}, timeout=5)
            status['sources']['wsprnet'] = {
                'status': 'online' if response.status_code == 200 else 'error',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            status['sources']['wsprnet'] = {
                'status': 'offline',
                'error': str(e)
            }

        # RBN note - requires telnet for live spots
        status['sources']['rbn'] = {
            'status': 'unavailable',
            'note': 'RBN requires telnet connection for live spots'
        }

        return status
