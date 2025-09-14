"""
Historical validation system for ham radio predictions.

Validates predictions against historical data and patterns.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np
from collections import defaultdict
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class HistoricalValidator:
    """Validates predictions against historical data and patterns."""
    
    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
        self.historical_data = defaultdict(list)
        
    def validate_prediction_against_history(self, prediction: Dict[str, Any], 
                                          prediction_type: str) -> Dict[str, Any]:
        """Validate prediction against historical patterns."""
        try:
            validation_result = {
                'prediction_type': prediction_type,
                'validation_timestamp': datetime.now().isoformat(),
                'historical_validation': {},
                'pattern_analysis': {},
                'anomaly_detection': {},
                'confidence': 0.0,
                'errors': []
            }
            
            # Get historical data for comparison
            historical_data = self._get_historical_data(prediction_type)
            
            if not historical_data:
                validation_result['errors'].append('No historical data available')
                return validation_result
            
            # Perform different types of validation
            if prediction_type == 'muf':
                validation_result.update(self._validate_muf_against_history(prediction, historical_data))
            elif prediction_type == 'band_quality':
                validation_result.update(self._validate_band_quality_against_history(prediction, historical_data))
            elif prediction_type == 'propagation_score':
                validation_result.update(self._validate_propagation_against_history(prediction, historical_data))
            elif prediction_type == 'best_bands':
                validation_result.update(self._validate_bands_against_history(prediction, historical_data))
            
            # Calculate overall confidence
            validation_result['confidence'] = self._calculate_historical_confidence(validation_result)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating prediction against history: {e}")
            return {
                'prediction_type': prediction_type,
                'validation_timestamp': datetime.now().isoformat(),
                'error': str(e),
                'confidence': 0.0
            }
    
    def _validate_muf_against_history(self, prediction: Dict[str, Any], 
                                    historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate MUF prediction against historical MUF data."""
        pred_muf = prediction.get('muf', 0)
        
        # Extract historical MUF values
        historical_mufs = [entry.get('muf', 0) for entry in historical_data if 'muf' in entry]
        
        if not historical_mufs:
            return {'historical_validation': {'error': 'No historical MUF data'}}
        
        # Calculate statistics
        mean_muf = np.mean(historical_mufs)
        std_muf = np.std(historical_mufs)
        min_muf = np.min(historical_mufs)
        max_muf = np.max(historical_mufs)
        
        # Check if prediction is within historical range
        within_range = min_muf <= pred_muf <= max_muf
        
        # Check if prediction is within 1 standard deviation
        within_1std = abs(pred_muf - mean_muf) <= std_muf
        
        # Check if prediction follows recent trend
        recent_trend = self._calculate_recent_trend(historical_mufs[-24:])  # Last 24 hours
        trend_consistency = self._check_trend_consistency(pred_muf, recent_trend, historical_mufs[-1])
        
        # Calculate seasonal pattern consistency
        seasonal_consistency = self._check_seasonal_consistency(pred_muf, historical_data)
        
        return {
            'historical_validation': {
                'within_range': within_range,
                'within_1std': within_1std,
                'trend_consistency': trend_consistency,
                'seasonal_consistency': seasonal_consistency,
                'historical_mean': mean_muf,
                'historical_std': std_muf,
                'historical_min': min_muf,
                'historical_max': max_muf,
                'prediction_deviation': abs(pred_muf - mean_muf) / std_muf if std_muf > 0 else 0
            },
            'pattern_analysis': {
                'recent_trend': recent_trend,
                'trend_direction': 'increasing' if recent_trend > 0 else 'decreasing' if recent_trend < 0 else 'stable',
                'prediction_vs_trend': 'consistent' if trend_consistency else 'inconsistent'
            },
            'anomaly_detection': {
                'is_anomaly': not within_1std,
                'anomaly_severity': 'high' if not within_range else 'medium' if not within_1std else 'none',
                'anomaly_explanation': self._explain_anomaly(pred_muf, mean_muf, std_muf, within_range, within_1std)
            }
        }
    
    def _validate_band_quality_against_history(self, prediction: Dict[str, Any], 
                                             historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate band quality prediction against historical data."""
        pred_bands = prediction.get('bands', {})
        
        # Extract historical band quality data
        historical_bands = defaultdict(list)
        for entry in historical_data:
            if 'bands' in entry:
                for band, quality_data in entry['bands'].items():
                    if 'quality' in quality_data:
                        historical_bands[band].append(quality_data['quality'])
        
        validation_results = {}
        for band, quality_data in pred_bands.items():
            if band in historical_bands and historical_bands[band]:
                pred_quality = quality_data.get('quality', 'Unknown')
                historical_qualities = historical_bands[band]
                
                # Calculate quality consistency
                quality_counts = defaultdict(int)
                for q in historical_qualities:
                    quality_counts[q] += 1
                
                most_common_quality = max(quality_counts, key=quality_counts.get)
                consistency = pred_quality == most_common_quality
                
                # Calculate quality trend
                quality_trend = self._calculate_band_quality_trend(historical_qualities[-7:])  # Last 7 days
                
                validation_results[band] = {
                    'predicted_quality': pred_quality,
                    'most_common_historical': most_common_quality,
                    'consistency': consistency,
                    'quality_trend': quality_trend,
                    'historical_frequency': dict(quality_counts)
                }
        
        return {
            'historical_validation': validation_results,
            'pattern_analysis': {
                'overall_consistency': sum(1 for r in validation_results.values() if r['consistency']) / len(validation_results) if validation_results else 0
            }
        }
    
    def _validate_propagation_against_history(self, prediction: Dict[str, Any], 
                                            historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate propagation score prediction against historical data."""
        pred_score = prediction.get('propagation_score', 0)
        
        # Extract historical propagation scores
        historical_scores = [entry.get('propagation_score', 0) for entry in historical_data if 'propagation_score' in entry]
        
        if not historical_scores:
            return {'historical_validation': {'error': 'No historical propagation data'}}
        
        # Calculate statistics
        mean_score = np.mean(historical_scores)
        std_score = np.std(historical_scores)
        
        # Check consistency with historical patterns
        within_1std = abs(pred_score - mean_score) <= std_score
        
        # Check time-of-day consistency
        time_consistency = self._check_time_of_day_consistency(pred_score, historical_data)
        
        # Check solar cycle consistency
        solar_consistency = self._check_solar_cycle_consistency(pred_score, historical_data)
        
        return {
            'historical_validation': {
                'within_1std': within_1std,
                'time_consistency': time_consistency,
                'solar_consistency': solar_consistency,
                'historical_mean': mean_score,
                'historical_std': std_score,
                'prediction_deviation': abs(pred_score - mean_score) / std_score if std_score > 0 else 0
            }
        }
    
    def _validate_bands_against_history(self, prediction: Dict[str, Any], 
                                      historical_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate best bands prediction against historical data."""
        pred_bands = prediction.get('best_bands', [])
        
        # Extract historical best bands
        historical_bands = [entry.get('best_bands', []) for entry in historical_data if 'best_bands' in entry]
        
        if not historical_bands:
            return {'historical_validation': {'error': 'No historical bands data'}}
        
        # Calculate band frequency in historical data
        band_frequency = defaultdict(int)
        for bands in historical_bands:
            for band in bands:
                band_frequency[band] += 1
        
        # Calculate frequency scores for predicted bands
        frequency_scores = []
        for band in pred_bands:
            if band in band_frequency:
                frequency_scores.append(band_frequency[band] / len(historical_bands))
            else:
                frequency_scores.append(0)
        
        # Calculate consistency with recent patterns
        recent_bands = historical_bands[-7:]  # Last 7 entries
        recent_consistency = self._calculate_bands_consistency(pred_bands, recent_bands)
        
        return {
            'historical_validation': {
                'band_frequency_scores': dict(zip(pred_bands, frequency_scores)),
                'recent_consistency': recent_consistency,
                'overall_frequency_score': np.mean(frequency_scores) if frequency_scores else 0,
                'most_common_bands': sorted(band_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
            }
        }
    
    def _get_historical_data(self, prediction_type: str) -> List[Dict[str, Any]]:
        """Get historical data for the specified prediction type."""
        try:
            # Try to get from cache first
            cached_data = cache_get('historical_validation', prediction_type)
            if cached_data:
                return cached_data
            
            # Generate simulated historical data for demonstration
            # In a real implementation, this would fetch from a database
            historical_data = self._generate_simulated_historical_data(prediction_type)
            
            # Cache the data
            cache_set('historical_validation', prediction_type, historical_data, max_age=3600)
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []
    
    def _generate_simulated_historical_data(self, prediction_type: str) -> List[Dict[str, Any]]:
        """Generate simulated historical data for testing."""
        data = []
        base_time = datetime.now() - timedelta(days=self.lookback_days)
        
        for i in range(self.lookback_days * 24):  # Hourly data
            timestamp = base_time + timedelta(hours=i)
            
            if prediction_type == 'muf':
                # Simulate MUF data with daily and seasonal patterns
                hour = timestamp.hour
                day_of_year = timestamp.timetuple().tm_yday
                
                # Daily pattern (higher during day)
                daily_factor = 0.5 + 0.5 * np.sin(2 * np.pi * (hour - 6) / 24)
                
                # Seasonal pattern
                seasonal_factor = 0.8 + 0.2 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
                
                # Base MUF with some randomness
                base_muf = 12.0 + np.random.normal(0, 2)
                muf = base_muf * daily_factor * seasonal_factor
                
                data.append({
                    'timestamp': timestamp.isoformat(),
                    'muf': max(5.0, min(25.0, muf)),
                    'hour': hour,
                    'day_of_year': day_of_year
                })
            
            elif prediction_type == 'band_quality':
                # Simulate band quality data
                bands = ['20m', '40m', '80m', '15m', '10m']
                band_data = {}
                
                for band in bands:
                    # Simulate quality with some randomness
                    quality_scores = ['Poor', 'Fair', 'Good', 'Very Good', 'Excellent']
                    quality = np.random.choice(quality_scores, p=[0.1, 0.2, 0.4, 0.2, 0.1])
                    
                    band_data[band] = {
                        'quality': quality,
                        'score': quality_scores.index(quality) + 1
                    }
                
                data.append({
                    'timestamp': timestamp.isoformat(),
                    'bands': band_data
                })
            
            elif prediction_type == 'propagation_score':
                # Simulate propagation score data
                score = 50 + 30 * np.random.random() + 20 * np.sin(2 * np.pi * timestamp.hour / 24)
                data.append({
                    'timestamp': timestamp.isoformat(),
                    'propagation_score': max(0, min(100, score))
                })
            
            elif prediction_type == 'best_bands':
                # Simulate best bands data
                all_bands = ['20m', '40m', '80m', '15m', '10m', '17m', '12m', '30m']
                num_bands = np.random.randint(3, 6)
                best_bands = np.random.choice(all_bands, num_bands, replace=False).tolist()
                
                data.append({
                    'timestamp': timestamp.isoformat(),
                    'best_bands': best_bands
                })
        
        return data
    
    def _calculate_recent_trend(self, values: List[float]) -> float:
        """Calculate trend in recent values."""
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        # Calculate linear trend
        slope = np.polyfit(x, y, 1)[0]
        return slope
    
    def _check_trend_consistency(self, prediction: float, trend: float, last_value: float) -> bool:
        """Check if prediction is consistent with recent trend."""
        if trend > 0:
            return prediction >= last_value
        elif trend < 0:
            return prediction <= last_value
        else:
            return abs(prediction - last_value) < 2.0  # Allow small variations for stable trends
    
    def _check_seasonal_consistency(self, prediction: float, historical_data: List[Dict[str, Any]]) -> bool:
        """Check if prediction is consistent with seasonal patterns."""
        # This would implement more sophisticated seasonal analysis
        # For now, return True as a placeholder
        return True
    
    def _calculate_band_quality_trend(self, qualities: List[str]) -> str:
        """Calculate trend in band quality over time."""
        if len(qualities) < 2:
            return 'stable'
        
        quality_scores = {'Poor': 1, 'Fair': 2, 'Good': 3, 'Very Good': 4, 'Excellent': 5}
        scores = [quality_scores.get(q, 0) for q in qualities]
        
        trend = np.polyfit(range(len(scores)), scores, 1)[0]
        
        if trend > 0.1:
            return 'improving'
        elif trend < -0.1:
            return 'declining'
        else:
            return 'stable'
    
    def _check_time_of_day_consistency(self, prediction: float, historical_data: List[Dict[str, Any]]) -> bool:
        """Check if prediction is consistent with time-of-day patterns."""
        # This would implement time-of-day analysis
        # For now, return True as a placeholder
        return True
    
    def _check_solar_cycle_consistency(self, prediction: float, historical_data: List[Dict[str, Any]]) -> bool:
        """Check if prediction is consistent with solar cycle patterns."""
        # This would implement solar cycle analysis
        # For now, return True as a placeholder
        return True
    
    def _calculate_bands_consistency(self, pred_bands: List[str], historical_bands: List[List[str]]) -> float:
        """Calculate consistency of predicted bands with historical patterns."""
        if not historical_bands:
            return 0.0
        
        consistency_scores = []
        for historical_set in historical_bands:
            if historical_set:
                # Calculate Jaccard similarity
                pred_set = set(pred_bands)
                hist_set = set(historical_set)
                intersection = len(pred_set.intersection(hist_set))
                union = len(pred_set.union(hist_set))
                similarity = intersection / union if union > 0 else 0
                consistency_scores.append(similarity)
        
        return np.mean(consistency_scores) if consistency_scores else 0.0
    
    def _explain_anomaly(self, prediction: float, mean: float, std: float, 
                        within_range: bool, within_1std: bool) -> str:
        """Explain why a prediction might be an anomaly."""
        if within_range and within_1std:
            return "Prediction is within normal historical range"
        elif within_range and not within_1std:
            return f"Prediction is within historical range but {abs(prediction - mean) / std:.1f} standard deviations from mean"
        else:
            return f"Prediction is outside historical range (mean: {mean:.1f}, range: ±{std:.1f})"
    
    def _calculate_historical_confidence(self, validation_result: Dict[str, Any]) -> float:
        """Calculate overall confidence based on historical validation."""
        try:
            confidence = 0.5  # Base confidence
            
            # Adjust based on historical validation results
            if 'historical_validation' in validation_result:
                hist_val = validation_result['historical_validation']
                
                # Check various consistency measures
                if hist_val.get('within_1std', False):
                    confidence += 0.2
                if hist_val.get('trend_consistency', False):
                    confidence += 0.1
                if hist_val.get('seasonal_consistency', False):
                    confidence += 0.1
                if hist_val.get('time_consistency', False):
                    confidence += 0.1
            
            # Adjust based on pattern analysis
            if 'pattern_analysis' in validation_result:
                pattern = validation_result['pattern_analysis']
                if pattern.get('overall_consistency', 0) > 0.7:
                    confidence += 0.1
            
            # Adjust based on anomaly detection
            if 'anomaly_detection' in validation_result:
                anomaly = validation_result['anomaly_detection']
                if anomaly.get('anomaly_severity') == 'none':
                    confidence += 0.1
                elif anomaly.get('anomaly_severity') == 'high':
                    confidence -= 0.2
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.error(f"Error calculating historical confidence: {e}")
            return 0.5
