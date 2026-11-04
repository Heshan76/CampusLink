"""Operations behind the MCP tools (also usable without MCP).

Every function works on a project root folder and only touches files inside it.
None of them runs shell commands or accepts arbitrary paths: experiment folders are
selected by an ID that must match a strict pattern.
"""
import json
import re
import shutil
import zipfile
from pathlib import Path

from .config import load_config
from .experiment import ExperimentBlocked, run_official, run_pilot
from .gates import (APPROVAL_PHRASE, config_status, official_run_blockers, tests_status,
                    validate_config)
from .reporting import build_workbook
from .validation import validate_experiment

EXPERIMENT_ID_PATTERN = re.compile(r"^official_\d{8}_\d{6}$")
REQUIRED_SCREENSHOTS = ("Screenshot_01_Direct_Measurement.png", "Screenshot_02_Epidemic_Measurement.png")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SOURCE_ITEMS = ("campuslink", "tests", "requirements.txt", "campuslink_config.json", "setup_windows.bat")


def _cfg(root):
    return load_config(Path(root) / "campuslink_config.json")


def official_experiments(root):
    base = Path(root) / "outputs" / "official"
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / "run_logs.csv").exists())


def resolve_official(root, experiment_id=None):
    """Return the folder of the chosen (default: latest) official experiment, or None."""
    exps = official_experiments(root)
    if experiment_id:
        if not EXPERIMENT_ID_PATTERN.match(experiment_id):
            raise ValueError("experiment_id must look like official_YYYYMMDD_HHMMSS")
        for p in exps:
            if p.name == experiment_id:
                return p
        return None
    return exps[-1] if exps else None


def missing_submission_items(root, experiment_id=None):
    root = Path(root)
    missing = []
    for name in ("README.md", "AI_Usage_Log.md"):
        if not (root / name).exists():
            missing.append(name)
    exp = resolve_official(root, experiment_id)
    if exp is None:
        missing.append("official experiment (run it after approval)")
    else:
        for name in ("run_logs.csv", "message_logs.csv", "experiment_config.json", "experiment_manifest.json"):
            if not (exp / name).exists():
                missing.append(f"raw_data/{name}")
        if not (exp / "CampusLink_Results.xlsx").exists():
            missing.append("results/CampusLink_Results.xlsx (run generate_workbook)")
    for name in REQUIRED_SCREENSHOTS:
        p = root / "evidence" / name
        if not p.exists():
            missing.append(f"evidence/{name} (student must capture the real running app)")
        elif p.read_bytes()[:8] != PNG_MAGIC:
            missing.append(f"evidence/{name} exists but is not a valid PNG")
    return missing


def get_status(root):
    root = Path(root)
    cfg = _cfg(root)
    pilot_dirs = sorted((root / "outputs" / "pilot").glob("pilot_*")) if (root / "outputs" / "pilot").exists() else []
    exps = official_experiments(root)
    out_files = sorted(str(p.relative_to(root)) for p in (root / "outputs").rglob("*")
                       if p.is_file() and "status" not in p.parts) if (root / "outputs").exists() else []
    return {
        "project_path": str(root),
        "configuration": cfg.to_dict(),
        "expected_official_runs": cfg.expected_runs,
        "output_files": out_files,
        "pilot_status": {"pilot_batches": len(pilot_dirs),
                         "latest": pilot_dirs[-1].name if pilot_dirs else None},
        "official_status": {"experiments": [p.name for p in exps],
                            "completed": bool(exps)},
        "test_status": tests_status(root),
        "config_status": config_status(root, cfg),
        "official_run_blockers_if_approved": official_run_blockers(root, cfg, APPROVAL_PHRASE),
        "missing_submission_items": missing_submission_items(root),
    }


def tool_run_pilot(root, node_count, routing_method, repetition, seed=None):
    run, folder = run_pilot(root, node_count, routing_method.upper(), repetition, seed)
    return {"saved_in": str(folder.relative_to(root)) if Path(root) in folder.parents else str(folder),
            "run_id": run.run_id, "scenario_id": run.scenario_id, "seed": run.random_seed,
            "messages_delivered": f"{run.messages_delivered}/{run.messages_attempted}",
            "delivery_percentage": run.delivery_percentage,
            "average_delivery_time_steps": run.average_delivery_time_steps,
            "total_copies_created": run.total_copies_created,
            "note": "PILOT result - not official data."}


def tool_run_official(root, approval):
    try:
        exp_id, folder, report = run_official(root, approval)
    except ExperimentBlocked as exc:
        return {"started": False, "message": str(exc)}
    return {"started": True, "experiment_id": exp_id, "folder": str(folder.relative_to(root)),
            "validation_passed": report.passed, "validation_report": report.text()}


def tool_validate(root, experiment_id=None):
    folder = resolve_official(root, experiment_id)
    if folder is None:
        return {"validated": False, "message": "No official experiment found."}
    rep = validate_experiment(folder)
    return {"validated": True, "passed": rep.passed, "report": rep.text()}


def tool_generate_workbook(root, experiment_id=None):
    folder = resolve_official(root, experiment_id)
    if folder is None:
        return {"generated": False, "message": "No official experiment found."}
    rep = validate_experiment(folder)
    if not rep.passed:
        return {"generated": False, "message": "Validation failed; workbook not generated.\n" + rep.text()}
    path = build_workbook(folder)
    return {"generated": True, "path": str(path.relative_to(root))}


def tool_prepare_submission(root, experiment_id=None):
    root = Path(root)
    missing = missing_submission_items(root, experiment_id)
    if missing:
        return {"prepared": False, "message": "Submission NOT created. Missing:\n- " + "\n- ".join(missing)}
    folder = resolve_official(root, experiment_id)
    rep = validate_experiment(folder)
    if not rep.passed:
        return {"prepared": False, "message": "Official data failed validation.\n" + rep.text()}

    staging = root / "submission" / "CampusLink_Submission"
    if staging.exists():
        shutil.rmtree(staging)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "outputs", ".DS_Store")
    (staging / "source_code").mkdir(parents=True)
    for item in SOURCE_ITEMS:
        src = root / item
        if src.is_dir():
            shutil.copytree(src, staging / "source_code" / item, ignore=ignore)
        elif src.exists():
            shutil.copy2(src, staging / "source_code" / item)
    shutil.copy2(root / "README.md", staging / "README.md")
    shutil.copy2(root / "AI_Usage_Log.md", staging / "AI_Usage_Log.md")
    (staging / "raw_data").mkdir()
    for name in ("run_logs.csv", "message_logs.csv", "experiment_config.json", "experiment_manifest.json"):
        shutil.copy2(folder / name, staging / "raw_data" / name)
    (staging / "results").mkdir()
    shutil.copy2(folder / "CampusLink_Results.xlsx", staging / "results" / "CampusLink_Results.xlsx")
    (staging / "evidence").mkdir()
    for name in REQUIRED_SCREENSHOTS:
        shutil.copy2(root / "evidence" / name, staging / "evidence" / name)

    zip_path = root / "submission" / "CampusLink_Submission.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(staging).as_posix())
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
    return {"prepared": True, "zip": str(zip_path.relative_to(root)), "files": names}
