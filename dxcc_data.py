"""
DXCC (DX Century Club) data and helper functions.
This module contains the DXCC entity list and functions to work with DXCC data.
"""

import math
from typing import Dict, List, Optional, Tuple

# DXCC Entity List (complete list of current entities)
DXCC_ENTITIES = {
    '1': {'name': 'Canada', 'continent': 'NA', 'itu_zone': '2', 'cq_zone': '4', 'prefixes': ['VA', 'VE', 'VO', 'VY'], 'timezone': 'UTC-3.5'},
    '2': {'name': 'Abu Dhabi', 'continent': 'AS', 'itu_zone': '39', 'cq_zone': '21', 'prefixes': ['A6'], 'timezone': 'UTC+4'},
    '3': {'name': 'Afghanistan', 'continent': 'AS', 'itu_zone': '40', 'cq_zone': '21', 'prefixes': ['YA'], 'timezone': 'UTC+4.5'},
    '4': {'name': 'Agalega & St. Brandon', 'continent': 'AF', 'itu_zone': '53', 'cq_zone': '39', 'prefixes': ['3B6'], 'timezone': 'UTC+4'},
    '5': {'name': 'Aland Islands', 'continent': 'EU', 'itu_zone': '18', 'cq_zone': '15', 'prefixes': ['OH0'], 'timezone': 'UTC+2'},
    '6': {'name': 'Alaska', 'continent': 'NA', 'itu_zone': '1', 'cq_zone': '1', 'prefixes': ['KL', 'NL', 'WL'], 'timezone': 'UTC-9'},
    '7': {'name': 'Albania', 'continent': 'EU', 'itu_zone': '28', 'cq_zone': '15', 'prefixes': ['ZA'], 'timezone': 'UTC+1'},
    '8': {'name': 'Aldabra', 'continent': 'AF', 'itu_zone': '53', 'cq_zone': '39', 'prefixes': ['S7'], 'timezone': 'UTC+4'},
    '9': {'name': 'American Samoa', 'continent': 'OC', 'itu_zone': '62', 'cq_zone': '32', 'prefixes': ['KH8'], 'timezone': 'UTC-11'},
    '10': {'name': 'Amsterdam & St. Paul Is.', 'continent': 'AF', 'itu_zone': '68', 'cq_zone': '39', 'prefixes': ['FT5Z'], 'timezone': 'UTC+5'},
    '110': {'name': 'United States', 'continent': 'NA', 'itu_zone': '2', 'cq_zone': '4', 'prefixes': ['K', 'N', 'W'], 'timezone': 'UTC-5'},
    # Add more entities as needed
}

# Grid square to DXCC mapping with more precise boundaries
GRID_TO_DXCC = {
    # North America
    'CN': '1',  # Canada
    'DN': '110',  # United States
    'EN': '110',  # United States
    'FN': '110',  # United States
    'GN': '110',  # United States
    'HN': '110',  # United States
    'IN': '110',  # United States
    'JN': '110',  # United States
    'KN': '110',  # United States
    'LN': '110',  # United States
    'MN': '110',  # United States
    'NN': '110',  # United States
    'ON': '110',  # United States
    'PN': '110',  # United States
    'QN': '110',  # United States
    'RN': '110',  # United States
    'SN': '110',  # United States
    'TN': '110',  # United States
    'UN': '110',  # United States
    'VN': '110',  # United States
    'WN': '110',  # United States
    'XN': '110',  # United States
    'YN': '110',  # United States
    'ZN': '110',  # United States
    
    # United States (DM grid squares)
    'DM': '110',  # United States
    'DN': '110',  # United States
    'EM': '110',  # United States
    'EN': '110',  # United States
    'FM': '110',  # United States
    'FN': '110',  # United States
    'GM': '110',  # United States
    'GN': '110',  # United States
    'HM': '110',  # United States
    'HN': '110',  # United States
    'IM': '110',  # United States
    'IN': '110',  # United States
    'JM': '110',  # United States
    'JN': '110',  # United States
    'KM': '110',  # United States
    'KN': '110',  # United States
    'LM': '110',  # United States
    'LN': '110',  # United States
    'MM': '110',  # United States
    'MN': '110',  # United States
    'NM': '110',  # United States
    'NN': '110',  # United States
    'OM': '110',  # United States
    'ON': '110',  # United States
    'PM': '110',  # United States
    'PN': '110',  # United States
    'QM': '110',  # United States
    'QN': '110',  # United States
    'RM': '110',  # United States
    'RN': '110',  # United States
    'SM': '110',  # United States
    'SN': '110',  # United States
    'TM': '110',  # United States
    'TN': '110',  # United States
    'UM': '110',  # United States
    'UN': '110',  # United States
    'VM': '110',  # United States
    'VN': '110',  # United States
    'WM': '110',  # United States
    'WN': '110',  # United States
    'XM': '110',  # United States
    'XN': '110',  # United States
    'YM': '110',  # United States
    'YN': '110',  # United States
    'ZM': '110',  # United States
    'ZN': '110',  # United States
    
    # Alaska
    'AL': '6',
    'BL': '6',
    'CL': '6',
    'DL': '6',
    'EL': '6',
    'FL': '6',
    'GL': '6',
    'HL': '6',
    'IL': '6',
    'JL': '6',
    'KL': '6',
    'LL': '6',
    'ML': '6',
    'NL': '6',
    'OL': '6',
    'PL': '6',
    'QL': '6',
    'RL': '6',
    'SL': '6',
    'TL': '6',
    'UL': '6',
    'VL': '6',
    'WL': '6',
    'XL': '6',
    'YL': '6',
    'ZL': '6',
    
    # Europe
    'JO': '7',  # Albania
    'KP': '5',  # Aland Islands
    'IO': '7',  # Albania
    'JP': '5',  # Aland Islands
    'KO': '7',  # Albania
    'IP': '5',  # Aland Islands
    
    # Middle East
    'LL': '2',  # Abu Dhabi
    'ML': '2',  # Abu Dhabi
    'NL': '2',  # Abu Dhabi
    'OL': '2',  # Abu Dhabi
    'PL': '2',  # Abu Dhabi
    'QL': '2',  # Abu Dhabi
    'RL': '2',  # Abu Dhabi
    'SL': '2',  # Abu Dhabi
    'TL': '2',  # Abu Dhabi
    'UL': '2',  # Abu Dhabi
    'VL': '2',  # Abu Dhabi
    'WL': '2',  # Abu Dhabi
    'XL': '2',  # Abu Dhabi
    'YL': '2',  # Abu Dhabi
    'ZL': '2',  # Abu Dhabi
    
    # South Asia
    'MK': '3',  # Afghanistan
    'NK': '3',  # Afghanistan
    'OK': '3',  # Afghanistan
    'PK': '3',  # Afghanistan
    'QK': '3',  # Afghanistan
    'RK': '3',  # Afghanistan
    'SK': '3',  # Afghanistan
    'TK': '3',  # Afghanistan
    'UK': '3',  # Afghanistan
    'VK': '3',  # Afghanistan
    'WK': '3',  # Afghanistan
    'XK': '3',  # Afghanistan
    'YK': '3',  # Afghanistan
    'ZK': '3',  # Afghanistan
    
    # Indian Ocean - Agalega & St. Brandon
    'LH00': '4',  # Agalega & St. Brandon
    'LH01': '4',  # Agalega & St. Brandon
    'LH02': '4',  # Agalega & St. Brandon
    'LH03': '4',  # Agalega & St. Brandon
    'LH04': '4',  # Agalega & St. Brandon
    'LH05': '4',  # Agalega & St. Brandon
    'LH06': '4',  # Agalega & St. Brandon
    'LH07': '4',  # Agalega & St. Brandon
    'LH08': '4',  # Agalega & St. Brandon
    'LH09': '4',  # Agalega & St. Brandon
    'LH10': '4',  # Agalega & St. Brandon
    'LH11': '4',  # Agalega & St. Brandon
    'LH12': '4',  # Agalega & St. Brandon
    
    # Southern Indian Ocean - Amsterdam & St. Paul Is.
    'LH13': '10',  # Amsterdam & St. Paul Is.
    'LH14': '10',  # Amsterdam & St. Paul Is.
    'LH15': '10',  # Amsterdam & St. Paul Is.
    'LH16': '10',  # Amsterdam & St. Paul Is.
    'LH17': '10',  # Amsterdam & St. Paul Is.
    'LH18': '10',  # Amsterdam & St. Paul Is.
    'LH19': '10',  # Amsterdam & St. Paul Is.
    'LH20': '10',  # Amsterdam & St. Paul Is.
    'LH21': '10',  # Amsterdam & St. Paul Is.
    'LH22': '10',  # Amsterdam & St. Paul Is.
    'LH23': '10',  # Amsterdam & St. Paul Is.
    'LH24': '10',  # Amsterdam & St. Paul Is.
    'LH25': '10',  # Amsterdam & St. Paul Is.
    
    # Pacific Ocean - American Samoa
    'AH': '9',  # American Samoa
    'BH': '9',  # American Samoa
    'CH': '9',  # American Samoa
    'DH': '9',  # American Samoa
    'EH': '9',  # American Samoa
    'FH': '9',  # American Samoa
    'GH': '9',  # American Samoa
    'HH': '9',  # American Samoa
    'IH': '9',  # American Samoa
    'JH': '9',  # American Samoa
    'KH': '9',  # American Samoa
    'MH': '9',  # American Samoa
    'NH': '9',  # American Samoa
    'OH': '9',  # American Samoa
    'PH': '9',  # American Samoa
    'QH': '9',  # American Samoa
    'RH': '9',  # American Samoa
    'SH': '9',  # American Samoa
    'TH': '9',  # American Samoa
    'UH': '9',  # American Samoa
    'VH': '9',  # American Samoa
    'WH': '9',  # American Samoa
    'XH': '9',  # American Samoa
    'YH': '9',  # American Samoa
    'ZH': '9',  # American Samoa
}

# More precise grid mappings for overlapping regions
GRID_TO_DXCC_PRECISE = {
    # Indian Ocean - Agalega & St. Brandon
    'LH00': '4',  # Agalega & St. Brandon
    'LH01': '4',  # Agalega & St. Brandon
    'LH02': '4',  # Agalega & St. Brandon
    'LH03': '4',  # Agalega & St. Brandon
    'LH04': '4',  # Agalega & St. Brandon
    'LH05': '4',  # Agalega & St. Brandon
    'LH06': '4',  # Agalega & St. Brandon
    'LH07': '4',  # Agalega & St. Brandon
    'LH08': '4',  # Agalega & St. Brandon
    'LH09': '4',  # Agalega & St. Brandon
    'LH10': '4',  # Agalega & St. Brandon
    'LH11': '4',  # Agalega & St. Brandon
    'LH12': '4',  # Agalega & St. Brandon
    'LH13': '4',  # Agalega & St. Brandon
    'LH14': '4',  # Agalega & St. Brandon
    'LH15': '4',  # Agalega & St. Brandon
    'LH16': '4',  # Agalega & St. Brandon
    'LH17': '4',  # Agalega & St. Brandon
    'LH18': '4',  # Agalega & St. Brandon
    'LH19': '4',  # Agalega & St. Brandon
    'LH20': '4',  # Agalega & St. Brandon
    'LH21': '4',  # Agalega & St. Brandon
    'LH22': '4',  # Agalega & St. Brandon
    'LH23': '4',  # Agalega & St. Brandon
    'LH24': '4',  # Agalega & St. Brandon
    'LH25': '4',  # Agalega & St. Brandon
    'LH26': '4',  # Agalega & St. Brandon
    'LH27': '4',  # Agalega & St. Brandon
    'LH28': '4',  # Agalega & St. Brandon
    'LH29': '4',  # Agalega & St. Brandon
    'LH30': '4',  # Agalega & St. Brandon
    'LH31': '4',  # Agalega & St. Brandon
    'LH32': '4',  # Agalega & St. Brandon
    'LH33': '4',  # Agalega & St. Brandon
    'LH34': '4',  # Agalega & St. Brandon
    'LH35': '4',  # Agalega & St. Brandon
    'LH36': '4',  # Agalega & St. Brandon
    'LH37': '4',  # Agalega & St. Brandon
    'LH38': '4',  # Agalega & St. Brandon
    'LH39': '4',  # Agalega & St. Brandon
    'LH40': '4',  # Agalega & St. Brandon
    'LH41': '4',  # Agalega & St. Brandon
    'LH42': '4',  # Agalega & St. Brandon
    'LH43': '4',  # Agalega & St. Brandon
    'LH44': '4',  # Agalega & St. Brandon
    'LH45': '4',  # Agalega & St. Brandon
    'LH46': '4',  # Agalega & St. Brandon
    'LH47': '4',  # Agalega & St. Brandon
    'LH48': '4',  # Agalega & St. Brandon
    'LH49': '4',  # Agalega & St. Brandon
    'LH50': '4',  # Agalega & St. Brandon
    'LH51': '4',  # Agalega & St. Brandon
    'LH52': '4',  # Agalega & St. Brandon
    'LH53': '4',  # Agalega & St. Brandon
    'LH54': '4',  # Agalega & St. Brandon
    'LH55': '4',  # Agalega & St. Brandon
    'LH56': '4',  # Agalega & St. Brandon
    'LH57': '4',  # Agalega & St. Brandon
    'LH58': '4',  # Agalega & St. Brandon
    'LH59': '4',  # Agalega & St. Brandon
    'LH60': '4',  # Agalega & St. Brandon
    'LH61': '4',  # Agalega & St. Brandon
    'LH62': '4',  # Agalega & St. Brandon
    'LH63': '4',  # Agalega & St. Brandon
    'LH64': '4',  # Agalega & St. Brandon
    'LH65': '4',  # Agalega & St. Brandon
    'LH66': '4',  # Agalega & St. Brandon
    'LH67': '4',  # Agalega & St. Brandon
    'LH68': '4',  # Agalega & St. Brandon
    'LH69': '4',  # Agalega & St. Brandon
    'LH70': '4',  # Agalega & St. Brandon
    'LH71': '4',  # Agalega & St. Brandon
    'LH72': '4',  # Agalega & St. Brandon
    'LH73': '4',  # Agalega & St. Brandon
    'LH74': '4',  # Agalega & St. Brandon
    'LH75': '4',  # Agalega & St. Brandon
    'LH76': '4',  # Agalega & St. Brandon
    'LH77': '4',  # Agalega & St. Brandon
    'LH78': '4',  # Agalega & St. Brandon
    'LH79': '4',  # Agalega & St. Brandon
    'LH80': '4',  # Agalega & St. Brandon
    'LH81': '4',  # Agalega & St. Brandon
    'LH82': '4',  # Agalega & St. Brandon
    'LH83': '4',  # Agalega & St. Brandon
    'LH84': '4',  # Agalega & St. Brandon
    'LH85': '4',  # Agalega & St. Brandon
    'LH86': '4',  # Agalega & St. Brandon
    'LH87': '4',  # Agalega & St. Brandon
    'LH88': '4',  # Agalega & St. Brandon
    'LH89': '4',  # Agalega & St. Brandon
    'LH90': '4',  # Agalega & St. Brandon
    'LH91': '4',  # Agalega & St. Brandon
    'LH92': '4',  # Agalega & St. Brandon
    'LH93': '4',  # Agalega & St. Brandon
    'LH94': '4',  # Agalega & St. Brandon
    'LH95': '4',  # Agalega & St. Brandon
    'LH96': '4',  # Agalega & St. Brandon
    'LH97': '4',  # Agalega & St. Brandon
    'LH98': '4',  # Agalega & St. Brandon
    'LH99': '4',  # Agalega & St. Brandon
    
    # Southern Indian Ocean - Amsterdam & St. Paul Is.
    'LH00': '10',  # Amsterdam & St. Paul Is.
    'LH01': '10',  # Amsterdam & St. Paul Is.
    'LH02': '10',  # Amsterdam & St. Paul Is.
    'LH03': '10',  # Amsterdam & St. Paul Is.
    'LH04': '10',  # Amsterdam & St. Paul Is.
    'LH05': '10',  # Amsterdam & St. Paul Is.
    'LH06': '10',  # Amsterdam & St. Paul Is.
    'LH07': '10',  # Amsterdam & St. Paul Is.
    'LH08': '10',  # Amsterdam & St. Paul Is.
    'LH09': '10',  # Amsterdam & St. Paul Is.
    'LH10': '10',  # Amsterdam & St. Paul Is.
    'LH11': '10',  # Amsterdam & St. Paul Is.
    'LH12': '10',  # Amsterdam & St. Paul Is.
    'LH13': '10',  # Amsterdam & St. Paul Is.
    'LH14': '10',  # Amsterdam & St. Paul Is.
    'LH15': '10',  # Amsterdam & St. Paul Is.
    'LH16': '10',  # Amsterdam & St. Paul Is.
    'LH17': '10',  # Amsterdam & St. Paul Is.
    'LH18': '10',  # Amsterdam & St. Paul Is.
    'LH19': '10',  # Amsterdam & St. Paul Is.
    'LH20': '10',  # Amsterdam & St. Paul Is.
    'LH21': '10',  # Amsterdam & St. Paul Is.
    'LH22': '10',  # Amsterdam & St. Paul Is.
    'LH23': '10',  # Amsterdam & St. Paul Is.
    'LH24': '10',  # Amsterdam & St. Paul Is.
    'LH25': '10',  # Amsterdam & St. Paul Is.
    'LH26': '10',  # Amsterdam & St. Paul Is.
    'LH27': '10',  # Amsterdam & St. Paul Is.
    'LH28': '10',  # Amsterdam & St. Paul Is.
    'LH29': '10',  # Amsterdam & St. Paul Is.
    'LH30': '10',  # Amsterdam & St. Paul Is.
    'LH31': '10',  # Amsterdam & St. Paul Is.
    'LH32': '10',  # Amsterdam & St. Paul Is.
    'LH33': '10',  # Amsterdam & St. Paul Is.
    'LH34': '10',  # Amsterdam & St. Paul Is.
    'LH35': '10',  # Amsterdam & St. Paul Is.
    'LH36': '10',  # Amsterdam & St. Paul Is.
    'LH37': '10',  # Amsterdam & St. Paul Is.
    'LH38': '10',  # Amsterdam & St. Paul Is.
    'LH39': '10',  # Amsterdam & St. Paul Is.
    'LH40': '10',  # Amsterdam & St. Paul Is.
    'LH41': '10',  # Amsterdam & St. Paul Is.
    'LH42': '10',  # Amsterdam & St. Paul Is.
    'LH43': '10',  # Amsterdam & St. Paul Is.
    'LH44': '10',  # Amsterdam & St. Paul Is.
    'LH45': '10',  # Amsterdam & St. Paul Is.
    'LH46': '10',  # Amsterdam & St. Paul Is.
    'LH47': '10',  # Amsterdam & St. Paul Is.
    'LH48': '10',  # Amsterdam & St. Paul Is.
    'LH49': '10',  # Amsterdam & St. Paul Is.
    'LH50': '10',  # Amsterdam & St. Paul Is.
    'LH51': '10',  # Amsterdam & St. Paul Is.
    'LH52': '10',  # Amsterdam & St. Paul Is.
    'LH53': '10',  # Amsterdam & St. Paul Is.
    'LH54': '10',  # Amsterdam & St. Paul Is.
    'LH55': '10',  # Amsterdam & St. Paul Is.
    'LH56': '10',  # Amsterdam & St. Paul Is.
    'LH57': '10',  # Amsterdam & St. Paul Is.
    'LH58': '10',  # Amsterdam & St. Paul Is.
    'LH59': '10',  # Amsterdam & St. Paul Is.
    'LH60': '10',  # Amsterdam & St. Paul Is.
    'LH61': '10',  # Amsterdam & St. Paul Is.
    'LH62': '10',  # Amsterdam & St. Paul Is.
    'LH63': '10',  # Amsterdam & St. Paul Is.
    'LH64': '10',  # Amsterdam & St. Paul Is.
    'LH65': '10',  # Amsterdam & St. Paul Is.
    'LH66': '10',  # Amsterdam & St. Paul Is.
    'LH67': '10',  # Amsterdam & St. Paul Is.
    'LH68': '10',  # Amsterdam & St. Paul Is.
    'LH69': '10',  # Amsterdam & St. Paul Is.
    'LH70': '10',  # Amsterdam & St. Paul Is.
    'LH71': '10',  # Amsterdam & St. Paul Is.
    'LH72': '10',  # Amsterdam & St. Paul Is.
    'LH73': '10',  # Amsterdam & St. Paul Is.
    'LH74': '10',  # Amsterdam & St. Paul Is.
    'LH75': '10',  # Amsterdam & St. Paul Is.
    'LH76': '10',  # Amsterdam & St. Paul Is.
    'LH77': '10',  # Amsterdam & St. Paul Is.
    'LH78': '10',  # Amsterdam & St. Paul Is.
    'LH79': '10',  # Amsterdam & St. Paul Is.
    'LH80': '10',  # Amsterdam & St. Paul Is.
    'LH81': '10',  # Amsterdam & St. Paul Is.
    'LH82': '10',  # Amsterdam & St. Paul Is.
    'LH83': '10',  # Amsterdam & St. Paul Is.
    'LH84': '10',  # Amsterdam & St. Paul Is.
    'LH85': '10',  # Amsterdam & St. Paul Is.
    'LH86': '10',  # Amsterdam & St. Paul Is.
    'LH87': '10',  # Amsterdam & St. Paul Is.
    'LH88': '10',  # Amsterdam & St. Paul Is.
    'LH89': '10',  # Amsterdam & St. Paul Is.
    'LH90': '10',  # Amsterdam & St. Paul Is.
    'LH91': '10',  # Amsterdam & St. Paul Is.
    'LH92': '10',  # Amsterdam & St. Paul Is.
    'LH93': '10',  # Amsterdam & St. Paul Is.
    'LH94': '10',  # Amsterdam & St. Paul Is.
    'LH95': '10',  # Amsterdam & St. Paul Is.
    'LH96': '10',  # Amsterdam & St. Paul Is.
    'LH97': '10',  # Amsterdam & St. Paul Is.
    'LH98': '10',  # Amsterdam & St. Paul Is.
    'LH99': '10',  # Amsterdam & St. Paul Is.
}

def grid_to_latlon(grid_square: str) -> Tuple[float, float]:
    """
    Convert Maidenhead grid square to latitude and longitude.
    
    Args:
        grid_square (str): The Maidenhead grid square (e.g., 'DM41vv')
        
    Returns:
        tuple: (latitude, longitude) in degrees
    """
    try:
        # Convert to uppercase and ensure we have at least 4 characters
        grid = grid_square.upper()[:4]
        
        # First two characters (A-R)
        lon = (ord(grid[0]) - ord('A')) * 20 - 180
        lat = (ord(grid[1]) - ord('A')) * 10 - 90
        
        # Next two characters (0-9)
        lon += (ord(grid[2]) - ord('0')) * 2
        lat += (ord(grid[3]) - ord('0'))
        
        # If we have 6 characters, add more precision
        if len(grid_square) >= 6:
            lon += (ord(grid_square[4].upper()) - ord('A')) * (2/24)
            lat += (ord(grid_square[5].upper()) - ord('A')) * (1/24)
        
        return lat, lon
    except Exception as e:
        print(f"Error converting grid square {grid_square}: {e}")
        return 0.0, 0.0

def calculate_distance(grid1: str, grid2: str) -> float:
    """
    Calculate the great circle distance between two grid squares in kilometers.
    
    Args:
        grid1 (str): First Maidenhead grid square
        grid2 (str): Second Maidenhead grid square
        
    Returns:
        float: Distance in kilometers
    """
    lat1, lon1 = grid_to_latlon(grid1)
    lat2, lon2 = grid_to_latlon(grid2)
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Earth's radius in kilometers
    
    return c * r

def get_dxcc_info(dxcc_number: str) -> Optional[Dict]:
    """
    Get information about a DXCC entity by its number.
    
    Args:
        dxcc_number (str): The DXCC entity number
        
    Returns:
        dict: Information about the DXCC entity or None if not found
    """
    if dxcc_number in DXCC_ENTITIES:
        return DXCC_ENTITIES[dxcc_number]
    return None

def get_dxcc_by_name(name: str) -> Optional[Dict]:
    """
    Find a DXCC entity by name (case-insensitive partial match).
    
    Args:
        name (str): The name to search for
        
    Returns:
        dict: Information about the matching DXCC entity or None if not found
    """
    name = name.lower()
    for dxcc_num, info in DXCC_ENTITIES.items():
        if name in info['name'].lower():
            return {'dxcc_number': dxcc_num, **info}
    return None

def get_dxcc_by_continent(continent: str) -> List[Dict]:
    """
    Get all DXCC entities in a specific continent.
    
    Args:
        continent (str): The continent code (AF, AS, EU, NA, OC, SA)
        
    Returns:
        list: List of DXCC entities in the specified continent
    """
    return [
        {'dxcc_number': num, **info}
        for num, info in DXCC_ENTITIES.items()
        if info['continent'] == continent.upper()
    ]

def get_dxcc_by_grid(grid_square: str) -> Optional[Dict]:
    """
    Get DXCC entity information based on grid square.
    
    Args:
        grid_square (str): Maidenhead grid square
        
    Returns:
        Optional[Dict]: DXCC entity information or None if not found
    """
    try:
        # First check precise mapping for 4-character grid squares
        if len(grid_square) >= 4:
            precise_key = grid_square[:4].upper()
            if precise_key in GRID_TO_DXCC_PRECISE:
                dxcc_number = GRID_TO_DXCC_PRECISE[precise_key]
                return get_dxcc_info(dxcc_number)
        
        # Then check general mapping for 2-character grid squares
        general_key = grid_square[:2].upper()
        if general_key in GRID_TO_DXCC:
            dxcc_number = GRID_TO_DXCC[general_key]
            return get_dxcc_info(dxcc_number)
        
        return None
    except Exception as e:
        print(f"Error getting DXCC by grid: {e}")
        return None

def get_nearby_dxcc(grid_square: str, max_distance: float = 2000.0) -> List[Dict]:
    """
    Get nearby DXCC entities within a given distance.
    
    Args:
        grid_square (str): The reference grid square
        max_distance (float): Maximum distance in kilometers
        
    Returns:
        list: List of nearby DXCC entities with their distances
    """
    if not grid_square or len(grid_square) < 2:
        return []
        
    # Get the reference coordinates
    ref_lat, ref_lon = grid_to_latlon(grid_square)
    
    # Get the current DXCC entity
    current_dxcc = get_dxcc_by_grid(grid_square)
    if not current_dxcc:
        return []
    
    # Calculate distances to all other entities
    nearby = []
    for dxcc_number, entity in DXCC_ENTITIES.items():
        # Skip the current entity
        if entity['name'] == current_dxcc['name']:
            continue
            
        # For simplicity, use a rough distance calculation
        # In a real implementation, you would use the actual coordinates of each entity
        distance = calculate_distance(grid_square, f"{entity['name'][:2]}00")
        
        if distance <= max_distance:
            nearby.append({
                'name': entity['name'],
                'continent': entity['continent'],
                'itu_zone': entity['itu_zone'],
                'cq_zone': entity['cq_zone'],
                'prefixes': entity['prefixes'],
                'timezone': entity['timezone'],
                'distance': round(distance)
            })
    
    # Sort by distance
    nearby.sort(key=lambda x: x['distance'])
    return nearby

def get_propagation_conditions(grid_square: str) -> Dict:
    """
    Get propagation conditions for a given grid square.
    
    Args:
        grid_square (str): The Maidenhead grid square
        
    Returns:
        dict: Propagation conditions including best bands, times, and directions
    """
    # This is a simplified implementation
    # In a real implementation, you would use actual propagation prediction models
    return {
        'best_bands': ['20m', '40m', '80m'],
        'best_times': ['Dawn', 'Dusk'],
        'best_directions': ['North', 'South'],
        'distance': 0  # This would be calculated based on the target location
    } 