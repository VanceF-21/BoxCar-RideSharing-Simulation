"""
This module defines the event types and Event class used to drive the simulation forward in time.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
import heapq


class EventType(Enum):
    """Types of events in the simulation"""
    # Driver events
    DRIVER_ARRIVAL = auto()        # New driver comes online
    DRIVER_OFFLINE = auto()        # Driver goes offline
    DRIVER_REACHES_PICKUP = auto() # Driver arrives at rider's location
    DRIVER_REACHES_DESTINATION = auto()  # Driver arrives at destination

    # Rider events
    RIDER_ARRIVAL = auto()         # New rider requests a ride
    RIDER_ABANDONMENT = auto()     # Rider patience timeout

    # System events
    SIMULATION_END = auto()        # End of simulation


@dataclass(order=True)
class Event:
    """
    Represents an event in the discrete-event simulation.

    Events are ordered by time, with earlier events having higher priority.
    When times are equal, events are ordered by their sequence number.
    """
    time: float
    sequence: int = field(compare=True)  # Tie-breaker for events at same time
    event_type: EventType = field(compare=False)
    entity_id: int = field(compare=False, default=-1)
    data: Any = field(compare=False, default=None)

    def __repr__(self):
        return f"Event({self.event_type.name}, t={self.time:.4f}, id={self.entity_id})"


class EventQueue:
    """
    Priority queue for managing simulation events.

    Uses a min-heap to efficiently retrieve the next event in chronological order.
    """

    def __init__(self):
        self._heap = []
        self._sequence = 0  # Counter for tie-breaking

    def schedule(self, time: float, event_type: EventType,
                 entity_id: int = -1, data: Any = None) -> Event:
        """
        Schedule a new event at the specified time.

        Args:
            time: The simulation time when the event should occur
            event_type: The type of event
            entity_id: ID of the associated entity (driver or rider)
            data: Additional data associated with the event

        Returns:
            The created Event object
        """
        event = Event(
            time=time,
            sequence=self._sequence,
            event_type=event_type,
            entity_id=entity_id,
            data=data
        )
        self._sequence += 1
        heapq.heappush(self._heap, event)
        return event

    def pop(self) -> Optional[Event]:
        """
        Remove and return the next event (earliest time).

        Returns:
            The next event, or None if queue is empty
        """
        if self._heap:
            return heapq.heappop(self._heap)
        return None

    def peek(self) -> Optional[Event]:
        """
        Return the next event without removing it.

        Returns:
            The next event, or None if queue is empty
        """
        if self._heap:
            return self._heap[0]
        return None

    def is_empty(self) -> bool:
        """Check if the event queue is empty"""
        return len(self._heap) == 0

    def __len__(self) -> int:
        """Return the number of events in the queue"""
        return len(self._heap)

    def remove_events(self, event_type: EventType, entity_id: int):
        """
        Remove all events of a specific type for a specific entity.

        Note: This is O(n) operation, use sparingly.
        """
        self._heap = [e for e in self._heap
                      if not (e.event_type == event_type and e.entity_id == entity_id)]
        heapq.heapify(self._heap)

    def clear(self):
        """Clear all events from the queue"""
        self._heap = []
        self._sequence = 0
