"""Plain data classes used across the simulator."""
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Position = Tuple[int, int]


@dataclass
class Node:
    """A person walking on the grid."""
    node_id: int
    x: int
    y: int

    @property
    def position(self) -> Position:
        return (self.x, self.y)


@dataclass(frozen=True)
class Message:
    message_id: int
    source: int
    destination: int
    creation_step: int


@dataclass(frozen=True)
class Contact:
    """Two nodes that are close enough to talk at a given step (node_a < node_b)."""
    step: int
    node_a: int
    node_b: int


@dataclass
class Scenario:
    """Everything that is random, generated BEFORE any routing method runs.

    positions_by_step[t][i] is the (x, y) of node i at step t.
    Step 0 is the starting layout; steps 1..max_steps are after each move.
    """
    scenario_id: str
    seed: int
    node_count: int
    grid_width: int
    grid_height: int
    max_steps: int
    messages: List[Message]
    positions_by_step: List[List[Position]]

    def trace_hash(self) -> str:
        """Short fingerprint of positions + messages (proves two runs share a scenario)."""
        text = repr(self.positions_by_step) + repr(self.messages)
        return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class MessageResult:
    message_id: int
    source_node_id: int
    destination_node_id: int
    creation_step: int
    delivered: bool
    delivery_step: Optional[int]
    delivery_time_steps: Optional[int]
    copies_created: int
    transfer_events: int


@dataclass
class RunResult:
    experiment_id: str
    run_id: str
    scenario_id: str
    node_count: int
    routing_method: str
    repetition: int
    random_seed: int
    grid_width: int
    grid_height: int
    maximum_steps: int
    contact_radius: int
    messages_attempted: int
    messages_delivered: int
    messages_not_delivered: int
    delivery_percentage: float
    average_delivery_time_steps: Optional[float]
    total_copies_created: int
    total_transfer_events: int
    trace_hash: str
    steps_simulated: int
    run_timestamp: str
    messages: List[MessageResult] = field(default_factory=list)
