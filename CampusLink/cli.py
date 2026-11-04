"""Command-line interface:  python -m campuslink.cli <command>

Works without MCP. Run with -h to see all commands.
"""
import argparse
import json
import sys
from pathlib import Path

from . import control
from .config import load_config, project_root
from .experiment import ExperimentBlocked, run_official, run_pilot, run_pilot_all
from .gates import APPROVAL_PHRASE, run_unit_tests, validate_config
from .reporting import build_workbook
from .validation import validate_experiment

ROOT = project_root()


def write_mcp_config(root, quiet=False):
    """Create/merge .agents/mcp_config.json with absolute paths for THIS computer."""
    root = Path(root).resolve()
    candidates = [root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"]
    python = next((p for p in candidates if p.exists()), None)
    if python is None:
        if not quiet:
            print("WARNING: .venv not found; using the current Python instead.")
        python = Path(sys.executable)
    path = root / ".agents" / "mcp_config.json"
    path.parent.mkdir(exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("mcpServers", {})["campuslink-control"] = {
        "command": str(python), "args": ["-m", "campuslink.mcp_server"],
        "cwd": str(root), "timeoutSeconds": 600}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(prog="campuslink", description="CampusLink simulator")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("test", help="run unit tests and record the result")
    sub.add_parser("validate-config", help="check campuslink_config.json and record the result")
    sub.add_parser("status", help="show project status")
    sp = sub.add_parser("pilot", help="run pilot simulation(s) (never official data)")
    sp.add_argument("--nodes", type=int, default=20)
    sp.add_argument("--method", default="DIRECT", choices=["DIRECT", "EPIDEMIC"])
    sp.add_argument("--repetition", type=int, default=1)
    sp.add_argument("--seed", type=int, default=None)
    sp.add_argument("--all", action="store_true", help="all node counts x both methods for the repetition")
    so = sub.add_parser("official", help="run the full 60-run experiment (needs approval phrase)")
    so.add_argument("--approve", default="", help=f'must be exactly "{APPROVAL_PHRASE}"')
    sv = sub.add_parser("validate", help="validate an official experiment")
    sv.add_argument("--experiment", default=None)
    sw = sub.add_parser("workbook", help="create CampusLink_Results.xlsx from official CSVs")
    sw.add_argument("--experiment", default=None)
    ss = sub.add_parser("submission", help="build CampusLink_Submission.zip")
    ss.add_argument("--experiment", default=None)
    sz = sub.add_parser("visualize", help="open the live visualizer")
    sz.add_argument("--nodes", type=int, default=None)
    sz.add_argument("--method", default="DIRECT", choices=["DIRECT", "EPIDEMIC"])
    sz.add_argument("--repetition", type=int, default=1)
    sz.add_argument("--pilot-scenario", action="store_true", help="use pilot seeds instead of official seeds")
    sz.add_argument("--autostart", action="store_true")
    sr = sub.add_parser("rerun", help="re-run ONE selected experiment now and compare with the official record")
    sr.add_argument("--nodes", type=int, required=True)
    sr.add_argument("--method", required=True, choices=["DIRECT", "EPIDEMIC"])
    sr.add_argument("--repetition", type=int, required=True)
    sub.add_parser("write-mcp-config", help="write .agents/mcp_config.json for this computer")
    args = p.parse_args(argv)

    if args.cmd == "test":
        rec = run_unit_tests(ROOT)
        print(json.dumps(rec, indent=2))
        return 0 if rec["passed"] else 1
    if args.cmd == "validate-config":
        rec = validate_config(ROOT)
        print(json.dumps(rec, indent=2))
        return 0 if rec["valid"] else 1
    if args.cmd == "status":
        print(json.dumps(control.get_status(ROOT), indent=2, default=str))
        return 0
    if args.cmd == "pilot":
        if args.all:
            runs, folder = run_pilot_all(ROOT, args.repetition)
        else:
            run, folder = run_pilot(ROOT, args.nodes, args.method, args.repetition, args.seed)
            runs = [run]
        print(f"PILOT results saved in {folder}")
        print(f"{'run_id':<18}{'seed':>8}{'delivered':>11}{'avg_time':>10}{'copies':>8}")
        for r in runs:
            avg = "N/A" if r.average_delivery_time_steps is None else f"{r.average_delivery_time_steps:.2f}"
            print(f"{r.run_id:<18}{r.random_seed:>8}{r.messages_delivered:>6}/{r.messages_attempted:<4}{avg:>10}{r.total_copies_created:>8}")
        return 0
    if args.cmd == "official":
        try:
            exp_id, folder, report = run_official(ROOT, args.approve)
        except ExperimentBlocked as exc:
            print(exc)
            return 2
        print(report.text())
        print(f"Official experiment saved in {folder}")
        return 0 if report.passed else 1
    if args.cmd == "validate":
        res = control.tool_validate(ROOT, args.experiment)
        print(res.get("report") or res["message"])
        return 0 if res.get("passed") else 1
    if args.cmd == "workbook":
        res = control.tool_generate_workbook(ROOT, args.experiment)
        print(res.get("path") or res["message"])
        return 0 if res["generated"] else 1
    if args.cmd == "submission":
        res = control.tool_prepare_submission(ROOT, args.experiment)
        print(res.get("zip") or res["message"])
        return 0 if res["prepared"] else 1
    if args.cmd == "visualize":
        from .visualizer import run_visualizer
        run_visualizer(args.nodes, args.method, args.repetition, not args.pilot_scenario, args.autostart)
        return 0
    if args.cmd == "rerun":
        from .experiment import run_batch
        from .visualizer import find_official_record
        cfg = load_config()
        run = run_batch(cfg, "rerun", [(args.nodes, args.repetition, args.method)])[0]
        avg = "N/A" if run.average_delivery_time_steps is None else f"{run.average_delivery_time_steps:.2f}"
        print(f"{run.run_id}  seed={run.random_seed}  delivered={run.messages_delivered}/{run.messages_attempted}  "
              f"avg_time={avg}  copies={run.total_copies_created}")
        for m in run.messages:
            print(f"  M{m.message_id}: {m.source_node_id} -> {m.destination_node_id}  "
                  + (f"delivered at step {m.delivery_step}" if m.delivered else "not delivered")
                  + f"  copies={m.copies_created}")
        rec = find_official_record(ROOT, run.run_id)
        if rec is None:
            print("No official record to compare with yet (official experiment not run).")
        else:
            same = (int(rec["messages_delivered"]) == run.messages_delivered and
                    int(rec["total_copies_created"]) == run.total_copies_created and
                    rec["trace_hash"] == run.trace_hash)
            print("Official record:", "MATCH" if same else "MISMATCH")
        return 0
    if args.cmd == "write-mcp-config":
        print(f"Wrote {write_mcp_config(ROOT)}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
