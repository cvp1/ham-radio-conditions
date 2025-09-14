"""
Statistical analysis system for ham radio predictions.

Provides statistical analysis of prediction accuracy and performance.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
from collections import defaultdict
from scipy import stats

logger = logging.getLogger(__name__)


class StatisticalAnalyzer:
    """Statistical analysis of prediction accuracy and performance."""
    
    def __init__(self):
        self.analysis_methods = {
            'correlation': self._analyze_correlation,
            'trend': self._analyze_trend,
            'seasonality': self._analyze_seasonality,
            'anomaly': self._detect_anomalies,
            'confidence': self._analyze_confidence_distribution
        }
    
    def analyze_prediction_accuracy(self, accuracy_data: List[Dict[str, Any]], 
                                  analysis_type: str = 'comprehensive') -> Dict[str, Any]:
        """Analyze prediction accuracy using statistical methods."""
        try:
            analysis_result = {
                'analysis_type': analysis_type,
                'timestamp': datetime.now().isoformat(),
                'data_points': len(accuracy_data),
                'statistical_analysis': {},
                'recommendations': []
            }
            
            if not accuracy_data:
                analysis_result['error'] = 'No accuracy data provided'
                return analysis_result
            
            # Extract accuracy values
            accuracy_values = [entry.get('accuracy', 0) for entry in accuracy_data if 'accuracy' in entry]
            
            if not accuracy_values:
                analysis_result['error'] = 'No accuracy values found in data'
                return analysis_result
            
            # Perform statistical analysis
            if analysis_type == 'comprehensive':
                analysis_result['statistical_analysis'] = self._comprehensive_analysis(accuracy_values, accuracy_data)
            elif analysis_type == 'trend':
                analysis_result['statistical_analysis'] = self._analyze_trend(accuracy_values, accuracy_data)
            elif analysis_type == 'correlation':
                analysis_result['statistical_analysis'] = self._analyze_correlation(accuracy_values, accuracy_data)
            elif analysis_type == 'seasonality':
                analysis_result['statistical_analysis'] = self._analyze_seasonality(accuracy_values, accuracy_data)
            else:
                analysis_result['error'] = f'Unknown analysis type: {analysis_type}'
                return analysis_result
            
            # Generate recommendations
            analysis_result['recommendations'] = self._generate_statistical_recommendations(
                analysis_result['statistical_analysis']
            )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing prediction accuracy: {e}")
            return {
                'analysis_type': analysis_type,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def _comprehensive_analysis(self, accuracy_values: List[float], 
                              accuracy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Perform comprehensive statistical analysis."""
        try:
            analysis = {}
            
            # Basic statistics
            analysis['basic_stats'] = {
                'mean': np.mean(accuracy_values),
                'median': np.median(accuracy_values),
                'std': np.std(accuracy_values),
                'min': np.min(accuracy_values),
                'max': np.max(accuracy_values),
                'range': np.max(accuracy_values) - np.min(accuracy_values),
                'q25': np.percentile(accuracy_values, 25),
                'q75': np.percentile(accuracy_values, 75)
            }
            
            # Distribution analysis
            analysis['distribution'] = self._analyze_distribution(accuracy_values)
            
            # Trend analysis
            analysis['trend'] = self._analyze_trend(accuracy_values, accuracy_data)
            
            # Correlation analysis
            analysis['correlation'] = self._analyze_correlation(accuracy_values, accuracy_data)
            
            # Seasonality analysis
            analysis['seasonality'] = self._analyze_seasonality(accuracy_values, accuracy_data)
            
            # Anomaly detection
            analysis['anomalies'] = self._detect_anomalies(accuracy_values, accuracy_data)
            
            # Confidence analysis
            analysis['confidence'] = self._analyze_confidence_distribution(accuracy_values, accuracy_data)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return {'error': str(e)}
    
    def _analyze_distribution(self, accuracy_values: List[float]) -> Dict[str, Any]:
        """Analyze the distribution of accuracy values."""
        try:
            # Normality test
            shapiro_stat, shapiro_p = stats.shapiro(accuracy_values)
            
            # Skewness and kurtosis
            skewness = stats.skew(accuracy_values)
            kurtosis = stats.kurtosis(accuracy_values)
            
            # Distribution shape
            if abs(skewness) < 0.5:
                shape = 'approximately normal'
            elif skewness > 0.5:
                shape = 'right-skewed'
            else:
                shape = 'left-skewed'
            
            return {
                'normality_test': {
                    'statistic': shapiro_stat,
                    'p_value': shapiro_p,
                    'is_normal': shapiro_p > 0.05
                },
                'skewness': skewness,
                'kurtosis': kurtosis,
                'shape': shape,
                'coefficient_of_variation': np.std(accuracy_values) / np.mean(accuracy_values) if np.mean(accuracy_values) > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing distribution: {e}")
            return {'error': str(e)}
    
    def _analyze_trend(self, accuracy_values: List[float], 
                      accuracy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends in accuracy over time."""
        try:
            if len(accuracy_values) < 2:
                return {'error': 'Insufficient data for trend analysis'}
            
            # Linear trend
            x = np.arange(len(accuracy_values))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, accuracy_values)
            
            # Moving average trends
            window_size = min(7, len(accuracy_values) // 3)  # 7-point or 1/3 of data
            if window_size > 1:
                moving_avg = np.convolve(accuracy_values, np.ones(window_size)/window_size, mode='valid')
                moving_trend = np.polyfit(range(len(moving_avg)), moving_avg, 1)[0]
            else:
                moving_trend = slope
            
            # Trend classification
            if abs(slope) < 0.001:
                trend_direction = 'stable'
            elif slope > 0:
                trend_direction = 'improving'
            else:
                trend_direction = 'declining'
            
            return {
                'linear_trend': {
                    'slope': slope,
                    'intercept': intercept,
                    'r_squared': r_value ** 2,
                    'p_value': p_value,
                    'std_error': std_err
                },
                'moving_average_trend': moving_trend,
                'trend_direction': trend_direction,
                'trend_strength': abs(slope),
                'confidence': 1 - p_value if p_value < 1 else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {'error': str(e)}
    
    def _analyze_correlation(self, accuracy_values: List[float], 
                           accuracy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze correlations between accuracy and other factors."""
        try:
            correlations = {}
            
            # Time-based correlations
            if len(accuracy_data) > 1:
                timestamps = []
                for entry in accuracy_data:
                    if 'timestamp' in entry:
                        try:
                            ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                            timestamps.append(ts.timestamp())
                        except:
                            continue
                
                if len(timestamps) == len(accuracy_values):
                    # Hour of day correlation
                    hours = [(datetime.fromtimestamp(ts).hour) for ts in timestamps]
                    hour_corr, hour_p = stats.pearsonr(hours, accuracy_values)
                    correlations['hour_of_day'] = {
                        'correlation': hour_corr,
                        'p_value': hour_p,
                        'significant': hour_p < 0.05
                    }
                    
                    # Day of week correlation
                    days = [(datetime.fromtimestamp(ts).weekday()) for ts in timestamps]
                    day_corr, day_p = stats.pearsonr(days, accuracy_values)
                    correlations['day_of_week'] = {
                        'correlation': day_corr,
                        'p_value': day_p,
                        'significant': day_p < 0.05
                    }
            
            # Prediction type correlations
            prediction_types = defaultdict(list)
            for i, entry in enumerate(accuracy_data):
                if 'prediction_type' in entry and i < len(accuracy_values):
                    prediction_types[entry['prediction_type']].append(accuracy_values[i])
            
            type_correlations = {}
            for pred_type, values in prediction_types.items():
                if len(values) > 1:
                    type_correlations[pred_type] = {
                        'mean_accuracy': np.mean(values),
                        'std_accuracy': np.std(values),
                        'count': len(values)
                    }
            
            correlations['prediction_types'] = type_correlations
            
            return correlations
            
        except Exception as e:
            logger.error(f"Error analyzing correlation: {e}")
            return {'error': str(e)}
    
    def _analyze_seasonality(self, accuracy_values: List[float], 
                           accuracy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze seasonal patterns in accuracy."""
        try:
            if len(accuracy_values) < 30:  # Need at least 30 data points
                return {'error': 'Insufficient data for seasonality analysis'}
            
            # Extract time components
            timestamps = []
            for entry in accuracy_data:
                if 'timestamp' in entry:
                    try:
                        ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                        timestamps.append(ts)
                    except:
                        continue
            
            if len(timestamps) != len(accuracy_values):
                return {'error': 'Timestamp mismatch in data'}
            
            # Monthly patterns
            monthly_accuracy = defaultdict(list)
            for i, ts in enumerate(timestamps):
                month = ts.month
                monthly_accuracy[month].append(accuracy_values[i])
            
            monthly_stats = {}
            for month, values in monthly_accuracy.items():
                if values:
                    monthly_stats[month] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'count': len(values)
                    }
            
            # Seasonal trend
            months = [ts.month for ts in timestamps]
            seasonal_corr, seasonal_p = stats.pearsonr(months, accuracy_values)
            
            return {
                'monthly_patterns': monthly_stats,
                'seasonal_correlation': {
                    'correlation': seasonal_corr,
                    'p_value': seasonal_p,
                    'significant': seasonal_p < 0.05
                },
                'seasonal_strength': abs(seasonal_corr)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing seasonality: {e}")
            return {'error': str(e)}
    
    def _detect_anomalies(self, accuracy_values: List[float], 
                         accuracy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect anomalies in accuracy data."""
        try:
            if len(accuracy_values) < 3:
                return {'error': 'Insufficient data for anomaly detection'}
            
            # Z-score based anomaly detection
            mean_acc = np.mean(accuracy_values)
            std_acc = np.std(accuracy_values)
            
            if std_acc == 0:
                return {'error': 'No variation in data'}
            
            z_scores = [(acc - mean_acc) / std_acc for acc in accuracy_values]
            anomalies = [i for i, z in enumerate(z_scores) if abs(z) > 2]
            
            # IQR based anomaly detection
            q1 = np.percentile(accuracy_values, 25)
            q3 = np.percentile(accuracy_values, 75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            iqr_anomalies = [i for i, acc in enumerate(accuracy_values) 
                           if acc < lower_bound or acc > upper_bound]
            
            # Combine anomaly detection methods
            all_anomalies = list(set(anomalies + iqr_anomalies))
            
            return {
                'z_score_anomalies': {
                    'indices': anomalies,
                    'count': len(anomalies),
                    'threshold': 2.0
                },
                'iqr_anomalies': {
                    'indices': iqr_anomalies,
                    'count': len(iqr_anomalies),
                    'bounds': [lower_bound, upper_bound]
                },
                'combined_anomalies': {
                    'indices': all_anomalies,
                    'count': len(all_anomalies)
                },
                'anomaly_rate': len(all_anomalies) / len(accuracy_values)
            }
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return {'error': str(e)}
    
    def _analyze_confidence_distribution(self, accuracy_values: List[float], 
                                       accuracy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the distribution of confidence levels."""
        try:
            # Extract confidence values if available
            confidence_values = []
            for entry in accuracy_data:
                if 'confidence' in entry:
                    confidence_values.append(entry['confidence'])
                elif 'overall_score' in entry:
                    confidence_values.append(entry['overall_score'])
            
            if not confidence_values:
                return {'error': 'No confidence data available'}
            
            # Analyze confidence distribution
            confidence_stats = {
                'mean': np.mean(confidence_values),
                'std': np.std(confidence_values),
                'min': np.min(confidence_values),
                'max': np.max(confidence_values)
            }
            
            # Confidence vs accuracy correlation
            if len(confidence_values) == len(accuracy_values):
                corr, p_value = stats.pearsonr(confidence_values, accuracy_values)
                confidence_stats['accuracy_correlation'] = {
                    'correlation': corr,
                    'p_value': p_value,
                    'significant': p_value < 0.05
                }
            
            return confidence_stats
            
        except Exception as e:
            logger.error(f"Error analyzing confidence distribution: {e}")
            return {'error': str(e)}
    
    def _generate_statistical_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on statistical analysis."""
        recommendations = []
        
        try:
            # Basic statistics recommendations
            if 'basic_stats' in analysis:
                basic = analysis['basic_stats']
                mean_acc = basic['mean']
                std_acc = basic['std']
                
                if mean_acc < 0.6:
                    recommendations.append("Mean accuracy is below 60% - consider model improvements")
                elif mean_acc > 0.8:
                    recommendations.append("Mean accuracy is excellent - maintain current approach")
                
                if std_acc > 0.2:
                    recommendations.append("High variability in accuracy - investigate causes")
                elif std_acc < 0.1:
                    recommendations.append("Low variability - predictions are consistent")
            
            # Trend recommendations
            if 'trend' in analysis and 'error' not in analysis['trend']:
                trend = analysis['trend']
                if trend['trend_direction'] == 'declining':
                    recommendations.append("Accuracy is declining - investigate recent changes")
                elif trend['trend_direction'] == 'improving':
                    recommendations.append("Accuracy is improving - continue current approach")
            
            # Distribution recommendations
            if 'distribution' in analysis and 'error' not in analysis['distribution']:
                dist = analysis['distribution']
                if not dist['normality_test']['is_normal']:
                    recommendations.append("Accuracy distribution is not normal - consider data transformation")
            
            # Anomaly recommendations
            if 'anomalies' in analysis and 'error' not in analysis['anomalies']:
                anomalies = analysis['anomalies']
                if anomalies['combined_anomalies']['count'] > 0:
                    recommendations.append(f"Found {anomalies['combined_anomalies']['count']} anomalies - investigate outliers")
            
            # Correlation recommendations
            if 'correlation' in analysis and 'error' not in analysis['correlation']:
                corr = analysis['correlation']
                if 'hour_of_day' in corr and corr['hour_of_day']['significant']:
                    recommendations.append("Significant correlation with hour of day - consider time-based adjustments")
                if 'day_of_week' in corr and corr['day_of_week']['significant']:
                    recommendations.append("Significant correlation with day of week - consider weekly patterns")
            
            if not recommendations:
                recommendations.append("Statistical analysis shows normal patterns - no specific recommendations")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("Error in statistical analysis - review data quality")
        
        return recommendations
