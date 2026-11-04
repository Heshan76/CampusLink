"""Experiment runner: builds the experiment matrix and runs pilot / official batches."""
from datetime import datetime
from pathlib import Path

from .config import load_config
from .contact import contacts_for_scenario
from .gates import APPROVAL_PHRASE, official_run_blockers
from .scenario import scenario_from_config
from .simulator import run_simulation
from .storage import (MESSAGE_FIELDS, RUN_FIELDS, message_rows, run_to_row, write_csv,
                      write_json)


class ExperimentBlocked(Exception):
    """Raised when a safety gate refuses to run the official experiment."""


def build_matrix(cfg):
    """Every (node_count, repetition, method) combination, in a fixed order."""
    return [(n, r, m)
            for n in cfg.node_counts
            for r in range(1, cfg.repetitions + 1)
            for m in cfg.routing_methods]


def run_batch(cfg, experiment_id, combos, pilot=False, seed_override=None, timestamp=None):
    """Run the given (node_count, repetition, method) combos.

    For each (node_count, repetition) ONE scenario is generated and reused for
    every method, so Direct and Epidemic experience identical movement.
    """
    timestamp = timestamp or datetime.now().isoformat(timespec="seconds")  # experiment-session timestamp
    scenarios = {}
    runs = []
    for node_count, repetition, method in combos:
        key = (node_count, repetition)
        if key not in scenarios:
            sc = scenario_from_config(cfg, node_count, repetition, pilot, seed_override)
            scenarios[key] = (sc, contacts_for_scenario(sc, cfg.contact_radius))
        scenario, contacts = scenarios[key]
        runs.append(run_simulation(scenario, method, cfg, experiment_id, repetition,
                                   pilot, contacts, timestamp))
    return runs


def save_runs(folder, runs):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "run_logs.csv", RUN_FIELDS, [run_to_row(r) for r in runs])
    write_csv(folder / "message_logs.csv", MESSAGE_FIELDS,
              [row for r in runs for row in message_rows(r)])


def run_pilot(root, node_count, method, repetition, seed=None, cfg=None):
    """Small pilot: one run. Saved ONLY under outputs/pilot/."""
    cfg = cfg or load_config(Path(root) / "campuslink_config.json")
    if method not in cfg.routing_methods:
        raise ValueError(f"routing method must be one of {cfg.routing_methods}")
    if node_count < 2:
        raise ValueError("node_count must be at least 2")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    experiment_id = f"pilot_{stamp}"
    folder = Path(root) / "outputs" / "pilot" / experiment_id
    runs = run_batch(cfg, experiment_id, [(node_count, repetition, method)], pilot=True,
                     seed_override=seed)
    save_runs(folder, runs)
    write_json(folder / "experiment_config.json", {**cfg.to_dict(), "PILOT_ONLY": True})
    return runs[0], folder


def run_official(root, approval, cfg=None):
    """Full 60-run experiment. Refuses unless every gate is green."""
    from .validation import validate_experiment  # local import avoids a circular import
    cfg = cfg or load_config(Path(root) / "campuslink_config.json")
    blockers = official_run_blockers(root, cfg, approval)
    if blockers:
        raise ExperimentBlocked("Official experiment NOT run:\n- " + "\n- ".join(blockers))

    started = datetime.now()
    experiment_id = "official_" + started.strftime("%Y%m%d_%H%M%S")
    folder = Path(root) / "outputs" / "official" / experiment_id
    folder.mkdir(parents=True, exist_ok=False)   # never reuse a folder

    matrix = build_matrix(cfg)
    runs = run_batch(cfg, experiment_id, matrix, timestamp=started.isoformat(timespec="seconds"))
    save_runs(folder, runs)
    write_json(folder / "experiment_config.json", cfg.to_dict())

    report = validate_experiment(folder)
    finished = datetime.now()
    write_json(folder / "experiment_manifest.json", {
        "experiment_id": experiment_id,
        "started": started.isoformat(timespec="seconds"),
        "finished": finished.isoformat(timespec="seconds"),
        "expected_runs": cfg.expected_runs,
        "actual_runs": len(runs),
        "node_configurations": list(cfg.node_counts),
        "routing_methods": list(cfg.routing_methods),
        "repetitions": cfg.repetitions,
        "base_seed": cfg.base_seed,
        "seeds": {cfg.scenario_id(n, r): cfg.seed_for(n, r)
                  for n in cfg.node_counts for r in range(1, cfg.repetitions + 1)},
        "grid": {"width": cfg.grid_width, "height": cfg.grid_height},
        "data_files": ["run_logs.csv", "message_logs.csv", "experiment_config.json",
                       "experiment_manifest.json"],
        "approval_phrase_used": APPROVAL_PHRASE,
        "validation_status": "PASSED" if report.passed else "FAILED",
    })
    return experiment_id, folder, report


def run_pilot_all(root, repetition=1, cfg=None):
    """Pilot of every node-count/method combination for ONE repetition (6 runs, 3 scenarios).

    Uses pilot seeds (different from official seeds). Saved only under outputs/pilot/.
    """
    cfg = cfg or load_config(Path(root) / "campuslink_config.json")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    experiment_id = f"pilot_{stamp}"
    folder = Path(root) / "outputs" / "pilot" / experiment_id
    combos = [(n, repetition, m) for n in cfg.node_counts for m in cfg.routing_methods]
    runs = run_batch(cfg, experiment_id, combos, pilot=True)
    save_runs(folder, runs)
    write_json(folder / "experiment_config.json", {**cfg.to_dict(), "PILOT_ONLY": True})
    return runs, folder
