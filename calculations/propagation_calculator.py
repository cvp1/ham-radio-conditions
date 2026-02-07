"""
Propagation calculator for ham radio conditions.

Handles propagation quality calculations and band recommendations.
"""

import math
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class PropagationCalculator:
    """Calculator for propagation quality and band recommendations."""
    
    def __init__(self):
        self.band_frequencies = {
            '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
            '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
            '10m': 28.0, '6m': 50.0
        }
    
    def calculate_propagation(self, solar_data: Dict, weather_data: Dict, muf_data: Dict, time_data: Dict = None) -> Dict:
        """Calculate propagation quality and band recommendations.

        Args:
            solar_data: Solar conditions data (SFI, K-index, etc.)
            weather_data: Weather conditions data
            muf_data: MUF calculation results
            time_data: Optional dict with keys: is_daytime (bool), zenith_angle (float),
                       lat (float), lon (float), sunrise_hour (float), sunset_hour (float),
                       current_hour (float)
        """
        try:
            muf = muf_data.get('muf', 15.0)
            sfi = self._extract_sfi(solar_data)
            k_index = self._extract_k_index(solar_data)

            # Calculate propagation quality
            quality = self._calculate_quality(muf, sfi, k_index)

            # Calculate best bands
            best_bands = self._calculate_best_bands(muf, sfi, k_index)

            # Calculate confidence
            confidence = self._calculate_confidence(muf, sfi, k_index)

            result = {
                'quality': quality,
                'best_bands': best_bands,
                'confidence': confidence,
                'muf': muf,
                'sfi': sfi,
                'k_index': k_index
            }

            # Add D-layer absorption and greyline info if time_data is provided
            if time_data:
                is_daytime = time_data.get('is_daytime', True)
                zenith_angle = time_data.get('zenith_angle', 45.0)

                # Calculate D-layer absorption for each band
                d_layer_absorption = {}
                for band, freq in self.band_frequencies.items():
                    d_layer_absorption[band] = self._calculate_d_layer_absorption(
                        freq, sfi, is_daytime, zenith_angle
                    )
                result['d_layer_absorption'] = d_layer_absorption

                # Detect greyline conditions
                lat = time_data.get('lat', 0.0)
                lon = time_data.get('lon', 0.0)
                sunrise_hour = time_data.get('sunrise_hour', 6.0)
                sunset_hour = time_data.get('sunset_hour', 18.0)
                current_hour = time_data.get('current_hour', 12.0)
                greyline = self._detect_greyline(lat, lon, sunrise_hour, sunset_hour, current_hour)
                result['greyline'] = greyline

            return result

        except Exception as e:
            logger.error(f"Error calculating propagation: {e}")
            return self._get_fallback_propagation()
    
    def _extract_sfi(self, solar_data: Dict) -> float:
        """Extract solar flux index from solar data."""
        try:
            sfi_str = solar_data.get('sfi', '100 SFI')
            sfi_str = sfi_str.replace(' SFI', '').strip()
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
    
    def _calculate_quality(self, muf: float, sfi: float, k_index: float) -> str:
        """Calculate propagation quality based on MUF, SFI, and K-index."""
        if muf >= 20.0 and sfi >= 120 and k_index <= 2:
            return "Excellent"
        elif muf >= 15.0 and sfi >= 100 and k_index <= 3:
            return "Very Good"
        elif muf >= 10.0 and sfi >= 80 and k_index <= 4:
            return "Good"
        elif muf >= 7.0 and sfi >= 60 and k_index <= 5:
            return "Fair"
        else:
            return "Poor"
    
    def _calculate_best_bands(self, muf: float, sfi: float, k_index: float) -> List[str]:
        """Calculate best bands based on MUF and conditions."""
        bands = []
        
        # Add bands based on MUF
        if muf >= 28.0:
            bands.extend(['10m', '12m', '15m', '17m', '20m'])
        elif muf >= 21.0:
            bands.extend(['15m', '17m', '20m', '30m'])
        elif muf >= 14.0:
            bands.extend(['20m', '30m', '40m'])
        elif muf >= 7.0:
            bands.extend(['40m', '80m'])
        else:
            bands.extend(['80m', '160m'])
        
        # Adjust based on K-index
        if k_index >= 4:
            # High K-index - remove higher bands
            bands = [b for b in bands if b in ['40m', '80m', '160m']]
        
        return bands[:5]  # Return top 5 bands
    
    def _calculate_confidence(self, muf: float, sfi: float, k_index: float) -> float:
        """Calculate confidence in propagation prediction."""
        # Base confidence on data quality
        confidence = 0.7
        
        # Adjust based on K-index stability
        if k_index <= 2:
            confidence += 0.2
        elif k_index <= 4:
            confidence += 0.1
        else:
            confidence -= 0.1
        
        # Adjust based on SFI level
        if 80 <= sfi <= 150:
            confidence += 0.1
        elif sfi < 60 or sfi > 200:
            confidence -= 0.1
        
        return max(0.3, min(1.0, confidence))
    
    def _calculate_d_layer_absorption(self, freq: float, sfi: float, is_daytime: bool, zenith_angle: float = 45.0) -> float:
        """Calculate D-layer absorption using the George (1971) simplified formula.

        The D-layer only exists during daytime and absorbs HF signals, particularly
        on lower frequencies. Absorption is proportional to:
            (1 + 0.0037 * SFI) * cos(zenith_angle)^0.75 / freq^1.98

        Args:
            freq: Frequency in MHz
            sfi: Solar Flux Index
            is_daytime: Whether the sun is above the horizon
            zenith_angle: Solar zenith angle in degrees (0 = overhead, 90 = horizon)

        Returns:
            Absorption in dB (float). Returns 0.0 if not daytime.
        """
        if not is_daytime:
            return 0.0

        zenith_rad = math.radians(zenith_angle)
        cos_zenith = max(math.cos(zenith_rad), 0.0)

        absorption = (1.0 + 0.0037 * sfi) * (cos_zenith ** 0.75) / (freq ** 1.98)
        return absorption

    def _detect_greyline(self, lat: float, lon: float, sunrise_hour: float, sunset_hour: float, current_hour: float) -> Dict:
        """Detect greyline (grey-line) propagation conditions.

        Greyline propagation occurs near sunrise and sunset when the D-layer is
        weakened, allowing low-frequency signals to propagate over long distances.

        Args:
            lat: Latitude of the station
            lon: Longitude of the station
            sunrise_hour: Local sunrise hour (e.g. 6.5 for 6:30 AM)
            sunset_hour: Local sunset hour (e.g. 18.5 for 6:30 PM)
            current_hour: Current local hour (e.g. 14.25 for 2:15 PM)

        Returns:
            Dict with keys:
                active (bool): Whether greyline conditions are present
                type (str or None): 'sunrise' or 'sunset' if active, else None
                boost_bands (list): Bands that benefit from greyline, empty if not active
        """
        sunrise_diff = abs(current_hour - sunrise_hour)
        sunset_diff = abs(current_hour - sunset_hour)

        # Handle midnight wraparound for differences
        if sunrise_diff > 12.0:
            sunrise_diff = 24.0 - sunrise_diff
        if sunset_diff > 12.0:
            sunset_diff = 24.0 - sunset_diff

        near_sunrise = sunrise_diff <= 1.0
        near_sunset = sunset_diff <= 1.0

        if near_sunrise:
            return {
                'active': True,
                'type': 'sunrise',
                'boost_bands': ['40m', '80m', '160m']
            }
        elif near_sunset:
            return {
                'active': True,
                'type': 'sunset',
                'boost_bands': ['40m', '80m', '160m']
            }
        else:
            return {
                'active': False,
                'type': None,
                'boost_bands': []
            }

    def _get_fallback_propagation(self) -> Dict:
        """Get fallback propagation data when calculation fails."""
        return {
            'quality': 'Fair',
            'best_bands': ['20m', '40m', '80m'],
            'confidence': 0.3,
            'muf': 15.0,
            'sfi': 100.0,
            'k_index': 2.0
        }
