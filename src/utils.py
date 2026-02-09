"""
This module provides helper functions for random variate generation,
trip time calculation, fare calculation, and other utilities.
"""

import random
import math
from typing import Tuple
from .entities import Location


class RandomGenerator:
    """
    Random variate generator for the simulation.

    Encapsulates all random number generation for easy seeding
    and reproducibility.
    """

    def __init__(self, seed: int = None):
        """
        Initialize the random generator.

        Args:
            seed: Random seed for reproducibility (None for random seed)
        """
        self.seed = seed
        if seed is not None:
            random.seed(seed)

    def exponential(self, rate: float) -> float:
        """
        Generate exponential random variate.

        Args:
            rate: Lambda parameter (events per unit time)

        Returns:
            Random variate from Exponential(rate) distribution
        """
        return random.expovariate(rate)

    def uniform(self, a: float, b: float) -> float:
        """
        Generate uniform random variate.

        Args:
            a: Lower bound
            b: Upper bound

        Returns:
            Random variate from Uniform(a, b) distribution
        """
        return random.uniform(a, b)

    def location(self, map_size: float = 20.0) -> Location:
        """
        Generate a random location uniformly in the map.

        Args:
            map_size: Size of the map (default 20 miles)

        Returns:
            Random Location object
        """
        return Location(
            x=random.uniform(0, map_size),
            y=random.uniform(0, map_size)
        )


def calculate_trip_time(distance: float, avg_speed: float = 20.0) -> float:
    """
    Calculate the actual trip time with variability.

    The actual trip time is uniformly distributed between 0.8*expected
    and 1.2*expected, where expected = distance / avg_speed.

    Args:
        distance: Distance in miles
        avg_speed: Average speed in miles per hour (default 20)

    Returns:
        Actual trip time in hours
    """
    expected_time = distance / avg_speed
    return random.uniform(0.8 * expected_time, 1.2 * expected_time)


def calculate_fare(distance: float, base_fare: float = 3.0,
                   per_mile_rate: float = 2.0) -> float:
    """
    Calculate the fare for a trip.

    Args:
        distance: Trip distance in miles (origin to destination only)
        base_fare: Initial charge (default £3)
        per_mile_rate: Rate per mile (default £2)

    Returns:
        Total fare in pounds
    """
    return base_fare + per_mile_rate * distance


def calculate_petrol_cost(distance: float, cost_per_mile: float = 0.20) -> float:
    """
    Calculate the petrol cost for driving a distance.

    Args:
        distance: Distance driven in miles
        cost_per_mile: Cost per mile (default £0.20)

    Returns:
        Total petrol cost in pounds
    """
    return distance * cost_per_mile


def format_time(hours: float) -> str:
    """
    Format time in hours to a human-readable string.

    Args:
        hours: Time in hours

    Returns:
        Formatted string (e.g., "2h 30m" or "45m")
    """
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60

    if h > 0:
        return f"{h}h {m}m"
    else:
        return f"{m}m"


def format_duration(hours: float) -> str:
    """
    Format duration for display.

    Args:
        hours: Duration in hours

    Returns:
        Formatted string with appropriate units
    """
    if hours < 1/60:  # Less than 1 minute
        return f"{hours * 3600:.1f} seconds"
    elif hours < 1:   # Less than 1 hour
        return f"{hours * 60:.1f} minutes"
    else:
        return f"{hours:.2f} hours"


class PerformanceMetrics:
    """Helper class for computing various performance metrics"""

    @staticmethod
    def throughput(completed_rides: int, simulation_time: float) -> float:
        """Calculate system throughput (rides per hour)"""
        if simulation_time <= 0:
            return 0.0
        return completed_rides / simulation_time

    @staticmethod
    def average_queue_length(total_queue_time: float, simulation_time: float) -> float:
        """Calculate average queue length using Little's Law"""
        if simulation_time <= 0:
            return 0.0
        return total_queue_time / simulation_time

    @staticmethod
    def utilization(busy_time: float, total_time: float) -> float:
        """Calculate resource utilization"""
        if total_time <= 0:
            return 0.0
        return min(1.0, busy_time / total_time)

    @staticmethod
    def coefficient_of_variation(values: list) -> float:
        """Calculate coefficient of variation (std / mean)"""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance) / mean


def validate_parameters(params: dict) -> bool:
    """
    Validate simulation parameters.

    Args:
        params: Dictionary of simulation parameters

    Returns:
        True if parameters are valid

    Raises:
        ValueError: If any parameter is invalid
    """
    required = ['simulation_time', 'map_size', 'driver_arrival_rate',
                'rider_arrival_rate', 'avg_speed']

    for key in required:
        if key not in params:
            raise ValueError(f"Missing required parameter: {key}")

    if params['simulation_time'] <= 0:
        raise ValueError("simulation_time must be positive")
    if params['map_size'] <= 0:
        raise ValueError("map_size must be positive")
    if params['driver_arrival_rate'] <= 0:
        raise ValueError("driver_arrival_rate must be positive")
    if params['rider_arrival_rate'] <= 0:
        raise ValueError("rider_arrival_rate must be positive")
    if params['avg_speed'] <= 0:
        raise ValueError("avg_speed must be positive")

    return True
