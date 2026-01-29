"""
MUF (Maximum Usable Frequency) calculator for ham radio conditions.

Handles various MUF calculation methods and validation.
"""

import math
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MUFCalculator:
    """Calculator for Maximum Usable Frequency (MUF)."""
    
    def __init__(self):
        self.band_frequencies = {
            '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
            '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
            '10m': 28.0, '6m': 50.0
        }
    
    def calculate_muf(self, solar_data: Dict, location_data: Dict) -> Dict:
        """Calculate MUF using multiple methods and return the best result."""
        try:
            # Extract solar flux index
            sfi = self._extract_sfi(solar_data)
            
            # Calculate traditional MUF
            traditional_muf = self._calculate_traditional_muf(sfi)
            
            # Calculate enhanced MUF
            enhanced_muf = self._calculate_enhanced_muf(solar_data, location_data)
            
            # Validate and select best MUF
            best_muf = self._validate_and_select_muf(traditional_muf, enhanced_muf, sfi)
            
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
    
    def _extract_sfi(self, solar_data: Dict) -> float:
        """Extract solar flux index from solar data."""
        try:
            sfi_str = solar_data.get('sfi', '100 SFI')
            # Remove 'SFI' suffix if present
            sfi_str = sfi_str.replace(' SFI', '').strip()
            return float(sfi_str)
        except (ValueError, TypeError):
            return 100.0  # Default fallback
    
    def _calculate_traditional_muf(self, sfi: float) -> float:
        """Calculate traditional MUF using solar flux index lookup table.

        Uses empirically-derived values based on real-world amateur radio
        propagation observations rather than theoretical ionospheric formulas.
        """
        # Lookup table based on SFI ranges - empirically derived for amateur radio
        if sfi >= 150:
            base_muf = 40  # Very high solar activity
        elif sfi >= 120:
            base_muf = 32  # High solar activity
        elif sfi >= 100:
            base_muf = 26  # Good solar activity
        elif sfi >= 80:
            base_muf = 21  # Moderate solar activity
        elif sfi >= 60:
            base_muf = 16  # Low solar activity
        else:
            base_muf = 12  # Very low solar activity

        return float(base_muf)
    
    def _calculate_enhanced_muf(self, solar_data: Dict, location_data: Dict) -> float:
        """Calculate enhanced MUF with geomagnetic adjustments.

        Starts with the SFI-based lookup table and applies corrections
        for K-index (geomagnetic storm activity) and A-index (daily average).
        """
        try:
            sfi = self._extract_sfi(solar_data)
            k_index = self._extract_k_index(solar_data)
            a_index = self._extract_a_index(solar_data)

            # Get base MUF from lookup table
            base_muf = self._calculate_traditional_muf(sfi)

            # Adjust for K-index (geomagnetic activity)
            # Higher K = more disturbed ionosphere = lower MUF
            if k_index > 6:  # Severe storm
                k_factor = 0.5
            elif k_index > 5:  # Strong storm
                k_factor = 0.7
            elif k_index > 4:  # Minor storm
                k_factor = 0.85
            elif k_index > 3:  # Unsettled
                k_factor = 0.92
            elif k_index > 2:  # Active
                k_factor = 0.96
            elif k_index > 1:  # Quiet
                k_factor = 0.98
            else:  # Very quiet
                k_factor = 1.0

            # Adjust for A-index (daily geomagnetic average)
            if a_index > 50:  # Severe storm
                a_factor = 0.6
            elif a_index > 30:  # Minor storm
                a_factor = 0.8
            elif a_index > 20:  # Unsettled
                a_factor = 0.9
            elif a_index > 10:  # Active
                a_factor = 0.95
            else:  # Quiet
                a_factor = 1.0

            # Calculate final MUF
            muf = base_muf * k_factor * a_factor

            return round(muf, 1)

        except Exception as e:
            logger.error(f"Error in enhanced MUF calculation: {e}")
            return self._calculate_traditional_muf(self._extract_sfi(solar_data))
    
    def _extract_k_index(self, solar_data: Dict) -> float:
        """Extract K-index from solar data."""
        try:
            k_str = str(solar_data.get('k_index', '2')).strip()
            return float(k_str)
        except (ValueError, TypeError):
            return 2.0  # Default fallback

    def _extract_a_index(self, solar_data: Dict) -> float:
        """Extract A-index from solar data."""
        try:
            a_str = str(solar_data.get('a_index', '5')).strip()
            return float(a_str)
        except (ValueError, TypeError):
            return 5.0  # Default fallback
    
    def _validate_and_select_muf(self, traditional_muf: float, enhanced_muf: float, sfi: float) -> float:
        """Validate MUF values and select the best one.

        Enhanced MUF is preferred as it includes geomagnetic corrections.
        Traditional MUF is used as fallback if enhanced calculation fails.
        """
        # Define reasonable MUF ranges (10-50 MHz for amateur radio)
        min_muf = 10.0
        max_muf = 50.0

        # Prefer enhanced MUF if it's within reasonable range
        if min_muf <= enhanced_muf <= max_muf:
            return enhanced_muf
        elif min_muf <= traditional_muf <= max_muf:
            return traditional_muf
        elif enhanced_muf > 0:
            # Clamp to reasonable range
            return max(min_muf, min(max_muf, enhanced_muf))
        else:
            return max(min_muf, min(max_muf, traditional_muf))

    def _calculate_muf_confidence(self, muf: float, sfi: float) -> float:
        """Calculate confidence in MUF calculation.

        Higher confidence when we have good solar data and
        MUF is within expected ranges for the SFI level.
        """
        # Base confidence
        confidence = 0.8

        # Adjust based on SFI validity
        if sfi > 0:
            confidence += 0.1

        # Adjust based on MUF being in realistic range
        if 15 <= muf <= 40:  # Sweet spot for HF propagation
            confidence += 0.05
        elif muf < 12 or muf > 45:  # Edge cases
            confidence -= 0.1

        # Clamp to valid range
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
