"""
Alerts system for ham radio conditions.
Evaluates current conditions and generates actionable alerts for operators.
"""

import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


class AlertsManager:
    """Evaluates conditions and generates alerts for operators."""

    ALERT_TYPES = {
        'geomagnetic_storm': {'icon': 'fa-bolt', 'color': 'red'},
        'solar_flare': {'icon': 'fa-sun', 'color': 'orange'},
        'band_opening': {'icon': 'fa-signal', 'color': 'green'},
        'best_time': {'icon': 'fa-clock', 'color': 'blue'},
        'degraded': {'icon': 'fa-exclamation-triangle', 'color': 'yellow'},
    }

    def evaluate_conditions(self, solar_data: Dict, time_data: Dict,
                            muf: float, weather_data: Dict = None) -> List[Dict]:
        """Evaluate current conditions and return a list of alerts."""
        alerts = []

        try:
            # Extract key values
            k_index = self._parse_float(solar_data.get('k_index', '2'))
            sfi_str = str(solar_data.get('sfi', '100')).replace(' SFI', '').strip()
            sfi = self._parse_float(sfi_str, 100.0)
            xray = str(solar_data.get('xray', 'B1'))
            storm_activity = solar_data.get('storm_activity', 'quiet')
            flare_class = solar_data.get('latest_flare_class', 'None')

            # 1. Geomagnetic storm alert (K >= 5)
            if k_index >= 5:
                severity = 'critical' if k_index >= 7 else 'warning'
                alerts.append({
                    'type': 'geomagnetic_storm',
                    'severity': severity,
                    'title': f'Geomagnetic Storm (Kp={k_index:.0f})',
                    'message': f'Storm level: {storm_activity}. HF propagation significantly degraded.',
                    'recommendation': 'Focus on VHF/UHF or wait for conditions to improve. Lower bands (160m/80m) may still work at night.',
                    'timestamp': datetime.now().isoformat(),
                })
            elif k_index >= 4:
                alerts.append({
                    'type': 'degraded',
                    'severity': 'info',
                    'title': f'Unsettled Conditions (Kp={k_index:.0f})',
                    'message': 'Geomagnetic activity is elevated. Higher bands may be affected.',
                    'recommendation': 'Try 20m and below. Avoid 10m/12m for DX.',
                    'timestamp': datetime.now().isoformat(),
                })

            # 2. Solar flare alert
            if flare_class and flare_class != 'None':
                first_char = flare_class[0].upper()
                if first_char in ('M', 'X'):
                    severity = 'critical' if first_char == 'X' else 'warning'
                    alerts.append({
                        'type': 'solar_flare',
                        'severity': severity,
                        'title': f'Solar Flare Detected ({flare_class})',
                        'message': f'An {first_char}-class solar flare has occurred. Shortwave fadeout possible on the daylit side.',
                        'recommendation': 'Daytime HF may experience fadeouts lasting 30-60 min. Nighttime paths unaffected.',
                        'timestamp': datetime.now().isoformat(),
                    })

            # 3. Band opening alert (MUF > 28 MHz = 10m is open)
            if muf and muf > 28:
                alerts.append({
                    'type': 'band_opening',
                    'severity': 'good',
                    'title': f'10m Band Opening (MUF {muf:.1f} MHz)',
                    'message': 'MUF supports 10m propagation. Excellent DX potential on higher bands.',
                    'recommendation': 'Work 10m, 12m, and 15m now. Use FT8 or SSB for DX.',
                    'timestamp': datetime.now().isoformat(),
                })
            elif muf and muf > 21:
                alerts.append({
                    'type': 'band_opening',
                    'severity': 'good',
                    'title': f'15m+ Bands Open (MUF {muf:.1f} MHz)',
                    'message': 'Good propagation on 15m and 17m bands.',
                    'recommendation': 'Try 15m and 17m for DX contacts.',
                    'timestamp': datetime.now().isoformat(),
                })

            # 4. Best operating time (greyline + quiet K)
            is_day = time_data.get('is_day', True)
            period = time_data.get('period', '')
            sunrise = time_data.get('sunrise', '')
            sunset = time_data.get('sunset', '')

            if period in ('dawn', 'early_morning') and k_index <= 3:
                alerts.append({
                    'type': 'best_time',
                    'severity': 'good',
                    'title': 'Greyline Opportunity',
                    'message': f'Sunrise at {sunrise}. Greyline propagation enhances low bands.',
                    'recommendation': 'Excellent time for 40m/80m/160m DX. Greyline path active.',
                    'timestamp': datetime.now().isoformat(),
                })
            elif period in ('evening', 'early_night') and k_index <= 3:
                alerts.append({
                    'type': 'best_time',
                    'severity': 'good',
                    'title': 'Evening Greyline Opportunity',
                    'message': f'Sunset at {sunset}. Greyline propagation enhances low bands.',
                    'recommendation': 'Try 40m/80m for DX during the sunset transition.',
                    'timestamp': datetime.now().isoformat(),
                })

            # 5. Quiet conditions = good time to operate
            if k_index <= 1 and sfi >= 100 and not alerts:
                alerts.append({
                    'type': 'best_time',
                    'severity': 'good',
                    'title': 'Excellent Conditions',
                    'message': f'Very quiet geomagnetic field (Kp={k_index:.0f}) with good solar flux ({sfi:.0f} SFI).',
                    'recommendation': 'Great time to get on the air. All bands should perform well.',
                    'timestamp': datetime.now().isoformat(),
                })

        except Exception as e:
            logger.error(f"Error evaluating alerts: {e}")

        return alerts

    def _parse_float(self, value, default: float = 0.0) -> float:
        """Safely parse a float from various input types."""
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).split()[0])
        except (ValueError, IndexError, TypeError):
            return default
