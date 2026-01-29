"""
Propagation calculator for ham radio conditions.

Handles propagation quality calculations and band recommendations.
"""

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
    
    def calculate_propagation(self, solar_data: Dict, weather_data: Dict, muf_data: Dict) -> Dict:
        """Calculate propagation quality and band recommendations."""
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
            
            return {
                'quality': quality,
                'best_bands': best_bands,
                'confidence': confidence,
                'muf': muf,
                'sfi': sfi,
                'k_index': k_index
            }
            
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

        # Add bands based on MUF - all bands below MUF are potentially usable
        if muf >= 28.0:
            bands.extend(['10m', '12m', '15m', '17m', '20m'])
        elif muf >= 24.0:
            bands.extend(['12m', '15m', '17m', '20m', '30m'])
        elif muf >= 21.0:
            bands.extend(['15m', '17m', '20m', '30m', '40m'])
        elif muf >= 18.0:
            bands.extend(['17m', '20m', '30m', '40m'])
        elif muf >= 14.0:
            bands.extend(['20m', '30m', '40m', '80m'])
        elif muf >= 10.0:
            bands.extend(['30m', '40m', '80m'])
        elif muf >= 7.0:
            bands.extend(['40m', '80m', '160m'])
        else:
            bands.extend(['80m', '160m'])

        # Adjust based on K-index - higher K reduces reliability of higher bands
        # but doesn't eliminate them if MUF supports them
        if k_index >= 6:  # Severe storm - stick to low bands only
            bands = [b for b in bands if b in ['40m', '80m', '160m']]
        elif k_index >= 5:  # Strong storm - limit to lower/mid bands
            bands = [b for b in bands if b in ['20m', '30m', '40m', '80m', '160m']]
        # For K <= 4, use MUF-based band selection without filtering

        # Ensure we always have some bands
        if not bands:
            bands = ['40m', '80m']

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
