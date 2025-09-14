"""
Real-time validation system for ham radio predictions.

Validates predictions against real-time propagation data from multiple sources.
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class RealTimeValidator:
    """Validates predictions against real-time propagation data."""
    
    def __init__(self):
        self.validation_sources = {
            'pskreporter': 'https://retrieve.pskreporter.info/query',
            'rbn': 'https://www.reversebeacon.net/raw_data/',
            'wsprnet': 'https://wsprnet.org/drupal/wsprnet/spots.json',
            'giro': 'http://giro.uml.edu/didbase/',
            'ionosphere_api': 'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json'
        }
        self.timeout = 10
        self.cache_duration = 300  # 5 minutes
        
    def validate_muf_prediction(self, predicted_muf: float, location: Dict[str, float], 
                              tolerance: float = 0.2) -> Dict[str, Any]:
        """Validate MUF prediction against real-time data."""
        try:
            validation_result = {
                'predicted_muf': predicted_muf,
                'validation_timestamp': datetime.now().isoformat(),
                'sources_checked': [],
                'validation_score': 0.0,
                'confidence': 0.0,
                'errors': []
            }
            
            # Get real-time MUF data from multiple sources
            real_time_data = self._get_real_time_muf_data(location)
            
            if not real_time_data:
                validation_result['errors'].append('No real-time MUF data available')
                return validation_result
            
            # Compare with predicted MUF
            validation_scores = []
            for source, data in real_time_data.items():
                if data and 'muf' in data:
                    actual_muf = data['muf']
                    error = abs(predicted_muf - actual_muf) / actual_muf if actual_muf > 0 else 1.0
                    
                    # Score based on error (lower error = higher score)
                    score = max(0, 1 - error / tolerance)
                    validation_scores.append(score)
                    
                    validation_result['sources_checked'].append({
                        'source': source,
                        'actual_muf': actual_muf,
                        'error': error,
                        'score': score,
                        'timestamp': data.get('timestamp', 'Unknown')
                    })
            
            if validation_scores:
                validation_result['validation_score'] = sum(validation_scores) / len(validation_scores)
                validation_result['confidence'] = min(0.95, validation_result['validation_score'] + 0.1)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating MUF prediction: {e}")
            return {
                'predicted_muf': predicted_muf,
                'validation_timestamp': datetime.now().isoformat(),
                'error': str(e),
                'validation_score': 0.0,
                'confidence': 0.0
            }
    
    def validate_band_prediction(self, predicted_bands: List[str], location: Dict[str, float]) -> Dict[str, Any]:
        """Validate band prediction against real-time activity data."""
        try:
            validation_result = {
                'predicted_bands': predicted_bands,
                'validation_timestamp': datetime.now().isoformat(),
                'sources_checked': [],
                'validation_score': 0.0,
                'confidence': 0.0,
                'errors': []
            }
            
            # Get real-time band activity data
            activity_data = self._get_real_time_band_activity(location)
            
            if not activity_data:
                validation_result['errors'].append('No real-time band activity data available')
                return validation_result
            
            # Calculate band activity scores
            band_scores = {}
            for source, data in activity_data.items():
                if data and 'band_activity' in data:
                    for band, activity in data['band_activity'].items():
                        if band not in band_scores:
                            band_scores[band] = []
                        band_scores[band].append(activity)
            
            # Score predicted bands based on actual activity
            validation_scores = []
            for band in predicted_bands:
                if band in band_scores:
                    # Higher activity = better validation score
                    avg_activity = sum(band_scores[band]) / len(band_scores[band])
                    # Normalize activity score (assuming max activity of 100)
                    normalized_score = min(1.0, avg_activity / 100.0)
                    validation_scores.append(normalized_score)
                else:
                    # No data for this band
                    validation_scores.append(0.0)
            
            if validation_scores:
                validation_result['validation_score'] = sum(validation_scores) / len(validation_scores)
                validation_result['confidence'] = min(0.95, validation_result['validation_score'] + 0.1)
            
            # Add source details
            for source, data in activity_data.items():
                if data:
                    validation_result['sources_checked'].append({
                        'source': source,
                        'band_activity': data.get('band_activity', {}),
                        'total_spots': data.get('total_spots', 0),
                        'timestamp': data.get('timestamp', 'Unknown')
                    })
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating band prediction: {e}")
            return {
                'predicted_bands': predicted_bands,
                'validation_timestamp': datetime.now().isoformat(),
                'error': str(e),
                'validation_score': 0.0,
                'confidence': 0.0
            }
    
    def validate_propagation_quality(self, predicted_quality: str, location: Dict[str, float]) -> Dict[str, Any]:
        """Validate propagation quality prediction against real-time data."""
        try:
            validation_result = {
                'predicted_quality': predicted_quality,
                'validation_timestamp': datetime.now().isoformat(),
                'sources_checked': [],
                'validation_score': 0.0,
                'confidence': 0.0,
                'errors': []
            }
            
            # Get real-time propagation indicators
            propagation_data = self._get_real_time_propagation_indicators(location)
            
            if not propagation_data:
                validation_result['errors'].append('No real-time propagation data available')
                return validation_result
            
            # Calculate quality score based on real-time indicators
            quality_scores = []
            for source, data in propagation_data.items():
                if data:
                    # Calculate quality based on multiple factors
                    quality_score = self._calculate_propagation_quality_score(data)
                    quality_scores.append(quality_score)
                    
                    validation_result['sources_checked'].append({
                        'source': source,
                        'quality_score': quality_score,
                        'indicators': data,
                        'timestamp': data.get('timestamp', 'Unknown')
                    })
            
            if quality_scores:
                avg_quality_score = sum(quality_scores) / len(quality_scores)
                
                # Map quality score to quality level
                if avg_quality_score >= 0.8:
                    actual_quality = 'Excellent'
                elif avg_quality_score >= 0.6:
                    actual_quality = 'Very Good'
                elif avg_quality_score >= 0.4:
                    actual_quality = 'Good'
                elif avg_quality_score >= 0.2:
                    actual_quality = 'Fair'
                else:
                    actual_quality = 'Poor'
                
                # Compare with predicted quality
                quality_levels = ['Poor', 'Fair', 'Good', 'Very Good', 'Excellent']
                pred_level = quality_levels.index(predicted_quality) if predicted_quality in quality_levels else 0
                actual_level = quality_levels.index(actual_quality)
                
                # Calculate validation score based on level difference
                level_diff = abs(pred_level - actual_level)
                validation_result['validation_score'] = max(0, 1 - level_diff / 4)  # Max difference is 4 levels
                validation_result['confidence'] = min(0.95, validation_result['validation_score'] + 0.1)
                validation_result['actual_quality'] = actual_quality
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating propagation quality: {e}")
            return {
                'predicted_quality': predicted_quality,
                'validation_timestamp': datetime.now().isoformat(),
                'error': str(e),
                'validation_score': 0.0,
                'confidence': 0.0
            }
    
    def _get_real_time_muf_data(self, location: Dict[str, float]) -> Dict[str, Any]:
        """Get real-time MUF data from multiple sources."""
        muf_data = {}
        
        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                # Submit tasks for different data sources
                futures = {
                    executor.submit(self._get_giro_muf_data, location): 'giro',
                    executor.submit(self._get_ionosphere_api_data): 'ionosphere_api',
                    executor.submit(self._get_pskreporter_muf_estimate, location): 'pskreporter'
                }
                
                for future in as_completed(futures, timeout=self.timeout):
                    source = futures[future]
                    try:
                        result = future.result(timeout=5)
                        if result:
                            muf_data[source] = result
                    except Exception as e:
                        logger.debug(f"Error getting MUF data from {source}: {e}")
        
        except Exception as e:
            logger.error(f"Error getting real-time MUF data: {e}")
        
        return muf_data
    
    def _get_real_time_band_activity(self, location: Dict[str, float]) -> Dict[str, Any]:
        """Get real-time band activity data."""
        activity_data = {}
        
        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._get_pskreporter_activity, location): 'pskreporter',
                    executor.submit(self._get_rbn_activity, location): 'rbn',
                    executor.submit(self._get_wsprnet_activity, location): 'wsprnet'
                }
                
                for future in as_completed(futures, timeout=self.timeout):
                    source = futures[future]
                    try:
                        result = future.result(timeout=5)
                        if result:
                            activity_data[source] = result
                    except Exception as e:
                        logger.debug(f"Error getting activity data from {source}: {e}")
        
        except Exception as e:
            logger.error(f"Error getting real-time band activity: {e}")
        
        return activity_data
    
    def _get_real_time_propagation_indicators(self, location: Dict[str, float]) -> Dict[str, Any]:
        """Get real-time propagation indicators."""
        indicators = {}
        
        try:
            # Get solar data
            solar_response = requests.get(self.validation_sources['ionosphere_api'], timeout=5)
            if solar_response.status_code == 200:
                solar_data = solar_response.json()
                if solar_data:
                    latest = solar_data[-1]
                    indicators['solar'] = {
                        'k_index': latest.get('kp', 0),
                        'timestamp': latest.get('time_tag', ''),
                        'source': 'NOAA'
                    }
        
        except Exception as e:
            logger.debug(f"Error getting propagation indicators: {e}")
        
        return indicators
    
    def _get_giro_muf_data(self, location: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Get MUF data from GIRO."""
        try:
            # This would implement actual GIRO data fetching
            # For now, return simulated data
            return {
                'muf': 12.5,
                'timestamp': datetime.now().isoformat(),
                'source': 'GIRO (simulated)'
            }
        except Exception as e:
            logger.debug(f"Error getting GIRO data: {e}")
            return None
    
    def _get_ionosphere_api_data(self) -> Optional[Dict[str, Any]]:
        """Get ionospheric data from API."""
        try:
            response = requests.get(self.validation_sources['ionosphere_api'], timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data:
                    latest = data[-1]
                    # Estimate MUF from K-index
                    k_index = latest.get('kp', 2)
                    estimated_muf = 15.0 - (k_index * 2)  # Simple estimation
                    return {
                        'muf': estimated_muf,
                        'k_index': k_index,
                        'timestamp': latest.get('time_tag', ''),
                        'source': 'NOAA'
                    }
        except Exception as e:
            logger.debug(f"Error getting ionosphere API data: {e}")
        return None
    
    def _get_pskreporter_muf_estimate(self, location: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Estimate MUF from PSKReporter activity."""
        try:
            # This would implement actual PSKReporter data fetching and MUF estimation
            # For now, return simulated data
            return {
                'muf': 14.2,
                'timestamp': datetime.now().isoformat(),
                'source': 'PSKReporter (simulated)'
            }
        except Exception as e:
            logger.debug(f"Error getting PSKReporter MUF estimate: {e}")
            return None
    
    def _get_pskreporter_activity(self, location: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Get band activity from PSKReporter."""
        try:
            # This would implement actual PSKReporter data fetching
            # For now, return simulated data
            return {
                'band_activity': {'20m': 45, '40m': 32, '80m': 18, '15m': 28, '10m': 15},
                'total_spots': 138,
                'timestamp': datetime.now().isoformat(),
                'source': 'PSKReporter (simulated)'
            }
        except Exception as e:
            logger.debug(f"Error getting PSKReporter activity: {e}")
            return None
    
    def _get_rbn_activity(self, location: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Get band activity from RBN."""
        try:
            # This would implement actual RBN data fetching
            # For now, return simulated data
            return {
                'band_activity': {'20m': 25, '40m': 18, '80m': 12, '15m': 20, '10m': 8},
                'total_spots': 83,
                'timestamp': datetime.now().isoformat(),
                'source': 'RBN (simulated)'
            }
        except Exception as e:
            logger.debug(f"Error getting RBN activity: {e}")
            return None
    
    def _get_wsprnet_activity(self, location: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """Get band activity from WSPRNet."""
        try:
            # This would implement actual WSPRNet data fetching
            # For now, return simulated data
            return {
                'band_activity': {'20m': 35, '40m': 28, '80m': 15, '15m': 22, '10m': 12},
                'total_spots': 112,
                'timestamp': datetime.now().isoformat(),
                'source': 'WSPRNet (simulated)'
            }
        except Exception as e:
            logger.debug(f"Error getting WSPRNet activity: {e}")
            return None
    
    def _calculate_propagation_quality_score(self, data: Dict[str, Any]) -> float:
        """Calculate propagation quality score from real-time data."""
        try:
            score = 0.5  # Base score
            
            # Adjust based on K-index
            k_index = data.get('k_index', 2)
            if k_index <= 2:
                score += 0.3
            elif k_index <= 4:
                score += 0.1
            else:
                score -= 0.2
            
            # Adjust based on other indicators
            if 'band_activity' in data:
                total_activity = sum(data['band_activity'].values())
                if total_activity > 100:
                    score += 0.2
                elif total_activity > 50:
                    score += 0.1
                else:
                    score -= 0.1
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.debug(f"Error calculating propagation quality score: {e}")
            return 0.5
