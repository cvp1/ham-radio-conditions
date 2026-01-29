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

# MUF lookup table based on SFI (empirically derived)
MUF_SFI_TABLE = [
    (150, 40),  # SFI >= 150: Very high solar activity
    (120, 32),  # SFI >= 120: High solar activity
    (100, 26),  # SFI >= 100: Good solar activity
    (80, 21),   # SFI >= 80: Moderate solar activity
    (60, 16),   # SFI >= 60: Low solar activity
    (0, 12),    # SFI < 60: Very low solar activity
]

# Cache durations in seconds
CACHE_DURATION_WEATHER = 1800  # 30 minutes
CACHE_DURATION_SOLAR = 300     # 5 minutes
CACHE_DURATION_SPOTS = 300     # 5 minutes

# API timeouts in seconds
API_TIMEOUT_DEFAULT = 10
API_TIMEOUT_SHORT = 5
API_TIMEOUT_SPOTS = 8

# MUF validation ranges
MUF_MIN = 10.0
MUF_MAX = 50.0
