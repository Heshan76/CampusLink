"""Live Tkinter visualizer. It only DISPLAYS a real Simulation; it contains no routing logic.

Evidence mode (default) replays the exact official scenario (same seed as the
official run with the same node count / repetition / method), so what you see can
be compared with the matching row of run_logs.csv.
"""
import csv
from pathlib import Path

from .config import load_config, project_root
from .scenario import scenario_from_config
from .simulator import Simulation, summarize
from .contact import contacts_for_scenario

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # keeps the rest of the package importable without Tk
    tk = None


class Session:
    """Builds the scenario + simulation for the chosen options (no GUI code here)."""

    def __init__(self, cfg, node_count, method, repetition, evidence=True):
        self.cfg, self.method, self.repetition = cfg, method, repetition
        self.pilot = not evidence
        self.scenario = scenario_from_config(cfg, node_count, repetition, pilot=self.pilot)
        self.sim = Simulation(self.scenario, method, cfg.contact_radius,
                              contacts_for_scenario(self.scenario, cfg.contact_radius),
                              stop_when_all_delivered=True)
        self.run_id = cfg.run_id(node_count, method, repetition, self.pilot)

    def snapshot(self):
        sim, sc = self.sim, self.scenario
        held = {}
        for st in sim.router.states:
            if not st.delivered:
                for h in st.holders:
                    held[h] = held.get(h, 0) + 1
        in_contact = {n for c in sim.current_contacts for n in (c.node_a, c.node_b)}
        return {
            "run_id": self.run_id, "scenario_id": sc.scenario_id, "seed": sc.seed,
            "method": self.method, "node_count": sc.node_count,
            "grid": (sc.grid_width, sc.grid_height),
            "step": max(sim.current_step, 0), "max_steps": sc.max_steps,
            "positions": sim.positions, "contacts": [(c.node_a, c.node_b) for c in sim.current_contacts],
            "in_contact": in_contact, "holders_count": held,
            "delivered": sim.delivered_count, "total": len(sim.router.states),
            "remaining": len(sim.router.states) - sim.delivered_count,
            "copies": sim.copies_created, "finished": sim.finished,
            "messages": [(s.message.message_id, s.message.source, s.message.destination, s.delivered,
                          s.delivery_step, len(s.holders), s.copies_created) for s in sim.router.states],
        }

    def final_metrics(self):
        total, delivered, pct, avg, copies, _ = summarize(self.sim.message_results())
        return {"total": total, "delivered": delivered, "pct": pct, "avg": avg, "copies": copies}


def find_official_record(root, run_id):
    """Row from the newest official run_logs.csv for this run_id (or None)."""
    base = Path(root) / "outputs" / "official"
    if not base.exists():
        return None
    folders = sorted(p for p in base.iterdir() if (p / "run_logs.csv").exists())
    if not folders:
        return None
    with open(folders[-1] / "run_logs.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["run_id"] == run_id:
                return row
    return None


class VisualizerApp:
    CANVAS = 640   # longest side of the grid in pixels

    def __init__(self, cfg, root, node_count=None, method="DIRECT", repetition=1,
                 evidence=True, autostart=False, delay_ms=120):
        if tk is None:
            raise RuntimeError("Tkinter is not available in this Python installation.")
        self.cfg, self.root_dir = cfg, root
        self.win = tk.Tk()
        self.win.title("CampusLink - live simulation")
        self.delay = tk.IntVar(value=delay_ms)
        self.method = tk.StringVar(value=method)
        self.nodes = tk.IntVar(value=node_count or cfg.node_counts[0])
        self.rep = tk.IntVar(value=repetition)
        self.evidence = tk.BooleanVar(value=evidence)
        self.running = False
        self._job = None
        self._build_widgets()
        self.reset()
        if autostart:
            self.toggle()

    # ---- layout ----------------------------------------------------------------
    def _build_widgets(self):
        top = ttk.Frame(self.win, padding=6)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(top, text="Method:").pack(side="left")
        for m in self.cfg.routing_methods:
            ttk.Radiobutton(top, text=m.title(), value=m, variable=self.method,
                            command=self.reset).pack(side="left", padx=2)
        ttk.Label(top, text="  Nodes:").pack(side="left")
        ttk.Combobox(top, width=4, state="readonly", values=list(self.cfg.node_counts),
                     textvariable=self.nodes).pack(side="left")
        self.nodes_box = top.winfo_children()[-1]
        self.nodes_box.bind("<<ComboboxSelected>>", lambda e: self.reset())
        ttk.Label(top, text="  Repetition:").pack(side="left")
        ttk.Spinbox(top, from_=1, to=self.cfg.repetitions, width=3, textvariable=self.rep,
                    command=self.reset).pack(side="left")
        ttk.Checkbutton(top, text="Official scenario (evidence mode)", variable=self.evidence,
                        command=self.reset).pack(side="left", padx=8)

        gw, gh = self.cfg.grid_width, self.cfg.grid_height
        cell0 = self.CANVAS / max(gw, gh)
        self.canvas = tk.Canvas(self.win, width=gw * cell0, height=gh * cell0, bg="white",
                                highlightthickness=1, highlightbackground="#888")
        self.canvas.grid(row=1, column=0, padx=6, pady=4, sticky="n")

        side = ttk.Frame(self.win, padding=6)
        side.grid(row=1, column=1, sticky="n")
        self.info = tk.Text(side, width=44, height=15, font=("Consolas", 10), state="disabled",
                            bg="#F7F7F7")
        self.info.pack()
        ttk.Label(side, text="Messages (id: source -> destination)").pack(anchor="w", pady=(6, 0))
        self.msgbox = tk.Text(side, width=44, height=9, font=("Consolas", 10), state="disabled",
                              bg="#F7F7F7")
        self.msgbox.pack()

        bar = ttk.Frame(self.win, padding=6)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.btn = ttk.Button(bar, text="Start", command=self.toggle)
        self.btn.pack(side="left")
        ttk.Button(bar, text="Step", command=self.single_step).pack(side="left", padx=4)
        ttk.Button(bar, text="Reset", command=self.reset).pack(side="left")
        ttk.Label(bar, text="   Delay (ms):").pack(side="left")
        ttk.Scale(bar, from_=10, to=600, variable=self.delay, length=140).pack(side="left")
        ttk.Label(bar, text="  Blue = no message | orange = holds message | red ring = in contact",
                  foreground="#555").pack(side="left", padx=8)

    # ---- control -----------------------------------------------------------------
    def reset(self):
        self._stop()
        self.session = Session(self.cfg, self.nodes.get(), self.method.get(), self.rep.get(),
                               self.evidence.get())
        self.session.sim.step()   # show step 0 (starting layout and any contact at t=0)
        self.draw()

    def _stop(self):
        self.running = False
        if self._job is not None:
            self.win.after_cancel(self._job)
            self._job = None
        if hasattr(self, "btn"):
            self.btn.config(text="Start")

    def toggle(self):
        if self.running:
            self._stop()
        elif not self.session.sim.finished:
            self.running = True
            self.btn.config(text="Pause")
            self._tick()

    def single_step(self):
        if not self.running:
            self.session.sim.step()
            self.draw()

    def _tick(self):
        if not self.running:
            return
        self.session.sim.step()
        self.draw()
        if self.session.sim.finished:
            self._stop()
        else:
            self._job = self.win.after(int(self.delay.get()), self._tick)

    # ---- drawing -----------------------------------------------------------------
    def draw(self):
        s = self.session.snapshot()
        w, h = s["grid"]
        cell = self.CANVAS / max(w, h)
        c = self.canvas
        c.delete("all")
        for i in range(w + 1):
            c.create_line(i * cell, 0, i * cell, h * cell, fill="#DDD")
        for j in range(h + 1):
            c.create_line(0, j * cell, w * cell, j * cell, fill="#DDD")

        def center(idx, slot=None):
            x, y = s["positions"][idx]
            return (x + 0.5) * cell, (y + 0.5) * cell

        # nodes that share a cell are spread over 4 sub-slots so IDs stay readable
        occupants = {}
        for idx, pos in enumerate(s["positions"]):
            occupants.setdefault(pos, []).append(idx)
        offsets = [(0, 0), (0.22, 0.22), (-0.22, 0.22), (0.22, -0.22), (-0.22, -0.22)]
        centers = {}
        for pos, ids in occupants.items():
            for k, idx in enumerate(ids):
                ox, oy = offsets[min(k, len(offsets) - 1)] if len(ids) > 1 else (0, 0)
                centers[idx] = ((pos[0] + 0.5 + ox) * cell, (pos[1] + 0.5 + oy) * cell)

        for a, b in s["contacts"]:
            c.create_line(*centers[a], *centers[b], fill="#D32F2F", width=2)
        r = cell * (0.30 if len(s["positions"]) <= 20 else 0.24)
        for idx in range(len(s["positions"])):
            x, y = centers[idx]
            held = idx in s["holders_count"]
            c.create_oval(x - r, y - r, x + r, y + r, fill="#FFB74D" if held else "#90CAF9",
                          outline="#D32F2F" if idx in s["in_contact"] else "#37474F",
                          width=3 if idx in s["in_contact"] else 1)
            c.create_text(x, y, text=str(idx), font=("Arial", 8 if r < 11 else 9, "bold"))

        lines = [
            f"Run ID      : {s['run_id']}",
            f"Scenario ID : {s['scenario_id']}",
            f"Random seed : {s['seed']}",
            f"Method      : {s['method']}",
            f"Nodes       : {s['node_count']}",
            f"Grid        : {s['grid'][0]} x {s['grid'][1]}",
            f"Step        : {s['step']} / {s['max_steps']}",
            f"Contacts now: {len(s['contacts'])}",
            f"Delivered   : {s['delivered']} / {s['total']}",
            f"Remaining   : {s['remaining']}",
            f"Copies made : {s['copies']}",
        ]
        if s["finished"]:
            fm = self.session.final_metrics()
            avg = "N/A" if fm["avg"] is None else f"{fm['avg']:.2f}"
            lines += ["", f"FINISHED  delivery {fm['pct']:.1f}%  avg time {avg}"]
            rec = find_official_record(self.root_dir, s["run_id"]) if self.evidence.get() else None
            if rec:
                same = (int(rec["messages_delivered"]) == fm["delivered"] and
                        int(rec["total_copies_created"]) == fm["copies"])
                lines.append(f"Official record: {'MATCH' if same else 'MISMATCH'}")
        self._set_text(self.info, "\n".join(lines))

        mlines = []
        for mid, src, dst, done, dstep, nholders, copies in s["messages"]:
            if done:
                mlines.append(f"M{mid}: {src:>2} -> {dst:>2}  DELIVERED t={dstep}")
            else:
                extra = f" holders={nholders}" if s["method"] == "EPIDEMIC" else ""
                mlines.append(f"M{mid}: {src:>2} -> {dst:>2}  waiting{extra}")
        self._set_text(self.msgbox, "\n".join(mlines))

    @staticmethod
    def _set_text(widget, text):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def run(self):
        self.win.mainloop()


def run_visualizer(node_count=None, method="DIRECT", repetition=1, evidence=True, autostart=False):
    cfg = load_config()
    app = VisualizerApp(cfg, project_root(), node_count, method, repetition, evidence, autostart)
    app.run()
