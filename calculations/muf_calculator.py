"""
MUF (Maximum Usable Frequency) calculator for ham radio conditions.

Handles various MUF calculation methods and validation.
"""

from typing import Dict
import logging

from .constants import BAND_FREQUENCIES, MUF_MIN, MUF_MAX
from .helpers import extract_sfi, extract_k_index, extract_a_index, get_base_muf_from_sfi

logger = logging.getLogger(__name__)


class MUFCalculator:
    """Calculator for Maximum Usable Frequency (MUF)."""

    def __init__(self):
        self.band_frequencies = BAND_FREQUENCIES

    def calculate_muf(self, solar_data: Dict, location_data: Dict) -> Dict:
        """Calculate MUF using multiple methods and return the best result."""
        try:
            sfi = extract_sfi(solar_data)
            traditional_muf = get_base_muf_from_sfi(sfi)
            enhanced_muf = self._calculate_enhanced_muf(solar_data, sfi)
            best_muf = self._validate_and_select_muf(traditional_muf, enhanced_muf)

            return {
                'muf': best_muf,
                'traditional_muf': traditional_muf,
                'enhanced_muf': enhanced_muf,
                'sfi': sfi,
                'confidence': self._calculate_muf_confidence(best_muf, sfi),
                'method': 'Multi-method validation'
            }

        except Exception as e:
            logger.error(f"Error calculating MUF: {e}")
            return self._get_fallback_muf()

    def _calculate_enhanced_muf(self, solar_data: Dict, sfi: float) -> float:
        """Calculate enhanced MUF with geomagnetic adjustments."""
        try:
            k_index = extract_k_index(solar_data)
            a_index = extract_a_index(solar_data)
            base_muf = get_base_muf_from_sfi(sfi)

            # K-index adjustment (geomagnetic activity)
            k_factors = {6: 0.5, 5: 0.7, 4: 0.85, 3: 0.92, 2: 0.96, 1: 0.98}
            k_factor = next((f for k, f in k_factors.items() if k_index > k), 1.0)

            # A-index adjustment (daily geomagnetic average)
            a_factors = {50: 0.6, 30: 0.8, 20: 0.9, 10: 0.95}
            a_factor = next((f for a, f in a_factors.items() if a_index > a), 1.0)

            return round(base_muf * k_factor * a_factor, 1)

        except Exception as e:
            logger.error(f"Error in enhanced MUF calculation: {e}")
            return get_base_muf_from_sfi(sfi)

    def _validate_and_select_muf(self, traditional_muf: float, enhanced_muf: float) -> float:
        """Validate MUF values and select the best one."""
        if MUF_MIN <= enhanced_muf <= MUF_MAX:
            return enhanced_muf
        elif MUF_MIN <= traditional_muf <= MUF_MAX:
            return traditional_muf
        else:
            return max(MUF_MIN, min(MUF_MAX, enhanced_muf or traditional_muf))

    def _calculate_muf_confidence(self, muf: float, sfi: float) -> float:
        """Calculate confidence in MUF calculation."""
        confidence = 0.8
        if sfi > 0:
            confidence += 0.1
        if 15 <= muf <= 40:
            confidence += 0.05
        elif muf < 12 or muf > 45:
            confidence -= 0.1
        return max(0.5, min(0.95, confidence))

    def _get_fallback_muf(self) -> Dict:
        """Get fallback MUF data when calculation fails."""
        return {
            'muf': 15.0,
            'traditional_muf': 15.0,
            'enhanced_muf': 15.0,
            'sfi': 100.0,
            'confidence': 0.3,
            'method': 'Fallback'
        }
