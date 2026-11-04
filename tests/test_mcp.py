import asyncio
import json
import sys
import unittest
import zipfile
from pathlib import Path

from campuslink import control
from campuslink.config import project_root
from campuslink.gates import APPROVAL_PHRASE
from tests.helpers import official_fixture, prepare_gates, temp_root

TOOLS = {"campuslink_get_status", "campuslink_run_pilot", "campuslink_run_official_experiment",
         "campuslink_validate_results", "campuslink_generate_workbook", "campuslink_prepare_submission"}
PNG = b"\x89PNG\r\n\x1a\n" + b"test-bytes-not-a-real-screenshot"


class ControlFunctionTests(unittest.TestCase):
    def test_status_reports_gates_and_missing_items(self):
        root = temp_root()
        st = control.get_status(root)
        self.assertEqual(st["expected_official_runs"], 60)
        self.assertEqual(st["test_status"]["state"], "NOT_RUN")
        self.assertFalse(st["official_status"]["completed"])
        self.assertTrue(any("Screenshot_01" in m for m in st["missing_submission_items"]))

    def test_pilot_tool_only_writes_pilot(self):
        root = temp_root()
        res = control.tool_run_pilot(root, 10, "direct", 1)
        self.assertIn("outputs", res["saved_in"])
        self.assertIn("pilot", res["saved_in"])
        self.assertFalse((root / "outputs" / "official").exists())

    def test_official_tool_blocks_without_approval(self):
        root = temp_root()
        prepare_gates(root)
        res = control.tool_run_official(root, "")
        self.assertFalse(res["started"])
        self.assertFalse((root / "outputs" / "official").exists())

    def test_official_tool_runs_with_approval_then_refuses_second_time(self):
        root = temp_root()
        prepare_gates(root)
        res = control.tool_run_official(root, APPROVAL_PHRASE)
        self.assertTrue(res["started"] and res["validation_passed"])
        again = control.tool_run_official(root, APPROVAL_PHRASE)
        self.assertFalse(again["started"])

    def test_experiment_id_must_match_pattern(self):
        fx = official_fixture()
        for bad in ("../../etc", "official_1", "outputs/official/x"):
            with self.assertRaises(ValueError):
                control.resolve_official(fx["root"], bad)
        self.assertEqual(control.resolve_official(fx["root"], fx["exp_id"]).name, fx["exp_id"])

    def test_validate_and_workbook_tools(self):
        fx = official_fixture()
        v = control.tool_validate(fx["root"])
        self.assertTrue(v["passed"], v["report"])
        w = control.tool_generate_workbook(fx["root"])
        self.assertTrue(w["generated"], w)
        self.assertTrue((fx["root"] / w["path"]).exists())

    def test_submission_refused_without_screenshots_then_built(self):
        fx = official_fixture()
        root = fx["root"]
        for name in ("README.md", "AI_Usage_Log.md"):
            (root / name).write_text("x", encoding="utf-8")
        for item in ("campuslink", "tests"):
            (root / item).mkdir(exist_ok=True)
            (root / item / "a.py").write_text("x=1", encoding="utf-8")
        (root / "campuslink" / "a.pyc").write_bytes(b"junk")
        (root / "requirements.txt").write_text("x", encoding="utf-8")
        control.tool_generate_workbook(root)
        res = control.tool_prepare_submission(root)
        self.assertFalse(res["prepared"])
        self.assertIn("Screenshot_01_Direct_Measurement.png", res["message"])
        self.assertFalse((root / "submission" / "CampusLink_Submission.zip").exists())
        (root / "evidence").mkdir(exist_ok=True)
        (root / "evidence" / "Screenshot_01_Direct_Measurement.png").write_bytes(b"not a png")
        (root / "evidence" / "Screenshot_02_Epidemic_Measurement.png").write_bytes(PNG)
        self.assertFalse(control.tool_prepare_submission(root)["prepared"])      # invalid PNG rejected
        (root / "evidence" / "Screenshot_01_Direct_Measurement.png").write_bytes(PNG)
        res = control.tool_prepare_submission(root)
        self.assertTrue(res["prepared"], res)
        names = set(res["files"])
        for must in ("README.md", "AI_Usage_Log.md", "raw_data/run_logs.csv", "raw_data/message_logs.csv",
                     "raw_data/experiment_config.json", "raw_data/experiment_manifest.json",
                     "results/CampusLink_Results.xlsx", "evidence/Screenshot_01_Direct_Measurement.png",
                     "evidence/Screenshot_02_Epidemic_Measurement.png", "source_code/campuslink/a.py"):
            self.assertIn(must, names)
        self.assertFalse([n for n in names if "__pycache__" in n or n.endswith(".pyc") or ".venv" in n])
        with zipfile.ZipFile(root / res["zip"]) as zf:
            self.assertIsNone(zf.testzip())


class McpServerTests(unittest.TestCase):
    def test_server_exposes_exactly_six_tools(self):
        from campuslink.mcp_server import server
        names = {t.name for t in asyncio.run(server.list_tools())}
        self.assertEqual(names, TOOLS)

    def test_stdio_protocol_roundtrip(self):
        """Start the real server as a subprocess and talk MCP over stdio."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def go():
            params = StdioServerParameters(command=sys.executable, args=["-m", "campuslink.mcp_server"],
                                           cwd=str(project_root()))
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    tools = {t.name for t in (await s.list_tools()).tools}
                    status = json.loads((await s.call_tool("campuslink_get_status", {})).content[0].text)
                    refused = json.loads((await s.call_tool("campuslink_run_official_experiment",
                                                            {"approval": "wrong"})).content[0].text)
                    return tools, status, refused

        tools, status, refused = asyncio.run(go())
        self.assertEqual(tools, TOOLS)
        self.assertEqual(status["expected_official_runs"], 60)
        self.assertFalse(refused["started"])

    def test_mcp_config_merges_without_deleting_other_servers(self):
        from campuslink.cli import write_mcp_config
        root = temp_root()
        (root / ".agents").mkdir()
        (root / ".agents" / "mcp_config.json").write_text(
            json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
        data = json.loads(write_mcp_config(root, quiet=True).read_text(encoding="utf-8"))
        self.assertIn("other", data["mcpServers"])
        entry = data["mcpServers"]["campuslink-control"]
        self.assertEqual(entry["args"], ["-m", "campuslink.mcp_server"])
        self.assertEqual(entry["timeoutSeconds"], 600)
        self.assertEqual(entry["cwd"], str(root.resolve()))


if __name__ == "__main__":
    unittest.main()
