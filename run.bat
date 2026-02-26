@echo off
REM Activate virtual environment if it exists, then run the launcher.

SET SCRIPT_DIR=%~dp0

IF EXIST "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    CALL "%SCRIPT_DIR%venv\Scripts\activate.bat"
)

python "%SCRIPT_DIR%launcher.py"

