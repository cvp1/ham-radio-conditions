from datetime import datetime, timedelta
import math
def _calculate_sunrise_sunset(self):
        """Calculate sunrise and sunset times for the current location"""
        try:
            # Use a simple approximation for sunrise/sunset
            # This is a basic calculation and could be improved with more accurate algorithms
            now = datetime.now(self.timezone)
            print(now)
            sunrise = now.replace(hour=6, minute=0, second=0, microsecond=0)
            print(sunrise)
            sunset = now.replace(hour=18, minute=0, second=0, microsecond=0)
            print(sunset)
            # Adjust for seasonal variations (simplified)
            day_of_year = now.timetuple().tm_yday
            seasonal_offset = math.sin((day_of_year - 80) * 2 * math.pi / 365) * 2  # 2 hours max variation
            
            sunrise = sunrise + timedelta(hours=seasonal_offset)
            sunset = sunset - timedelta(hours=seasonal_offset)
            
            return {
                'sunrise': sunrise.strftime('%I:%M %p'),
                'sunset': sunset.strftime('%I:%M %p'),
                'is_day': sunrise <= now <= sunset
            }
            
        except Exception as e:
            print(f"Error calculating sunrise/sunset: {e}")
            return {
                'sunrise': 'N/A',
                'sunset': 'N/A',
                'is_day': True
            }
t = _calculate_sunrise_sunset()
print(t)