import csv
import unittest

from campuslink.config import ExperimentConfig, config_problems, config_warnings
from campuslink.experiment import ExperimentBlocked, build_matrix, run_official, run_pilot, run_pilot_all
from campuslink.gates import APPROVAL_PHRASE, record_test_result, validate_config
from campuslink.storage import MESSAGE_FIELDS, RUN_FIELDS, read_csv, read_json, typed_message_row, typed_run_row
from campuslink.validation import validate_experiment
from tests.helpers import official_fixture, prepare_gates, temp_root

CFG = ExperimentConfig()


class MatrixTests(unittest.TestCase):
    def test_15_matrix_is_3x2x10(self):
        m = build_matrix(CFG)
        self.assertEqual(len(m), 60)
        self.assertEqual(len(set(m)), 60)
        self.assertEqual({x[0] for x in m}, {10, 20, 40})
        self.assertEqual({x[2] for x in m}, {"DIRECT", "EPIDEMIC"})

    def test_config_defaults_and_checks(self):
        self.assertEqual((CFG.grid_width, CFG.grid_height), (18, 6))   # from the proposal
        self.assertEqual((CFG.messages_per_run, CFG.max_steps, CFG.contact_radius), (6, 180, 1))
        self.assertEqual(config_problems(CFG), [])
        self.assertTrue(config_warnings(CFG))                          # non-square grid is flagged, not hidden
        self.assertEqual(config_warnings(ExperimentConfig(grid_width=16, grid_height=16)), [])
        self.assertTrue(config_problems(ExperimentConfig(node_counts=(1, 20))))

    def test_config_is_changeable_without_code_edits(self):
        cfg = ExperimentConfig(grid_width=20, grid_height=20, node_counts=(5, 8), repetitions=3,
                               messages_per_run=2, max_steps=50, contact_radius=2, base_seed=7)
        self.assertEqual(len(build_matrix(cfg)), 2 * 2 * 3)
        self.assertEqual(cfg.expected_runs, 12)


class OfficialExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = official_fixture()
        cls.runs = [typed_run_row(r) for r in read_csv(cls.fx["folder"] / "run_logs.csv")]
        cls.msgs = [typed_message_row(r) for r in read_csv(cls.fx["folder"] / "message_logs.csv")]

    def test_16_exactly_60_unique_runs(self):
        self.assertEqual(len(self.runs), 60)
        self.assertEqual(len({r["run_id"] for r in self.runs}), 60)
        self.assertEqual(len({r["experiment_id"] for r in self.runs}), 1)

    def test_17_ten_repetitions_per_combination(self):
        for n in (10, 20, 40):
            for m in ("DIRECT", "EPIDEMIC"):
                reps = sorted(r["repetition"] for r in self.runs
                              if r["node_count"] == n and r["routing_method"] == m)
                self.assertEqual(reps, list(range(1, 11)))

    def test_18_csv_agrees_with_message_logs(self):
        self.assertEqual(len(self.msgs), 60 * CFG.messages_per_run)
        for r in self.runs:
            ms = [m for m in self.msgs if m["run_id"] == r["run_id"]]
            delivered = [m for m in ms if m["delivered"]]
            self.assertEqual(r["messages_attempted"], len(ms))
            self.assertEqual(r["messages_delivered"], len(delivered))
            self.assertAlmostEqual(r["delivery_percentage"], len(delivered) / len(ms) * 100, places=4)
            self.assertEqual(r["total_copies_created"], sum(m["copies_created"] for m in ms))
            if delivered:
                self.assertAlmostEqual(r["average_delivery_time_steps"],
                                       sum(m["delivery_time_steps"] for m in delivered) / len(delivered), places=4)
            else:
                self.assertIsNone(r["average_delivery_time_steps"])

    def test_csv_headers_and_files(self):
        folder = self.fx["folder"]
        self.assertEqual(list(read_csv(folder / "run_logs.csv")[0].keys()), RUN_FIELDS)
        self.assertEqual(list(read_csv(folder / "message_logs.csv")[0].keys()), MESSAGE_FIELDS)
        for name in ("experiment_config.json", "experiment_manifest.json"):
            self.assertTrue((folder / name).exists())

    def test_validation_passes_and_manifest_is_correct(self):
        self.assertTrue(self.fx["report"].passed, self.fx["report"].text())
        rep = validate_experiment(self.fx["folder"])
        self.assertTrue(rep.passed, rep.text())
        man = read_json(self.fx["folder"] / "experiment_manifest.json")
        self.assertEqual((man["expected_runs"], man["actual_runs"], man["validation_status"]), (60, 60, "PASSED"))
        self.assertEqual(len(man["seeds"]), 30)

    def test_paired_runs_share_seed_and_trace(self):
        by = {}
        for r in self.runs:
            by.setdefault(r["scenario_id"], []).append(r)
        self.assertEqual(len(by), 30)
        for rows in by.values():
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["random_seed"], rows[1]["random_seed"])
            self.assertEqual(rows[0]["trace_hash"], rows[1]["trace_hash"])

    def test_direct_rows_have_zero_copies(self):
        for r in self.runs:
            if r["routing_method"] == "DIRECT":
                self.assertEqual(r["total_copies_created"], 0)

    def test_validator_detects_tampering(self):
        root = temp_root()
        folder = root / "tampered"
        folder.mkdir()
        for name in ("run_logs.csv", "message_logs.csv", "experiment_config.json"):
            (folder / name).write_bytes((self.fx["folder"] / name).read_bytes())
        rows = read_csv(folder / "run_logs.csv")
        rows[0]["messages_delivered"] = str(int(rows[0]["messages_delivered"]) + 1)
        with open(folder / "run_logs.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=RUN_FIELDS)
            w.writeheader()
            w.writerows(rows)
        self.assertFalse(validate_experiment(folder).passed)


class GateTests(unittest.TestCase):
    def test_official_refuses_without_approval(self):
        root = temp_root()
        prepare_gates(root)
        for bad in ("", "approve", "APPROVE OFFICIAL EXPERIMENT"):
            with self.assertRaises(ExperimentBlocked):
                run_official(root, bad)
        self.assertFalse(any((root / "outputs" / "official").glob("*")) if (root / "outputs" / "official").exists() else False)

    def test_official_refuses_when_tests_not_passed(self):
        root = temp_root()
        validate_config(root, CFG)
        with self.assertRaises(ExperimentBlocked):
            run_official(root, APPROVAL_PHRASE)
        record_test_result(root, tests_run=3, failures=1, errors=0)
        with self.assertRaises(ExperimentBlocked):
            run_official(root, APPROVAL_PHRASE)

    def test_official_refuses_when_config_not_validated(self):
        root = temp_root()
        record_test_result(root, 1, 0, 0)
        with self.assertRaises(ExperimentBlocked):
            run_official(root, APPROVAL_PHRASE)

    def test_official_never_overwrites_existing(self):
        fx = official_fixture()
        with self.assertRaises(ExperimentBlocked) as ctx:
            run_official(fx["root"], APPROVAL_PHRASE)
        self.assertIn("already exists", str(ctx.exception))
        self.assertEqual(len(list((fx["root"] / "outputs" / "official").iterdir())), 1)

    def test_pilot_is_saved_only_in_pilot_folder(self):
        root = temp_root()
        run, folder = run_pilot(root, 10, "EPIDEMIC", 1)
        self.assertEqual(folder.parent, root / "outputs" / "pilot")
        self.assertTrue((folder / "run_logs.csv").exists())
        self.assertFalse((root / "outputs" / "official").exists())
        self.assertTrue(run.run_id.startswith("P"))
        self.assertNotEqual(run.random_seed, CFG.seed_for(10, 1))
        runs, folder2 = run_pilot_all(root, 1)
        self.assertEqual(len(runs), 6)
        self.assertNotEqual(folder, folder2)


if __name__ == "__main__":
    unittest.main()
