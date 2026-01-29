"""
Shared helper functions for ham radio calculations.
"""

from typing import Dict
from .constants import MUF_SFI_TABLE


def extract_sfi(solar_data: Dict) -> float:
    """Extract solar flux index from solar data."""
    try:
        sfi_str = str(solar_data.get('sfi', '100 SFI'))
        sfi_str = sfi_str.replace(' SFI', '').strip()
        return float(sfi_str)
    except (ValueError, TypeError):
        return 100.0


def extract_k_index(solar_data: Dict) -> float:
    """Extract K-index from solar data."""
    try:
        k_str = str(solar_data.get('k_index', '2')).strip()
        return float(k_str)
    except (ValueError, TypeError):
        return 2.0


def extract_a_index(solar_data: Dict) -> float:
    """Extract A-index from solar data."""
    try:
        a_str = str(solar_data.get('a_index', '5')).strip()
        return float(a_str)
    except (ValueError, TypeError):
        return 5.0


def get_base_muf_from_sfi(sfi: float) -> float:
    """Get base MUF value from SFI using lookup table."""
    for threshold, muf in MUF_SFI_TABLE:
        if sfi >= threshold:
            return float(muf)
    return 12.0
