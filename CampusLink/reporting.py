"""Excel workbook generation (XlsxWriter) from the official raw CSV files.

Nothing is typed in by hand: Run_Data / Message_Data are copied from the CSV
files, and every Summary number is an Excel FORMULA over Run_Data. The cached
value stored next to each formula is computed in Python from the same CSV data,
so the file shows correct numbers even before Excel recalculates.
"""
import statistics
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from .config import ExperimentConfig
from .storage import (MESSAGE_FIELDS, RUN_FIELDS, read_csv, read_json, typed_message_row,
                      typed_run_row)

METHOD_LABEL = {"DIRECT": "Direct", "EPIDEMIC": "Epidemic"}


def _mean_sd(values):
    """(mean, sample standard deviation) or None parts when not computable."""
    if not values:
        return None, None
    mean = sum(values) / len(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    return mean, sd


def summary_stats(runs, cfg):
    """One dict per (node_count, method) row, in the order shown in the Summary sheet."""
    rows = []
    for n in cfg.node_counts:
        for m in cfg.routing_methods:
            sel = [r for r in runs if r["node_count"] == n and r["routing_method"] == m]
            pct_m, pct_sd = _mean_sd([r["delivery_percentage"] for r in sel])
            times = [r["average_delivery_time_steps"] for r in sel
                     if r["average_delivery_time_steps"] is not None]
            t_m, t_sd = _mean_sd(times)
            c_m, c_sd = _mean_sd([r["total_copies_created"] for r in sel])
            rows.append({"node_count": n, "method": m, "repetitions": len(sel),
                         "pct_mean": pct_m, "pct_sd": pct_sd,
                         "time_mean": t_m, "time_runs": len(times), "time_sd": t_sd,
                         "copies_mean": c_m, "copies_sd": c_sd})
    return rows


def methodology_lines(cfg, experiment_id):
    g = f"{cfg.grid_width} x {cfg.grid_height}"
    return [
        ("Experimental setup",
         f"Experiment {experiment_id}. Grid {g} cells. Node counts {list(cfg.node_counts)}. "
         f"Routing methods {list(cfg.routing_methods)}. {cfg.repetitions} repetitions per combination = "
         f"{cfg.expected_runs} runs. {cfg.messages_per_run} messages per run, all created at step 0. "
         f"Each run simulates {cfg.max_steps} steps (it continues through all steps; a delivered message simply stops being forwarded)."),
        ("Grid size", f"A {g} grid ({'as specified in the project proposal' if cfg.grid_width != cfg.grid_height else 'square'})."),
        ("Node movement",
         "Each node starts in a random cell. At every step each node either stays or moves one cell left, right, up or down, "
         "chosen uniformly among 'stay' and the moves that keep it inside the grid. There is no wrap-around. "
         "Several nodes may share a cell."),
        ("Contact detection",
         f"Manhattan distance |x1-x2| + |y1-y2| <= {cfg.contact_radius}. With radius 1 two nodes can talk when they are in the "
         "same cell or in horizontally/vertically adjacent cells; diagonal neighbours cannot."),
        ("Direct routing",
         "The source keeps the original message until it meets the destination, then hands it over. "
         "Intermediate nodes never receive it. Handing over the original is not a copy, so Direct always creates 0 copies."),
        ("Epidemic routing",
         "A holder gives a copy to every neighbour that does not already hold the message (a node never receives the same "
         "message twice). Spreading uses the holders at the start of each step, so a message moves one hop per step. "
         "If the destination touches a holder in a step, it is delivered in that step and nothing else is replicated that step. "
         "After delivery, replication of that message stops (implementation decision)."),
        ("Fixed seed strategy",
         f"scenario seed = {cfg.base_seed} + node_count x 100 + repetition. The scenario (start positions, message "
         "source/destination pairs and the whole movement trace) is generated from that seed BEFORE routing. "
         "Direct and Epidemic replay exactly the same scenario, so they are compared under identical movement."),
        ("Repetitions", f"{cfg.repetitions} different scenarios (seeds) for every node-count/method combination, to average out luck."),
        ("Delivery percentage", "messages delivered / messages generated x 100 (per run)."),
        ("Average delivery time",
         "For delivered messages: delivery step - creation step. The run value is the mean over delivered messages only. "
         "Undelivered messages are never counted as 0. A run with no delivered message has a blank value."),
        ("Copies created",
         "Number of times a NEW node received a message for the first time beyond the original held by the source "
         "(Epidemic: includes the final copy given to the destination). Direct = 0. "
         "Successful transfers are also logged as 'transfer events' for diagnostics; they are not the copies metric."),
        ("Summary statistics",
         "Mean and sample standard deviation (n-1) over the repeated runs of each row. Delivery-time statistics use only runs "
         "with at least one delivered message (column 'Runs with delivery'). All are Excel formulas over Run_Data."),
        ("Limitations",
         "Simple random walk on a small grid; not a real campus map. Instant, error-free, unlimited-capacity transfers. "
         "No message expiry or buffer limits. Only 10 repetitions, so averages carry sampling noise. "
         "Epidemic stops replicating a message after delivery, which lowers its copy count compared with unrestricted flooding."),
    ]


def build_workbook(experiment_dir, out_path=None):
    experiment_dir = Path(experiment_dir)
    cfg = ExperimentConfig.from_dict(read_json(experiment_dir / "experiment_config.json"))
    experiment_id = experiment_dir.name
    runs = [typed_run_row(r) for r in read_csv(experiment_dir / "run_logs.csv")]
    msgs = [typed_message_row(r) for r in read_csv(experiment_dir / "message_logs.csv")]
    out_path = Path(out_path) if out_path else experiment_dir / "CampusLink_Results.xlsx"

    wb = xlsxwriter.Workbook(str(out_path))
    base = {"font_name": "Arial", "font_size": 10}
    f_title = wb.add_format({**base, "bold": True, "font_size": 14})
    f_head = wb.add_format({**base, "bold": True, "bg_color": "#1F4E78", "font_color": "white",
                            "border": 1, "text_wrap": True, "valign": "vcenter", "align": "center"})
    f_txt = wb.add_format({**base, "border": 1})
    f_int = wb.add_format({**base, "border": 1, "num_format": "0"})
    f_2dp = wb.add_format({**base, "border": 1, "num_format": "0.00"})
    f_note = wb.add_format({**base, "italic": True, "font_color": "#555555"})
    f_wrap = wb.add_format({**base, "text_wrap": True, "valign": "top", "border": 1})
    f_bold = wb.add_format({**base, "bold": True, "text_wrap": True, "valign": "top", "border": 1})

    # Sheet order requested: Summary, Run_Data, Message_Data, Methodology
    ws_sum = wb.add_worksheet("Summary")
    ws_run = wb.add_worksheet("Run_Data")
    ws_msg = wb.add_worksheet("Message_Data")
    ws_met = wb.add_worksheet("Methodology")

    # ---- Run_Data ---------------------------------------------------------
    for c, name in enumerate(RUN_FIELDS):
        ws_run.write(0, c, name, f_head)
    for r, row in enumerate(runs, start=1):
        for c, name in enumerate(RUN_FIELDS):
            v = row[name]
            if v is None:
                continue  # blank cell = no delivered message (kept truly empty on purpose)
            ws_run.write(r, c, v, f_2dp if name in ("delivery_percentage", "average_delivery_time_steps") else f_txt)
    ws_run.freeze_panes(1, 0)
    ws_run.autofilter(0, 0, len(runs), len(RUN_FIELDS) - 1)
    ws_run.set_column(0, len(RUN_FIELDS) - 1, 16)
    ws_run.set_row(0, 32)

    # ---- Message_Data -----------------------------------------------------
    for c, name in enumerate(MESSAGE_FIELDS):
        ws_msg.write(0, c, name, f_head)
    for r, row in enumerate(msgs, start=1):
        for c, name in enumerate(MESSAGE_FIELDS):
            v = row[name]
            if v is None:
                continue
            ws_msg.write(r, c, v, f_txt)
    ws_msg.freeze_panes(1, 0)
    ws_msg.autofilter(0, 0, len(msgs), len(MESSAGE_FIELDS) - 1)
    ws_msg.set_column(0, len(MESSAGE_FIELDS) - 1, 16)
    ws_msg.set_row(0, 32)

    # ---- Summary (formulas over Run_Data) --------------------------------------
    last = len(runs) + 1  # last Excel row of Run_Data

    def rng(field):
        col = xl_col_to_name(RUN_FIELDS.index(field))
        return f"Run_Data!${col}$2:${col}${last}"

    node, meth = rng("node_count"), rng("routing_method")
    pct, tim, cop = rng("delivery_percentage"), rng("average_delivery_time_steps"), rng("total_copies_created")

    ws_sum.write(0, 0, f"CampusLink - Direct vs Epidemic summary ({experiment_id})", f_title)
    ws_sum.write(1, 0, "Every number below is a formula over the Run_Data sheet (the raw simulator output).", f_note)
    heads = ["Configuration", "Node count", "Routing method", "Repetitions",
             "Mean delivery %", "SD delivery %", "Mean delivery time (steps)",
             "Runs with delivery (used for time)", "SD delivery time (steps)",
             "Mean copies created", "SD copies created"]
    for c, h in enumerate(heads):
        ws_sum.write(2, c, h, f_head)
    ws_sum.set_row(2, 45)

    stats = summary_stats(runs, cfg)
    first = 4  # Excel row of first summary line
    for i, s in enumerate(stats):
        r0, x = 3 + i, first + i  # zero-based row, Excel row number
        label = f"{s['node_count']} nodes \u2013 {METHOD_LABEL[s['method']]}"
        ws_sum.write(r0, 0, label, f_txt)
        ws_sum.write(r0, 1, s["node_count"], f_int)
        ws_sum.write(r0, 2, s["method"], f_txt)
        sel = f"({node}=$B{x})*({meth}=$C{x})"
        ws_sum.write_formula(r0, 3, f"=COUNTIFS({node},$B{x},{meth},$C{x})", f_int, s["repetitions"])
        ws_sum.write_formula(r0, 4, f"=AVERAGEIFS({pct},{node},$B{x},{meth},$C{x})", f_2dp, s["pct_mean"])
        ws_sum.write_formula(r0, 5, f'=IF(D{x}>1,SQRT(SUMPRODUCT({sel}*({pct}-E{x})^2)/(D{x}-1)),"N/A")',
                             f_2dp, "N/A" if s["pct_sd"] is None else s["pct_sd"])
        ws_sum.write_formula(r0, 7, f'=COUNTIFS({node},$B{x},{meth},$C{x},{tim},">=0")', f_int, s["time_runs"])
        ws_sum.write_formula(r0, 6, f'=IF(H{x}>0,AVERAGEIFS({tim},{node},$B{x},{meth},$C{x}),"N/A")',
                             f_2dp, "N/A" if s["time_mean"] is None else s["time_mean"])
        ws_sum.write_formula(r0, 8, f'=IF(H{x}>1,SQRT(SUMPRODUCT({sel}*({tim}<>"")*({tim}-G{x})^2)/(H{x}-1)),"N/A")',
                             f_2dp, "N/A" if s["time_sd"] is None else s["time_sd"])
        ws_sum.write_formula(r0, 9, f"=AVERAGEIFS({cop},{node},$B{x},{meth},$C{x})", f_2dp, s["copies_mean"])
        ws_sum.write_formula(r0, 10, f'=IF(D{x}>1,SQRT(SUMPRODUCT({sel}*({cop}-J{x})^2)/(D{x}-1)),"N/A")',
                             f_2dp, "N/A" if s["copies_sd"] is None else s["copies_sd"])
    ws_sum.set_column(0, 0, 22)
    ws_sum.set_column(1, 10, 15)

    # chart helper table: rows = node counts, columns = Direct / Epidemic
    ct = first + len(stats) + 2          # Excel row of chart-table title
    ws_sum.write(ct - 1, 0, "Chart data (linked to the summary table above)", f_title)
    chart_heads = ["Nodes", "Direct - delivery %", "Epidemic - delivery %",
                   "Direct - delivery time", "Epidemic - delivery time",
                   "Direct - copies", "Epidemic - copies"]
    for c, h in enumerate(chart_heads):
        ws_sum.write(ct, c, h, f_head)
    ws_sum.set_row(ct, 32)
    n_methods = len(cfg.routing_methods)
    for i, n in enumerate(cfg.node_counts):
        r0 = ct + 1 + i
        ws_sum.write(r0, 0, f"{n} nodes", f_txt)
        for j, m in enumerate(cfg.routing_methods):          # DIRECT then EPIDEMIC
            srow = first + i * n_methods + j                  # Excel row in summary
            s = stats[i * n_methods + j]
            ws_sum.write_formula(r0, 1 + j, f"=E{srow}", f_2dp, s["pct_mean"])
            tv = s["time_mean"]
            ws_sum.write_formula(r0, 3 + j, f"=IF(ISNUMBER(G{srow}),G{srow},NA())", f_2dp,
                                 tv if tv is not None else "#N/A")
            ws_sum.write_formula(r0, 5 + j, f"=J{srow}", f_2dp, s["copies_mean"])
    cat_ref = ["Summary", ct + 1, 0, ct + len(cfg.node_counts), 0]

    def make_chart(title, ytitle, col_direct, fmt_max=None):
        ch = wb.add_chart({"type": "column"})
        for name, col, color in (("Direct", col_direct, "#2E75B6"), ("Epidemic", col_direct + 1, "#ED7D31")):
            ch.add_series({
                "name": name,
                "categories": cat_ref,
                "values": ["Summary", ct + 1, col, ct + len(cfg.node_counts), col],
                "fill": {"color": color},
                "data_labels": {"value": True, "num_format": "0.0", "font": {"name": "Arial", "size": 9}},
            })
        ch.set_title({"name": title, "name_font": {"name": "Arial", "size": 12}})
        ch.set_x_axis({"name": "Number of nodes", "name_font": {"name": "Arial", "size": 10}})
        y = {"name": ytitle, "name_font": {"name": "Arial", "size": 10}, "min": 0,
             "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}}}
        if fmt_max:
            y["max"] = fmt_max
        ch.set_y_axis(y)
        ch.set_legend({"position": "bottom"})
        ch.set_size({"width": 760, "height": 320})
        return ch

    chart_row = ct + len(cfg.node_counts) + 3
    ws_sum.insert_chart(chart_row, 0, make_chart("Delivery percentage: Direct vs Epidemic",
                                                 "Messages delivered (%)", 1, 100))
    ws_sum.insert_chart(chart_row + 17, 0, make_chart("Average delivery time: Direct vs Epidemic",
                                                      "Average delivery time (simulation steps)", 3))
    ws_sum.insert_chart(chart_row + 34, 0, make_chart("Copies created: Direct vs Epidemic",
                                                      "Mean copies created per run", 5))

    # ---- Methodology --------------------------------------------------------------
    ws_met.set_column(0, 0, 26)
    ws_met.set_column(1, 1, 120)
    ws_met.write(0, 0, "CampusLink methodology", f_title)
    for i, (k, v) in enumerate(methodology_lines(cfg, experiment_id), start=2):
        ws_met.write(i, 0, k, f_bold)
        ws_met.write(i, 1, v, f_wrap)
        ws_met.set_row(i, 15 * (1 + len(v) // 115))
    ws_met.write(len(methodology_lines(cfg, experiment_id)) + 3, 0,
                 f"Data source: {experiment_dir.name}/run_logs.csv and message_logs.csv (generated by the simulator).", f_note)

    wb.close()
    return out_path
