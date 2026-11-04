@echo off
REM One-time setup for CampusLink on Windows. Run from the CampusLink folder.
python --version || (echo Python 3.10+ is required. Install it from python.org & exit /b 1)
python -m venv .venv || exit /b 1
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt || exit /b 1
.venv\Scripts\python -m campuslink.cli test || exit /b 1
.venv\Scripts\python -m campuslink.cli validate-config || exit /b 1
.venv\Scripts\python -m campuslink.cli write-mcp-config
echo.
echo Setup finished. Next: .venv\Scripts\python -m campuslink.cli pilot --all
