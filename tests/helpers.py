"""Shared test helpers. Official-style experiments are run in a TEMP folder only."""
import atexit
import shutil
import tempfile
from pathlib import Path

from campuslink.config import ExperimentConfig
from campuslink.experiment import run_official
from campuslink.gates import APPROVAL_PHRASE, record_test_result, validate_config
from campuslink.models import Contact

_FIXTURE = {}


def temp_root():
    d = Path(tempfile.mkdtemp(prefix="campuslink_test_"))
    atexit.register(shutil.rmtree, d, True)
    return d


def prepare_gates(root, cfg=None):
    """Mark tests/config as passed in a temp root so official runs are allowed there."""
    record_test_result(root, tests_run=1, failures=0, errors=0)
    validate_config(root, cfg or ExperimentConfig())


def official_fixture():
    """One real 60-run experiment in a temp root, created once and reused by tests."""
    if not _FIXTURE:
        root = temp_root()
        prepare_gates(root)
        exp_id, folder, report = run_official(root, APPROVAL_PHRASE)
        _FIXTURE.update(root=root, exp_id=exp_id, folder=folder, report=report)
    return _FIXTURE


def contacts(*pairs, step=0):
    return [Contact(step, min(a, b), max(a, b)) for a, b in pairs]
