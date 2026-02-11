"""
This module provides classes for collecting, storing, and analyzing
simulation statistics for both riders and drivers.
"""

import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json


@dataclass
class RiderStatistics:
    """Statistics for a single rider"""
    rider_id: int
    request_time: float
    origin: tuple
    destination: tuple
    trip_distance: float
    status: str  # 'completed' or 'abandoned'
    waiting_time: Optional[float] = None  # Time from request to pickup
    trip_time: Optional[float] = None     # Time from pickup to dropoff
    total_time: Optional[float] = None    # Total time from request to dropoff
    fare: Optional[float] = None


@dataclass
class DriverStatistics:
    """Statistics for a single driver"""
    driver_id: int
    available_time: float
    offline_time: float
    online_duration: float
    total_trips: int
    total_earnings: float
    total_distance: float
    net_earnings: float
    hourly_earnings: float        # gross earnings / online_duration
    net_hourly_earnings: float = 0.0  # net_earnings / online_duration (Ê_i in report)
    idle_time: float = 0.0
    driving_time: float = 0.0
    utilization: float = 0.0      # B_i / H_i (busy fraction)
    rest_fraction: float = 0.0    # R_i / H_i = 1 - utilization
    idle_blocks: list = field(default_factory=list)  # list of idle block durations
    max_idle_block: float = 0.0   # ℓ_max_i = max_k ℓ_ik


class SimulationStatistics:
    """
    Collects and analyzes statistics from the simulation.

    Tracks metrics for both rider and driver satisfaction,
    as well as overall system performance.
    """

    def __init__(self):
        self.rider_stats: List[RiderStatistics] = []
        self.driver_stats: List[DriverStatistics] = []

        # Aggregate metrics
        self._total_riders = 0
        self._completed_rides = 0
        self._abandoned_rides = 0
        self._total_waiting_time = 0.0
        self._total_trip_time = 0.0
        self._total_revenue = 0.0

    def record_rider(self, rider_stat: RiderStatistics):
        """Record statistics for a rider"""
        self.rider_stats.append(rider_stat)
        self._total_riders += 1

        if rider_stat.status == 'completed':
            self._completed_rides += 1
            if rider_stat.waiting_time is not None:
                self._total_waiting_time += rider_stat.waiting_time
            if rider_stat.trip_time is not None:
                self._total_trip_time += rider_stat.trip_time
            if rider_stat.fare is not None:
                self._total_revenue += rider_stat.fare
        else:
            self._abandoned_rides += 1

    def record_driver(self, driver_stat: DriverStatistics):
        """Record statistics for a driver"""
        self.driver_stats.append(driver_stat)

    # ==================== Rider Metrics ====================

    def get_abandonment_rate(self) -> float:
        """Calculate the rider abandonment rate"""
        if self._total_riders == 0:
            return 0.0
        return self._abandoned_rides / self._total_riders

    def get_completion_rate(self) -> float:
        """Calculate the ride completion rate"""
        if self._total_riders == 0:
            return 0.0
        return self._completed_rides / self._total_riders

    def get_average_waiting_time(self) -> float:
        """Calculate average waiting time for completed rides"""
        if self._completed_rides == 0:
            return 0.0
        return self._total_waiting_time / self._completed_rides

    def get_waiting_time_distribution(self) -> Dict[str, float]:
        """Get waiting time statistics"""
        waiting_times = [r.waiting_time for r in self.rider_stats
                         if r.waiting_time is not None]
        if not waiting_times:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'median': 0}

        mean = sum(waiting_times) / len(waiting_times)
        variance = sum((x - mean) ** 2 for x in waiting_times) / len(waiting_times)
        std = math.sqrt(variance)
        sorted_times = sorted(waiting_times)
        median = sorted_times[len(sorted_times) // 2]

        return {
            'mean': mean,
            'std': std,
            'min': min(waiting_times),
            'max': max(waiting_times),
            'median': median,
            'count': len(waiting_times)
        }

    def get_pickup_waiting_time_p90(self) -> float:
        """Calculate P90 of pickup waiting times (tail KPI from report Table 1)"""
        waiting_times = [r.waiting_time for r in self.rider_stats
                         if r.waiting_time is not None]
        if not waiting_times:
            return 0.0
        sorted_times = sorted(waiting_times)
        idx = int(math.ceil(0.9 * len(sorted_times))) - 1
        return sorted_times[max(0, idx)]

    def get_average_trip_distance(self) -> float:
        """Calculate average trip distance"""
        distances = [r.trip_distance for r in self.rider_stats
                     if r.status == 'completed']
        if not distances:
            return 0.0
        return sum(distances) / len(distances)

    # ==================== Driver Metrics ====================

    def get_average_hourly_earnings(self) -> float:
        """Calculate average hourly earnings across all drivers"""
        if not self.driver_stats:
            return 0.0
        earnings = [d.hourly_earnings for d in self.driver_stats]
        return sum(earnings) / len(earnings)

    def get_earnings_distribution(self) -> Dict[str, float]:
        """Get earnings distribution statistics"""
        earnings = [d.hourly_earnings for d in self.driver_stats]
        if not earnings:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'gini': 0}

        mean = sum(earnings) / len(earnings)
        variance = sum((x - mean) ** 2 for x in earnings) / len(earnings)
        std = math.sqrt(variance)

        # Calculate Gini coefficient for fairness
        gini = self._calculate_gini(earnings)

        return {
            'mean': mean,
            'std': std,
            'min': min(earnings),
            'max': max(earnings),
            'gini': gini,
            'cv': std / mean if mean > 0 else 0  # Coefficient of variation
        }

    def _calculate_gini(self, values: List[float]) -> float:
        """Calculate Gini coefficient (0 = perfect equality, 1 = perfect inequality)"""
        if not values or sum(values) == 0:
            return 0.0
        sorted_values = sorted(values)
        n = len(sorted_values)
        cumsum = sum((i + 1) * v for i, v in enumerate(sorted_values))
        return (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n

    def get_average_net_hourly_earnings(self) -> float:
        """Calculate system-level average net earnings per hour (Ē from report Table 2)"""
        if not self.driver_stats:
            return 0.0
        earnings = [d.net_hourly_earnings for d in self.driver_stats]
        return sum(earnings) / len(earnings)

    def get_time_weighted_net_hourly_earnings(self) -> float:
        """Calculate time-weighted system net earnings per hour (Ē_w from report)"""
        if not self.driver_stats:
            return 0.0
        total_profit = sum(d.net_earnings for d in self.driver_stats)
        total_hours = sum(d.online_duration for d in self.driver_stats)
        if total_hours <= 0:
            return 0.0
        return total_profit / total_hours

    def get_fairness_ratio(self) -> float:
        """Calculate fairness ratio P90(E_i)/P10(E_i) (report Table 2, smaller is fairer)"""
        if not self.driver_stats:
            return 0.0
        earnings = sorted([d.net_hourly_earnings for d in self.driver_stats])
        n = len(earnings)
        if n < 2:
            return 1.0
        p10_idx = max(0, int(math.ceil(0.1 * n)) - 1)
        p90_idx = max(0, int(math.ceil(0.9 * n)) - 1)
        p10 = earnings[p10_idx]
        p90 = earnings[p90_idx]
        if p10 <= 0:
            return float('inf')
        return p90 / p10

    def get_average_rest_fraction(self) -> float:
        """Calculate average rest fraction across all drivers (1 - U_i)"""
        if not self.driver_stats:
            return 0.0
        rest_fracs = [d.rest_fraction for d in self.driver_stats]
        return sum(rest_fracs) / len(rest_fracs)

    def get_long_rest_probability(self, theta: float = 0.25) -> float:
        """
        Calculate long-rest probability p̂^rest(θ) from report Table 2.
        Fraction of drivers whose max idle block >= θ hours.

        Args:
            theta: rest threshold in hours (default 0.25 = 15 minutes)
        """
        if not self.driver_stats:
            return 0.0
        count = sum(1 for d in self.driver_stats if d.max_idle_block >= theta)
        return count / len(self.driver_stats)

    def get_average_utilization(self) -> float:
        """Calculate average driver utilization"""
        if not self.driver_stats:
            return 0.0
        utils = [d.utilization for d in self.driver_stats]
        return sum(utils) / len(utils)

    def get_trips_per_driver(self) -> Dict[str, float]:
        """Get trips per driver statistics"""
        trips = [d.total_trips for d in self.driver_stats]
        if not trips:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0}

        mean = sum(trips) / len(trips)
        variance = sum((x - mean) ** 2 for x in trips) / len(trips)
        std = math.sqrt(variance)

        return {
            'mean': mean,
            'std': std,
            'min': min(trips),
            'max': max(trips)
        }

    # ==================== System Metrics ====================

    def get_total_revenue(self) -> float:
        """Get total system revenue"""
        return self._total_revenue

    def get_summary(self) -> Dict:
        """Get a comprehensive summary of all statistics"""
        return {
            'rider_metrics': {
                'total_riders': self._total_riders,
                'completed_rides': self._completed_rides,
                'abandoned_rides': self._abandoned_rides,
                'abandonment_rate': self.get_abandonment_rate(),
                'average_waiting_time': self.get_average_waiting_time(),
                'pickup_waiting_time_p90': self.get_pickup_waiting_time_p90(),
                'waiting_time_stats': self.get_waiting_time_distribution(),
                'average_trip_distance': self.get_average_trip_distance(),
            },
            'driver_metrics': {
                'total_drivers': len(self.driver_stats),
                'average_hourly_earnings': self.get_average_hourly_earnings(),
                'average_net_hourly_earnings': self.get_average_net_hourly_earnings(),
                'time_weighted_net_hourly_earnings': self.get_time_weighted_net_hourly_earnings(),
                'fairness_ratio': self.get_fairness_ratio(),
                'earnings_distribution': self.get_earnings_distribution(),
                'average_utilization': self.get_average_utilization(),
                'average_rest_fraction': self.get_average_rest_fraction(),
                'long_rest_prob_15min': self.get_long_rest_probability(0.25),
                'long_rest_prob_30min': self.get_long_rest_probability(0.5),
                'trips_per_driver': self.get_trips_per_driver(),
            },
            'system_metrics': {
                'total_revenue': self.get_total_revenue(),
                'rides_per_hour': self._completed_rides,  # Will be normalized
            }
        }

    def to_json(self, filepath: str):
        """Export statistics to JSON file"""
        data = {
            'summary': self.get_summary(),
            'rider_details': [
                {
                    'rider_id': r.rider_id,
                    'status': r.status,
                    'waiting_time': r.waiting_time,
                    'trip_time': r.trip_time,
                    'trip_distance': r.trip_distance,
                    'fare': r.fare
                }
                for r in self.rider_stats
            ],
            'driver_details': [
                {
                    'driver_id': d.driver_id,
                    'total_trips': d.total_trips,
                    'total_earnings': d.total_earnings,
                    'hourly_earnings': d.hourly_earnings,
                    'utilization': d.utilization
                }
                for d in self.driver_stats
            ]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def print_summary(self):
        """Print a formatted summary of statistics"""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("SIMULATION RESULTS SUMMARY")
        print("=" * 60)

        print("\n--- Rider KPIs (Table 1) ---")
        rm = summary['rider_metrics']
        print(f"Total Riders: {rm['total_riders']}")
        print(f"Completed Rides: {rm['completed_rides']}")
        print(f"Abandoned Rides: {rm['abandoned_rides']}")
        print(f"Abandonment Rate (p_abd): {rm['abandonment_rate']:.4f} ({rm['abandonment_rate']:.2%})")
        print(f"Mean Pickup Wait (W_pu): {rm['average_waiting_time'] * 60:.2f} minutes")
        print(f"P90 Pickup Wait: {rm['pickup_waiting_time_p90'] * 60:.2f} minutes")
        print(f"Average Trip Distance: {rm['average_trip_distance']:.2f} miles")

        print("\n--- Driver KPIs (Table 2) ---")
        dm = summary['driver_metrics']
        print(f"Total Drivers: {dm['total_drivers']}")
        print(f"Avg Net Earnings/hr (E_bar): £{dm['average_net_hourly_earnings']:.2f}")
        print(f"Time-Wtd Net Earnings/hr (E_bar_w): £{dm['time_weighted_net_hourly_earnings']:.2f}")
        fr = dm['fairness_ratio']
        print(f"Fairness Ratio P90/P10: {'inf' if fr == float('inf') else f'{fr:.2f}'}")
        print(f"Avg Utilization (U_hat): {dm['average_utilization']:.4f} ({dm['average_utilization']:.2%})")
        print(f"Avg Rest Fraction (1-U): {dm['average_rest_fraction']:.4f}")
        print(f"Long-Rest Prob (theta=15min): {dm['long_rest_prob_15min']:.4f}")
        print(f"Long-Rest Prob (theta=30min): {dm['long_rest_prob_30min']:.4f}")
        ed = dm['earnings_distribution']
        print(f"Gini Coefficient: {ed['gini']:.3f}")
        print(f"Avg Gross Earnings/hr: £{dm['average_hourly_earnings']:.2f}")

        tpd = dm['trips_per_driver']
        print(f"Avg Trips per Driver: {tpd['mean']:.2f}")

        print("\n--- System Metrics ---")
        print(f"Total Revenue: £{summary['system_metrics']['total_revenue']:.2f}")
        print("=" * 60)
