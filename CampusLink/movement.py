"""Random movement on a bounded grid (no wrap-around)."""
import random

# The four allowed moves: left, right, up, down. No diagonals.
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def valid_moves(x: int, y: int, width: int, height: int):
    """Moves that keep the node inside the grid (corners have 2, edges 3, inside 4)."""
    return [(dx, dy) for dx, dy in DIRECTIONS
            if 0 <= x + dx < width and 0 <= y + dy < height]


def move_node(node, rng: random.Random, width: int, height: int) -> None:
    """Each step a node either STAYS or moves one cell (proposal section 5.1).

    The choice is uniform among: stay + every move that keeps the node inside the grid.
    """
    dx, dy = rng.choice([(0, 0)] + valid_moves(node.x, node.y, width, height))
    node.x += dx
    node.y += dy
