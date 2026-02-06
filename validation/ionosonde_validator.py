"""
Ionosonde-based MUF validation.

Compares calculated MUF values against real ionosonde measurements
from the GIRO network via prop.kc2g.com API.
"""

import urllib.request
import urllib.error
import json
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations.muf_calculator import MUFCalculator

logger = logging.getLogger(__name__)


class IonosondeValidator:
    """Validates MUF calculations against real ionosonde measurements."""

    IONOSONDE_API = "https://prop.kc2g.com/api/stations.json"

    def __init__(self):
        self.muf_calculator = MUFCalculator()
        self.timeout = 15

    def fetch_ionosonde_data(self) -> List[Dict[str, Any]]:
        """Fetch real-time ionosonde data from GIRO via prop.kc2g.com."""
        try:
            req = urllib.request.Request(
                self.IONOSONDE_API,
                headers={'User-Agent': 'ham-radio-conditions/1.0'}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            # Filter for valid, recent measurements with high confidence
            valid_stations = []
            cutoff_time = datetime.now() - timedelta(hours=1)

            for station in data:
                # Check for required fields
                if not station.get('fof2') or not station.get('mufd'):
                    continue

                # Check confidence score (cs)
                cs = station.get('cs', 0)
                if cs < 50:  # Skip low-confidence measurements
                    continue

                # Check timestamp freshness
                time_str = station.get('time', '')
                try:
                    measurement_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    if measurement_time.replace(tzinfo=None) < cutoff_time:
                        continue
                except (ValueError, TypeError):
                    continue

                valid_stations.append({
                    'name': station.get('station', {}).get('name', 'Unknown'),
                    'code': station.get('station', {}).get('code', ''),
                    'lat': float(station.get('station', {}).get('latitude', 0)),
                    'lon': float(station.get('station', {}).get('longitude', 0)),
                    'fof2': float(station['fof2']),
                    'mufd': float(station['mufd']),  # MUF for 3000km path
                    'md': float(station.get('md', 3.0)),  # M-factor
                    'confidence': cs,
                    'timestamp': time_str,
                    'source': station.get('source', 'unknown')
                })

            return valid_stations

        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            logger.error(f"Failed to fetch ionosonde data: {e}")
            return []

    def validate_muf_formula(self, solar_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate MUF calculation against real ionosonde measurements.

        Args:
            solar_data: Dict containing 'sfi', 'k_index', 'a_index'

        Returns:
            Validation report with accuracy metrics
        """
        # Fetch real ionosonde data
        ionosonde_data = self.fetch_ionosonde_data()

        if not ionosonde_data:
            return {
                'success': False,
                'error': 'No ionosonde data available',
                'timestamp': datetime.now().isoformat()
            }

        # Calculate our predicted values
        location_data = {'lat': 40.0, 'lon': -100.0}  # Mid-latitude reference
        calculated = self.muf_calculator.calculate_muf(solar_data, location_data)

        # Extract our calculated foF2 for comparison (using new coefficients)
        sfi = self.muf_calculator._extract_sfi(solar_data)
        our_fof2 = self.muf_calculator.FOF2_COEFFICIENT * math.sqrt(sfi)
        our_muf = calculated['muf']

        # Compare against each ionosonde station
        comparisons = []
        fof2_errors = []
        muf_errors = []

        for station in ionosonde_data:
            measured_fof2 = station['fof2']
            measured_muf = station['mufd']

            # Calculate errors
            fof2_error = abs(our_fof2 - measured_fof2)
            fof2_pct_error = (fof2_error / measured_fof2 * 100) if measured_fof2 > 0 else 0

            muf_error = abs(our_muf - measured_muf)
            muf_pct_error = (muf_error / measured_muf * 100) if measured_muf > 0 else 0

            fof2_errors.append(fof2_pct_error)
            muf_errors.append(muf_pct_error)

            comparisons.append({
                'station': station['name'],
                'code': station['code'],
                'lat': station['lat'],
                'measured_fof2': round(measured_fof2, 2),
                'measured_muf': round(measured_muf, 2),
                'calculated_fof2': round(our_fof2, 2),
                'calculated_muf': round(our_muf, 2),
                'fof2_error_pct': round(fof2_pct_error, 1),
                'muf_error_pct': round(muf_pct_error, 1),
                'confidence': station['confidence'],
                'timestamp': station['timestamp']
            })

        # Calculate summary statistics
        avg_fof2_error = sum(fof2_errors) / len(fof2_errors) if fof2_errors else 0
        avg_muf_error = sum(muf_errors) / len(muf_errors) if muf_errors else 0

        return {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'input_sfi': sfi,
            'calculated_fof2': round(our_fof2, 2),
            'calculated_muf': round(our_muf, 2),
            'stations_compared': len(comparisons),
            'summary': {
                'avg_fof2_error_pct': round(avg_fof2_error, 1),
                'avg_muf_error_pct': round(avg_muf_error, 1),
                'min_fof2_error_pct': round(min(fof2_errors), 1) if fof2_errors else 0,
                'max_fof2_error_pct': round(max(fof2_errors), 1) if fof2_errors else 0,
                'min_muf_error_pct': round(min(muf_errors), 1) if muf_errors else 0,
                'max_muf_error_pct': round(max(muf_errors), 1) if muf_errors else 0,
            },
            'comparisons': comparisons,
            'formula_analysis': self._analyze_formula_accuracy(comparisons, sfi)
        }

    def _analyze_formula_accuracy(self, comparisons: List[Dict], sfi: float) -> Dict[str, Any]:
        """Analyze what coefficients would better match the ionosonde data."""
        if not comparisons:
            return {}

        current_fof2_coef = self.muf_calculator.FOF2_COEFFICIENT
        current_m_factor = self.muf_calculator.M_FACTOR_3000

        measured_fof2_values = [c['measured_fof2'] for c in comparisons]
        avg_measured_fof2 = sum(measured_fof2_values) / len(measured_fof2_values)

        # What coefficient would give us this foF2?
        sqrt_sfi = math.sqrt(sfi)
        optimal_coefficient = avg_measured_fof2 / sqrt_sfi if sqrt_sfi > 0 else current_fof2_coef

        # Analyze M-factor (MUF/foF2 ratio)
        m_factors = []
        for c in comparisons:
            if c['measured_fof2'] > 0:
                m = c['measured_muf'] / c['measured_fof2']
                m_factors.append(m)

        avg_m_factor = sum(m_factors) / len(m_factors) if m_factors else 3.0

        adjustment_pct = ((optimal_coefficient - current_fof2_coef) / current_fof2_coef * 100
                         if current_fof2_coef > 0 else 0)

        return {
            'current_fof2_coefficient': current_fof2_coef,
            'optimal_fof2_coefficient': round(optimal_coefficient, 3),
            'coefficient_adjustment_needed': round(adjustment_pct, 1),
            'current_m_factor': current_m_factor,
            'observed_avg_m_factor': round(avg_m_factor, 2),
            'note': 'M-factor for 3000km path typically ranges 2.5-4.0'
        }

    def run_validation_report(self, solar_data: Optional[Dict] = None) -> str:
        """Run validation and return a formatted report."""
        # Use default solar data if not provided
        if solar_data is None:
            solar_data = {'sfi': '150 SFI', 'k_index': '2', 'a_index': '8'}

        result = self.validate_muf_formula(solar_data)

        if not result['success']:
            return f"Validation failed: {result.get('error', 'Unknown error')}"

        fof2_coef = self.muf_calculator.FOF2_COEFFICIENT
        m_factor = self.muf_calculator.M_FACTOR_3000

        lines = [
            "=" * 70,
            "MUF CALCULATION VALIDATION REPORT",
            "=" * 70,
            f"Timestamp: {result['timestamp']}",
            f"Input SFI: {result['input_sfi']}",
            "",
            "OUR CALCULATED VALUES:",
            f"  foF2: {result['calculated_fof2']} MHz  (formula: {fof2_coef} * sqrt(SFI))",
            f"  MUF:  {result['calculated_muf']} MHz  (formula: {m_factor} * foF2)",
            "",
            f"COMPARED AGAINST {result['stations_compared']} IONOSONDE STATIONS",
            "-" * 70,
            "",
            "SUMMARY STATISTICS:",
            f"  Average foF2 error: {result['summary']['avg_fof2_error_pct']}%",
            f"  Average MUF error:  {result['summary']['avg_muf_error_pct']}%",
            f"  foF2 error range:   {result['summary']['min_fof2_error_pct']}% - {result['summary']['max_fof2_error_pct']}%",
            f"  MUF error range:    {result['summary']['min_muf_error_pct']}% - {result['summary']['max_muf_error_pct']}%",
            "",
            "FORMULA ANALYSIS:",
        ]

        analysis = result['formula_analysis']
        if analysis:
            lines.extend([
                f"  Current foF2 coefficient:  {analysis['current_fof2_coefficient']}",
                f"  Optimal foF2 coefficient:  {analysis['optimal_fof2_coefficient']}",
                f"  Adjustment needed:         {analysis['coefficient_adjustment_needed']}%",
                f"  Current M-factor:          {analysis['current_m_factor']}",
                f"  Observed avg M-factor:     {analysis['observed_avg_m_factor']}",
                f"  Note: {analysis['note']}",
            ])

        lines.extend([
            "",
            "-" * 70,
            "STATION-BY-STATION COMPARISON:",
            "-" * 70,
            f"{'Station':<30} {'Meas foF2':>10} {'Calc foF2':>10} {'Err%':>6} | {'Meas MUF':>10} {'Calc MUF':>10} {'Err%':>6}",
            "-" * 70,
        ])

        for c in result['comparisons'][:15]:  # Show top 15 stations
            lines.append(
                f"{c['station'][:29]:<30} {c['measured_fof2']:>10.2f} {c['calculated_fof2']:>10.2f} {c['fof2_error_pct']:>5.1f}% | "
                f"{c['measured_muf']:>10.2f} {c['calculated_muf']:>10.2f} {c['muf_error_pct']:>5.1f}%"
            )

        if len(result['comparisons']) > 15:
            lines.append(f"... and {len(result['comparisons']) - 15} more stations")

        lines.extend([
            "",
            "=" * 70,
            "INTERPRETATION:",
        ])

        avg_error = result['summary']['avg_muf_error_pct']
        if avg_error < 20:
            lines.append("  MUF calculation is ACCURATE (< 20% average error)")
        elif avg_error < 40:
            lines.append("  MUF calculation is MODERATE (20-40% average error)")
            lines.append("  Consider adjusting the foF2 coefficient based on analysis above")
        else:
            lines.append("  MUF calculation needs IMPROVEMENT (> 40% average error)")
            lines.append("  The formula coefficients may not match current ionospheric conditions")

        lines.append("=" * 70)

        return "\n".join(lines)


def main():
    """Run validation from command line."""
    import argparse

    parser = argparse.ArgumentParser(description='Validate MUF calculations against ionosonde data')
    parser.add_argument('--sfi', type=float, default=150, help='Solar Flux Index (default: 150)')
    parser.add_argument('--k-index', type=float, default=2, help='K-index (default: 2)')
    parser.add_argument('--a-index', type=float, default=8, help='A-index (default: 8)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    solar_data = {
        'sfi': f'{args.sfi} SFI',
        'k_index': str(args.k_index),
        'a_index': str(args.a_index)
    }

    validator = IonosondeValidator()

    if args.json:
        import json
        result = validator.validate_muf_formula(solar_data)
        print(json.dumps(result, indent=2))
    else:
        print(validator.run_validation_report(solar_data))


if __name__ == '__main__':
    main()
