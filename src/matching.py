"""
This module implements various matching strategies for pairing available drivers with waiting riders.
"""

from typing import List, Optional, Tuple
from .entities import Driver, Rider, DriverStatus, RiderStatus


class MatchingAlgorithm:
    """Base class for matching algorithms"""

    def find_best_driver(self, rider: Rider, drivers: List[Driver]) -> Optional[Driver]:
        """
        Find the best available driver for a rider.

        Args:
            rider: The rider seeking a match
            drivers: List of all drivers in the system

        Returns:
            The best matching driver, or None if no driver is available
        """
        raise NotImplementedError

    def find_best_rider(self, driver: Driver, riders: List[Rider]) -> Optional[Rider]:
        """
        Find the best waiting rider for a driver.

        Args:
            driver: The driver seeking a rider
            riders: List of all riders in the system

        Returns:
            The best matching rider, or None if no rider is waiting
        """
        raise NotImplementedError


class NearestMatchingAlgorithm(MatchingAlgorithm):
    """
    Matches based on minimum Euclidean distance.

    This is the default matching strategy used by BoxCar:
    - When a rider requests: match with the nearest idle driver
    - When a driver becomes free: match with the nearest waiting rider
    """

    def find_best_driver(self, rider: Rider, drivers: List[Driver]) -> Optional[Driver]:
        """Find the nearest idle driver to the rider's origin"""
        idle_drivers = [d for d in drivers if d.status == DriverStatus.IDLE]

        if not idle_drivers:
            return None

        # Find driver with minimum distance to rider's origin
        best_driver = min(
            idle_drivers,
            key=lambda d: d.location.distance_to(rider.origin)
        )
        return best_driver

    def find_best_rider(self, driver: Driver, riders: List[Rider]) -> Optional[Rider]:
        """Find the nearest waiting rider to the driver's location"""
        waiting_riders = [r for r in riders if r.status == RiderStatus.WAITING]

        if not waiting_riders:
            return None

        # Find rider with minimum distance from driver
        best_rider = min(
            waiting_riders,
            key=lambda r: driver.location.distance_to(r.origin)
        )
        return best_rider


class FIFOMatchingAlgorithm(MatchingAlgorithm):
    """
    First-In-First-Out matching strategy.

    Alternative strategy that prioritizes riders who have been waiting longest.
    """

    def find_best_driver(self, rider: Rider, drivers: List[Driver]) -> Optional[Driver]:
        """Find the nearest idle driver (same as nearest for driver selection)"""
        idle_drivers = [d for d in drivers if d.status == DriverStatus.IDLE]

        if not idle_drivers:
            return None

        # Still use nearest driver for rider
        return min(
            idle_drivers,
            key=lambda d: d.location.distance_to(rider.origin)
        )

    def find_best_rider(self, driver: Driver, riders: List[Rider]) -> Optional[Rider]:
        """Find the rider who has been waiting the longest"""
        waiting_riders = [r for r in riders if r.status == RiderStatus.WAITING]

        if not waiting_riders:
            return None

        # Find rider who requested earliest (FIFO)
        return min(waiting_riders, key=lambda r: r.request_time)


class ZonedMatchingAlgorithm(MatchingAlgorithm):
    """
    Zone-based matching strategy.

    Divides the map into zones and prioritizes matches within the same zone.
    Falls back to nearest matching if no match in zone.
    """

    def __init__(self, zone_size: float = 5.0):
        """
        Initialize with zone size.

        Args:
            zone_size: Size of each zone (default 5 miles, creating 4x4 grid)
        """
        self.zone_size = zone_size

    def _get_zone(self, x: float, y: float) -> Tuple[int, int]:
        """Get the zone coordinates for a location"""
        return (int(x // self.zone_size), int(y // self.zone_size))

    def find_best_driver(self, rider: Rider, drivers: List[Driver]) -> Optional[Driver]:
        """Find driver, prioritizing same zone"""
        idle_drivers = [d for d in drivers if d.status == DriverStatus.IDLE]

        if not idle_drivers:
            return None

        rider_zone = self._get_zone(rider.origin.x, rider.origin.y)

        # First, try to find drivers in the same zone
        same_zone_drivers = [
            d for d in idle_drivers
            if self._get_zone(d.location.x, d.location.y) == rider_zone
        ]

        if same_zone_drivers:
            return min(
                same_zone_drivers,
                key=lambda d: d.location.distance_to(rider.origin)
            )

        # Fall back to nearest overall
        return min(
            idle_drivers,
            key=lambda d: d.location.distance_to(rider.origin)
        )

    def find_best_rider(self, driver: Driver, riders: List[Rider]) -> Optional[Rider]:
        """Find rider, prioritizing same zone"""
        waiting_riders = [r for r in riders if r.status == RiderStatus.WAITING]

        if not waiting_riders:
            return None

        driver_zone = self._get_zone(driver.location.x, driver.location.y)

        # First, try to find riders in the same zone
        same_zone_riders = [
            r for r in waiting_riders
            if self._get_zone(r.origin.x, r.origin.y) == driver_zone
        ]

        if same_zone_riders:
            return min(
                same_zone_riders,
                key=lambda r: driver.location.distance_to(r.origin)
            )

        # Fall back to nearest overall
        return min(
            waiting_riders,
            key=lambda r: driver.location.distance_to(r.origin)
        )


class BatchMatchingAlgorithm(MatchingAlgorithm):
    """
    Batch matching that considers multiple riders and drivers together.

    This is a more sophisticated algorithm that tries to minimize
    total pickup distance across all matches.
    """

    def __init__(self, batch_interval: float = 0.05):
        """
        Initialize batch matching.

        Args:
            batch_interval: Time interval for batch processing (in hours)
        """
        self.batch_interval = batch_interval
        self.pending_matches: List[Tuple[Driver, Rider, float]] = []

    def find_best_driver(self, rider: Rider, drivers: List[Driver]) -> Optional[Driver]:
        """For individual queries, use nearest matching"""
        idle_drivers = [d for d in drivers if d.status == DriverStatus.IDLE]
        if not idle_drivers:
            return None
        return min(idle_drivers, key=lambda d: d.location.distance_to(rider.origin))

    def find_best_rider(self, driver: Driver, riders: List[Rider]) -> Optional[Rider]:
        """For individual queries, use nearest matching"""
        waiting_riders = [r for r in riders if r.status == RiderStatus.WAITING]
        if not waiting_riders:
            return None
        return min(waiting_riders, key=lambda r: driver.location.distance_to(r.origin))

    def batch_match(self, drivers: List[Driver], riders: List[Rider]) -> List[Tuple[Driver, Rider]]:
        """
        Perform batch matching to minimize total pickup distance.

        Uses a greedy algorithm for simplicity.
        Could be replaced with Hungarian algorithm for optimal matching.
        """
        idle_drivers = [d for d in drivers if d.status == DriverStatus.IDLE]
        waiting_riders = [r for r in riders if r.status == RiderStatus.WAITING]

        matches = []
        used_drivers = set()
        used_riders = set()

        # Create all possible pairs with distances
        pairs = []
        for driver in idle_drivers:
            for rider in waiting_riders:
                distance = driver.location.distance_to(rider.origin)
                pairs.append((distance, driver, rider))

        # Sort by distance and greedily match
        pairs.sort(key=lambda x: x[0])

        for distance, driver, rider in pairs:
            if driver.driver_id not in used_drivers and rider.rider_id not in used_riders:
                matches.append((driver, rider))
                used_drivers.add(driver.driver_id)
                used_riders.add(rider.rider_id)

        return matches


def get_matching_algorithm(name: str = "nearest") -> MatchingAlgorithm:
    """
    Factory function to get a matching algorithm by name.

    Args:
        name: Name of the algorithm ('nearest', 'fifo', 'zoned', 'batch')

    Returns:
        An instance of the requested matching algorithm
    """
    algorithms = {
        'nearest': NearestMatchingAlgorithm,
        'fifo': FIFOMatchingAlgorithm,
        'zoned': ZonedMatchingAlgorithm,
        'batch': BatchMatchingAlgorithm,
    }

    if name not in algorithms:
        raise ValueError(f"Unknown matching algorithm: {name}")

    return algorithms[name]()
