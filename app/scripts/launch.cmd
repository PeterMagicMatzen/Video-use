@echo off
setlocal
cd /d "%~dp0..\.."
set PY=C:\Users\Varun B\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
"%PY%" "app\scripts\start_server.py"
if errorlevel 1 (
  echo.
  echo video-use failed to start. Log: %USERPROFILE%\.video-use\server.log
  pause
  exit /b 1
)
start "" http://127.0.0.1:8787
