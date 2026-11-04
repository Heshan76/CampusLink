"""Direct and Epidemic routing.

Vocabulary used in the code and the report
------------------------------------------
* holder          : a node that currently owns a message.
* copy created    : a NEW node receives the message for the first time while the
                    source keeps its own. (Epidemic only.)
* hand-over       : Direct routing gives the ORIGINAL message to the destination.
                    This is not a copy, so Direct always has 0 copies.
* transfer event  : any successful message transfer (diagnostic only).
"""
from typing import List


class MessageState:
    """Book-keeping for one message during one run."""

    def __init__(self, message):
        self.message = message
        self.holders = {message.source}  # the source owns the original at the start
        self.delivered = False
        self.delivery_step = None
        self.copies_created = 0
        self.transfer_events = 0

    def mark_delivered(self, step: int) -> None:
        self.delivered = True
        self.delivery_step = step


class Router:
    method = ""

    def __init__(self, messages):
        self.states: List[MessageState] = [MessageState(m) for m in messages]

    def process_step(self, step: int, contacts) -> None:
        raise NotImplementedError


class DirectRouter(Router):
    """The source keeps the message until it meets the destination in person."""
    method = "DIRECT"

    def process_step(self, step, contacts):
        for st in self.states:
            if st.delivered:
                continue
            src, dst = st.message.source, st.message.destination
            for c in contacts:
                if (c.node_a, c.node_b) in ((src, dst), (dst, src)):
                    # Hand-over of the original: the destination now holds it, no copy made.
                    st.holders = {dst}
                    st.transfer_events += 1
                    st.mark_delivered(step)
                    break


class EpidemicRouter(Router):
    """Holders pass a copy to every neighbour that does not have one yet.

    Rules that keep the counting exact and independent of contact order:
    1. Spreading uses a SNAPSHOT of the holders taken at the start of the step,
       so a message moves at most one hop per step.
    2. Delivery check comes first: if the destination touches a holder this step,
       the destination gets its copy, the message is delivered, and nothing else
       is replicated in that step.
    3. After delivery, replication of that message stops (implementation decision
       to keep the experiment controlled).
    4. A node never receives the same message twice: we only copy to nodes that
       are not already in `holders`.
    """
    method = "EPIDEMIC"

    def process_step(self, step, contacts):
        for st in self.states:
            if st.delivered:
                continue
            dst = st.message.destination
            snapshot = frozenset(st.holders)

            # Rule 2: delivery first
            met = any((c.node_a == dst and c.node_b in snapshot) or
                      (c.node_b == dst and c.node_a in snapshot) for c in contacts)
            if met:
                st.holders.add(dst)
                st.copies_created += 1
                st.transfer_events += 1
                st.mark_delivered(step)
                continue

            # Otherwise spread to new neighbours of holders
            for c in contacts:
                for giver, receiver in ((c.node_a, c.node_b), (c.node_b, c.node_a)):
                    if giver in snapshot and receiver not in st.holders:
                        st.holders.add(receiver)
                        st.copies_created += 1
                        st.transfer_events += 1


def make_router(method: str, messages) -> Router:
    if method == "DIRECT":
        return DirectRouter(messages)
    if method == "EPIDEMIC":
        return EpidemicRouter(messages)
    raise ValueError(f"Unknown routing method: {method!r}")
