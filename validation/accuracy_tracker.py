"""
Accuracy tracking system for ham radio predictions.

Tracks prediction accuracy over time and provides comprehensive metrics.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from collections import defaultdict, deque
import numpy as np
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)


class AccuracyTracker:
    """Tracks and analyzes prediction accuracy over time."""
    
    def __init__(self, max_history_days: int = 30):
        self.max_history_days = max_history_days
        self.accuracy_data = deque(maxlen=max_history_days * 24)  # Hourly data
        self.prediction_types = ['muf', 'band_quality', 'propagation_score', 'best_bands']
        
    def record_prediction(self, prediction: Dict[str, Any], prediction_type: str, 
                         timestamp: Optional[datetime] = None) -> str:
        """Record a prediction for future accuracy tracking."""
        if timestamp is None:
            timestamp = datetime.now()
            
        prediction_id = f"{prediction_type}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        prediction_record = {
            'id': prediction_id,
            'type': prediction_type,
            'prediction': prediction,
            'timestamp': timestamp.isoformat(),
            'status': 'pending_validation'
        }
        
        # Store in cache
        cache_set('predictions', prediction_id, prediction_record, max_age=86400 * 7)  # 7 days
        
        logger.info(f"Recorded prediction {prediction_id} for {prediction_type}")
        return prediction_id
    
    def record_actual_result(self, prediction_id: str, actual_result: Dict[str, Any]) -> Dict[str, Any]:
        """Record the actual result and calculate accuracy."""
        try:
            # Get the original prediction
            prediction_record = cache_get('predictions', prediction_id)
            if not prediction_record:
                logger.error(f"Prediction {prediction_id} not found")
                return {'error': 'Prediction not found'}
            
            # Calculate accuracy metrics
            accuracy_metrics = self._calculate_accuracy_metrics(
                prediction_record['prediction'], 
                actual_result,
                prediction_record['type']
            )
            
            # Update the prediction record
            prediction_record['actual_result'] = actual_result
            prediction_record['accuracy_metrics'] = accuracy_metrics
            prediction_record['status'] = 'validated'
            prediction_record['validation_timestamp'] = datetime.now().isoformat()
            
            # Store updated record
            cache_set('predictions', prediction_id, prediction_record, max_age=86400 * 7)
            
            # Add to accuracy history
            self._add_to_accuracy_history(accuracy_metrics, prediction_record['type'])
            
            logger.info(f"Recorded actual result for {prediction_id}: {accuracy_metrics['overall_accuracy']:.2f}")
            return accuracy_metrics
            
        except Exception as e:
            logger.error(f"Error recording actual result: {e}")
            return {'error': str(e)}
    
    def _calculate_accuracy_metrics(self, prediction: Dict[str, Any], 
                                  actual: Dict[str, Any], prediction_type: str) -> Dict[str, Any]:
        """Calculate comprehensive accuracy metrics."""
        metrics = {
            'prediction_type': prediction_type,
            'timestamp': datetime.now().isoformat(),
            'overall_accuracy': 0.0,
            'individual_metrics': {},
            'errors': []
        }
        
        try:
            if prediction_type == 'muf':
                metrics.update(self._calculate_muf_accuracy(prediction, actual))
            elif prediction_type == 'band_quality':
                metrics.update(self._calculate_band_accuracy(prediction, actual))
            elif prediction_type == 'propagation_score':
                metrics.update(self._calculate_propagation_accuracy(prediction, actual))
            elif prediction_type == 'best_bands':
                metrics.update(self._calculate_bands_accuracy(prediction, actual))
            else:
                metrics['errors'].append(f"Unknown prediction type: {prediction_type}")
                
        except Exception as e:
            logger.error(f"Error calculating accuracy metrics: {e}")
            metrics['errors'].append(str(e))
        
        return metrics
    
    def _calculate_muf_accuracy(self, prediction: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate MUF prediction accuracy."""
        pred_muf = prediction.get('muf', 0)
        actual_muf = actual.get('muf', 0)
        
        if actual_muf == 0:
            return {'overall_accuracy': 0.0, 'individual_metrics': {'muf_error': 'No actual MUF data'}}
        
        # Calculate relative error
        relative_error = abs(pred_muf - actual_muf) / actual_muf
        accuracy = max(0, 1 - relative_error)
        
        return {
            'overall_accuracy': accuracy,
            'individual_metrics': {
                'muf_relative_error': relative_error,
                'muf_absolute_error': abs(pred_muf - actual_muf),
                'predicted_muf': pred_muf,
                'actual_muf': actual_muf
            }
        }
    
    def _calculate_band_accuracy(self, prediction: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate band quality prediction accuracy."""
        pred_bands = prediction.get('bands', {})
        actual_bands = actual.get('bands', {})
        
        if not actual_bands:
            return {'overall_accuracy': 0.0, 'individual_metrics': {'band_error': 'No actual band data'}}
        
        # Compare band quality predictions
        band_accuracy_scores = []
        for band in ['20m', '40m', '80m', '15m', '10m']:
            if band in pred_bands and band in actual_bands:
                pred_quality = pred_bands[band].get('quality', 'Unknown')
                actual_quality = actual_bands[band].get('quality', 'Unknown')
                
                # Simple quality comparison
                quality_scores = {'Excellent': 5, 'Very Good': 4, 'Good': 3, 'Fair': 2, 'Poor': 1, 'Unknown': 0}
                pred_score = quality_scores.get(pred_quality, 0)
                actual_score = quality_scores.get(actual_quality, 0)
                
                if actual_score > 0:
                    band_accuracy = 1 - abs(pred_score - actual_score) / actual_score
                    band_accuracy_scores.append(max(0, band_accuracy))
        
        overall_accuracy = np.mean(band_accuracy_scores) if band_accuracy_scores else 0.0
        
        return {
            'overall_accuracy': overall_accuracy,
            'individual_metrics': {
                'band_accuracy_scores': band_accuracy_scores,
                'bands_compared': len(band_accuracy_scores)
            }
        }
    
    def _calculate_propagation_accuracy(self, prediction: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate propagation score prediction accuracy."""
        pred_score = prediction.get('propagation_score', 0)
        actual_score = actual.get('propagation_score', 0)
        
        if actual_score == 0:
            return {'overall_accuracy': 0.0, 'individual_metrics': {'propagation_error': 'No actual propagation data'}}
        
        relative_error = abs(pred_score - actual_score) / actual_score
        accuracy = max(0, 1 - relative_error)
        
        return {
            'overall_accuracy': accuracy,
            'individual_metrics': {
                'propagation_relative_error': relative_error,
                'predicted_score': pred_score,
                'actual_score': actual_score
            }
        }
    
    def _calculate_bands_accuracy(self, prediction: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate best bands prediction accuracy."""
        pred_bands = prediction.get('best_bands', [])
        actual_bands = actual.get('best_bands', [])
        
        if not actual_bands:
            return {'overall_accuracy': 0.0, 'individual_metrics': {'bands_error': 'No actual bands data'}}
        
        # Calculate Jaccard similarity (intersection over union)
        pred_set = set(pred_bands)
        actual_set = set(actual_bands)
        
        if len(actual_set) == 0:
            return {'overall_accuracy': 0.0, 'individual_metrics': {'bands_error': 'Empty actual bands'}}
        
        intersection = len(pred_set.intersection(actual_set))
        union = len(pred_set.union(actual_set))
        
        jaccard_similarity = intersection / union if union > 0 else 0
        
        # Also calculate position-weighted accuracy
        position_accuracy = 0
        for i, band in enumerate(actual_bands[:5]):  # Top 5 bands
            if band in pred_bands:
                pred_position = pred_bands.index(band)
                # Higher accuracy for bands closer to correct position
                position_accuracy += max(0, 1 - abs(i - pred_position) / 5)
        
        position_accuracy = position_accuracy / min(5, len(actual_bands))
        
        overall_accuracy = (jaccard_similarity + position_accuracy) / 2
        
        return {
            'overall_accuracy': overall_accuracy,
            'individual_metrics': {
                'jaccard_similarity': jaccard_similarity,
                'position_accuracy': position_accuracy,
                'predicted_bands': pred_bands,
                'actual_bands': actual_bands,
                'common_bands': list(pred_set.intersection(actual_set))
            }
        }
    
    def _add_to_accuracy_history(self, accuracy_metrics: Dict[str, Any], prediction_type: str):
        """Add accuracy metrics to historical tracking."""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'prediction_type': prediction_type,
            'accuracy': accuracy_metrics['overall_accuracy'],
            'metrics': accuracy_metrics['individual_metrics']
        }
        
        self.accuracy_data.append(history_entry)
        
        # Also store in cache for persistence
        cache_set('accuracy_history', f"{prediction_type}_{datetime.now().strftime('%Y%m%d')}", 
                 list(self.accuracy_data), max_age=86400 * 30)
    
    def get_accuracy_summary(self, prediction_type: Optional[str] = None, 
                           days: int = 7) -> Dict[str, Any]:
        """Get accuracy summary for specified time period."""
        try:
            # Filter data by time period and type
            cutoff_time = datetime.now() - timedelta(days=days)
            filtered_data = []
            
            for entry in self.accuracy_data:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if entry_time >= cutoff_time:
                    if prediction_type is None or entry['prediction_type'] == prediction_type:
                        filtered_data.append(entry)
            
            if not filtered_data:
                return {'error': 'No accuracy data available for the specified period'}
            
            # Calculate statistics
            accuracies = [entry['accuracy'] for entry in filtered_data]
            
            summary = {
                'period_days': days,
                'prediction_type': prediction_type or 'all',
                'total_predictions': len(filtered_data),
                'mean_accuracy': np.mean(accuracies),
                'median_accuracy': np.median(accuracies),
                'std_accuracy': np.std(accuracies),
                'min_accuracy': np.min(accuracies),
                'max_accuracy': np.max(accuracies),
                'accuracy_trend': self._calculate_trend(accuracies),
                'recent_accuracy': np.mean(accuracies[-24:]) if len(accuracies) >= 24 else np.mean(accuracies)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting accuracy summary: {e}")
            return {'error': str(e)}
    
    def _calculate_trend(self, accuracies: List[float]) -> str:
        """Calculate accuracy trend over time."""
        if len(accuracies) < 2:
            return 'insufficient_data'
        
        # Simple linear trend calculation
        x = np.arange(len(accuracies))
        y = np.array(accuracies)
        
        # Calculate slope
        slope = np.polyfit(x, y, 1)[0]
        
        if slope > 0.01:
            return 'improving'
        elif slope < -0.01:
            return 'declining'
        else:
            return 'stable'
    
    def get_prediction_confidence(self, prediction_type: str) -> float:
        """Get confidence score based on historical accuracy."""
        summary = self.get_accuracy_summary(prediction_type, days=7)
        
        if 'error' in summary:
            return 0.5  # Default confidence
        
        # Base confidence on recent accuracy
        recent_accuracy = summary['recent_accuracy']
        
        # Adjust for trend
        if summary['accuracy_trend'] == 'improving':
            confidence = min(0.95, recent_accuracy + 0.1)
        elif summary['accuracy_trend'] == 'declining':
            confidence = max(0.1, recent_accuracy - 0.1)
        else:
            confidence = recent_accuracy
        
        return confidence
