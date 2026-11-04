"""Contact (encounter) detection using Manhattan distance."""
from typing import List

from .models import Contact


def manhattan(p1, p2) -> int:
    """distance = |x1 - x2| + |y1 - y2|"""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


def find_contacts(positions, radius: int, step: int) -> List[Contact]:
    """All node pairs whose Manhattan distance <= radius at this step.

    Pairs are returned in a fixed order (a < b, ascending) so that routing
    always processes contacts in the same deterministic order.
    With radius 1: same cell or horizontally/vertically adjacent. Diagonals do not count.
    """
    contacts = []
    n = len(positions)
    for a in range(n):
        for b in range(a + 1, n):
            if manhattan(positions[a], positions[b]) <= radius:
                contacts.append(Contact(step, a, b))
    return contacts


def contacts_for_scenario(scenario, radius: int) -> List[List[Contact]]:
    """Contacts for every step 0..max_steps (computed once, shared by both methods)."""
    return [find_contacts(scenario.positions_by_step[t], radius, t)
            for t in range(scenario.max_steps + 1)]
