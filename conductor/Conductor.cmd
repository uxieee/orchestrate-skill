@echo off
rem Double-click to start Conductor on Windows and open it in your browser.
rem Uses the Python launcher (py) if it is installed, otherwise python.
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0start.py" %*
) else (
  python "%~dp0start.py" %*
)
if errorlevel 1 pause
