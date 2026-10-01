"""
Shared constants for ham radio calculations.
"""

# Band frequencies in MHz
BAND_FREQUENCIES = {
    '160m': 1.8,
    '80m': 3.5,
    '40m': 7.0,
    '30m': 10.1,
    '20m': 14.0,
    '17m': 18.1,
    '15m': 21.0,
    '12m': 24.9,
    '10m': 28.0,
    '6m': 50.0
}

# (minimum SFI, MUF in MHz), highest first; empirically derived.
MUF_SFI_TABLE = [
    (150, 40),
    (120, 32),
    (100, 26),
    (80, 21),
    (60, 16),
    (0, 12),
]

# Cache durations in seconds
CACHE_DURATION_WEATHER = 1800
CACHE_DURATION_SOLAR = 300
CACHE_DURATION_SPOTS = 300

# API timeouts in seconds
API_TIMEOUT_DEFAULT = 10
API_TIMEOUT_SHORT = 5
API_TIMEOUT_SPOTS = 8

MUF_MIN = 10.0
MUF_MAX = 50.0
