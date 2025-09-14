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
        """Calculate traditional MUF using solar flux index."""
        # Traditional MUF calculation: MUF ≈ 0.85 * foF2
        # foF2 ≈ 0.4 * sqrt(SFI) for mid-latitudes
        foF2 = 0.4 * math.sqrt(sfi)
        muf = 0.85 * foF2
        return round(muf, 2)
    
    def _calculate_enhanced_muf(self, solar_data: Dict, location_data: Dict) -> float:
        """Calculate enhanced MUF with additional factors."""
        try:
            sfi = self._extract_sfi(solar_data)
            k_index = self._extract_k_index(solar_data)
            a_index = self._extract_a_index(solar_data)
            
            # Base foF2 calculation
            foF2 = 0.4 * math.sqrt(sfi)
            
            # Apply K-index adjustment
            k_adjustment = 1.0 - (k_index * 0.05)  # 5% reduction per K-index point
            
            # Apply A-index adjustment
            a_adjustment = 1.0 - (a_index * 0.01)  # 1% reduction per A-index point
            
            # Calculate enhanced foF2
            enhanced_foF2 = foF2 * k_adjustment * a_adjustment
            
            # Calculate MUF
            muf = 0.85 * enhanced_foF2
            
            return round(muf, 2)
            
        except Exception as e:
            logger.error(f"Error in enhanced MUF calculation: {e}")
            return self._calculate_traditional_muf(self._extract_sfi(solar_data))
    
    def _extract_k_index(self, solar_data: Dict) -> float:
        """Extract K-index from solar data."""
        try:
            k_str = solar_data.get('k_index', '2')
            return float(k_str)
        except (ValueError, TypeError):
            return 2.0  # Default fallback
    
    def _extract_a_index(self, solar_data: Dict) -> float:
        """Extract A-index from solar data."""
        try:
            a_str = solar_data.get('a_index', '5')
            return float(a_str)
        except (ValueError, TypeError):
            return 5.0  # Default fallback
    
    def _validate_and_select_muf(self, traditional_muf: float, enhanced_muf: float, sfi: float) -> float:
        """Validate MUF values and select the best one."""
        # Define reasonable MUF ranges based on SFI
        min_muf = sfi * 0.05  # 5% of SFI
        max_muf = sfi * 0.4   # 40% of SFI
        
        # Check if enhanced MUF is within reasonable range
        if min_muf <= enhanced_muf <= max_muf:
            return enhanced_muf
        elif min_muf <= traditional_muf <= max_muf:
            return traditional_muf
        else:
            # Both are out of range, use the one closer to expected range
            expected_muf = sfi * 0.2  # 20% of SFI as expected
            if abs(enhanced_muf - expected_muf) < abs(traditional_muf - expected_muf):
                return enhanced_muf
            else:
                return traditional_muf
    
    def _calculate_muf_confidence(self, muf: float, sfi: float) -> float:
        """Calculate confidence in MUF calculation."""
        # Base confidence on how close MUF is to expected range
        expected_muf = sfi * 0.2
        if expected_muf > 0:
            ratio = muf / expected_muf
            if 0.5 <= ratio <= 2.0:  # Within 50% to 200% of expected
                return 0.9
            elif 0.3 <= ratio <= 3.0:  # Within 30% to 300% of expected
                return 0.7
            else:
                return 0.5
        return 0.5
    
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
