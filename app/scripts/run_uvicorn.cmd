@echo off
cd /d "%~dp0..\.."
if not exist "%USERPROFILE%\.video-use" mkdir "%USERPROFILE%\.video-use"
set PYW=C:\Users\Varun B\AppData\Local\Programs\Python\Python312\pythonw.exe
if not exist "%PYW%" set PYW=pythonw
start "" /B "%PYW%" "app\scripts\serve.py"
