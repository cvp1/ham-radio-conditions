"""
Activations data provider for ham radio conditions.

Handles fetching POTA and SOTA activator data from public APIs:
- POTA: Parks on the Air (api.pota.app)
- SOTA: Summits on the Air (api2.sota.org.uk)
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class ActivationsDataProvider:
    """Provider for POTA and SOTA activation data."""

    def __init__(self):
        self.cache_duration = 180  # 3 minutes

    def get_combined_activations(self) -> Dict:
        """Get combined POTA and SOTA activations."""
        try:
            cached = cache_get('activations', 'combined')
            if cached:
                return cached

            results = {}
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(self.get_pota_spots): 'pota',
                    executor.submit(self.get_sota_spots): 'sota',
                }
                for future in as_completed(futures, timeout=12):
                    source = futures[future]
                    try:
                        result = future.result(timeout=5)
                        if result:
                            results[source] = result
                    except Exception as e:
                        logger.debug(f"Error fetching {source} activations: {e}")

            pota_list = results.get('pota', [])
            sota_list = results.get('sota', [])
            all_activations = pota_list + sota_list
            all_activations.sort(key=lambda x: x.get('time', ''), reverse=True)

            combined = {
                'timestamp': datetime.now().isoformat(),
                'pota_count': len(pota_list),
                'sota_count': len(sota_list),
                'total_count': len(all_activations),
                'activations': all_activations[:50],
                'summary': {
                    'total': len(all_activations),
                    'pota': len(pota_list),
                    'sota': len(sota_list),
                }
            }

            cache_set('activations', 'combined', combined, self.cache_duration)
            return combined

        except Exception as e:
            logger.error(f"Error getting combined activations: {e}")
            return self._get_fallback()

    def get_pota_spots(self) -> List[Dict]:
        """Get current POTA activator spots."""
        try:
            response = requests.get(
                'https://api.pota.app/spot/activator',
                timeout=8,
                headers={'User-Agent': 'ham-radio-conditions/1.0'}
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                return []

            spots = []
            for item in data[:50]:
                pota_time = item.get('spotTime', '')
                # Ensure UTC suffix for frontend conversion
                if pota_time and not pota_time.endswith('Z') and '+' not in pota_time:
                    pota_time = pota_time + 'Z'
                spots.append({
                    'time': pota_time,
                    'callsign': item.get('activator', ''),
                    'type': 'POTA',
                    'reference': item.get('reference', ''),
                    'name': item.get('name', item.get('locationDesc', '')),
                    'frequency': item.get('frequency', ''),
                    'mode': item.get('mode', ''),
                    'source': 'POTA',
                })
            return spots

        except Exception as e:
            logger.debug(f"Error fetching POTA spots: {e}")
            return []

    def get_sota_spots(self) -> List[Dict]:
        """Get current SOTA activator spots."""
        try:
            response = requests.get(
                'https://api2.sota.org.uk/api/spots/-1/all?limit=50',
                timeout=8,
                headers={
                    'User-Agent': 'ham-radio-conditions/1.0',
                    'Accept': 'application/json',
                }
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                return []

            spots = []
            for item in data[:50]:
                ref = item.get('associationCode', '')
                summit = item.get('summitCode', '')
                reference = f"{ref}/{summit}" if ref and summit else ref or summit

                sota_time = item.get('timeStamp', '')
                # Ensure UTC suffix for frontend conversion
                if sota_time and not sota_time.endswith('Z') and '+' not in sota_time:
                    sota_time = sota_time + 'Z'
                spots.append({
                    'time': sota_time,
                    'callsign': item.get('activatorCallsign', ''),
                    'type': 'SOTA',
                    'reference': reference,
                    'name': item.get('summitDetails', item.get('comments', '')),
                    'frequency': item.get('frequency', ''),
                    'mode': item.get('mode', ''),
                    'source': 'SOTA',
                })
            return spots

        except Exception as e:
            logger.debug(f"Error fetching SOTA spots: {e}")
            return []

    def _get_fallback(self) -> Dict:
        return {
            'timestamp': datetime.now().isoformat(),
            'pota_count': 0,
            'sota_count': 0,
            'total_count': 0,
            'activations': [],
            'summary': {'total': 0, 'pota': 0, 'sota': 0}
        }
