"""Step-by-step simulation of ONE routing method on ONE (already generated) scenario."""
from datetime import datetime
from typing import List, Optional

from .contact import find_contacts
from .models import MessageResult, RunResult
from .routing import make_router


class Simulation:
    """Advance with step(); the visualizer and the batch runner both use this class."""

    def __init__(self, scenario, method: str, contact_radius: int, contacts_by_step=None,
                 stop_when_all_delivered: bool = False):
        self.scenario = scenario
        self.method = method
        self.radius = contact_radius
        self._contacts_by_step = contacts_by_step
        self.stop_early = stop_when_all_delivered   # proposal: runs continue through all steps
        self.router = make_router(method, scenario.messages)
        self.current_step = -1          # nothing processed yet
        self.current_contacts = []

    @property
    def positions(self):
        t = max(self.current_step, 0)
        return self.scenario.positions_by_step[t]

    @property
    def finished(self) -> bool:
        all_done = self.stop_early and all(s.delivered for s in self.router.states)
        return all_done or self.current_step >= self.scenario.max_steps

    def step(self) -> None:
        if self.finished:
            return
        t = self.current_step + 1
        if self._contacts_by_step is not None:
            contacts = self._contacts_by_step[t]
        else:
            contacts = find_contacts(self.scenario.positions_by_step[t], self.radius, t)
        self.router.process_step(t, contacts)
        self.current_step = t
        self.current_contacts = contacts

    def run_to_end(self) -> None:
        while not self.finished:
            self.step()

    # ---- live counters (visualizer) --------------------------------------
    @property
    def delivered_count(self) -> int:
        return sum(1 for s in self.router.states if s.delivered)

    @property
    def copies_created(self) -> int:
        return sum(s.copies_created for s in self.router.states)

    # ---- results -----------------------------------------------------------
    def message_results(self) -> List[MessageResult]:
        out = []
        for st in self.router.states:
            m = st.message
            dt = (st.delivery_step - m.creation_step) if st.delivered else None
            out.append(MessageResult(m.message_id, m.source, m.destination, m.creation_step,
                                     st.delivered, st.delivery_step if st.delivered else None,
                                     dt, st.copies_created, st.transfer_events))
        return out


def summarize(message_results):
    """Run-level metrics from message-level results (single source of truth)."""
    total = len(message_results)
    delivered = [m for m in message_results if m.delivered]
    pct = (len(delivered) / total * 100.0) if total else 0.0
    # Average over DELIVERED messages only; undelivered are never counted as 0.
    avg = (sum(m.delivery_time_steps for m in delivered) / len(delivered)) if delivered else None
    copies = sum(m.copies_created for m in message_results)
    transfers = sum(m.transfer_events for m in message_results)
    return total, len(delivered), pct, avg, copies, transfers


def run_simulation(scenario, method: str, cfg, experiment_id: str, repetition: int,
                   pilot: bool = False, contacts_by_step=None, timestamp: str = None) -> RunResult:
    """Run one method on a scenario to completion and package the result."""
    sim = Simulation(scenario, method, cfg.contact_radius, contacts_by_step)
    sim.run_to_end()
    msgs = sim.message_results()
    total, delivered, pct, avg, copies, transfers = summarize(msgs)
    return RunResult(
        experiment_id=experiment_id,
        run_id=cfg.run_id(scenario.node_count, method, repetition, pilot),
        scenario_id=scenario.scenario_id,
        node_count=scenario.node_count,
        routing_method=method,
        repetition=repetition,
        random_seed=scenario.seed,
        grid_width=scenario.grid_width,
        grid_height=scenario.grid_height,
        maximum_steps=scenario.max_steps,
        contact_radius=cfg.contact_radius,
        messages_attempted=total,
        messages_delivered=delivered,
        messages_not_delivered=total - delivered,
        delivery_percentage=round(pct, 6),
        average_delivery_time_steps=None if avg is None else round(avg, 6),
        total_copies_created=copies,
        total_transfer_events=transfers,
        trace_hash=scenario.trace_hash(),
        steps_simulated=sim.current_step,
        run_timestamp=timestamp or datetime.now().isoformat(timespec="seconds"),
        messages=msgs,
    )
