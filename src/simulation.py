"""
This module contains the core simulation logic for the BoxCar ride-sharing system. 
It uses a discrete-event simulation approach where the system state changes only at discrete time points (events).
"""

import random
from typing import Dict, List, Optional
from dataclasses import dataclass

from .entities import (
    Driver, Rider, Location,
    DriverStatus, RiderStatus
)
from .events import Event, EventType, EventQueue
from .matching import MatchingAlgorithm, NearestMatchingAlgorithm
from .statistics import SimulationStatistics, RiderStatistics, DriverStatistics
from .utils import calculate_trip_time, calculate_fare, RandomGenerator


@dataclass
class SimulationConfig:
    """Configuration parameters for the simulation"""
    # Time settings
    simulation_time: float = 24.0  # hours
    warmup_time: float = 2.0       # hours (excluded from statistics)

    # Map settings
    map_size: float = 20.0  # miles (square map)

    # Driver parameters
    driver_arrival_rate: float = 3.0      # per hour (exponential)
    driver_availability_min: float = 5.0   # hours (uniform lower)
    driver_availability_max: float = 8.0   # hours (uniform upper)

    # Rider parameters
    rider_arrival_rate: float = 30.0      # per hour (exponential)
    rider_patience_rate: float = 5.0      # per hour (exponential, mean = 12 min)

    # Trip parameters
    avg_speed: float = 20.0               # miles per hour
    trip_time_variation: float = 0.2      # +/- 20% of expected time

    # Fare parameters
    base_fare: float = 3.0                # £ initial charge
    per_mile_rate: float = 2.0            # £ per mile
    petrol_cost_per_mile: float = 0.20    # £ per mile

    # Simulation settings
    random_seed: Optional[int] = None
    verbose: bool = False


class RideSharingSimulation:
    """
    Discrete-event simulation for the BoxCar ride-sharing system.

    This class manages the simulation state, event processing, and
    statistics collection. It implements the simulation logic as
    described in the project specification.
    """

    def __init__(self, config: SimulationConfig = None,
                 matching_algorithm: MatchingAlgorithm = None):
        """
        Initialize the simulation.

        Args:
            config: Simulation configuration (uses defaults if None)
            matching_algorithm: Algorithm for driver-rider matching
        """
        self.config = config or SimulationConfig()
        self.matching = matching_algorithm or NearestMatchingAlgorithm()

        # Initialize random generator
        self.rng = RandomGenerator(self.config.random_seed)
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)

        # State variables
        self.current_time: float = 0.0
        self.drivers: Dict[int, Driver] = {}
        self.riders: Dict[int, Rider] = {}
        self.event_queue: EventQueue = EventQueue()

        # Counters
        self._next_driver_id = 0
        self._next_rider_id = 0

        # Statistics
        self.stats = SimulationStatistics()

        # Track active entities
        self._waiting_riders: List[Rider] = []
        self._idle_drivers: List[Driver] = []

    def _log(self, message: str):
        """Log a message if verbose mode is enabled"""
        if self.config.verbose:
            print(f"[t={self.current_time:.4f}] {message}")

    def run(self) -> SimulationStatistics:
        """
        Run the simulation.

        Returns:
            SimulationStatistics object with collected metrics
        """
        self._initialize()

        # Process events until simulation ends
        while not self.event_queue.is_empty():
            event = self.event_queue.pop()

            # Check if simulation should end
            if event.time > self.config.simulation_time:
                break

            self.current_time = event.time
            self._process_event(event)

        # Finalize statistics
        self._finalize_statistics()

        return self.stats

    def _initialize(self):
        """Initialize the simulation by scheduling initial events"""
        # Schedule first driver arrival
        first_driver_time = self.rng.exponential(self.config.driver_arrival_rate)
        self.event_queue.schedule(
            time=first_driver_time,
            event_type=EventType.DRIVER_ARRIVAL
        )

        # Schedule first rider arrival
        first_rider_time = self.rng.exponential(self.config.rider_arrival_rate)
        self.event_queue.schedule(
            time=first_rider_time,
            event_type=EventType.RIDER_ARRIVAL
        )

        # Schedule simulation end
        self.event_queue.schedule(
            time=self.config.simulation_time,
            event_type=EventType.SIMULATION_END
        )

        self._log("Simulation initialized")

    def _process_event(self, event: Event):
        """
        Process a single event.

        Args:
            event: The event to process
        """
        handlers = {
            EventType.DRIVER_ARRIVAL: self._handle_driver_arrival,
            EventType.DRIVER_OFFLINE: self._handle_driver_offline,
            EventType.DRIVER_REACHES_PICKUP: self._handle_driver_pickup,
            EventType.DRIVER_REACHES_DESTINATION: self._handle_driver_destination,
            EventType.RIDER_ARRIVAL: self._handle_rider_arrival,
            EventType.RIDER_ABANDONMENT: self._handle_rider_abandonment,
            EventType.SIMULATION_END: self._handle_simulation_end,
        }

        handler = handlers.get(event.event_type)
        if handler:
            handler(event)

    def _handle_driver_arrival(self, event: Event):
        """Handle a new driver coming online"""
        # Create new driver
        driver_id = self._next_driver_id
        self._next_driver_id += 1

        location = self.rng.location(self.config.map_size)
        availability = self.rng.uniform(
            self.config.driver_availability_min,
            self.config.driver_availability_max
        )

        driver = Driver(driver_id=driver_id, location=location)
        driver.go_online(self.current_time, location, availability)
        self.drivers[driver_id] = driver

        self._log(f"Driver {driver_id} came online at {location}")

        # Schedule driver going offline
        self.event_queue.schedule(
            time=driver.offline_time,
            event_type=EventType.DRIVER_OFFLINE,
            entity_id=driver_id
        )

        # Try to match with waiting rider
        self._try_match_driver(driver)

        # Schedule next driver arrival
        next_arrival = self.current_time + self.rng.exponential(
            self.config.driver_arrival_rate
        )
        if next_arrival < self.config.simulation_time:
            self.event_queue.schedule(
                time=next_arrival,
                event_type=EventType.DRIVER_ARRIVAL
            )

    def _handle_driver_offline(self, event: Event):
        """Handle a driver going offline"""
        driver = self.drivers.get(event.entity_id)
        if driver is None:
            return

        # Only go offline if idle (otherwise wait until trip completes)
        if driver.status == DriverStatus.IDLE:
            driver.go_offline(self.current_time)
            self._log(f"Driver {driver.driver_id} went offline")
        else:
            # Driver is busy, will go offline after completing current trip
            pass

    def _handle_driver_pickup(self, event: Event):
        """Handle driver arriving at rider's pickup location"""
        driver = self.drivers.get(event.entity_id)
        if driver is None or driver.current_rider is None:
            return

        rider = driver.current_rider

        # Update states
        driver.pickup_rider(self.current_time)
        rider.pickup(self.current_time)

        self._log(f"Driver {driver.driver_id} picked up Rider {rider.rider_id}")

        # Calculate trip time to destination
        trip_distance = rider.get_trip_distance()
        trip_time = calculate_trip_time(trip_distance, self.config.avg_speed)

        # Update driver's location and distance
        driver.update_location(rider.destination)
        driver.add_distance(trip_distance, trip_time)

        # Schedule arrival at destination
        self.event_queue.schedule(
            time=self.current_time + trip_time,
            event_type=EventType.DRIVER_REACHES_DESTINATION,
            entity_id=driver.driver_id
        )

    def _handle_driver_destination(self, event: Event):
        """Handle driver arriving at rider's destination"""
        driver = self.drivers.get(event.entity_id)
        if driver is None or driver.current_rider is None:
            return

        rider = driver.current_rider

        # Calculate fare and complete trip
        trip_distance = rider.get_trip_distance()
        fare = calculate_fare(
            trip_distance,
            self.config.base_fare,
            self.config.per_mile_rate
        )

        rider.dropoff(self.current_time)
        driver.complete_trip(self.current_time, fare, trip_distance)

        self._log(f"Driver {driver.driver_id} dropped off Rider {rider.rider_id}, "
                  f"fare: £{fare:.2f}")

        # Record rider statistics (only after warmup)
        if self.current_time > self.config.warmup_time:
            self._record_rider_stats(rider)

        # Check if driver should go offline
        if self.current_time >= driver.offline_time:
            driver.go_offline(self.current_time)
            self._log(f"Driver {driver.driver_id} went offline after trip")
        else:
            # Try to match with waiting rider
            self._try_match_driver(driver)

    def _handle_rider_arrival(self, event: Event):
        """Handle a new rider requesting a ride"""
        # Create new rider
        rider_id = self._next_rider_id
        self._next_rider_id += 1

        origin = self.rng.location(self.config.map_size)
        destination = self.rng.location(self.config.map_size)
        patience = self.rng.exponential(self.config.rider_patience_rate)

        rider = Rider(
            rider_id=rider_id,
            origin=origin,
            destination=destination,
            request_time=self.current_time,
            patience_time=patience
        )
        self.riders[rider_id] = rider

        self._log(f"Rider {rider_id} requested ride from {origin} to {destination}")

        # Schedule potential abandonment
        self.event_queue.schedule(
            time=self.current_time + patience,
            event_type=EventType.RIDER_ABANDONMENT,
            entity_id=rider_id
        )

        # Try to match with available driver
        self._try_match_rider(rider)

        # Schedule next rider arrival
        next_arrival = self.current_time + self.rng.exponential(
            self.config.rider_arrival_rate
        )
        if next_arrival < self.config.simulation_time:
            self.event_queue.schedule(
                time=next_arrival,
                event_type=EventType.RIDER_ARRIVAL
            )

    def _handle_rider_abandonment(self, event: Event):
        """Handle rider abandoning due to timeout"""
        rider = self.riders.get(event.entity_id)
        if rider is None:
            return

        # Only abandon if still waiting (not matched)
        if rider.status == RiderStatus.WAITING:
            rider.abandon(self.current_time)
            self._log(f"Rider {rider.rider_id} abandoned (timeout)")

            # Record statistics (only after warmup)
            if self.current_time > self.config.warmup_time:
                self._record_rider_stats(rider)

    def _handle_simulation_end(self, event: Event):
        """Handle end of simulation"""
        self._log("Simulation ended")

    def _try_match_rider(self, rider: Rider):
        """Try to match a rider with an available driver"""
        if rider.status != RiderStatus.WAITING:
            return

        # Get list of idle drivers
        idle_drivers = [d for d in self.drivers.values()
                        if d.status == DriverStatus.IDLE]

        # Find best driver
        best_driver = self.matching.find_best_driver(rider, idle_drivers)

        if best_driver is not None:
            self._create_match(best_driver, rider)

    def _try_match_driver(self, driver: Driver):
        """Try to match a driver with a waiting rider"""
        if driver.status != DriverStatus.IDLE:
            return

        # Get list of waiting riders
        waiting_riders = [r for r in self.riders.values()
                          if r.status == RiderStatus.WAITING]

        # Find best rider
        best_rider = self.matching.find_best_rider(driver, waiting_riders)

        if best_rider is not None:
            self._create_match(driver, best_rider)

    def _create_match(self, driver: Driver, rider: Rider):
        """Create a match between a driver and rider"""
        # Update states
        driver.assign_rider(rider, self.current_time)
        rider.match_with_driver(driver, self.current_time)

        # Cancel the abandonment event for this rider
        self.event_queue.remove_events(
            EventType.RIDER_ABANDONMENT,
            rider.rider_id
        )

        self._log(f"Matched Driver {driver.driver_id} with Rider {rider.rider_id}")

        # Calculate pickup time
        pickup_distance = driver.location.distance_to(rider.origin)
        pickup_time = calculate_trip_time(pickup_distance, self.config.avg_speed)

        # Update driver's distance (pickup doesn't earn fare but costs petrol)
        driver.add_distance(pickup_distance, pickup_time)

        # Schedule pickup event
        self.event_queue.schedule(
            time=self.current_time + pickup_time,
            event_type=EventType.DRIVER_REACHES_PICKUP,
            entity_id=driver.driver_id
        )

    def _record_rider_stats(self, rider: Rider):
        """Record statistics for a completed or abandoned rider"""
        stat = RiderStatistics(
            rider_id=rider.rider_id,
            request_time=rider.request_time,
            origin=(rider.origin.x, rider.origin.y),
            destination=(rider.destination.x, rider.destination.y),
            trip_distance=rider.get_trip_distance(),
            status='completed' if rider.status == RiderStatus.COMPLETED else 'abandoned',
            waiting_time=rider.get_waiting_time(),
            trip_time=(rider.dropoff_time - rider.pickup_time)
                      if rider.dropoff_time and rider.pickup_time else None,
            total_time=rider.get_total_time(),
            fare=rider.get_fare(self.config.base_fare, self.config.per_mile_rate)
                 if rider.status == RiderStatus.COMPLETED else None
        )
        self.stats.record_rider(stat)

    def _finalize_statistics(self):
        """Finalize statistics at the end of simulation"""
        # Record driver statistics
        for driver in self.drivers.values():
            # Make sure to account for final idle time
            if driver.status == DriverStatus.IDLE:
                driver.go_offline(self.current_time)

            # Actual online duration = total idle time + total driving time
            # This accounts for drivers who work past their scheduled offline time
            actual_online = driver.total_idle_time + driver.total_driving_time
            scheduled_online = min(driver.offline_time, self.config.simulation_time) - driver.available_time
            online_duration = max(actual_online, scheduled_online)
            if online_duration <= 0:
                continue

            net_earn = driver.get_net_earnings(self.config.petrol_cost_per_mile)
            utilization = driver.total_driving_time / online_duration if online_duration > 0 else 0.0
            net_hourly = net_earn / online_duration if online_duration > 0 else 0.0
            max_idle = max(driver.idle_blocks) if driver.idle_blocks else 0.0

            stat = DriverStatistics(
                driver_id=driver.driver_id,
                available_time=driver.available_time,
                offline_time=driver.offline_time,
                online_duration=online_duration,
                total_trips=driver.total_trips,
                total_earnings=driver.total_earnings,
                total_distance=driver.total_distance,
                net_earnings=net_earn,
                hourly_earnings=driver.get_hourly_earnings(),
                net_hourly_earnings=net_hourly,
                idle_time=driver.total_idle_time,
                driving_time=driver.total_driving_time,
                utilization=utilization,
                rest_fraction=1.0 - utilization,
                idle_blocks=list(driver.idle_blocks),
                max_idle_block=max_idle,
            )
            self.stats.record_driver(stat)


def run_simulation(config: SimulationConfig = None,
                   matching_algorithm: MatchingAlgorithm = None,
                   num_replications: int = 1) -> List[SimulationStatistics]:
    """
    Convenience function to run multiple simulation replications.

    Args:
        config: Simulation configuration
        matching_algorithm: Matching algorithm to use
        num_replications: Number of replications to run

    Returns:
        List of SimulationStatistics, one per replication
    """
    results = []

    for i in range(num_replications):
        # Create new config with different seed for each replication
        rep_config = config or SimulationConfig()
        if rep_config.random_seed is not None:
            rep_config.random_seed = rep_config.random_seed + i

        sim = RideSharingSimulation(rep_config, matching_algorithm)
        stats = sim.run()
        results.append(stats)

        print(f"Completed replication {i + 1}/{num_replications}")

    return results
