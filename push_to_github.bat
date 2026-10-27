@echo off
rem Pushes this folder to https://github.com/henrynawaung/mytutor
rem 1. Create an EMPTY repo named "mytutor" on GitHub first (no README).
rem 2. Run this file from inside the unzipped mytutor folder.
cd /d "%~dp0"
git remote remove origin 2>nul
git remote add origin https://github.com/henrynawaung/mytutor.git
git branch -M main
git push -u origin main
pause
