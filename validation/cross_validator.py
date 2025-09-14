"""
Cross-validation system for ham radio predictions.

Validates predictions using multiple alternative methods.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


class CrossValidator:
    """Cross-validation using multiple prediction methods."""
    
    def __init__(self):
        self.validation_methods = {
            'traditional_muf': self._calculate_traditional_muf,
            'simplified_muf': self._calculate_simplified_muf,
            'frequency_bands': self._select_frequency_bands,
            'activity_bands': self._select_activity_bands
        }
    
    def cross_validate_prediction(self, prediction: Dict[str, Any], 
                                prediction_type: str, location: Dict[str, float]) -> Dict[str, Any]:
        """Perform cross-validation using alternative methods."""
        try:
            cross_validation_result = {
                'prediction_type': prediction_type,
                'timestamp': datetime.now().isoformat(),
                'methods_used': [],
                'consistency_scores': {},
                'overall_consistency': 0.0,
                'agreement_level': 'unknown',
                'details': {},
                'recommendations': []
            }
            
            if prediction_type == 'muf':
                return self._cross_validate_muf(prediction, location, cross_validation_result)
            elif prediction_type == 'best_bands':
                return self._cross_validate_bands(prediction, location, cross_validation_result)
            else:
                cross_validation_result['error'] = f'Cross-validation not implemented for {prediction_type}'
                return cross_validation_result
                
        except Exception as e:
            logger.error(f"Error in cross-validation: {e}")
            return {
                'prediction_type': prediction_type,
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'overall_consistency': 0.0
            }
    
    def _cross_validate_muf(self, prediction: Dict[str, Any], 
                          location: Dict[str, float], result: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-validate MUF prediction using alternative methods."""
        try:
            predicted_muf = prediction.get('muf', 0)
            
            # Get alternative MUF calculations
            alternative_methods = {
                'traditional': self._calculate_traditional_muf(prediction, location),
                'simplified': self._calculate_simplified_muf(prediction, location),
                'geographic_adjusted': self._calculate_geographic_muf(prediction, location)
            }
            
            result['methods_used'] = list(alternative_methods.keys())
            result['details'] = alternative_methods
            
            # Calculate consistency scores
            muf_values = [predicted_muf] + [m.get('muf', 0) for m in alternative_methods.values()]
            consistency_scores = self._calculate_muf_consistency(muf_values)
            
            result['consistency_scores'] = dict(zip(['predicted'] + list(alternative_methods.keys()), consistency_scores))
            result['overall_consistency'] = np.mean(consistency_scores)
            result['agreement_level'] = self._determine_agreement_level(result['overall_consistency'])
            
            # Generate recommendations
            result['recommendations'] = self._generate_muf_recommendations(
                predicted_muf, alternative_methods, result['overall_consistency']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error cross-validating MUF: {e}")
            result['error'] = str(e)
            return result
    
    def _cross_validate_bands(self, prediction: Dict[str, Any], 
                            location: Dict[str, float], result: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-validate band prediction using alternative methods."""
        try:
            predicted_bands = prediction.get('best_bands', [])
            
            # Get alternative band selections
            alternative_methods = {
                'frequency_based': self._select_frequency_bands(prediction, location),
                'activity_based': self._select_activity_bands(prediction, location),
                'time_based': self._select_time_based_bands(prediction, location)
            }
            
            result['methods_used'] = list(alternative_methods.keys())
            result['details'] = alternative_methods
            
            # Calculate consistency scores
            band_sets = [set(predicted_bands)] + [set(m.get('best_bands', [])) for m in alternative_methods.values()]
            consistency_scores = self._calculate_band_consistency(band_sets)
            
            result['consistency_scores'] = dict(zip(['predicted'] + list(alternative_methods.keys()), consistency_scores))
            result['overall_consistency'] = np.mean(consistency_scores)
            result['agreement_level'] = self._determine_agreement_level(result['overall_consistency'])
            
            # Generate recommendations
            result['recommendations'] = self._generate_band_recommendations(
                predicted_bands, alternative_methods, result['overall_consistency']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error cross-validating bands: {e}")
            result['error'] = str(e)
            return result
    
    def _calculate_traditional_muf(self, prediction: Dict[str, Any], location: Dict[str, float]) -> Dict[str, Any]:
        """Calculate MUF using traditional foF2 method."""
        try:
            # Simulate traditional MUF calculation
            sfi = prediction.get('sfi', 100)
            traditional_muf = 0.85 * 0.4 * (sfi ** 0.5)  # Traditional formula
            
            return {
                'muf': traditional_muf,
                'method': 'Traditional foF2 calculation',
                'confidence': 0.7,
                'formula': 'MUF = 0.85 * foF2, foF2 = 0.4 * sqrt(SFI)'
            }
        except Exception as e:
            logger.error(f"Error calculating traditional MUF: {e}")
            return {'muf': 0, 'error': str(e)}
    
    def _calculate_simplified_muf(self, prediction: Dict[str, Any], location: Dict[str, float]) -> Dict[str, Any]:
        """Calculate MUF using simplified SFI-based method."""
        try:
            # Simulate simplified MUF calculation
            sfi = prediction.get('sfi', 100)
            simplified_muf = sfi * 0.15  # Simplified formula
            
            return {
                'muf': simplified_muf,
                'method': 'Simplified SFI-based calculation',
                'confidence': 0.6,
                'formula': 'MUF = SFI * 0.15'
            }
        except Exception as e:
            logger.error(f"Error calculating simplified MUF: {e}")
            return {'muf': 0, 'error': str(e)}
    
    def _calculate_geographic_muf(self, prediction: Dict[str, Any], location: Dict[str, float]) -> Dict[str, Any]:
        """Calculate MUF with geographic adjustments."""
        try:
            # Simulate geographic-adjusted MUF calculation
            base_muf = prediction.get('muf', 15.0)
            lat = location.get('lat', 0)
            
            # Adjust for latitude (simplified)
            if lat > 60:  # High latitude
                geographic_muf = base_muf * 0.8
            elif lat < 30:  # Low latitude
                geographic_muf = base_muf * 1.2
            else:  # Mid latitude
                geographic_muf = base_muf
            
            return {
                'muf': geographic_muf,
                'method': 'Geographic-adjusted calculation',
                'confidence': 0.75,
                'latitude_factor': lat
            }
        except Exception as e:
            logger.error(f"Error calculating geographic MUF: {e}")
            return {'muf': 0, 'error': str(e)}
    
    def _select_frequency_bands(self, prediction: Dict[str, Any], location: Dict[str, float]) -> Dict[str, Any]:
        """Select bands based on frequency analysis."""
        try:
            # Simulate frequency-based band selection
            muf = prediction.get('muf', 15.0)
            
            bands = []
            if muf >= 28.0:
                bands = ['10m', '12m', '15m', '17m', '20m']
            elif muf >= 21.0:
                bands = ['15m', '17m', '20m', '30m', '40m']
            elif muf >= 14.0:
                bands = ['20m', '30m', '40m', '80m']
            else:
                bands = ['40m', '80m', '160m']
            
            return {
                'best_bands': bands,
                'method': 'Frequency-based selection',
                'confidence': 0.7,
                'muf_threshold': muf
            }
        except Exception as e:
            logger.error(f"Error selecting frequency bands: {e}")
            return {'best_bands': [], 'error': str(e)}
    
    def _select_activity_bands(self, prediction: Dict[str, Any], location: Dict[str, float]) -> Dict[str, Any]:
        """Select bands based on activity analysis."""
        try:
            # Simulate activity-based band selection
            # This would normally use real activity data
            bands = ['20m', '40m', '80m', '15m', '10m']  # Simulated based on typical activity
            
            return {
                'best_bands': bands,
                'method': 'Activity-based selection',
                'confidence': 0.65,
                'activity_source': 'simulated'
            }
        except Exception as e:
            logger.error(f"Error selecting activity bands: {e}")
            return {'best_bands': [], 'error': str(e)}
    
    def _select_time_based_bands(self, prediction: Dict[str, Any], location: Dict[str, float]) -> Dict[str, Any]:
        """Select bands based on time of day."""
        try:
            # Simulate time-based band selection
            current_hour = datetime.now().hour
            
            if 6 <= current_hour < 12:  # Morning
                bands = ['20m', '15m', '17m', '10m', '12m']
            elif 12 <= current_hour < 18:  # Afternoon
                bands = ['20m', '15m', '17m', '12m', '10m']
            elif 18 <= current_hour < 24:  # Evening
                bands = ['40m', '20m', '80m', '15m', '30m']
            else:  # Night
                bands = ['80m', '40m', '160m', '20m', '30m']
            
            return {
                'best_bands': bands,
                'method': 'Time-based selection',
                'confidence': 0.6,
                'time_factor': current_hour
            }
        except Exception as e:
            logger.error(f"Error selecting time-based bands: {e}")
            return {'best_bands': [], 'error': str(e)}
    
    def _calculate_muf_consistency(self, muf_values: List[float]) -> List[float]:
        """Calculate consistency scores for MUF values."""
        if len(muf_values) < 2:
            return [1.0] * len(muf_values)
        
        mean_muf = np.mean(muf_values)
        if mean_muf == 0:
            return [1.0] * len(muf_values)
        
        consistency_scores = []
        for muf in muf_values:
            # Calculate relative deviation from mean
            relative_deviation = abs(muf - mean_muf) / mean_muf
            # Convert to consistency score (lower deviation = higher consistency)
            consistency = max(0, 1 - relative_deviation)
            consistency_scores.append(consistency)
        
        return consistency_scores
    
    def _calculate_band_consistency(self, band_sets: List[set]) -> List[float]:
        """Calculate consistency scores for band selections."""
        if len(band_sets) < 2:
            return [1.0] * len(band_sets)
        
        consistency_scores = []
        for i, band_set in enumerate(band_sets):
            # Calculate average Jaccard similarity with other sets
            similarities = []
            for j, other_set in enumerate(band_sets):
                if i != j:
                    if len(band_set) == 0 and len(other_set) == 0:
                        similarity = 1.0
                    elif len(band_set) == 0 or len(other_set) == 0:
                        similarity = 0.0
                    else:
                        intersection = len(band_set.intersection(other_set))
                        union = len(band_set.union(other_set))
                        similarity = intersection / union if union > 0 else 0
                    similarities.append(similarity)
            
            consistency = np.mean(similarities) if similarities else 1.0
            consistency_scores.append(consistency)
        
        return consistency_scores
    
    def _determine_agreement_level(self, consistency: float) -> str:
        """Determine agreement level based on consistency score."""
        if consistency >= 0.8:
            return 'high'
        elif consistency >= 0.6:
            return 'medium'
        elif consistency >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def _generate_muf_recommendations(self, predicted_muf: float, 
                                    alternative_methods: Dict[str, Any], 
                                    consistency: float) -> List[str]:
        """Generate recommendations based on MUF cross-validation."""
        recommendations = []
        
        if consistency >= 0.8:
            recommendations.append("High consistency between MUF calculation methods")
        elif consistency >= 0.6:
            recommendations.append("Moderate consistency - consider using multiple methods")
        else:
            recommendations.append("Low consistency - investigate calculation differences")
        
        # Check for outliers
        muf_values = [predicted_muf] + [m.get('muf', 0) for m in alternative_methods.values()]
        mean_muf = np.mean(muf_values)
        std_muf = np.std(muf_values)
        
        if std_muf > mean_muf * 0.2:  # High variation
            recommendations.append("High variation in MUF calculations - review input parameters")
        
        return recommendations
    
    def _generate_band_recommendations(self, predicted_bands: List[str], 
                                     alternative_methods: Dict[str, Any], 
                                     consistency: float) -> List[str]:
        """Generate recommendations based on band cross-validation."""
        recommendations = []
        
        if consistency >= 0.8:
            recommendations.append("High agreement on band selection")
        elif consistency >= 0.6:
            recommendations.append("Moderate agreement - consider multiple selection criteria")
        else:
            recommendations.append("Low agreement - review band selection logic")
        
        # Check for common bands
        all_bands = [set(predicted_bands)]
        for method in alternative_methods.values():
            all_bands.append(set(method.get('best_bands', [])))
        
        if all_bands:
            common_bands = set.intersection(*all_bands)
            if common_bands:
                recommendations.append(f"Common bands across methods: {', '.join(common_bands)}")
        
        return recommendations
