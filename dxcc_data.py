"""
DXCC (DX Century Club) data and helper functions.
This module contains the DXCC entity list and functions to work with DXCC data.
"""

# DXCC Entity List (abbreviated for example - full list would be much longer)
DXCC_ENTITIES = {
    '1': {'name': 'Canada', 'continent': 'NA', 'itu_zone': '2', 'cq_zone': '4'},
    '2': {'name': 'Abu Dhabi', 'continent': 'AS', 'itu_zone': '39', 'cq_zone': '21'},
    '3': {'name': 'Afghanistan', 'continent': 'AS', 'itu_zone': '40', 'cq_zone': '21'},
    '4': {'name': 'Agalega & St. Brandon', 'continent': 'AF', 'itu_zone': '53', 'cq_zone': '39'},
    '5': {'name': 'Aland Islands', 'continent': 'EU', 'itu_zone': '18', 'cq_zone': '15'},
    '6': {'name': 'Alaska', 'continent': 'NA', 'itu_zone': '1', 'cq_zone': '1'},
    '7': {'name': 'Albania', 'continent': 'EU', 'itu_zone': '28', 'cq_zone': '15'},
    '8': {'name': 'Aldabra', 'continent': 'AF', 'itu_zone': '53', 'cq_zone': '39'},
    '9': {'name': 'American Samoa', 'continent': 'OC', 'itu_zone': '62', 'cq_zone': '32'},
    '10': {'name': 'Amsterdam & St. Paul Is.', 'continent': 'AF', 'itu_zone': '68', 'cq_zone': '39'},
    '110': {'name': 'United States', 'continent': 'NA', 'itu_zone': '2', 'cq_zone': '4'},
    # Add more entities as needed
}

# Grid square to DXCC mapping
# This is a simplified mapping - a complete implementation would need more precise boundaries
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
}

def get_dxcc_info(dxcc_number):
    """
    Get information about a specific DXCC entity.
    
    Args:
        dxcc_number (str): The DXCC entity number
        
    Returns:
        dict: Information about the DXCC entity or None if not found
    """
    return DXCC_ENTITIES.get(str(dxcc_number))

def get_dxcc_by_name(name):
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

def get_dxcc_by_continent(continent):
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

def get_dxcc_by_grid(grid_square):
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