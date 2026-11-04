# AI Usage Log - CampusLink

This file records AI assistance honestly. Only what is listed here is known to the AI session that wrote it.

## Entry 1 - Initial project build
| Item | Details |
|---|---|
| Date | 2026-11-05 |
| AI tool / platform | Claude (Anthropic), claude.ai chat with a code-execution sandbox. **Not** Antigravity - the project was not built inside Antigravity. |
| Purpose | Build the CampusLink simulator project from the students' master development prompt (Option F). |
| Work done with AI help | Wrote the Python package (config, movement, contact detection, scenario generation, Direct/Epidemic routing, simulator, experiment runner, validation, CSV/JSON storage, Excel report generator, Tkinter visualizer, CLI, local MCP server); wrote 59 unit tests and ran them; ran a pilot; checked the Excel formulas by recalculating a throw-away copy in LibreOffice; wrote README.md, the Sinhala viva guide and this log. |
| Main files affected | `campuslink/*.py`, `tests/*.py`, `campuslink_config.json`, `README.md`, `VIVA_GUIDE_SI.md`, `setup_windows.bat`, `requirements.txt`. |
| What the AI did NOT do | It did not run the official 60-run experiment, did not create screenshots, and did not read the assignment PDF or approved proposal (not provided). It did not test the connection from Antigravity. |
| Student verification / modifications | *(Students: fill in - e.g. which files you read line by line, what you changed, what you ran and checked on your own computer.)* |

## Entry 2 - Aligning the project with the group proposal
| Item | Details |
|---|---|
| Date | 2026-11-05 |
| AI tool / platform | Claude (Anthropic), claude.ai chat with a code-execution sandbox (same session as Entry 1). |
| Purpose | Compare the uploaded proposal PDF with the first build and update the project to follow it. |
| Work done with AI help | Changed grid to 18 x 6; made nodes "stay or move"; made runs continue through all 180 steps; used one experiment-session timestamp for all runs; added `rerun` command and a non-blocking grid-shape warning; updated tests (62 now), README, viva guide. Re-ran tests and a new pilot. |
| Main files affected | `campuslink/config.py`, `movement.py`, `simulator.py`, `experiment.py`, `gates.py`, `cli.py`, `visualizer.py`, `reporting.py`, `campuslink_config.json`, `tests/*`, docs. |
| Student verification / modifications | *(Students: fill in.)* |

## Previous or additional AI assistance (students to complete)
*(Add any other AI use not visible to the session above: tool, date, purpose, what it produced, what you verified or changed. Leave nothing out.)*

| Date | Tool | Purpose | Output / files affected | Student verification |
|---|---|---|---|---|
|  |  |  |  |  |
