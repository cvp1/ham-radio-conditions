"""
Geocoding utilities for converting ZIP codes to coordinates.
"""

import urllib.request
import urllib.error
import json
import logging
import math
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# Common US ZIP code data (fallback for when API is unavailable)
# Format: ZIP -> (lat, lon, city, state, timezone)
COMMON_ZIPS = {
    "85630": (31.8973, -110.2154, "St. David", "AZ", "America/Phoenix"),
    "10001": (40.7484, -73.9967, "New York", "NY", "America/New_York"),
    "90210": (34.0901, -118.4065, "Beverly Hills", "CA", "America/Los_Angeles"),
    "60601": (41.8819, -87.6278, "Chicago", "IL", "America/Chicago"),
    "77001": (29.7604, -95.3698, "Houston", "TX", "America/Chicago"),
    "85001": (33.4484, -112.0740, "Phoenix", "AZ", "America/Phoenix"),
    "19101": (39.9526, -75.1652, "Philadelphia", "PA", "America/New_York"),
    "78201": (29.4241, -98.4936, "San Antonio", "TX", "America/Chicago"),
    "92101": (32.7157, -117.1611, "San Diego", "CA", "America/Los_Angeles"),
    "75201": (32.7767, -96.7970, "Dallas", "TX", "America/Chicago"),
}


def zip_to_coordinates(zip_code: str) -> Optional[Dict]:
    """
    Convert a US ZIP code to lat/lon coordinates.

    Args:
        zip_code: 5-digit US ZIP code

    Returns:
        Dict with lat, lon, city, state, timezone, grid_square or None if not found
    """
    zip_code = str(zip_code).strip()[:5]

    if not zip_code.isdigit() or len(zip_code) != 5:
        logger.warning(f"Invalid ZIP code format: {zip_code}")
        return None

    # Check local cache first
    if zip_code in COMMON_ZIPS:
        lat, lon, city, state, tz = COMMON_ZIPS[zip_code]
        return {
            'zip_code': zip_code,
            'lat': lat,
            'lon': lon,
            'city': city,
            'state': state,
            'timezone': tz,
            'grid_square': latlon_to_grid(lat, lon),
            'source': 'cache'
        }

    # Try free geocoding API (Zippopotam.us - no API key required)
    result = _fetch_from_zippopotamus(zip_code)
    if result:
        return result

    # Fallback: estimate based on ZIP prefix
    return _estimate_from_zip_prefix(zip_code)


def _fetch_from_zippopotamus(zip_code: str) -> Optional[Dict]:
    """Fetch coordinates from Zippopotam.us API."""
    try:
        url = f"https://api.zippopotam.us/us/{zip_code}"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'ham-radio-conditions/1.0'}
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))

        if 'places' in data and len(data['places']) > 0:
            place = data['places'][0]
            lat = float(place['latitude'])
            lon = float(place['longitude'])
            city = place.get('place name', 'Unknown')
            state = place.get('state abbreviation', 'XX')

            # Determine timezone from state
            timezone = _state_to_timezone(state)

            return {
                'zip_code': zip_code,
                'lat': lat,
                'lon': lon,
                'city': city,
                'state': state,
                'timezone': timezone,
                'grid_square': latlon_to_grid(lat, lon),
                'source': 'zippopotamus'
            }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.debug(f"ZIP code not found: {zip_code}")
        else:
            logger.debug(f"HTTP error fetching ZIP data: {e}")
    except Exception as e:
        logger.debug(f"Error fetching ZIP data: {e}")

    return None


def _estimate_from_zip_prefix(zip_code: str) -> Optional[Dict]:
    """Estimate location from ZIP code prefix regions."""
    prefix = zip_code[:3]
    prefix_int = int(prefix)

    # US ZIP code regions (approximate centers)
    regions = {
        (0, 99): (42.0, -72.0, "New England", "MA", "America/New_York"),
        (100, 149): (42.5, -75.0, "New York", "NY", "America/New_York"),
        (150, 196): (40.5, -76.0, "Pennsylvania", "PA", "America/New_York"),
        (197, 199): (39.0, -75.5, "Delaware", "DE", "America/New_York"),
        (200, 205): (38.9, -77.0, "Washington DC", "DC", "America/New_York"),
        (206, 219): (38.0, -78.5, "Virginia", "VA", "America/New_York"),
        (220, 246): (39.0, -80.0, "West Virginia", "WV", "America/New_York"),
        (247, 268): (35.5, -79.0, "North Carolina", "NC", "America/New_York"),
        (269, 289): (34.0, -81.0, "South Carolina", "SC", "America/New_York"),
        (290, 319): (33.0, -84.0, "Georgia", "GA", "America/New_York"),
        (320, 339): (28.0, -82.0, "Florida", "FL", "America/New_York"),
        (350, 369): (33.5, -86.8, "Alabama", "AL", "America/Chicago"),
        (370, 385): (36.0, -86.5, "Tennessee", "TN", "America/Chicago"),
        (386, 397): (32.5, -90.0, "Mississippi", "MS", "America/Chicago"),
        (400, 427): (38.0, -85.5, "Kentucky", "KY", "America/New_York"),
        (430, 458): (40.0, -83.0, "Ohio", "OH", "America/New_York"),
        (460, 479): (40.0, -86.0, "Indiana", "IN", "America/New_York"),
        (480, 499): (43.0, -84.5, "Michigan", "MI", "America/New_York"),
        (500, 528): (42.0, -93.5, "Iowa", "IA", "America/Chicago"),
        (530, 549): (44.0, -90.0, "Wisconsin", "WI", "America/Chicago"),
        (550, 567): (45.0, -93.5, "Minnesota", "MN", "America/Chicago"),
        (570, 577): (44.0, -100.0, "South Dakota", "SD", "America/Chicago"),
        (580, 588): (47.0, -100.0, "North Dakota", "ND", "America/Chicago"),
        (590, 599): (47.0, -110.0, "Montana", "MT", "America/Denver"),
        (600, 629): (40.0, -89.0, "Illinois", "IL", "America/Chicago"),
        (630, 658): (38.5, -92.0, "Missouri", "MO", "America/Chicago"),
        (660, 679): (39.0, -98.0, "Kansas", "KS", "America/Chicago"),
        (680, 693): (41.0, -100.0, "Nebraska", "NE", "America/Chicago"),
        (700, 714): (30.5, -91.0, "Louisiana", "LA", "America/Chicago"),
        (716, 729): (34.5, -92.5, "Arkansas", "AR", "America/Chicago"),
        (730, 749): (35.5, -97.5, "Oklahoma", "OK", "America/Chicago"),
        (750, 799): (31.5, -99.0, "Texas", "TX", "America/Chicago"),
        (800, 816): (39.5, -105.0, "Colorado", "CO", "America/Denver"),
        (820, 831): (43.0, -108.0, "Wyoming", "WY", "America/Denver"),
        (832, 838): (43.5, -114.0, "Idaho", "ID", "America/Boise"),
        (840, 847): (40.5, -111.5, "Utah", "UT", "America/Denver"),
        (850, 865): (34.0, -111.5, "Arizona", "AZ", "America/Phoenix"),
        (870, 884): (35.0, -106.0, "New Mexico", "NM", "America/Denver"),
        (889, 898): (39.5, -117.0, "Nevada", "NV", "America/Los_Angeles"),
        (900, 961): (36.0, -119.0, "California", "CA", "America/Los_Angeles"),
        (967, 968): (21.3, -157.8, "Hawaii", "HI", "Pacific/Honolulu"),
        (970, 979): (44.0, -121.0, "Oregon", "OR", "America/Los_Angeles"),
        (980, 994): (47.5, -121.0, "Washington", "WA", "America/Los_Angeles"),
        (995, 999): (64.0, -153.0, "Alaska", "AK", "America/Anchorage"),
    }

    for (start, end), (lat, lon, city, state, tz) in regions.items():
        if start <= prefix_int <= end:
            return {
                'zip_code': zip_code,
                'lat': lat,
                'lon': lon,
                'city': f"{city} Area",
                'state': state,
                'timezone': tz,
                'grid_square': latlon_to_grid(lat, lon),
                'source': 'estimated'
            }

    # Default fallback
    return {
        'zip_code': zip_code,
        'lat': 39.8283,
        'lon': -98.5795,
        'city': 'Geographic Center of US',
        'state': 'KS',
        'timezone': 'America/Chicago',
        'grid_square': latlon_to_grid(39.8283, -98.5795),
        'source': 'default'
    }


def _state_to_timezone(state: str) -> str:
    """Map US state abbreviation to timezone."""
    eastern = ['CT', 'DE', 'FL', 'GA', 'IN', 'KY', 'ME', 'MD', 'MA', 'MI',
               'NH', 'NJ', 'NY', 'NC', 'OH', 'PA', 'RI', 'SC', 'VT', 'VA', 'WV', 'DC']
    central = ['AL', 'AR', 'IL', 'IA', 'KS', 'LA', 'MN', 'MS', 'MO', 'NE',
               'ND', 'OK', 'SD', 'TN', 'TX', 'WI']
    mountain = ['AZ', 'CO', 'ID', 'MT', 'NM', 'UT', 'WY']
    pacific = ['CA', 'NV', 'OR', 'WA']

    if state in eastern:
        return 'America/New_York'
    elif state in central:
        return 'America/Chicago'
    elif state in mountain:
        return 'America/Denver' if state != 'AZ' else 'America/Phoenix'
    elif state in pacific:
        return 'America/Los_Angeles'
    elif state == 'AK':
        return 'America/Anchorage'
    elif state == 'HI':
        return 'Pacific/Honolulu'
    else:
        return 'America/New_York'


def latlon_to_grid(lat: float, lon: float) -> str:
    """Convert latitude/longitude to Maidenhead grid square (6 character)."""
    # Adjust longitude and latitude
    lon = lon + 180
    lat = lat + 90

    # First pair (field)
    lon_field = int(lon / 20)
    lat_field = int(lat / 10)

    # Second pair (square)
    lon_square = int((lon % 20) / 2)
    lat_square = int((lat % 10) / 1)

    # Third pair (subsquare)
    lon_subsquare = int((lon % 2) * 12)
    lat_subsquare = int((lat % 1) * 24)

    grid = chr(ord('A') + lon_field) + chr(ord('A') + lat_field)
    grid += str(lon_square) + str(lat_square)
    grid += chr(ord('a') + lon_subsquare) + chr(ord('a') + lat_subsquare)

    return grid


def grid_to_latlon(grid: str) -> Optional[Tuple[float, float]]:
    """Convert Maidenhead grid square to latitude/longitude (center of grid)."""
    grid = grid.upper()

    if len(grid) < 4:
        return None

    try:
        lon = (ord(grid[0]) - ord('A')) * 20 - 180
        lat = (ord(grid[1]) - ord('A')) * 10 - 90

        lon += int(grid[2]) * 2
        lat += int(grid[3]) * 1

        if len(grid) >= 6:
            lon += (ord(grid[4].upper()) - ord('A')) / 12.0
            lat += (ord(grid[5].upper()) - ord('A')) / 24.0

        # Return center of grid
        lon += 1.0 if len(grid) < 6 else 1/24.0
        lat += 0.5 if len(grid) < 6 else 1/48.0

        return (lat, lon)
    except (IndexError, ValueError):
        return None
