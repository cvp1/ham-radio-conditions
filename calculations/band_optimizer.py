"""
Band optimizer for ham radio conditions.

Handles band optimization based on solar, weather, and time conditions.
"""

from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class BandOptimizer:
    """Optimizer for band selection based on current conditions."""
    
    def __init__(self):
        self.band_frequencies = {
            '160m': 1.8, '80m': 3.5, '40m': 7.0, '30m': 10.1,
            '20m': 14.0, '17m': 18.1, '15m': 21.0, '12m': 24.9,
            '10m': 28.0, '6m': 50.0
        }
    
    def optimize_bands(self, solar_data: Dict, weather_data: Dict, time_data: Dict, muf: float = None) -> Dict:
        """Optimize band selection based on current conditions."""
        try:
            sfi = self._extract_sfi(solar_data)
            k_index = self._extract_k_index(solar_data)
            is_daytime = time_data.get('is_day', True)

            # Use provided MUF or estimate from SFI
            if muf is None:
                muf = 0.75 * (sfi ** 0.5) * 3.0  # Estimate MUF(3000)

            # Get base band recommendations using MUF
            bands = self._get_base_band_recommendations(muf, sfi, k_index, is_daytime)

            # Apply time-of-day adjustments
            bands = self._apply_time_adjustments(bands, time_data)

            # Apply weather adjustments
            bands = self._apply_weather_adjustments(bands, weather_data)

            # Sort bands by quality score
            sorted_bands = self._sort_bands_by_quality(bands)

            return {
                'bands': sorted_bands,
                'confidence': self._calculate_band_confidence(sfi, k_index),
                'time_period': time_data.get('period', 'unknown'),
                'is_daytime': is_daytime,
                'muf_used': muf
            }

        except Exception as e:
            logger.error(f"Error optimizing bands: {e}")
            return self._get_fallback_bands()
    
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
    
    def _get_base_band_recommendations(self, muf: float, sfi: float, k_index: float, is_daytime: bool) -> Dict:
        """Get base band recommendations based on MUF and solar conditions."""
        bands = {}

        # Define band quality based on MUF and K-index
        for band, freq in self.band_frequencies.items():
            quality = self._calculate_band_quality(band, freq, muf, k_index, is_daytime)
            bands[band] = {
                'frequency': freq,
                'quality': quality,
                'score': self._calculate_band_score(quality),
                'notes': self._get_band_notes(band, quality)
            }

        return bands

    def _calculate_band_quality(self, band: str, freq: float, muf: float, k_index: float, is_daytime: bool) -> str:
        """Calculate quality for a specific band based on MUF."""
        # Calculate how close the frequency is to MUF
        # Bands well below MUF = good, near MUF = fair, above MUF = poor
        freq_ratio = freq / muf if muf > 0 else 1.0

        # K-index penalty
        k_penalty = max(0, k_index - 2) * 0.1  # 10% penalty per K above 2

        if freq_ratio <= 0.5:
            # Well below MUF - reliable but may have absorption
            if is_daytime:
                # Daytime: lower bands have D-layer absorption
                if freq <= 7.0:
                    return "Fair" if k_index <= 3 else "Poor"
                else:
                    return "Good" if k_index <= 3 else "Fair"
            else:
                # Nighttime: lower bands are excellent
                return "Excellent" if k_index <= 2 else "Very Good"
        elif freq_ratio <= 0.75:
            # Good operating range
            if k_index <= 2:
                return "Excellent"
            elif k_index <= 4:
                return "Very Good"
            else:
                return "Good"
        elif freq_ratio <= 0.95:
            # Near optimal - best DX potential
            if k_index <= 2:
                return "Excellent"
            elif k_index <= 3:
                return "Very Good"
            else:
                return "Good"
        elif freq_ratio <= 1.1:
            # At or slightly above MUF - marginal
            if k_index <= 2:
                return "Good"
            elif k_index <= 4:
                return "Fair"
            else:
                return "Poor"
        else:
            # Above MUF - unlikely to propagate
            return "Poor"
    
    def _calculate_band_score(self, quality: str) -> float:
        """Calculate numerical score for band quality."""
        scores = {
            'Excellent': 5.0,
            'Very Good': 4.0,
            'Good': 3.0,
            'Fair': 2.0,
            'Poor': 1.0
        }
        return scores.get(quality, 2.0)
    
    def _get_band_notes(self, band: str, quality: str) -> str:
        """Get notes for a band based on its quality."""
        if quality == "Excellent":
            return "Optimal conditions"
        elif quality == "Very Good":
            return "Very good conditions"
        elif quality == "Good":
            return "Good conditions"
        elif quality == "Fair":
            return "Fair conditions"
        else:
            return "Poor conditions"
    
    def _apply_time_adjustments(self, bands: Dict, time_data: Dict) -> Dict:
        """Apply time-of-day adjustments to band recommendations."""
        period = time_data.get('period', 'unknown')
        
        # Time-based adjustments
        if period in ['dawn', 'dusk']:
            # Dawn/dusk favors mid-range bands
            for band in ['40m', '30m', '20m']:
                if band in bands:
                    bands[band]['score'] *= 1.2
        elif period in ['midday']:
            # Midday favors higher bands
            for band in ['20m', '17m', '15m', '12m']:
                if band in bands:
                    bands[band]['score'] *= 1.3
        elif period in ['night']:
            # Night favors lower bands
            for band in ['80m', '160m', '40m']:
                if band in bands:
                    bands[band]['score'] *= 1.2
        
        return bands
    
    def _apply_weather_adjustments(self, bands: Dict, weather_data: Dict) -> Dict:
        """Apply weather-based adjustments to band recommendations."""
        # Weather adjustments would be implemented here
        # For now, return bands unchanged
        return bands
    
    def _sort_bands_by_quality(self, bands: Dict) -> Dict:
        """Sort bands by quality score."""
        sorted_bands = dict(sorted(bands.items(), key=lambda x: x[1]['score'], reverse=True))
        return sorted_bands
    
    def _calculate_band_confidence(self, sfi: float, k_index: float) -> float:
        """Calculate confidence in band recommendations."""
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
        
        return max(0.3, min(1.0, confidence))
    
    def _get_fallback_bands(self) -> Dict:
        """Get fallback band recommendations when calculation fails."""
        return {
            'bands': {
                '20m': {'frequency': 14.0, 'quality': 'Good', 'score': 3.0, 'notes': 'Primary band'},
                '40m': {'frequency': 7.0, 'quality': 'Good', 'score': 3.0, 'notes': 'Secondary band'},
                '80m': {'frequency': 3.5, 'quality': 'Fair', 'score': 2.0, 'notes': 'Night band'}
            },
            'confidence': 0.3,
            'time_period': 'unknown',
            'is_daytime': True
        }
