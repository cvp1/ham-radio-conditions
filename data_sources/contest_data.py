"""
Contest calendar data provider for ham radio conditions.

Fetches upcoming and active contests from WA7BNM Contest Calendar RSS feed.
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from utils.cache_manager import cache_get, cache_set

logger = logging.getLogger(__name__)

MONTH_MAP = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}


class ContestDataProvider:
    """Provider for ham radio contest calendar data."""

    def __init__(self):
        self.rss_url = 'https://www.contestcalendar.com/contestcal.php?mode=xml'
        self.cache_duration = 1800  # 30 minutes

    def get_contests(self) -> Dict:
        """Get current and upcoming contests."""
        try:
            cached = cache_get('contests', 'current')
            if cached:
                return cached

            contests = self._fetch_contests()

            active = [c for c in contests if c.get('status') == 'active']
            upcoming = [c for c in contests if c.get('status') == 'upcoming']

            result = {
                'timestamp': datetime.now().isoformat(),
                'contests': contests[:10],
                'active_count': len(active),
                'upcoming_count': len(upcoming),
            }

            cache_set('contests', 'current', result, self.cache_duration)
            return result

        except Exception as e:
            logger.error(f"Error getting contests: {e}")
            return self._get_fallback()

    def _fetch_contests(self) -> List[Dict]:
        """Fetch and parse contests from WA7BNM RSS feed."""
        try:
            response = requests.get(
                self.rss_url,
                timeout=10,
                headers={'User-Agent': 'ham-radio-conditions/1.0'}
            )
            response.raise_for_status()

            root = ET.fromstring(response.content)
            contests = []

            for item in root.findall('.//item'):
                title = self._get_text(item, 'title')
                link = self._get_text(item, 'link')
                description = self._get_text(item, 'description')

                if not title:
                    continue

                start_dt, end_dt = self._parse_contest_times(description)
                mode = self._detect_mode(title)
                status, time_info = self._determine_status(start_dt, end_dt)

                contests.append({
                    'name': title,
                    'link': link,
                    'description': description,
                    'mode': mode,
                    'status': status,
                    'time_info': time_info,
                    'start': start_dt.isoformat() if start_dt else None,
                    'end': end_dt.isoformat() if end_dt else None,
                })

            # Sort: active first, then upcoming by start time
            contests.sort(key=lambda c: (
                0 if c['status'] == 'active' else 1,
                c.get('start') or '9999'
            ))

            return contests

        except Exception as e:
            logger.debug(f"Error fetching contest RSS: {e}")
            return []

    def _get_text(self, element, tag: str) -> str:
        el = element.find(tag)
        return el.text.strip() if el is not None and el.text else ''

    def _parse_contest_times(self, description: str):
        """Parse start/end times from contest description text."""
        if not description:
            return None, None

        now = datetime.utcnow()
        year = now.year

        # Pattern: "HHMMz, Mon DD to HHMMz, Mon DD" (multi-day)
        multi = re.search(
            r'(\d{4})[Zz],?\s+(\w{3})\s+(\d{1,2})\s+to\s+(\d{4})[Zz],?\s+(\w{3})\s+(\d{1,2})',
            description
        )
        if multi:
            return self._build_datetimes(
                year,
                multi.group(2), int(multi.group(3)), multi.group(1),
                multi.group(5), int(multi.group(6)), multi.group(4),
            )

        # Pattern: "HHMMz-HHMMz, Mon DD" (single-day)
        single = re.search(
            r'(\d{4})[Zz]\s*[-–]\s*(\d{4})[Zz],?\s+(\w{3})\s+(\d{1,2})',
            description
        )
        if single:
            return self._build_datetimes(
                year,
                single.group(3), int(single.group(4)), single.group(1),
                single.group(3), int(single.group(4)), single.group(2),
            )

        return None, None

    def _build_datetimes(self, year, s_mon, s_day, s_time, e_mon, e_day, e_time):
        """Build datetime objects from parsed fields."""
        try:
            s_month = MONTH_MAP.get(s_mon)
            e_month = MONTH_MAP.get(e_mon)
            if not s_month or not e_month:
                return None, None

            s_hour = int(s_time[:2])
            s_min = int(s_time[2:])
            e_hour = int(e_time[:2])
            e_min = int(e_time[2:])

            start_dt = datetime(year, s_month, s_day, s_hour, s_min)

            # Handle 2400Z as midnight next day
            if e_hour == 24:
                end_dt = datetime(year, e_month, e_day, 0, 0) + timedelta(days=1)
            else:
                end_dt = datetime(year, e_month, e_day, e_hour, e_min)

            # If end is before start, it spans into next year
            if end_dt < start_dt:
                end_dt = end_dt.replace(year=year + 1)

            return start_dt, end_dt

        except (ValueError, TypeError) as e:
            logger.debug(f"Error building contest datetime: {e}")
            return None, None

    def _detect_mode(self, title: str) -> str:
        """Detect contest mode from title keywords."""
        t = title.upper()
        if 'CW' in t:
            return 'CW'
        if 'SSB' in t or 'PHONE' in t:
            return 'SSB'
        if 'RTTY' in t:
            return 'RTTY'
        if 'FT8' in t or 'FT4' in t or 'DIGI' in t:
            return 'Digital'
        return 'Mixed'

    def _determine_status(self, start_dt, end_dt):
        """Determine if a contest is active, upcoming, or past."""
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
                else:
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
            'active_count': 0,
            'upcoming_count': 0,
        }
