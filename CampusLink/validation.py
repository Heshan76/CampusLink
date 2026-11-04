"""Independent validation of a saved experiment folder.

Reads only the saved files (CSV/JSON), recomputes every metric from the
message-level rows, and finally REPLAYS every run from its seed to confirm the
saved numbers are what the simulator really produces.
"""
from collections import Counter, defaultdict
from pathlib import Path

from .config import ExperimentConfig
from .contact import contacts_for_scenario
from .experiment import build_matrix, run_batch
from .storage import (MESSAGE_FIELDS, RUN_FIELDS, read_csv, read_json, typed_message_row,
                      typed_run_row)

TOL = 1e-4


class ValidationReport:
    def __init__(self, folder):
        self.folder = str(folder)
        self.checks = []   # (name, passed, detail)

    def add(self, name, passed, detail=""):
        self.checks.append((name, bool(passed), detail))

    @property
    def passed(self):
        return all(p for _, p, _ in self.checks)

    def failures(self):
        return [(n, d) for n, p, d in self.checks if not p]

    def text(self):
        lines = [f"Validation report for {self.folder}", ""]
        for name, ok, detail in self.checks:
            lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
        lines += ["", f"OVERALL: {'PASSED' if self.passed else 'FAILED'} "
                      f"({sum(p for _, p, _ in self.checks)}/{len(self.checks)} checks passed)"]
        return "\n".join(lines)


def validate_experiment(folder) -> ValidationReport:
    folder = Path(folder)
    rep = ValidationReport(folder)

    # ---- files and structure -------------------------------------------
    needed = ["run_logs.csv", "message_logs.csv", "experiment_config.json"]
    missing = [f for f in needed if not (folder / f).exists()]
    rep.add("Required files exist", not missing, f"missing: {missing}" if missing else "")
    if missing:
        return rep

    raw_runs = read_csv(folder / "run_logs.csv")
    raw_msgs = read_csv(folder / "message_logs.csv")
    with open(folder / "run_logs.csv", encoding="utf-8") as fh:
        run_header = fh.readline().strip().split(",")
    with open(folder / "message_logs.csv", encoding="utf-8") as fh:
        msg_header = fh.readline().strip().split(",")
    rep.add("run_logs.csv columns correct", run_header == RUN_FIELDS)
    rep.add("message_logs.csv columns correct", msg_header == MESSAGE_FIELDS)
    if run_header != RUN_FIELDS or msg_header != MESSAGE_FIELDS:
        return rep

    cfg = ExperimentConfig.from_dict(read_json(folder / "experiment_config.json"))
    runs = [typed_run_row(r) for r in raw_runs]
    msgs = [typed_message_row(m) for m in raw_msgs]

    # ---- run count, duplicates, repetitions ------------------------------
    rep.add("Run count matches design", len(runs) == cfg.expected_runs,
            f"expected {cfg.expected_runs}, found {len(runs)}")
    ids = [r["run_id"] for r in runs]
    dupes = [k for k, v in Counter(ids).items() if v > 1]
    rep.add("No duplicate run_id", not dupes, str(dupes))
    combo_counts = Counter((r["node_count"], r["routing_method"]) for r in runs)
    expected_combos = {(n, m): cfg.repetitions for n in cfg.node_counts for m in cfg.routing_methods}
    rep.add("Every node-count/method combination has the right number of repetitions",
            dict(combo_counts) == expected_combos, str(dict(combo_counts)))
    reps_ok = all(sorted(r["repetition"] for r in runs if (r["node_count"], r["routing_method"]) == c)
                  == list(range(1, cfg.repetitions + 1)) for c in expected_combos)
    rep.add("Repetition numbers are 1..N for every combination", reps_ok)
    rep.add("Run IDs match the expected experiment matrix",
            sorted(ids) == sorted(cfg.run_id(n, m, r) for n, r, m in build_matrix(cfg)))

    # ---- paired scenarios: same seed + same movement trace ----------------
    by_scn = defaultdict(list)
    for r in runs:
        by_scn[r["scenario_id"]].append(r)
    pairs_ok = all(len(v) == len(cfg.routing_methods) and
                   len({x["random_seed"] for x in v}) == 1 and
                   len({x["trace_hash"] for x in v}) == 1 and
                   {x["routing_method"] for x in v} == set(cfg.routing_methods)
                   for v in by_scn.values())
    rep.add("Direct/Epidemic pairs share seed and movement-trace hash", pairs_ok and bool(by_scn))
    seeds_ok = all(r["random_seed"] == cfg.seed_for(r["node_count"], r["repetition"]) for r in runs)
    rep.add("Seeds follow the documented formula", seeds_ok)
    same_cfg = all(r["grid_width"] == cfg.grid_width and r["grid_height"] == cfg.grid_height and
                   r["maximum_steps"] == cfg.max_steps and r["contact_radius"] == cfg.contact_radius
                   for r in runs)
    rep.add("Every run row records the configured grid, steps and radius", same_cfg)

    # ---- message level ----------------------------------------------------
    keys = [(m["run_id"], m["message_id"]) for m in msgs]
    rep.add("No duplicate message records", len(keys) == len(set(keys)))
    msgs_by_run = defaultdict(list)
    for m in msgs:
        msgs_by_run[m["run_id"]].append(m)
    rep.add("Every run has exactly messages_attempted message rows",
            all(len(msgs_by_run[r["run_id"]]) == r["messages_attempted"] == cfg.messages_per_run
                for r in runs))
    rep.add("No message rows without a run", set(msgs_by_run) <= set(ids))

    bad_msg = []
    for m in msgs:
        if m["source_node_id"] == m["destination_node_id"]:
            bad_msg.append(f"{m['run_id']}#{m['message_id']}: source == destination")
        if m["delivered"]:
            if m["delivery_step"] is None or m["delivery_time_steps"] is None or \
               m["delivery_time_steps"] != m["delivery_step"] - m["creation_step"] or \
               m["delivery_time_steps"] < 0 or m["delivery_step"] > cfg.max_steps:
                bad_msg.append(f"{m['run_id']}#{m['message_id']}: bad delivery time")
        elif m["delivery_step"] is not None or m["delivery_time_steps"] is not None:
            bad_msg.append(f"{m['run_id']}#{m['message_id']}: undelivered but has a delivery time")
        if m["copies_created"] < 0 or m["copies_created"] > m["node_count"] - 1:
            bad_msg.append(f"{m['run_id']}#{m['message_id']}: impossible copy count")
        if m["routing_method"] == "DIRECT" and m["copies_created"] != 0:
            bad_msg.append(f"{m['run_id']}#{m['message_id']}: Direct made copies")
        if m["routing_method"] == "EPIDEMIC" and m["delivered"] and m["copies_created"] < 1:
            bad_msg.append(f"{m['run_id']}#{m['message_id']}: Epidemic delivered with no copy")
    rep.add("Message-level values are consistent", not bad_msg, "; ".join(bad_msg[:5]))

    # ---- run level recomputed from message level -------------------------
    bad_run = []
    for r in runs:
        ms = msgs_by_run[r["run_id"]]
        delivered = [m for m in ms if m["delivered"]]
        if r["messages_delivered"] != len(delivered) or \
           r["messages_not_delivered"] != len(ms) - len(delivered) or \
           r["messages_attempted"] != len(ms):
            bad_run.append(f"{r['run_id']}: message counts")
        pct = len(delivered) / len(ms) * 100 if ms else 0
        if abs(r["delivery_percentage"] - pct) > TOL:
            bad_run.append(f"{r['run_id']}: delivery %")
        if delivered:
            avg = sum(m["delivery_time_steps"] for m in delivered) / len(delivered)
            if r["average_delivery_time_steps"] is None or abs(r["average_delivery_time_steps"] - avg) > TOL:
                bad_run.append(f"{r['run_id']}: average delivery time")
        elif r["average_delivery_time_steps"] is not None:
            bad_run.append(f"{r['run_id']}: average time should be blank")
        if r["total_copies_created"] != sum(m["copies_created"] for m in ms) or r["total_copies_created"] < 0:
            bad_run.append(f"{r['run_id']}: copies total")
        if r["total_transfer_events"] != sum(m["transfer_events"] for m in ms):
            bad_run.append(f"{r['run_id']}: transfer total")
    rep.add("Run-level metrics equal the values recomputed from message logs", not bad_run,
            "; ".join(bad_run[:5]))

    # ---- replay every run from its seed ---------------------------------------
    replay_bad = []
    try:
        replayed = run_batch(cfg, "replay", build_matrix(cfg))
        saved = {r["run_id"]: r for r in runs}
        saved_msgs = {(m["run_id"], m["message_id"]): m for m in msgs}
        for rr in replayed:
            s = saved.get(rr.run_id)
            if s is None:
                replay_bad.append(f"{rr.run_id}: not saved")
                continue
            same_avg = (s["average_delivery_time_steps"] is None) == (rr.average_delivery_time_steps is None) \
                and (rr.average_delivery_time_steps is None or
                     abs(s["average_delivery_time_steps"] - rr.average_delivery_time_steps) < TOL)
            if not (s["messages_delivered"] == rr.messages_delivered and same_avg and
                    s["total_copies_created"] == rr.total_copies_created and
                    s["trace_hash"] == rr.trace_hash and s["random_seed"] == rr.random_seed):
                replay_bad.append(f"{rr.run_id}: differs from replay")
            for mr in rr.messages:
                sm = saved_msgs.get((rr.run_id, mr.message_id))
                if sm is None or sm["delivery_step"] != mr.delivery_step or \
                   sm["copies_created"] != mr.copies_created or \
                   sm["source_node_id"] != mr.source_node_id or \
                   sm["destination_node_id"] != mr.destination_node_id:
                    replay_bad.append(f"{rr.run_id}#{mr.message_id}: message differs from replay")
    except Exception as exc:  # report, never crash the validator
        replay_bad.append(f"replay failed: {exc!r}")
    rep.add("Replaying every run from its seed reproduces the saved results", not replay_bad,
            "; ".join(replay_bad[:5]))

    # ---- manifest (only if already written) -------------------------------------
    mpath = folder / "experiment_manifest.json"
    if mpath.exists():
        man = read_json(mpath)
        rep.add("Manifest agrees with the data",
                man.get("actual_runs") == len(runs) and man.get("expected_runs") == cfg.expected_runs)
    return rep
