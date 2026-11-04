# CampusLink: Direct vs Epidemic Message Delivery in a Campus Walkway

Advanced Mobile Computing - Option F. Group: CampusLink Team (PHMLCB Abeyrathne D/BSE/24/0018, MAH Dharmasiri D/BCS/24/0009). A small Python simulator in which people (nodes) walk randomly
on a square grid and pass messages when they meet. It compares **Direct** routing with **Epidemic**
routing over **3 group sizes x 2 methods x 10 repetitions = 60 runs** and measures
**delivery percentage**, **average delivery time** and **copies made**.

> **Project status:** built and tested; pilot done. The 60-run official experiment has **not** been run
> yet (it needs your approval phrase) and the two real screenshots have **not** been captured yet.

## Settings and their source
Taken from the project proposal (`reference/CampusLink_Proposal.pdf`): **18 x 6 grid**, nodes 10/20/40, both methods, 10 repetitions
(60 runs), **6 messages/run**, **180 steps** (the run continues through all 180 steps), nodes **stay or move** one cell,
contact = same or horizontally/vertically adjacent cell, matched fixed seeds, copies include delivery to the destination.
Still my own decisions (not in the proposal): base seed 42 and the seed formula, Manhattan-distance wording, "uniform among stay + legal moves".

**Open conflict to resolve before the official run:** the proposal specifies a narrow 18 x 6 grid, but the lecturer reportedly asked
for a larger, **squarish** grid. The assignment PDF was not available, so this could not be checked. `validate-config` prints a
warning while the grid is not square. If a square grid applies, change `grid_width`/`grid_height` in `campuslink_config.json`
(e.g. 16 and 16) and re-run `campuslink test` and `campuslink validate-config`. No code changes are needed.

## Requirements
Windows 10/11, Python 3.10 or newer (tested with 3.12). Tkinter is included with the python.org installer.
Packages: `mcp` (MCP server only), `xlsxwriter` (Excel), `openpyxl` (tests only).

## Installation (Windows, Command Prompt in the CampusLink folder)
```
setup_windows.bat
```
or manually:
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m campuslink.cli test
.venv\Scripts\python -m campuslink.cli validate-config
```
All later commands use `.venv\Scripts\python -m campuslink.cli ...` (written as `campuslink ...` below).

## How it works (short)
* **Grid:** 18 columns x 6 rows (configurable), no wrap-around. **Movement:** every step each node either stays or moves one cell left/right/up/down (uniform among "stay" and the moves that keep it inside the grid).
* **Contact:** Manhattan distance <= 1 (same cell or side-by-side/above-below; **diagonals do not count**).
* **Direct:** the source keeps the message until it meets the destination, then hands over the original. No copies.
* **Epidemic:** a holder gives a copy to each neighbour without one. One hop per step; if the destination is touched in a step it is delivered first; after delivery that message stops being forwarded, but the run still continues through all 180 steps.
* **Fair comparison:** one scenario (start positions, message pairs, whole movement trace) is generated per node-count/repetition from a seed, **before** routing, and replayed for both methods. Seed = `42 + nodes x 100 + repetition`.
* **Metrics:** delivery % = delivered / generated x 100. Delivery time = delivery step - creation step, averaged over *delivered* messages only (undelivered are never counted as 0; blank if none delivered). Copies = times a new node received a message for the first time beyond the source's original (Direct = 0; Epidemic includes the final copy to the destination). *Transfer events* are logged separately as a diagnostic.

## Commands
| Task | Command |
|---|---|
| Run unit tests (records result) | `campuslink test` |
| Validate configuration | `campuslink validate-config` |
| Pilot: all 6 combinations, repetition 1 | `campuslink pilot --all` |
| Pilot: one run | `campuslink pilot --nodes 20 --method EPIDEMIC --repetition 1` |
| Re-run one selected experiment live (compares with official record) | `campuslink rerun --nodes 20 --method EPIDEMIC --repetition 1` |
| Live visualizer (Direct) | `campuslink visualize --nodes 20 --method DIRECT --repetition 1` |
| Live visualizer (Epidemic) | `campuslink visualize --nodes 20 --method EPIDEMIC --repetition 1` |
| **Official 60 runs** | `campuslink official --approve "APPROVE OFFICIAL 60-RUN EXPERIMENT"` |
| Validate official data | `campuslink validate` |
| Excel workbook | `campuslink workbook` |
| Final ZIP | `campuslink submission` |
| Project status | `campuslink status` |

Pilot results go to `outputs\pilot\` and are **never** official data. Official results go to a new
`outputs\official\official_<date_time>\` folder containing `run_logs.csv` (60 rows; `run_timestamp` is the experiment-session timestamp shared by all runs), `message_logs.csv`,
`experiment_config.json`, `experiment_manifest.json` and later `CampusLink_Results.xlsx`.
The official run refuses unless: the exact phrase is given, tests passed for the *current* code, the config is validated,
and no official experiment exists yet (it never overwrites).

## Visualization and screenshots
`campuslink visualize ...` opens a Tkinter window showing the grid, node IDs, method, node count, step, contacts, delivered/remaining,
copies, seed and run/scenario ID. By default it replays the **official scenario** (same seed as the official run), and after the
official experiment exists it shows **MATCH/MISMATCH** against the official record when a run finishes.
Press **Start**, and capture the window with **Win + Shift + S** while it is running (or at the end), once for Direct and once for Epidemic.
Save as `evidence\Screenshot_01_Direct_Measurement.png` and `evidence\Screenshot_02_Epidemic_Measurement.png`.
Use the same node count and repetition for both (e.g. 20 nodes, repetition 1). Screenshots must be real captures of the running program.

## MCP server (CampusLink Control MCP)
A local stdio server with six tools: `campuslink_get_status`, `campuslink_run_pilot`, `campuslink_run_official_experiment`,
`campuslink_validate_results`, `campuslink_generate_workbook`, `campuslink_prepare_submission`. No shell, no file paths, no network.
1. `campuslink write-mcp-config` creates/merges `.agents\mcp_config.json` with this computer's real paths (existing servers are kept).
2. Restart/refresh MCP servers in Antigravity and check that the six tools appear.
3. If it does not connect, use the normal commands above - the simulator never needs MCP.
Manual start for debugging: `.venv\Scripts\python -m campuslink.mcp_server`.

## Final ZIP
After the official run, workbook and both screenshots exist: `campuslink submission` creates `submission\CampusLink_Submission.zip`
with `README.md`, `source_code\`, `raw_data\`, `results\CampusLink_Results.xlsx`, `evidence\` (2 screenshots) and `AI_Usage_Log.md`.
It refuses (and lists what is missing) if anything, including either screenshot, is absent.

## Project layout
`campuslink\` (config, models, movement, contact, scenario, routing, simulator, experiment, validation, storage, reporting,
visualizer, control, mcp_server, cli) - `tests\` - `outputs\pilot|official` - `evidence\` - `reference\` - `VIVA_GUIDE_SI.md` (Sinhala viva notes).

## Not included
The proposal also mentions a required 2-3 page report and a summary/chart for the live demonstration. The report is **not** part of this
package; write it after the official results exist (the workbook has the table and charts).

## Limitations
Random walk on a small grid, instant lossless transfers, no buffer limits or message expiry, 10 repetitions only.
Epidemic stops spreading a message after delivery, so its copy counts are lower than unrestricted flooding.
