"""
This module defines the Driver and Rider classes that represent the main actors in the ride-sharing simulation.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Optional, Tuple
from enum import Enum


class DriverStatus(Enum):
    """Enumeration of possible driver states"""
    OFFLINE = "offline"
    IDLE = "idle"           # Available and waiting for assignment
    DRIVING_TO_PICKUP = "driving_to_pickup"
    DRIVING_TO_DESTINATION = "driving_to_destination"


class RiderStatus(Enum):
    """Enumeration of possible rider states"""
    WAITING = "waiting"          # Waiting for driver match
    MATCHED = "matched"          # Matched, waiting for pickup
    IN_TRANSIT = "in_transit"    # In the taxi
    COMPLETED = "completed"      # Reached destination
    ABANDONED = "abandoned"      # Left due to timeout


@dataclass
class Location:
    """Represents a 2D location in Squareshire"""
    x: float
    y: float

    def distance_to(self, other: 'Location') -> float:
        """Calculate Euclidean distance to another location"""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    @staticmethod
    def random(map_size: float = 20.0) -> 'Location':
        """Generate a random location uniformly distributed in the map"""
        return Location(
            x=random.uniform(0, map_size),
            y=random.uniform(0, map_size)
        )

    def __repr__(self):
        return f"({self.x:.2f}, {self.y:.2f})"


@dataclass
class Driver:
    """
    Represents a driver in the BoxCar system.

    Attributes:
        driver_id: Unique identifier for the driver
        location: Current location of the driver
        status: Current status (OFFLINE, IDLE, etc.)
        available_time: Time when driver came online
        offline_time: Planned time to go offline
        current_rider: Currently assigned rider (if any)
        total_earnings: Accumulated earnings
        total_trips: Number of completed trips
        total_distance: Total distance driven (miles)
        total_idle_time: Time spent waiting for assignments
    """
    driver_id: int
    location: Location
    status: DriverStatus = DriverStatus.OFFLINE
    available_time: float = 0.0
    offline_time: float = 0.0
    current_rider: Optional['Rider'] = None

    # Statistics
    total_earnings: float = 0.0
    total_trips: int = 0
    total_distance: float = 0.0
    total_idle_time: float = 0.0
    total_driving_time: float = 0.0
    last_idle_start: float = 0.0

    def __hash__(self):
        return hash(self.driver_id)

    def go_online(self, time: float, location: Location, availability_duration: float):
        """Driver comes online at specified location"""
        self.status = DriverStatus.IDLE
        self.location = location
        self.available_time = time
        self.offline_time = time + availability_duration
        self.last_idle_start = time

    def go_offline(self, time: float):
        """Driver goes offline"""
        if self.status == DriverStatus.IDLE:
            self.total_idle_time += time - self.last_idle_start
        self.status = DriverStatus.OFFLINE

    def assign_rider(self, rider: 'Rider', time: float):
        """Assign a rider to this driver"""
        if self.status == DriverStatus.IDLE:
            self.total_idle_time += time - self.last_idle_start
        self.current_rider = rider
        self.status = DriverStatus.DRIVING_TO_PICKUP

    def pickup_rider(self, time: float):
        """Pick up the assigned rider"""
        self.status = DriverStatus.DRIVING_TO_DESTINATION

    def complete_trip(self, time: float, fare: float, distance: float):
        """Complete a trip and receive payment"""
        self.total_earnings += fare
        self.total_trips += 1
        self.current_rider = None
        self.status = DriverStatus.IDLE
        self.last_idle_start = time

    def update_location(self, new_location: Location):
        """Update driver's current location"""
        self.location = new_location

    def add_distance(self, distance: float, driving_time: float):
        """Record distance and time driven"""
        self.total_distance += distance
        self.total_driving_time += driving_time

    def get_hourly_earnings(self) -> float:
        """Calculate average hourly earnings"""
        total_time = self.total_idle_time + self.total_driving_time
        if total_time > 0:
            return self.total_earnings / total_time
        return 0.0

    def get_net_earnings(self, petrol_cost_per_mile: float = 0.20) -> float:
        """Calculate net earnings after petrol cost"""
        return self.total_earnings - (self.total_distance * petrol_cost_per_mile)


@dataclass
class Rider:
    """
    Represents a rider (customer) in the BoxCar system.

    Attributes:
        rider_id: Unique identifier for the rider
        origin: Pick-up location
        destination: Drop-off location
        request_time: Time when ride was requested
        patience_time: Maximum time willing to wait for a match
        status: Current status
        assigned_driver: Driver assigned to this rider (if any)
        pickup_time: Time when picked up (if applicable)
        dropoff_time: Time when dropped off (if applicable)
    """
    rider_id: int
    origin: Location
    destination: Location
    request_time: float
    patience_time: float
    status: RiderStatus = RiderStatus.WAITING
    assigned_driver: Optional[Driver] = None
    match_time: Optional[float] = None
    pickup_time: Optional[float] = None
    dropoff_time: Optional[float] = None

    def __hash__(self):
        return hash(self.rider_id)

    def get_trip_distance(self) -> float:
        """Calculate the distance from origin to destination"""
        return self.origin.distance_to(self.destination)

    def get_fare(self, base_fare: float = 3.0, per_mile_rate: float = 2.0) -> float:
        """Calculate the fare for this trip"""
        return base_fare + per_mile_rate * self.get_trip_distance()

    def match_with_driver(self, driver: Driver, time: float):
        """Match this rider with a driver"""
        self.assigned_driver = driver
        self.status = RiderStatus.MATCHED
        self.match_time = time

    def pickup(self, time: float):
        """Rider is picked up"""
        self.status = RiderStatus.IN_TRANSIT
        self.pickup_time = time

    def dropoff(self, time: float):
        """Rider is dropped off at destination"""
        self.status = RiderStatus.COMPLETED
        self.dropoff_time = time

    def abandon(self, time: float):
        """Rider abandons due to timeout"""
        self.status = RiderStatus.ABANDONED

    def get_waiting_time(self) -> Optional[float]:
        """Get the time rider waited for pickup"""
        if self.pickup_time is not None:
            return self.pickup_time - self.request_time
        return None

    def get_total_time(self) -> Optional[float]:
        """Get total time from request to dropoff"""
        if self.dropoff_time is not None:
            return self.dropoff_time - self.request_time
        return None

    def is_patience_exceeded(self, current_time: float) -> bool:
        """Check if rider's patience has been exceeded"""
        return current_time >= self.request_time + self.patience_time
