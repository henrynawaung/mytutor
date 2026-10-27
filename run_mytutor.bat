@echo off
rem One myTutor run. Used by n8n, or by Windows Task Scheduler as the fall-back.
cd /d "%~dp0"
py run.py >> jobs\run_output.log 2>&1
