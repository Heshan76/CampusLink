"""Reading and writing the raw data files (CSV / JSON)."""
import csv
import json
from pathlib import Path

RUN_FIELDS = [
    "experiment_id", "run_id", "scenario_id", "node_count", "routing_method", "repetition",
    "random_seed", "grid_width", "grid_height", "maximum_steps", "contact_radius",
    "messages_attempted", "messages_delivered", "messages_not_delivered",
    "delivery_percentage", "average_delivery_time_steps", "total_copies_created",
    "total_transfer_events", "trace_hash", "steps_simulated", "run_timestamp",
]

MESSAGE_FIELDS = [
    "run_id", "scenario_id", "node_count", "routing_method", "repetition", "random_seed",
    "message_id", "source_node_id", "destination_node_id", "creation_step", "delivered",
    "delivery_step", "delivery_time_steps", "copies_created", "transfer_events",
]

INT_RUN = {"node_count", "repetition", "random_seed", "grid_width", "grid_height",
           "maximum_steps", "contact_radius", "messages_attempted", "messages_delivered",
           "messages_not_delivered", "total_copies_created", "total_transfer_events",
           "steps_simulated"}
FLOAT_RUN = {"delivery_percentage", "average_delivery_time_steps"}
INT_MSG = {"node_count", "repetition", "random_seed", "message_id", "source_node_id",
           "destination_node_id", "creation_step", "delivery_step", "delivery_time_steps",
           "copies_created", "transfer_events"}


def run_to_row(run) -> dict:
    row = {f: getattr(run, f) for f in RUN_FIELDS}
    if row["average_delivery_time_steps"] is None:
        row["average_delivery_time_steps"] = ""      # blank = no delivered message
    return row


def message_rows(run) -> list:
    rows = []
    for m in run.messages:
        rows.append({
            "run_id": run.run_id, "scenario_id": run.scenario_id, "node_count": run.node_count,
            "routing_method": run.routing_method, "repetition": run.repetition,
            "random_seed": run.random_seed, "message_id": m.message_id,
            "source_node_id": m.source_node_id, "destination_node_id": m.destination_node_id,
            "creation_step": m.creation_step, "delivered": "TRUE" if m.delivered else "FALSE",
            "delivery_step": "" if m.delivery_step is None else m.delivery_step,
            "delivery_time_steps": "" if m.delivery_time_steps is None else m.delivery_time_steps,
            "copies_created": m.copies_created, "transfer_events": m.transfer_events,
        })
    return rows


def write_csv(path, fieldnames, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def typed_run_row(row: dict) -> dict:
    """CSV strings -> numbers (blank average time -> None)."""
    out = dict(row)
    for k in INT_RUN:
        out[k] = int(row[k])
    for k in FLOAT_RUN:
        out[k] = float(row[k]) if row[k] != "" else None
    return out


def typed_message_row(row: dict) -> dict:
    out = dict(row)
    for k in INT_MSG:
        out[k] = int(row[k]) if row[k] != "" else None
    out["delivered"] = row["delivered"].upper() == "TRUE"
    return out


def write_json(path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
