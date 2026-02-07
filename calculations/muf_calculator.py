"""
MUF (Maximum Usable Frequency) calculator for ham radio conditions.

Calculates MUF using real ionosonde data when available, with formula-based
fallback. Validated against GIRO network measurements.
"""

import math
import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MUFCalculator:
    """Calculator for Maximum Usable Frequency (MUF).

    Uses real ionosonde data from GIRO network (via prop.kc2g.com) as primary
    source, with improved formula-based calculation as fallback.
    """

    IONOSONDE_API = "https://prop.kc2g.com/api/stations.json"
    IONOSONDE_CACHE_SECONDS = 300  # 5 minutes

    # Corrected coefficients based on ionosonde validation
    # Old values: FOF2_COEFFICIENT=0.4, M_FACTOR=0.85
    FOF2_COEFFICIENT = 0.75  # Validated against ionosonde data
    M_FACTOR_3000 = 3.0      # M-factor for 3000km path (typical range 2.5-4.0)

    def __init__(self):
        self.band_frequencies = {
            '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
            '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
            '10m': 28.0, '6m': 50.0
        }
        self._ionosonde_cache = None
        self._ionosonde_cache_time = None

    def calculate_muf(self, solar_data: Dict, location_data: Dict) -> Dict:
        """Calculate MUF using ionosonde data or formula fallback.

        Args:
            solar_data: Dict with 'sfi', 'k_index', 'a_index'
            location_data: Dict with 'lat', 'lon' for finding nearest station

        Returns:
            Dict with MUF data including source and confidence
        """
        try:
            sfi = self._extract_sfi(solar_data)
            lat = location_data.get('lat', 40.0)
            lon = location_data.get('lon', -100.0)

            # Try ionosonde data first
            ionosonde_result = self._get_ionosonde_muf(lat, lon)

            if ionosonde_result:
                return {
                    'muf': ionosonde_result['muf'],
                    'fof2': ionosonde_result['fof2'],
                    'traditional_muf': self._calculate_formula_muf(sfi),
                    'enhanced_muf': ionosonde_result['muf'],
                    'sfi': sfi,
                    'confidence': ionosonde_result['confidence'],
                    'method': 'Ionosonde',
                    'source': ionosonde_result['source'],
                    'station': ionosonde_result['station'],
                    'station_distance_km': ionosonde_result['distance_km'],
                    'measurement_time': ionosonde_result['timestamp']
                }

            # Fallback to formula-based calculation
            formula_muf = self._calculate_enhanced_muf(solar_data, location_data)
            formula_fof2 = self.FOF2_COEFFICIENT * math.sqrt(sfi)

            return {
                'muf': formula_muf,
                'fof2': round(formula_fof2, 2),
                'traditional_muf': self._calculate_formula_muf(sfi),
                'enhanced_muf': formula_muf,
                'sfi': sfi,
                'confidence': self._calculate_muf_confidence(formula_muf, sfi),
                'method': 'Formula (ionosonde unavailable)'
            }

        except Exception as e:
            logger.error(f"Error calculating MUF: {e}")
            return self._get_fallback_muf()

    def _get_ionosonde_muf(self, lat: float, lon: float) -> Optional[Dict]:
        """Get MUF from nearest ionosonde station."""
        try:
            stations = self._fetch_ionosonde_data()
            if not stations:
                return None

            # Find nearest station with valid data
            nearest = self._find_nearest_station(stations, lat, lon)
            if not nearest:
                return None

            # Calculate confidence based on distance and measurement confidence
            distance_km = nearest['distance_km']
            station_confidence = nearest['confidence'] / 100.0

            # Reduce confidence for distant stations (>2000km = lower confidence)
            distance_factor = max(0.5, 1.0 - (distance_km / 4000.0))
            overall_confidence = station_confidence * distance_factor

            return {
                'muf': nearest['mufd'],
                'fof2': nearest['fof2'],
                'station': nearest['name'],
                'distance_km': round(distance_km, 0),
                'confidence': round(overall_confidence, 2),
                'timestamp': nearest['timestamp'],
                'source': f"GIRO ({nearest['source']})"
            }

        except Exception as e:
            logger.debug(f"Failed to get ionosonde MUF: {e}")
            return None

    def _fetch_ionosonde_data(self) -> List[Dict]:
        """Fetch ionosonde data with caching."""
        now = datetime.now()

        # Return cached data if fresh
        if (self._ionosonde_cache is not None and
            self._ionosonde_cache_time is not None and
            (now - self._ionosonde_cache_time).total_seconds() < self.IONOSONDE_CACHE_SECONDS):
            return self._ionosonde_cache

        try:
            req = urllib.request.Request(
                self.IONOSONDE_API,
                headers={'User-Agent': 'ham-radio-conditions/1.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Filter for valid recent measurements
            valid_stations = []
            cutoff_time = now - timedelta(hours=2)

            for station in data:
                if not station.get('fof2') or not station.get('mufd'):
                    continue

                cs = station.get('cs', 0)
                if cs < 25:  # Skip very low confidence
                    continue

                time_str = station.get('time', '')
                try:
                    measurement_time = datetime.fromisoformat(
                        time_str.replace('Z', '+00:00')
                    )
                    if measurement_time.replace(tzinfo=None) < cutoff_time:
                        continue
                except (ValueError, TypeError):
                    continue

                valid_stations.append({
                    'name': station.get('station', {}).get('name', 'Unknown'),
                    'code': station.get('station', {}).get('code', ''),
                    'lat': float(station.get('station', {}).get('latitude', 0)),
                    'lon': float(station.get('station', {}).get('longitude', 0)),
                    'fof2': float(station['fof2']),
                    'mufd': float(station['mufd']),
                    'md': float(station.get('md', 3.0)),
                    'confidence': cs,
                    'timestamp': time_str,
                    'source': station.get('source', 'giro')
                })

            self._ionosonde_cache = valid_stations
            self._ionosonde_cache_time = now
            return valid_stations

        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            logger.debug(f"Failed to fetch ionosonde data: {e}")
            return self._ionosonde_cache or []

    def _find_nearest_station(self, stations: List[Dict], lat: float, lon: float) -> Optional[Dict]:
        """Find the nearest ionosonde station to given coordinates."""
        if not stations:
            return None

        # Normalize longitude to 0-360 for comparison (ionosonde data uses this)
        if lon < 0:
            lon_normalized = lon + 360
        else:
            lon_normalized = lon

        nearest = None
        min_distance = float('inf')

        for station in stations:
            station_lat = station['lat']
            station_lon = station['lon']

            # Calculate approximate distance in km
            distance = self._haversine_distance(lat, lon_normalized, station_lat, station_lon)

            if distance < min_distance:
                min_distance = distance
                nearest = station.copy()
                nearest['distance_km'] = distance

        return nearest

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km."""
        R = 6371  # Earth's radius in km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _calculate_formula_muf(self, sfi: float) -> float:
        """Calculate MUF using corrected formula.

        Uses validated coefficients:
        - foF2 = 0.75 * sqrt(SFI)
        - MUF(3000) = 3.0 * foF2
        """
        foF2 = self.FOF2_COEFFICIENT * math.sqrt(sfi)
        muf = self.M_FACTOR_3000 * foF2
        return round(muf, 2)

    def _calculate_enhanced_muf(self, solar_data: Dict, location_data: Dict) -> float:
        """Calculate enhanced MUF with geomagnetic adjustments."""
        try:
            sfi = self._extract_sfi(solar_data)
            k_index = self._extract_k_index(solar_data)
            a_index = self._extract_a_index(solar_data)

            # Base foF2 with corrected coefficient
            foF2 = self.FOF2_COEFFICIENT * math.sqrt(sfi)

            # Apply geomagnetic adjustments
            # K-index: 5% reduction per point above 2
            k_adjustment = 1.0 - max(0, (k_index - 2) * 0.05)

            # A-index: 1% reduction per point above 10
            a_adjustment = 1.0 - max(0, (a_index - 10) * 0.01)

            # Ensure adjustments don't go below 0.5
            k_adjustment = max(0.5, k_adjustment)
            a_adjustment = max(0.5, a_adjustment)

            # Calculate adjusted foF2
            adjusted_foF2 = foF2 * k_adjustment * a_adjustment

            # Apply M-factor for 3000km path
            muf = self.M_FACTOR_3000 * adjusted_foF2

            # Apply seasonal adjustment
            lat = location_data.get('lat', 40.0)
            muf = self._apply_seasonal_adjustment(muf, lat)

            return round(muf, 2)

        except Exception as e:
            logger.error(f"Error in enhanced MUF calculation: {e}")
            return self._calculate_formula_muf(self._extract_sfi(solar_data))

    def _extract_sfi(self, solar_data: Dict) -> float:
        """Extract solar flux index from solar data."""
        try:
            sfi_str = solar_data.get('sfi', '100 SFI')
            sfi_str = str(sfi_str).replace(' SFI', '').strip()
            return float(sfi_str)
        except (ValueError, TypeError):
            return 100.0

    def _extract_k_index(self, solar_data: Dict) -> float:
        """Extract K-index from solar data."""
        try:
            k_str = solar_data.get('k_index', '2')
            return float(k_str)
        except (ValueError, TypeError):
            return 2.0

    def _extract_a_index(self, solar_data: Dict) -> float:
        """Extract A-index from solar data."""
        try:
            a_str = solar_data.get('a_index', '5')
            return float(a_str)
        except (ValueError, TypeError):
            return 5.0

    def _calculate_muf_confidence(self, muf: float, sfi: float) -> float:
        """Calculate confidence for formula-based MUF."""
        # Formula-based has lower confidence than ionosonde
        # Base confidence around 0.6 for formula
        expected_muf = self.FOF2_COEFFICIENT * math.sqrt(sfi) * self.M_FACTOR_3000

        if expected_muf > 0:
            ratio = muf / expected_muf
            if 0.8 <= ratio <= 1.2:
                return 0.65
            elif 0.6 <= ratio <= 1.4:
                return 0.55
            else:
                return 0.45
        return 0.45

    def _apply_seasonal_adjustment(self, base_muf: float, lat: float) -> float:
        """Apply seasonal adjustment to MUF based on latitude and month."""
        from datetime import datetime
        month = datetime.now().month

        # Latitude weight: strongest at mid-latitudes (30-50 deg)
        abs_lat = abs(lat)
        lat_weight = 1.0 - abs(abs_lat - 40) / 50.0
        lat_weight = max(0.2, min(1.0, lat_weight))

        # Seasonal factors
        if month in (3, 4, 9, 10):  # Equinox months
            factor = 1.0 + 0.10 * lat_weight  # +10% enhancement
        elif month in (12, 1, 2):  # Winter (northern hemisphere)
            if lat >= 0:
                factor = 1.0 + 0.05 * lat_weight  # Winter anomaly +5%
            else:
                factor = 1.0 - 0.10 * lat_weight  # Summer reduction -10%
        elif month in (6, 7, 8):  # Summer (northern hemisphere)
            if lat >= 0:
                factor = 1.0 - 0.10 * lat_weight  # Summer reduction -10%
            else:
                factor = 1.0 + 0.05 * lat_weight  # Winter anomaly +5%
        else:
            factor = 1.0  # Transition months

        return base_muf * factor

    def _get_fallback_muf(self) -> Dict:
        """Get fallback MUF data when all calculations fail."""
        return {
            'muf': 21.0,  # Reasonable mid-range value
            'fof2': 7.0,
            'traditional_muf': 21.0,
            'enhanced_muf': 21.0,
            'sfi': 100.0,
            'confidence': 0.3,
            'method': 'Fallback'
        }

    # Legacy method for backwards compatibility
    def _calculate_traditional_muf(self, sfi: float) -> float:
        """Legacy method - now uses corrected formula."""
        return self._calculate_formula_muf(sfi)
