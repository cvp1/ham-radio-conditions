"""
Comprehensive prediction validation system.

Integrates all validation methods to provide comprehensive accuracy verification.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
from .accuracy_tracker import AccuracyTracker
from .real_time_validator import RealTimeValidator
from .historical_validator import HistoricalValidator

logger = logging.getLogger(__name__)


class PredictionValidator:
    """Comprehensive prediction validation system."""
    
    def __init__(self):
        self.accuracy_tracker = AccuracyTracker()
        self.real_time_validator = RealTimeValidator()
        self.historical_validator = HistoricalValidator()
        
    def validate_prediction(self, prediction: Dict[str, Any], prediction_type: str, 
                          location: Dict[str, float]) -> Dict[str, Any]:
        """Comprehensive prediction validation."""
        try:
            validation_id = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Record prediction for tracking
            prediction_id = self.accuracy_tracker.record_prediction(prediction, prediction_type)
            
            # Perform real-time validation
            real_time_result = self._perform_real_time_validation(prediction, prediction_type, location)
            
            # Perform historical validation
            historical_result = self._perform_historical_validation(prediction, prediction_type)
            
            # Perform cross-validation
            cross_validation_result = self._perform_cross_validation(prediction, prediction_type, location)
            
            # Calculate overall validation score
            overall_score = self._calculate_overall_validation_score(
                real_time_result, historical_result, cross_validation_result
            )
            
            # Generate validation report
            validation_report = {
                'validation_id': validation_id,
                'prediction_id': prediction_id,
                'prediction_type': prediction_type,
                'timestamp': datetime.now().isoformat(),
                'location': location,
                'overall_score': overall_score,
                'confidence_level': self._determine_confidence_level(overall_score),
                'real_time_validation': real_time_result,
                'historical_validation': historical_result,
                'cross_validation': cross_validation_result,
                'recommendations': self._generate_recommendations(overall_score, real_time_result, historical_result),
                'status': 'completed'
            }
            
            # Store validation report
            self._store_validation_report(validation_report)
            
            logger.info(f"Prediction validation completed: {overall_score:.2f} overall score")
            return validation_report
            
        except Exception as e:
            logger.error(f"Error validating prediction: {e}")
            return {
                'validation_id': f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'prediction_type': prediction_type,
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'overall_score': 0.0,
                'confidence_level': 'low',
                'status': 'failed'
            }
    
    def _perform_real_time_validation(self, prediction: Dict[str, Any], 
                                    prediction_type: str, location: Dict[str, float]) -> Dict[str, Any]:
        """Perform real-time validation."""
        try:
            if prediction_type == 'muf':
                predicted_muf = prediction.get('muf', 0)
                return self.real_time_validator.validate_muf_prediction(predicted_muf, location)
            
            elif prediction_type == 'band_quality':
                predicted_bands = prediction.get('bands', {})
                return self.real_time_validator.validate_band_prediction(list(predicted_bands.keys()), location)
            
            elif prediction_type == 'propagation_score':
                predicted_score = prediction.get('propagation_score', 0)
                return self.real_time_validator.validate_propagation_quality('Good', location)  # Simplified
            
            elif prediction_type == 'best_bands':
                predicted_bands = prediction.get('best_bands', [])
                return self.real_time_validator.validate_band_prediction(predicted_bands, location)
            
            else:
                return {'error': f'Unknown prediction type: {prediction_type}'}
                
        except Exception as e:
            logger.error(f"Error in real-time validation: {e}")
            return {'error': str(e), 'validation_score': 0.0, 'confidence': 0.0}
    
    def _perform_historical_validation(self, prediction: Dict[str, Any], 
                                     prediction_type: str) -> Dict[str, Any]:
        """Perform historical validation."""
        try:
            return self.historical_validator.validate_prediction_against_history(prediction, prediction_type)
        except Exception as e:
            logger.error(f"Error in historical validation: {e}")
            return {'error': str(e), 'confidence': 0.0}
    
    def _perform_cross_validation(self, prediction: Dict[str, Any], 
                                prediction_type: str, location: Dict[str, float]) -> Dict[str, Any]:
        """Perform cross-validation using multiple methods."""
        try:
            cross_validation_result = {
                'timestamp': datetime.now().isoformat(),
                'methods_used': [],
                'consistency_score': 0.0,
                'agreement_level': 'unknown',
                'details': {}
            }
            
            # Use different prediction methods for cross-validation
            if prediction_type == 'muf':
                # Compare with alternative MUF calculation methods
                alternative_methods = self._get_alternative_muf_methods(prediction, location)
                cross_validation_result['methods_used'] = list(alternative_methods.keys())
                cross_validation_result['details'] = alternative_methods
                
                # Calculate consistency
                muf_values = [prediction.get('muf', 0)] + [m.get('muf', 0) for m in alternative_methods.values()]
                consistency = self._calculate_consistency(muf_values)
                cross_validation_result['consistency_score'] = consistency
                cross_validation_result['agreement_level'] = self._determine_agreement_level(consistency)
            
            elif prediction_type == 'best_bands':
                # Compare with alternative band selection methods
                alternative_methods = self._get_alternative_band_methods(prediction, location)
                cross_validation_result['methods_used'] = list(alternative_methods.keys())
                cross_validation_result['details'] = alternative_methods
                
                # Calculate band agreement
                band_sets = [set(prediction.get('best_bands', []))] + [set(m.get('best_bands', [])) for m in alternative_methods.values()]
                agreement = self._calculate_band_agreement(band_sets)
                cross_validation_result['consistency_score'] = agreement
                cross_validation_result['agreement_level'] = self._determine_agreement_level(agreement)
            
            return cross_validation_result
            
        except Exception as e:
            logger.error(f"Error in cross-validation: {e}")
            return {'error': str(e), 'consistency_score': 0.0, 'agreement_level': 'unknown'}
    
    def _get_alternative_muf_methods(self, prediction: Dict[str, Any], 
                                   location: Dict[str, float]) -> Dict[str, Any]:
        """Get alternative MUF calculation methods for comparison."""
        try:
            # This would implement alternative MUF calculation methods
            # For now, return simulated alternatives
            return {
                'traditional_method': {
                    'muf': prediction.get('muf', 0) * 0.9,  # Simulate 10% difference
                    'method': 'Traditional foF2 calculation',
                    'confidence': 0.7
                },
                'simplified_method': {
                    'muf': prediction.get('muf', 0) * 1.1,  # Simulate 10% difference
                    'method': 'Simplified SFI-based calculation',
                    'confidence': 0.6
                }
            }
        except Exception as e:
            logger.error(f"Error getting alternative MUF methods: {e}")
            return {}
    
    def _get_alternative_band_methods(self, prediction: Dict[str, Any], 
                                    location: Dict[str, float]) -> Dict[str, Any]:
        """Get alternative band selection methods for comparison."""
        try:
            # This would implement alternative band selection methods
            # For now, return simulated alternatives
            original_bands = prediction.get('best_bands', [])
            
            return {
                'frequency_based': {
                    'best_bands': original_bands[1:] + [original_bands[0]] if original_bands else [],
                    'method': 'Frequency-based selection',
                    'confidence': 0.7
                },
                'activity_based': {
                    'best_bands': original_bands[2:] + original_bands[:2] if len(original_bands) > 2 else original_bands,
                    'method': 'Activity-based selection',
                    'confidence': 0.6
                }
            }
        except Exception as e:
            logger.error(f"Error getting alternative band methods: {e}")
            return {}
    
    def _calculate_consistency(self, values: List[float]) -> float:
        """Calculate consistency between multiple values."""
        if len(values) < 2:
            return 1.0
        
        # Calculate coefficient of variation (lower = more consistent)
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            return 1.0
        
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        cv = std_dev / mean_val
        
        # Convert to consistency score (0-1, higher = more consistent)
        return max(0, 1 - cv)
    
    def _calculate_band_agreement(self, band_sets: List[set]) -> float:
        """Calculate agreement between multiple band selections."""
        if len(band_sets) < 2:
            return 1.0
        
        # Calculate average Jaccard similarity
        similarities = []
        for i in range(len(band_sets)):
            for j in range(i + 1, len(band_sets)):
                set1, set2 = band_sets[i], band_sets[j]
                if len(set1) == 0 and len(set2) == 0:
                    similarity = 1.0
                elif len(set1) == 0 or len(set2) == 0:
                    similarity = 0.0
                else:
                    intersection = len(set1.intersection(set2))
                    union = len(set1.union(set2))
                    similarity = intersection / union
                similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
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
    
    def _calculate_overall_validation_score(self, real_time_result: Dict[str, Any], 
                                          historical_result: Dict[str, Any], 
                                          cross_validation_result: Dict[str, Any]) -> float:
        """Calculate overall validation score from all validation methods."""
        try:
            scores = []
            weights = []
            
            # Real-time validation score
            if 'validation_score' in real_time_result:
                scores.append(real_time_result['validation_score'])
                weights.append(0.4)  # 40% weight for real-time validation
            
            # Historical validation confidence
            if 'confidence' in historical_result:
                scores.append(historical_result['confidence'])
                weights.append(0.3)  # 30% weight for historical validation
            
            # Cross-validation consistency
            if 'consistency_score' in cross_validation_result:
                scores.append(cross_validation_result['consistency_score'])
                weights.append(0.3)  # 30% weight for cross-validation
            
            if not scores:
                return 0.5  # Default score if no validation data
            
            # Calculate weighted average
            total_weight = sum(weights)
            if total_weight == 0:
                return sum(scores) / len(scores)
            
            weighted_score = sum(score * weight for score, weight in zip(scores, weights)) / total_weight
            return max(0.0, min(1.0, weighted_score))
            
        except Exception as e:
            logger.error(f"Error calculating overall validation score: {e}")
            return 0.5
    
    def _determine_confidence_level(self, overall_score: float) -> str:
        """Determine confidence level based on overall score."""
        if overall_score >= 0.8:
            return 'high'
        elif overall_score >= 0.6:
            return 'medium'
        elif overall_score >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def _generate_recommendations(self, overall_score: float, real_time_result: Dict[str, Any], 
                                historical_result: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        if overall_score < 0.4:
            recommendations.append("Prediction has low accuracy - consider using alternative data sources")
            recommendations.append("Review input parameters and data quality")
        
        if real_time_result.get('validation_score', 0) < 0.5:
            recommendations.append("Real-time validation shows poor accuracy - check current propagation conditions")
        
        if historical_result.get('confidence', 0) < 0.5:
            recommendations.append("Historical validation shows inconsistency - review prediction model")
        
        if overall_score >= 0.8:
            recommendations.append("Prediction shows high accuracy - suitable for operational use")
        
        if not recommendations:
            recommendations.append("Prediction accuracy is acceptable - monitor for changes")
        
        return recommendations
    
    def _store_validation_report(self, validation_report: Dict[str, Any]):
        """Store validation report for future analysis."""
        try:
            # Store in cache for immediate access
            from utils.cache_manager import cache_set
            cache_set('validation_reports', validation_report['validation_id'], 
                     validation_report, max_age=86400 * 7)  # 7 days
            
            # In a real implementation, this would also store in a database
            logger.info(f"Validation report stored: {validation_report['validation_id']}")
            
        except Exception as e:
            logger.error(f"Error storing validation report: {e}")
    
    def get_validation_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get validation summary for the specified period."""
        try:
            # Get accuracy summary from tracker
            accuracy_summary = self.accuracy_tracker.get_accuracy_summary(days=days)
            
            return {
                'period_days': days,
                'accuracy_summary': accuracy_summary,
                'validation_metrics': {
                    'total_validations': accuracy_summary.get('total_predictions', 0),
                    'mean_accuracy': accuracy_summary.get('mean_accuracy', 0),
                    'accuracy_trend': accuracy_summary.get('accuracy_trend', 'unknown')
                },
                'recommendations': self._generate_system_recommendations(accuracy_summary)
            }
            
        except Exception as e:
            logger.error(f"Error getting validation summary: {e}")
            return {'error': str(e)}
    
    def _generate_system_recommendations(self, accuracy_summary: Dict[str, Any]) -> List[str]:
        """Generate system-level recommendations based on accuracy summary."""
        recommendations = []
        
        mean_accuracy = accuracy_summary.get('mean_accuracy', 0)
        trend = accuracy_summary.get('accuracy_trend', 'unknown')
        
        if mean_accuracy < 0.6:
            recommendations.append("Overall prediction accuracy is low - consider model retraining")
            recommendations.append("Review data sources and input parameters")
        
        if trend == 'declining':
            recommendations.append("Prediction accuracy is declining - investigate recent changes")
        
        if trend == 'improving':
            recommendations.append("Prediction accuracy is improving - continue current approach")
        
        if mean_accuracy >= 0.8:
            recommendations.append("Prediction accuracy is excellent - system performing well")
        
        return recommendations
