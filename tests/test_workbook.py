import unittest
import zipfile

import openpyxl

from campuslink.config import ExperimentConfig
from campuslink.reporting import build_workbook, summary_stats
from campuslink.storage import RUN_FIELDS, MESSAGE_FIELDS, read_csv, typed_message_row, typed_run_row
from tests.helpers import official_fixture

CFG = ExperimentConfig()


class WorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = official_fixture()
        cls.path = cls.fx["folder"] / "wb_test.xlsx"
        build_workbook(cls.fx["folder"], cls.path)
        cls.runs = [typed_run_row(r) for r in read_csv(cls.fx["folder"] / "run_logs.csv")]
        cls.msgs = [typed_message_row(r) for r in read_csv(cls.fx["folder"] / "message_logs.csv")]
        cls.wb_values = openpyxl.load_workbook(cls.path, data_only=True)
        cls.wb_formulas = openpyxl.load_workbook(cls.path)

    def test_19_sheets_present_in_order(self):
        self.assertEqual(self.wb_values.sheetnames, ["Summary", "Run_Data", "Message_Data", "Methodology"])

    def test_19_run_data_equals_csv(self):
        ws = self.wb_values["Run_Data"]
        self.assertEqual(ws.max_row, 61)
        self.assertEqual([c.value for c in ws[1]], RUN_FIELDS)
        for i, run in enumerate(self.runs, start=2):
            for j, name in enumerate(RUN_FIELDS, start=1):
                got, want = ws.cell(i, j).value, run[name]
                if isinstance(want, float):
                    self.assertAlmostEqual(got, want, places=6)
                else:
                    self.assertEqual(got, want, f"{name} row {i}")

    def test_19_message_data_equals_csv(self):
        ws = self.wb_values["Message_Data"]
        self.assertEqual(ws.max_row, 1 + len(self.msgs))
        self.assertEqual([c.value for c in ws[1]], MESSAGE_FIELDS)
        for i, m in enumerate(self.msgs, start=2):
            self.assertEqual(ws.cell(i, MESSAGE_FIELDS.index("message_id") + 1).value, m["message_id"])
            self.assertEqual(ws.cell(i, MESSAGE_FIELDS.index("copies_created") + 1).value, m["copies_created"])
            self.assertEqual(ws.cell(i, MESSAGE_FIELDS.index("delivery_time_steps") + 1).value, m["delivery_time_steps"])

    def test_19_summary_has_six_rows_matching_raw_data(self):
        ws, wf = self.wb_values["Summary"], self.wb_formulas["Summary"]
        stats = summary_stats(self.runs, CFG)
        self.assertEqual(len(stats), 6)
        for i, s in enumerate(stats):
            row = 4 + i
            self.assertEqual(ws.cell(row, 2).value, s["node_count"])
            self.assertEqual(ws.cell(row, 3).value, s["method"])
            self.assertEqual(ws.cell(row, 4).value, 10)
            self.assertAlmostEqual(ws.cell(row, 5).value, s["pct_mean"], places=6)
            self.assertAlmostEqual(ws.cell(row, 10).value, s["copies_mean"], places=6)
            for col in (4, 5, 6, 7, 8, 9, 10, 11):          # all statistics are formulas, not typed numbers
                self.assertTrue(str(wf.cell(row, col).value).startswith("="), f"R{row}C{col}")
            self.assertIn("Run_Data", wf.cell(row, 5).value)

    def test_19_three_separate_charts(self):
        with zipfile.ZipFile(self.path) as zf:
            charts = [n for n in zf.namelist() if n.startswith("xl/charts/chart")]
            self.assertEqual(len(charts), 3)
            xml = " ".join(zf.read(n).decode("utf-8") for n in charts)
        for text in ("Delivery percentage", "Average delivery time", "Copies created", "Number of nodes"):
            self.assertIn(text, xml)
        self.assertIn("Direct", xml)
        self.assertIn("Epidemic", xml)

    def test_methodology_sheet_mentions_key_rules(self):
        text = " ".join(str(c.value) for row in self.wb_values["Methodology"].iter_rows() for c in row if c.value)
        for key in ("Manhattan", "Direct routing", "Epidemic routing", "seed", "Limitations", "18 x 6"):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main()
