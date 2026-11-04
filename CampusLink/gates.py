"""Safety gates that must be green before official data is collected.

* Tests gate  : `python -m campuslink.cli test` runs the unit tests and records the
                result together with a fingerprint of the source code. If the code
                changes afterwards, the record becomes stale.
* Config gate : `python -m campuslink.cli validate-config` checks the configuration
                and records a fingerprint of the config file.
* Approval    : the exact phrase below must be passed to the official run.
"""
import hashlib
import json
import unittest
from datetime import datetime
from pathlib import Path

from .config import config_problems, config_warnings, load_config

APPROVAL_PHRASE = "APPROVE OFFICIAL 60-RUN EXPERIMENT"


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def code_fingerprint() -> str:
    """Hash of every .py file in the campuslink package."""
    h = hashlib.sha256()
    for path in sorted(_package_dir().glob("*.py")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def config_fingerprint(cfg) -> str:
    return hashlib.sha256(json.dumps(cfg.to_dict(), sort_keys=True).encode()).hexdigest()[:16]


def _status_dir(root) -> Path:
    d = Path(root) / "outputs" / "status"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---- tests gate -----------------------------------------------------------
def record_test_result(root, tests_run, failures, errors) -> dict:
    rec = {"passed": failures == 0 and errors == 0 and tests_run > 0,
           "tests_run": tests_run, "failures": failures, "errors": errors,
           "code_fingerprint": code_fingerprint(),
           "timestamp": datetime.now().isoformat(timespec="seconds")}
    (_status_dir(root) / "test_status.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def run_unit_tests(root, verbosity=1) -> dict:
    """Discover and run tests/, then record the real outcome."""
    tests_dir = Path(root) / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests_dir), top_level_dir=str(root))
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return record_test_result(root, result.testsRun, len(result.failures), len(result.errors))


def tests_status(root) -> dict:
    rec = _read(_status_dir(root) / "test_status.json")
    if rec is None:
        return {"state": "NOT_RUN"}
    if rec.get("code_fingerprint") != code_fingerprint():
        return {"state": "STALE (code changed since tests ran)", **rec}
    return {"state": "PASSED" if rec["passed"] else "FAILED", **rec}


# ---- config gate ----------------------------------------------------------
def validate_config(root, cfg=None) -> dict:
    cfg = cfg or load_config(Path(root) / "campuslink_config.json")
    problems = config_problems(cfg)
    rec = {"valid": not problems, "problems": problems, "warnings": config_warnings(cfg),
           "config_fingerprint": config_fingerprint(cfg),
           "expected_runs": cfg.expected_runs,
           "timestamp": datetime.now().isoformat(timespec="seconds")}
    (_status_dir(root) / "config_validation.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def config_status(root, cfg) -> dict:
    rec = _read(_status_dir(root) / "config_validation.json")
    if rec is None:
        return {"state": "NOT_VALIDATED"}
    if rec.get("config_fingerprint") != config_fingerprint(cfg):
        return {"state": "STALE (config changed since validation)", **rec}
    return {"state": "VALID" if rec["valid"] else "INVALID", **rec}


# ---- combined check used by the official run --------------------------------
def official_run_blockers(root, cfg, approval) -> list:
    blockers = []
    if approval != APPROVAL_PHRASE:
        blockers.append(f'Approval phrase missing or wrong. It must be exactly: "{APPROVAL_PHRASE}"')
    if tests_status(root)["state"] != "PASSED":
        blockers.append("Unit tests have not passed for the current code (run: python -m campuslink.cli test).")
    if config_status(root, cfg)["state"] != "VALID":
        blockers.append("Configuration has not been validated (run: python -m campuslink.cli validate-config).")
    official_dir = Path(root) / "outputs" / "official"
    if official_dir.exists() and any((p / "run_logs.csv").exists() for p in official_dir.iterdir() if p.is_dir()):
        blockers.append("An official experiment already exists in outputs/official. It will not be overwritten. "
                        "Move it elsewhere first if you really need a new one.")
    return blockers
