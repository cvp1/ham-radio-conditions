"""
Propagation calculator for ham radio conditions.

Handles propagation quality calculations and band recommendations.
"""

from typing import Dict, List
import logging

from .constants import BAND_FREQUENCIES
from .helpers import extract_sfi, extract_k_index

logger = logging.getLogger(__name__)


class PropagationCalculator:
    """Calculator for propagation quality and band recommendations."""

    def __init__(self):
        self.band_frequencies = BAND_FREQUENCIES

    def calculate_propagation(self, solar_data: Dict, weather_data: Dict, muf_data: Dict) -> Dict:
        """Calculate propagation quality and band recommendations."""
        try:
            muf = muf_data.get('muf', 15.0)
            sfi = extract_sfi(solar_data)
            k_index = extract_k_index(solar_data)

            return {
                'quality': self._calculate_quality(muf, sfi, k_index),
                'best_bands': self._calculate_best_bands(muf, k_index),
                'confidence': self._calculate_confidence(sfi, k_index),
                'muf': muf,
                'sfi': sfi,
                'k_index': k_index
            }

        except Exception as e:
            logger.error(f"Error calculating propagation: {e}")
            return self._get_fallback_propagation()

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

    def _calculate_best_bands(self, muf: float, k_index: float) -> List[str]:
        """Calculate best bands based on MUF and conditions."""
        # Select bands based on MUF
        if muf >= 28.0:
            bands = ['10m', '12m', '15m', '17m', '20m']
        elif muf >= 24.0:
            bands = ['12m', '15m', '17m', '20m', '30m']
        elif muf >= 21.0:
            bands = ['15m', '17m', '20m', '30m', '40m']
        elif muf >= 18.0:
            bands = ['17m', '20m', '30m', '40m']
        elif muf >= 14.0:
            bands = ['20m', '30m', '40m', '80m']
        elif muf >= 10.0:
            bands = ['30m', '40m', '80m']
        elif muf >= 7.0:
            bands = ['40m', '80m', '160m']
        else:
            bands = ['80m', '160m']

        # Filter for severe geomagnetic storms
        if k_index >= 6:
            bands = [b for b in bands if b in ['40m', '80m', '160m']]
        elif k_index >= 5:
            bands = [b for b in bands if b in ['20m', '30m', '40m', '80m', '160m']]

        return bands[:5] if bands else ['40m', '80m']

    def _calculate_confidence(self, sfi: float, k_index: float) -> float:
        """Calculate confidence in propagation prediction."""
        confidence = 0.7
        if k_index <= 2:
            confidence += 0.2
        elif k_index <= 4:
            confidence += 0.1
        else:
            confidence -= 0.1
        if 80 <= sfi <= 150:
            confidence += 0.1
        elif sfi < 60 or sfi > 200:
            confidence -= 0.1
        return max(0.3, min(1.0, confidence))

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
