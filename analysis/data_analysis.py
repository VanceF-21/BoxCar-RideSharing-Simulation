"""
This module provides tools for analyzing the rider and driver
datasets provided by BoxCar to validate or adjust model parameters.
"""

import math
import ast
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import os

# Try to import pandas, provide fallback message if not available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Warning: pandas not available. Install with: pip install pandas openpyxl")


@dataclass
class DataPoint:
    """Generic data point for analysis"""
    value: float
    timestamp: Optional[float] = None


@dataclass
class AnalysisResults:
    """Container for data analysis results"""
    # Driver parameters
    driver_arrival_rate: float = 0.0
    driver_availability_min: float = 0.0
    driver_availability_max: float = 0.0

    # Rider parameters
    rider_arrival_rate: float = 0.0
    rider_patience_mean: float = 0.0

    # Trip parameters
    avg_trip_distance: float = 0.0
    avg_speed: float = 0.0

    # Performance metrics from data
    abandonment_rate: float = 0.0
    avg_waiting_time: float = 0.0

    # Sample sizes
    num_drivers: int = 0
    num_riders: int = 0


class DataAnalyzer:
    """
    Analyzes input data to estimate distribution parameters.

    Can be used to:
    1. Validate BoxCar's assumptions
    2. Fit better distributions to real data
    3. Identify patterns (e.g., time-of-day effects)
    """

    def __init__(self, logger=None):
        """
        Initialize the analyzer.

        Args:
            logger: Optional logger instance for output
        """
        self.rider_df = None
        self.driver_df = None
        self.logger = logger
        self.results = AnalysisResults()

    def _log(self, message: str, level: str = 'info'):
        """Log a message if logger is available"""
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(message)

    def _parse_location(self, loc_str: str) -> Tuple[float, float]:
        """
        Parse location string like '(x, y)' to tuple.

        Args:
            loc_str: Location string in format "(x, y)"

        Returns:
            Tuple of (x, y) coordinates
        """
        try:
            # Use ast.literal_eval for safe parsing
            return ast.literal_eval(loc_str)
        except:
            return (0.0, 0.0)

    def load_data(self, driver_file: str = None, rider_file: str = None) -> bool:
        """
        Load data from Excel files.

        Args:
            driver_file: Path to drivers.xlsx
            rider_file: Path to riders.xlsx

        Returns:
            True if data loaded successfully
        """
        if not PANDAS_AVAILABLE:
            self._log("Cannot load data: pandas not available", 'error')
            return False

        try:
            if driver_file and os.path.exists(driver_file):
                self._log(f"Loading driver data from {driver_file}")
                self.driver_df = pd.read_excel(driver_file)
                self._log(f"  Loaded {len(self.driver_df)} driver records")
                self.results.num_drivers = len(self.driver_df)

            if rider_file and os.path.exists(rider_file):
                self._log(f"Loading rider data from {rider_file}")
                self.rider_df = pd.read_excel(rider_file)
                self._log(f"  Loaded {len(self.rider_df)} rider records")
                self.results.num_riders = len(self.rider_df)

            return True
        except Exception as e:
            self._log(f"Error loading data: {e}", 'error')
            return False

    def analyze_drivers(self) -> Dict:
        """
        Analyze driver data to estimate parameters.

        Returns:
            Dictionary with driver statistics
        """
        if self.driver_df is None:
            return {}

        self._log("Analyzing driver data...")

        # Calculate availability durations
        durations = self.driver_df['offline_time'] - self.driver_df['arrival_time']

        # Calculate inter-arrival times
        arrival_times = self.driver_df['arrival_time'].sort_values().values
        inter_arrivals = [arrival_times[i+1] - arrival_times[i]
                         for i in range(len(arrival_times) - 1)]

        # Estimate arrival rate
        mean_inter_arrival = sum(inter_arrivals) / len(inter_arrivals)
        arrival_rate = 1.0 / mean_inter_arrival if mean_inter_arrival > 0 else 0

        # Parse initial locations
        locations = [self._parse_location(loc)
                     for loc in self.driver_df['initial_location']]

        results = {
            'count': len(self.driver_df),
            'arrival_rate': arrival_rate,
            'mean_inter_arrival_hours': mean_inter_arrival,
            'mean_inter_arrival_minutes': mean_inter_arrival * 60,
            'availability': {
                'mean': durations.mean(),
                'min': durations.min(),
                'max': durations.max(),
                'std': durations.std()
            },
            'location': self._analyze_locations(locations),
            'time_range': {
                'start': self.driver_df['arrival_time'].min(),
                'end': self.driver_df['arrival_time'].max()
            }
        }

        # Update results
        self.results.driver_arrival_rate = arrival_rate
        self.results.driver_availability_min = durations.min()
        self.results.driver_availability_max = durations.max()

        self._log(f"  Arrival rate: {arrival_rate:.2f} per hour")
        self._log(f"  Availability: {durations.min():.1f} - {durations.max():.1f} hours")

        return results

    def analyze_riders(self) -> Dict:
        """
        Analyze rider data to estimate parameters.

        Returns:
            Dictionary with rider statistics
        """
        if self.rider_df is None:
            return {}

        self._log("Analyzing rider data...")

        # Map status values
        status_mapping = {
            'dropped-off': 'completed',
            'abandoned': 'abandoned',
            'dropoff-scheduled': 'completed',
            'pickup-scheduled': 'in_progress'
        }
        self.rider_df['mapped_status'] = self.rider_df['status'].map(
            lambda x: status_mapping.get(x, x)
        )

        # Calculate inter-arrival times
        request_times = self.rider_df['request_time'].sort_values().values
        inter_arrivals = [request_times[i+1] - request_times[i]
                         for i in range(len(request_times) - 1)]

        mean_inter_arrival = sum(inter_arrivals) / len(inter_arrivals)
        arrival_rate = 1.0 / mean_inter_arrival if mean_inter_arrival > 0 else 0

        # Analyze completed rides
        completed = self.rider_df[self.rider_df['mapped_status'] == 'completed'].copy()
        abandoned = self.rider_df[self.rider_df['mapped_status'] == 'abandoned']

        # Calculate waiting times (request to pickup)
        if len(completed) > 0:
            completed['waiting_time'] = completed['pickup_time'] - completed['request_time']
            completed['trip_time'] = completed['dropoff_time'] - completed['pickup_time']

            # Parse locations and calculate distances
            pickup_locs = completed['pickup_location'].apply(self._parse_location)
            dropoff_locs = completed['dropoff_location'].apply(self._parse_location)

            distances = [
                math.sqrt((d[0] - p[0])**2 + (d[1] - p[1])**2)
                for p, d in zip(pickup_locs, dropoff_locs)
            ]
            completed['distance'] = distances

            # Estimate average speed
            valid_trips = completed[completed['trip_time'] > 0]
            if len(valid_trips) > 0:
                avg_speed = valid_trips['distance'].sum() / valid_trips['trip_time'].sum()
            else:
                avg_speed = 20.0  # Default
        else:
            avg_speed = 20.0

        # Calculate abandonment rate
        abandonment_rate = len(abandoned) / len(self.rider_df) if len(self.rider_df) > 0 else 0

        # Estimate patience time from abandoned riders
        # Note: This is approximate since we don't have exact patience times
        patience_estimate = 0.2  # Default ~12 minutes if can't estimate

        results = {
            'count': len(self.rider_df),
            'completed': len(completed),
            'abandoned': len(abandoned),
            'abandonment_rate': abandonment_rate,
            'arrival_rate': arrival_rate,
            'mean_inter_arrival_minutes': mean_inter_arrival * 60,
            'waiting_time': {
                'mean': completed['waiting_time'].mean() if len(completed) > 0 else 0,
                'std': completed['waiting_time'].std() if len(completed) > 0 else 0,
                'mean_minutes': completed['waiting_time'].mean() * 60 if len(completed) > 0 else 0,
            },
            'trip_distance': {
                'mean': completed['distance'].mean() if len(completed) > 0 else 0,
                'std': completed['distance'].std() if len(completed) > 0 else 0,
                'min': completed['distance'].min() if len(completed) > 0 else 0,
                'max': completed['distance'].max() if len(completed) > 0 else 0,
            },
            'estimated_avg_speed': avg_speed,
            'time_range': {
                'start': self.rider_df['request_time'].min(),
                'end': self.rider_df['request_time'].max()
            }
        }

        # Update results
        self.results.rider_arrival_rate = arrival_rate
        self.results.abandonment_rate = abandonment_rate
        self.results.avg_waiting_time = completed['waiting_time'].mean() if len(completed) > 0 else 0
        self.results.avg_trip_distance = completed['distance'].mean() if len(completed) > 0 else 0
        self.results.avg_speed = avg_speed

        self._log(f"  Arrival rate: {arrival_rate:.2f} per hour")
        self._log(f"  Abandonment rate: {abandonment_rate*100:.2f}%")
        self._log(f"  Avg waiting time: {results['waiting_time']['mean_minutes']:.2f} minutes")
        self._log(f"  Avg trip distance: {results['trip_distance']['mean']:.2f} miles")
        self._log(f"  Estimated avg speed: {avg_speed:.2f} mph")

        return results

    def _analyze_locations(self, coordinates: List[Tuple[float, float]],
                          map_size: float = 20.0) -> Dict:
        """Analyze spatial distribution of locations."""
        if not coordinates:
            return {}

        xs = [c[0] for c in coordinates]
        ys = [c[1] for c in coordinates]

        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        expected_mean = map_size / 2

        # Calculate quadrant distribution
        quadrants = {'NE': 0, 'NW': 0, 'SE': 0, 'SW': 0}
        mid = map_size / 2
        for x, y in coordinates:
            if x >= mid and y >= mid:
                quadrants['NE'] += 1
            elif x < mid and y >= mid:
                quadrants['NW'] += 1
            elif x >= mid and y < mid:
                quadrants['SE'] += 1
            else:
                quadrants['SW'] += 1

        n = len(coordinates)
        quadrant_pcts = {k: v / n for k, v in quadrants.items()}

        return {
            'mean_x': mean_x,
            'mean_y': mean_y,
            'expected_mean': expected_mean,
            'quadrant_distribution': quadrant_pcts,
            'sample_size': n
        }

    def get_estimated_parameters(self) -> Dict:
        """
        Get estimated simulation parameters based on data analysis.

        Returns:
            Dictionary with parameter estimates suitable for SimulationConfig
        """
        return {
            'driver_arrival_rate': self.results.driver_arrival_rate,
            'driver_availability_min': self.results.driver_availability_min,
            'driver_availability_max': self.results.driver_availability_max,
            'rider_arrival_rate': self.results.rider_arrival_rate,
            'avg_speed': self.results.avg_speed if self.results.avg_speed > 0 else 20.0,
        }

    def compare_with_assumptions(self) -> Dict:
        """
        Compare estimated parameters with BoxCar's assumptions.

        Returns:
            Dictionary comparing assumed vs estimated values
        """
        assumptions = {
            'driver_arrival_rate': 3.0,
            'driver_availability_min': 5.0,
            'driver_availability_max': 8.0,
            'rider_arrival_rate': 30.0,
            'avg_speed': 20.0,
        }

        estimated = self.get_estimated_parameters()

        comparison = {}
        for key in assumptions:
            assumed = assumptions[key]
            est = estimated.get(key, 0)
            diff_pct = ((est - assumed) / assumed * 100) if assumed != 0 else 0
            comparison[key] = {
                'assumed': assumed,
                'estimated': est,
                'difference_pct': diff_pct
            }

        return comparison

    def generate_report(self) -> str:
        """Generate a summary report of data analysis"""
        lines = []
        lines.append("=" * 70)
        lines.append("DATA ANALYSIS REPORT")
        lines.append("=" * 70)

        if self.driver_df is not None:
            driver_results = self.analyze_drivers()
            lines.append("\n--- DRIVER ANALYSIS ---")
            lines.append(f"Total drivers: {driver_results['count']}")
            lines.append(f"Arrival rate: {driver_results['arrival_rate']:.2f} per hour")
            lines.append(f"Mean inter-arrival: {driver_results['mean_inter_arrival_minutes']:.2f} minutes")
            lines.append(f"Availability range: {driver_results['availability']['min']:.1f} - "
                        f"{driver_results['availability']['max']:.1f} hours")

        if self.rider_df is not None:
            rider_results = self.analyze_riders()
            lines.append("\n--- RIDER ANALYSIS ---")
            lines.append(f"Total riders: {rider_results['count']}")
            lines.append(f"Completed: {rider_results['completed']}")
            lines.append(f"Abandoned: {rider_results['abandoned']}")
            lines.append(f"Abandonment rate: {rider_results['abandonment_rate']*100:.2f}%")
            lines.append(f"Arrival rate: {rider_results['arrival_rate']:.2f} per hour")
            lines.append(f"Avg waiting time: {rider_results['waiting_time']['mean_minutes']:.2f} minutes")
            lines.append(f"Avg trip distance: {rider_results['trip_distance']['mean']:.2f} miles")
            lines.append(f"Estimated avg speed: {rider_results['estimated_avg_speed']:.2f} mph")

        # Comparison with assumptions
        if self.driver_df is not None or self.rider_df is not None:
            comparison = self.compare_with_assumptions()
            lines.append("\n--- COMPARISON WITH ASSUMPTIONS ---")
            lines.append(f"{'Parameter':<30} {'Assumed':>12} {'Estimated':>12} {'Diff %':>10}")
            lines.append("-" * 66)
            for key, vals in comparison.items():
                lines.append(f"{key:<30} {vals['assumed']:>12.2f} {vals['estimated']:>12.2f} "
                           f"{vals['difference_pct']:>+10.1f}%")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)


def analyze_input_data(driver_file: str = None, rider_file: str = None,
                       logger=None) -> Dict:
    """
    Analyze input data files and return estimated parameters.

    Args:
        driver_file: Path to driver data file
        rider_file: Path to rider data file
        logger: Optional logger instance

    Returns:
        Dictionary with estimated parameters and analysis results
    """
    analyzer = DataAnalyzer(logger=logger)
    analyzer.load_data(driver_file, rider_file)

    results = {
        'parameters': analyzer.get_estimated_parameters(),
        'comparison': analyzer.compare_with_assumptions(),
        'report': analyzer.generate_report(),
        'results': analyzer.results
    }

    return results
