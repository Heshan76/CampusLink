"""Scenario generation: start positions, messages and the whole movement trace.

The scenario is generated ONLY from the seed, before any routing runs.
Direct and Epidemic therefore replay exactly the same walk.
"""
import random

from .models import Message, Node, Scenario
from .movement import move_node


def generate_scenario(scenario_id: str, seed: int, node_count: int, width: int, height: int,
                      max_steps: int, message_count: int) -> Scenario:
    rng = random.Random(seed)  # private generator: never touches global random state

    # 1) start positions (several nodes may share a cell)
    nodes = [Node(i, rng.randrange(width), rng.randrange(height)) for i in range(node_count)]

    # 2) messages: source != destination, all created at step 0
    messages = []
    for m in range(1, message_count + 1):
        source = rng.randrange(node_count)
        destination = rng.randrange(node_count - 1)
        if destination >= source:  # skip over the source so dest != source, still uniform
            destination += 1
        messages.append(Message(m, source, destination, creation_step=0))

    # 3) full movement trace: positions at step 0, 1, ..., max_steps
    trace = [[n.position for n in nodes]]
    for _ in range(max_steps):
        for node in nodes:  # fixed node order keeps the random stream reproducible
            move_node(node, rng, width, height)
        trace.append([n.position for n in nodes])

    return Scenario(scenario_id, seed, node_count, width, height, max_steps, messages, trace)


def scenario_from_config(cfg, node_count: int, repetition: int, pilot: bool = False,
                         seed: int = None) -> Scenario:
    seed = cfg.seed_for(node_count, repetition, pilot) if seed is None else seed
    return generate_scenario(cfg.scenario_id(node_count, repetition, pilot), seed, node_count,
                             cfg.grid_width, cfg.grid_height, cfg.max_steps, cfg.messages_per_run)
