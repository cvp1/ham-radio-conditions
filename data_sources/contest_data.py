"""
Contest calendar data provider for ham radio conditions.

Fetches upcoming and active contests from the OpenHamClock contest API.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List
import logging
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)

API_URL = 'https://open-hamclock-production.up.railway.app/api/contests'


class ContestDataProvider:
    """Provider for ham radio contest calendar data."""

    def __init__(self):
        self.cache_duration = 1800  # 30 minutes
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'ham-radio-conditions/1.0'})

    def get_contests(self) -> Dict:
        """Get current and upcoming contests categorized by time window."""
        try:
            cached = cache_get('contests', 'current')
            if cached:
                return cached

            contests = self._fetch_contests()

            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            week_end = today_start + timedelta(days=7)

            today = []
            this_week = []
            upcoming = []

            for c in contests:
                status = c.get('status')
                start_dt = c.get('_start_dt')

                if status == 'active':
                    today.append(c)
                elif status == 'upcoming' and start_dt:
                    if start_dt < today_end:
                        today.append(c)
                    elif start_dt < week_end:
                        this_week.append(c)
                    else:
                        upcoming.append(c)
                elif status == 'upcoming':
                    upcoming.append(c)

            # Strip internal datetime objects before returning
            for c in contests:
                c.pop('_start_dt', None)
                c.pop('_end_dt', None)

            result = {
                'timestamp': datetime.now().isoformat(),
                'contests': contests,
                'today': today,
                'this_week': this_week,
                'upcoming': upcoming,
                'active_count': len([c for c in contests if c.get('status') == 'active']),
                'upcoming_count': len([c for c in contests if c.get('status') == 'upcoming']),
            }

            cache_set('contests', 'current', result, self.cache_duration)
            return result

        except Exception as e:
            logger.error(f"Error getting contests: {e}")
            return self._get_fallback()

    def _fetch_contests(self) -> List[Dict]:
        """Fetch contests from the OpenHamClock JSON API."""
        try:
            response = self.session.get(API_URL, timeout=10)
            response.raise_for_status()
            raw = response.json()

            contests = []
            for item in raw:
                name = item.get('name', '')
                if not name:
                    continue

                start_dt = self._parse_iso(item.get('start'))
                end_dt = self._parse_iso(item.get('end'))
                status, time_info = self._determine_status(start_dt, end_dt)

                contests.append({
                    'name': name,
                    'link': item.get('url', ''),
                    'mode': item.get('mode', 'Mixed'),
                    'status': status,
                    'time_info': time_info,
                    'start': start_dt.isoformat() if start_dt else None,
                    'end': end_dt.isoformat() if end_dt else None,
                    # Internal use for bucketing; stripped before returning
                    '_start_dt': start_dt,
                    '_end_dt': end_dt,
                })

            # Active first, then by start time
            contests.sort(key=lambda c: (
                0 if c['status'] == 'active' else 1,
                c.get('start') or '9999'
            ))

            logger.info(f"Fetched {len(contests)} contests from OpenHamClock API")
            return contests

        except Exception as e:
            logger.error(f"Error fetching contests from API: {e}")
            return []

    def _parse_iso(self, s: str):
        """Parse ISO 8601 string (with or without Z) to naive UTC datetime."""
        if not s:
            return None
        try:
            # Python 3.9 fromisoformat doesn't handle Z suffix
            return datetime.fromisoformat(s.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return None

    def _determine_status(self, start_dt, end_dt):
        """Compute active/upcoming status and a human-readable time_info string."""
        now = datetime.utcnow()

        if start_dt and end_dt:
            if start_dt <= now <= end_dt:
                remaining = end_dt - now
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                return 'active', f'{hours}h {mins}m remaining'
            elif now < start_dt:
                until = start_dt - now
                days = until.days
                hours = int((until.total_seconds() % 86400) // 3600)
                if days > 0:
                    return 'upcoming', f'Starts in {days}d {hours}h'
                return 'upcoming', f'Starts in {hours}h'
            else:
                return 'past', 'Ended'
        elif start_dt and now < start_dt:
            until = start_dt - now
            days = until.days
            hours = int((until.total_seconds() % 86400) // 3600)
            if days > 0:
                return 'upcoming', f'Starts in {days}d {hours}h'
            return 'upcoming', f'Starts in {hours}h'

        return 'upcoming', ''

    def _get_fallback(self) -> Dict:
        return {
            'timestamp': datetime.now().isoformat(),
            'contests': [],
            'today': [],
            'this_week': [],
            'upcoming': [],
            'active_count': 0,
            'upcoming_count': 0,
        }
