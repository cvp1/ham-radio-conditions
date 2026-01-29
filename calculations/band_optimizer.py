"""
Band optimizer for ham radio conditions.

Handles band optimization based on solar, weather, and time conditions.
"""

from typing import Dict
import logging

from .constants import BAND_FREQUENCIES
from .helpers import extract_sfi, extract_k_index, get_base_muf_from_sfi

logger = logging.getLogger(__name__)


class BandOptimizer:
    """Optimizer for band selection based on current conditions."""

    def __init__(self):
        self.band_frequencies = BAND_FREQUENCIES

    def optimize_bands(self, solar_data: Dict, weather_data: Dict, time_data: Dict) -> Dict:
        """Optimize band selection based on current conditions."""
        try:
            sfi = extract_sfi(solar_data)
            k_index = extract_k_index(solar_data)
            is_daytime = time_data.get('is_day', True)

            bands = self._get_base_band_recommendations(sfi, k_index, is_daytime)
            bands = self._apply_time_adjustments(bands, time_data)
            sorted_bands = self._sort_bands_by_quality(bands)

            return {
                'bands': sorted_bands,
                'confidence': self._calculate_band_confidence(sfi, k_index),
                'time_period': time_data.get('period', 'unknown'),
                'is_daytime': is_daytime
            }

        except Exception as e:
            logger.error(f"Error optimizing bands: {e}")
            return self._get_fallback_bands()

    def _get_base_band_recommendations(self, sfi: float, k_index: float, is_daytime: bool) -> Dict:
        """Get base band recommendations based on solar conditions."""
        bands = {}
        for band, freq in self.band_frequencies.items():
            quality = self._calculate_band_quality(freq, sfi, k_index, is_daytime)
            bands[band] = {
                'frequency': freq,
                'quality': quality,
                'score': self._quality_to_score(quality),
                'notes': f"{quality} conditions"
            }
        return bands

    def _calculate_band_quality(self, freq: float, sfi: float, k_index: float, is_daytime: bool) -> str:
        """Calculate quality for a specific band based on MUF estimate."""
        # Estimate MUF from SFI
        estimated_muf = get_base_muf_from_sfi(sfi)

        # Apply K-index degradation
        if k_index >= 5:
            estimated_muf *= 0.7
        elif k_index >= 4:
            estimated_muf *= 0.85
        elif k_index >= 3:
            estimated_muf *= 0.92

        # Determine quality based on frequency vs estimated MUF
        if estimated_muf <= 0:
            return "Poor"

        freq_ratio = freq / estimated_muf

        if freq_ratio <= 0.5:
            return "Excellent" if is_daytime and k_index <= 2 else "Very Good"
        elif freq_ratio <= 0.75:
            return "Very Good" if is_daytime and k_index <= 3 else "Good"
        elif freq_ratio <= 1.0:
            return "Good" if is_daytime and k_index <= 3 else "Fair"
        else:
            return "Poor"

    def _quality_to_score(self, quality: str) -> float:
        """Convert quality string to numerical score."""
        scores = {'Excellent': 5.0, 'Very Good': 4.0, 'Good': 3.0, 'Fair': 2.0, 'Poor': 1.0}
        return scores.get(quality, 2.0)

    def _apply_time_adjustments(self, bands: Dict, time_data: Dict) -> Dict:
        """Apply time-of-day adjustments to band recommendations."""
        period = time_data.get('period', 'unknown')
        adjustments = {
            'dawn': ['40m', '30m', '20m'],
            'dusk': ['40m', '30m', '20m'],
            'midday': ['20m', '17m', '15m', '12m'],
            'night': ['80m', '160m', '40m']
        }

        boost_bands = adjustments.get(period, [])
        boost_factor = 1.3 if period == 'midday' else 1.2

        for band in boost_bands:
            if band in bands:
                bands[band]['score'] *= boost_factor

        return bands

    def _sort_bands_by_quality(self, bands: Dict) -> Dict:
        """Sort bands by quality score."""
        return dict(sorted(bands.items(), key=lambda x: x[1]['score'], reverse=True))

    def _calculate_band_confidence(self, sfi: float, k_index: float) -> float:
        """Calculate confidence in band recommendations."""
        confidence = 0.7
        if k_index <= 2:
            confidence += 0.2
        elif k_index <= 4:
            confidence += 0.1
        else:
            confidence -= 0.1
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
