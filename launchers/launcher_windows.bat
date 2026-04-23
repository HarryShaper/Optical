@echo off

REM Get root directory (one level up from launchers)
set ROOT_DIR=%~dp0..
set SCRIPT_PATH=%ROOT_DIR%\optical\optical.py

python "%SCRIPT_PATH%" %*