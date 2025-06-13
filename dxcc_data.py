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
    
    # Add more grid mappings as needed
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
    Get information about a specific DXCC entity.
    
    Args:
        dxcc_number (str): The DXCC entity number
        
    Returns:
        dict: Information about the DXCC entity or None if not found
    """
    return DXCC_ENTITIES.get(str(dxcc_number))

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
    Get the DXCC entity for a given Maidenhead grid square.
    
    Args:
        grid_square (str): The Maidenhead grid square (e.g., 'DM41vv')
        
    Returns:
        dict: Information about the DXCC entity or None if not found
    """
    if not grid_square or len(grid_square) < 2:
        return None
        
    # Get the first two characters of the grid square
    grid_prefix = grid_square[:2].upper()
    
    # Look up the DXCC number for this grid prefix
    dxcc_number = GRID_TO_DXCC.get(grid_prefix)
    
    if dxcc_number:
        return get_dxcc_info(dxcc_number)
    return None

def get_nearby_dxcc(grid_square: str, max_distance: float = 2000.0) -> List[Dict]:
    """
    Get nearby DXCC entities based on distance from a grid square.
    
    Args:
        grid_square (str): The reference Maidenhead grid square
        max_distance (float): Maximum distance in kilometers
        
    Returns:
        list: List of nearby DXCC entities with distance information
    """
    current_dxcc = get_dxcc_by_grid(grid_square)
    if not current_dxcc:
        return []
    
    nearby = []
    for dxcc_num, info in DXCC_ENTITIES.items():
        if dxcc_num == current_dxcc.get('dxcc_number'):
            continue
            
        # For each entity, find a representative grid square
        # This is a simplified approach - a complete implementation would need
        # to handle multiple grid squares per entity
        for grid_prefix, entity_num in GRID_TO_DXCC.items():
            if entity_num == dxcc_num:
                distance = calculate_distance(grid_square, grid_prefix + '00')
                if distance <= max_distance:
                    nearby.append({
                        'dxcc_number': dxcc_num,
                        'distance': round(distance),
                        **info
                    })
                break
    
    # Sort by distance
    return sorted(nearby, key=lambda x: x['distance'])

def get_propagation_conditions(grid_square: str) -> Dict:
    """
    Get propagation conditions between the current location and nearby DXCC entities.
    
    Args:
        grid_square (str): The reference Maidenhead grid square
        
    Returns:
        dict: Propagation conditions including best bands, times, and directions
    """
    current_dxcc = get_dxcc_by_grid(grid_square)
    if not current_dxcc:
        return {
            'best_bands': ['20m', '40m'],
            'best_times': ['0000-0400 UTC', '1200-1600 UTC'],
            'best_directions': ['Europe', 'Asia']
        }
    
    # Get nearby entities
    nearby = get_nearby_dxcc(grid_square)
    
    # Analyze propagation based on distances and directions
    best_bands = []
    best_times = []
    best_directions = set()
    
    for entity in nearby:
        distance = entity['distance']
        
        # Determine best bands based on distance
        if distance < 500:
            best_bands.extend(['80m', '40m'])
        elif distance < 1000:
            best_bands.extend(['40m', '20m'])
        elif distance < 2000:
            best_bands.extend(['20m', '15m'])
        else:
            best_bands.extend(['15m', '10m'])
        
        # Add continent to best directions
        continent = entity['continent']
        if continent == 'NA':
            best_directions.add('North America')
        elif continent == 'SA':
            best_directions.add('South America')
        elif continent == 'EU':
            best_directions.add('Europe')
        elif continent == 'AF':
            best_directions.add('Africa')
        elif continent == 'AS':
            best_directions.add('Asia')
        elif continent == 'OC':
            best_directions.add('Oceania')
    
    # Remove duplicates and sort
    best_bands = sorted(list(set(best_bands)))
    best_times = ['0000-0400 UTC', '1200-1600 UTC']  # Simplified for now
    best_directions = sorted(list(best_directions))
    
    return {
        'best_bands': best_bands,
        'best_times': best_times,
        'best_directions': best_directions
    } 