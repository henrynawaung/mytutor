@echo off
rem Creates a "myTutor Control Centre" shortcut with the myTutor icon (mytutor.ico)
rem on your Desktop and in this folder. A .bat file cannot carry its own icon, so the shortcut does.
rem Safe to run again: it just replaces the shortcut.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell; $dir = (Get-Location).Path;" ^
  "foreach ($d in @([Environment]::GetFolderPath('Desktop'), $dir)) {" ^
  "  $s = $w.CreateShortcut((Join-Path $d 'myTutor Control Centre.lnk'));" ^
  "  $s.TargetPath = (Join-Path $dir 'myTutor Control Centre.bat'); $s.WorkingDirectory = $dir;" ^
  "  $s.IconLocation = (Join-Path $dir 'mytutor.ico') + ',0'; $s.WindowStyle = 7;" ^
  "  $s.Description = 'myTutor by henryZ: Control Centre'; $s.Save(); Write-Host ('Shortcut created: ' + $d) }"
echo.
echo Done. Use the "myTutor Control Centre" shortcut on your Desktop.
echo Tip: right-click it and choose "Pin to taskbar" or "Pin to Start".
pause
