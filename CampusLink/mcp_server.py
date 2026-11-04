"""CampusLink Control MCP - a small local MCP server (stdio) for experiment control.

It exposes exactly six narrow tools. The simulator itself lives in the normal
Python modules and works from the command line without MCP.
There is no shell access and no tool accepts a file path.

Start (stdio):  python -m campuslink.mcp_server
"""
import json

from mcp.server.mcpserver import MCPServer

from . import control
from .config import project_root

ROOT = project_root()

server = MCPServer("CampusLink Control MCP")


def _json(data) -> str:
    return json.dumps(data, indent=2, default=str)


@server.tool()
def campuslink_get_status() -> str:
    """Show project path, configuration, output files, pilot/official/test status and missing submission items."""
    return _json(control.get_status(ROOT))


@server.tool()
def campuslink_run_pilot(node_count: int, routing_method: str, repetition: int, seed: int | None = None) -> str:
    """Run ONE pilot simulation (routing_method DIRECT or EPIDEMIC). Saved only under outputs/pilot; never touches official data."""
    if routing_method.upper() not in ("DIRECT", "EPIDEMIC"):
        return "routing_method must be DIRECT or EPIDEMIC"
    if not (2 <= node_count <= 200) or not (1 <= repetition <= 99):
        return "node_count must be 2-200 and repetition 1-99"
    return _json(control.tool_run_pilot(ROOT, node_count, routing_method, repetition, seed))


@server.tool()
def campuslink_run_official_experiment(approval: str) -> str:
    """Run the full 60-run official experiment. Requires the exact approval phrase, passing tests, a validated config, and no existing official experiment."""
    return _json(control.tool_run_official(ROOT, approval))


@server.tool()
def campuslink_validate_results(experiment_id: str | None = None) -> str:
    """Validate an official experiment (latest if no id): run counts, repetitions, seeds, CSV structure, metrics, copies, duplicates, and a full replay."""
    result = control.tool_validate(ROOT, experiment_id)
    return result.get("report") or result["message"]


@server.tool()
def campuslink_generate_workbook(experiment_id: str | None = None) -> str:
    """Generate CampusLink_Results.xlsx from the official raw CSV files (only if validation passes)."""
    return _json(control.tool_generate_workbook(ROOT, experiment_id))


@server.tool()
def campuslink_prepare_submission(experiment_id: str | None = None) -> str:
    """Build CampusLink_Submission.zip - refuses unless every required file (including both real screenshots) exists."""
    return _json(control.tool_prepare_submission(ROOT, experiment_id))


if __name__ == "__main__":
    server.run("stdio")
