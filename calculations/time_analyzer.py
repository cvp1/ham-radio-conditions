"""
Time analyzer for ham radio conditions.

Handles time-of-day analysis and period determination.
"""

from datetime import datetime
from typing import Dict
import logging
import pytz

logger = logging.getLogger(__name__)


class TimeAnalyzer:
    """Analyzer for time-of-day effects on propagation."""
    
    def __init__(self):
        self.time_periods = {
            'dawn': {'start': 5, 'end': 7, 'description': 'Dawn - Lower bands optimal'},
            'early_morning': {'start': 7, 'end': 9, 'description': 'Early Morning - F2 building'},
            'mid_morning': {'start': 9, 'end': 11, 'description': 'Mid Morning - F2 strong'},
            'midday': {'start': 11, 'end': 15, 'description': 'Midday - Peak F2 layer'},
            'late_afternoon': {'start': 15, 'end': 17, 'description': 'Late Afternoon - F2 declining'},
            'evening': {'start': 17, 'end': 19, 'description': 'Evening - Transition period'},
            'early_night': {'start': 19, 'end': 21, 'description': 'Early Night - D layer fading'},
            'night': {'start': 21, 'end': 23, 'description': 'Night - Lower bands optimal'},
            'late_night': {'start': 23, 'end': 5, 'description': 'Late Night - Lowest bands'}
        }
    
    def analyze_current_time(self, lat: float, timezone_str: str) -> Dict:
        """Analyze current time and determine propagation period."""
        try:
            # Get current time in specified timezone
            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            current_hour = now.hour
            
            # Calculate sunrise/sunset times (simplified)
            sunrise_hour, sunset_hour = self._calculate_sunrise_sunset(lat)
            
            # Determine if it's daytime
            is_day = sunrise_hour <= current_hour < sunset_hour
            
            # Determine time period
            period = self._determine_time_period(current_hour, sunrise_hour, sunset_hour)
            
            # Get period description
            period_info = self.time_periods.get(period, {})
            
            return {
                'current_time': now.strftime('%I:%M %p %Z'),
                'current_hour': current_hour,
                'sunrise_hour': sunrise_hour,
                'sunset_hour': sunset_hour,
                'is_day': is_day,
                'period': period,
                'description': period_info.get('description', 'Unknown period'),
                'sunrise': f"{sunrise_hour:02d}:00 AM",
                'sunset': f"{sunset_hour:02d}:00 PM"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing current time: {e}")
            return self._get_fallback_time_data()
    
    def _calculate_sunrise_sunset(self, lat: float) -> tuple[int, int]:
        """Calculate sunrise and sunset hours (simplified)."""
        # Simplified calculation - in practice would use astral library
        if lat > 0:  # Northern hemisphere
            sunrise_hour = 6
            sunset_hour = 18
        else:  # Southern hemisphere
            sunrise_hour = 6
            sunset_hour = 18
        
        # Adjust for season (simplified)
        month = datetime.now().month
        if month in [12, 1, 2]:  # Winter
            sunrise_hour += 1
            sunset_hour -= 1
        elif month in [6, 7, 8]:  # Summer
            sunrise_hour -= 1
            sunset_hour += 1
        
        return sunrise_hour, sunset_hour
    
    def _determine_time_period(self, current_hour: int, sunrise_hour: int, sunset_hour: int) -> str:
        """Determine time period based on current hour."""
        # Handle late night period (crosses midnight)
        if current_hour >= 23 or current_hour < 5:
            return 'late_night'
        elif current_hour < sunrise_hour:
            return 'dawn'
        elif current_hour < sunrise_hour + 2:
            return 'early_morning'
        elif current_hour < sunrise_hour + 4:
            return 'mid_morning'
        elif current_hour < sunset_hour - 4:
            return 'midday'
        elif current_hour < sunset_hour - 2:
            return 'late_afternoon'
        elif current_hour < sunset_hour:
            return 'evening'
        elif current_hour < sunset_hour + 2:
            return 'early_night'
        else:
            return 'night'
    
    def _get_fallback_time_data(self) -> Dict:
        """Get fallback time data when analysis fails."""
        return {
            'current_time': datetime.now().strftime('%I:%M %p %Z'),
            'current_hour': 12,
            'sunrise_hour': 6,
            'sunset_hour': 18,
            'is_day': True,
            'period': 'midday',
            'description': 'Midday - Peak F2 layer',
            'sunrise': '06:00 AM',
            'sunset': '06:00 PM'
        }
