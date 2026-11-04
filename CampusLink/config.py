"""Central experiment configuration.

All experiment parameters live in `campuslink_config.json` (project root).
Nothing else in the code base hard-codes grid size, node counts, etc.
The defaults below are only a fallback if the JSON file is missing.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

CONFIG_FILENAME = "campuslink_config.json"
ROUTING_METHODS = ("DIRECT", "EPIDEMIC")


def project_root() -> Path:
    """Folder that contains the `campuslink` package (the project root)."""
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ExperimentConfig:
    project_name: str = "CampusLink"
    grid_width: int = 18
    grid_height: int = 6
    node_counts: tuple = (10, 20, 40)
    routing_methods: tuple = ("DIRECT", "EPIDEMIC")
    repetitions: int = 10
    messages_per_run: int = 6
    max_steps: int = 180
    contact_radius: int = 1
    base_seed: int = 42
    pilot_base_seed: int = 900000  # pilot seeds never overlap official seeds

    # ---- derived helpers -------------------------------------------------
    @property
    def expected_runs(self) -> int:
        return len(self.node_counts) * len(self.routing_methods) * self.repetitions

    def seed_for(self, node_count: int, repetition: int, pilot: bool = False) -> int:
        """Scenario seed. Same value is used for Direct AND Epidemic (paired runs)."""
        base = self.pilot_base_seed if pilot else self.base_seed
        return base + node_count * 100 + repetition

    @staticmethod
    def scenario_id(node_count: int, repetition: int, pilot: bool = False) -> str:
        prefix = "P" if pilot else "N"
        return f"{prefix}{node_count}_R{repetition:02d}"

    @staticmethod
    def run_id(node_count: int, method: str, repetition: int, pilot: bool = False) -> str:
        prefix = "P" if pilot else "N"
        return f"{prefix}{node_count}_{method}_R{repetition:02d}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["node_counts"] = list(self.node_counts)
        d["routing_methods"] = list(self.routing_methods)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ExperimentConfig":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        for key in ("node_counts", "routing_methods"):
            if key in known:
                known[key] = tuple(known[key])
        return cls(**known)


def load_config(path=None) -> ExperimentConfig:
    """Load config from JSON (default: project_root/campuslink_config.json)."""
    path = Path(path) if path else project_root() / CONFIG_FILENAME
    if path.exists():
        return ExperimentConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))
    return ExperimentConfig()


def config_warnings(cfg: ExperimentConfig) -> list:
    """Things that do not block a run but must be consciously confirmed."""
    warnings = []
    if cfg.grid_width != cfg.grid_height:
        warnings.append(f"Grid is {cfg.grid_width} x {cfg.grid_height} (not square). The proposal specifies 18 x 6, "
                        "but lecturer feedback reportedly asked for a larger, squarish grid - confirm which applies.")
    return warnings


def config_problems(cfg: ExperimentConfig) -> list:
    """Return a list of human-readable problems (empty list = config is sane)."""
    problems = []
    if cfg.grid_width < 2 or cfg.grid_height < 2:
        problems.append("Grid must be at least 2 x 2.")
    if not cfg.node_counts or any(n < 2 for n in cfg.node_counts):
        problems.append("Every node count must be >= 2 (a message needs source != destination).")
    if len(set(cfg.node_counts)) != len(cfg.node_counts):
        problems.append("Duplicate node counts.")
    if sorted(cfg.routing_methods) != sorted(ROUTING_METHODS):
        problems.append("routing_methods must be exactly DIRECT and EPIDEMIC.")
    if not (1 <= cfg.repetitions <= 99):
        problems.append("repetitions must be between 1 and 99 (seed formula limit).")
    if cfg.messages_per_run < 1:
        problems.append("messages_per_run must be >= 1.")
    if cfg.max_steps < 1:
        problems.append("max_steps must be >= 1.")
    if cfg.contact_radius < 0:
        problems.append("contact_radius must be >= 0.")
    return problems
