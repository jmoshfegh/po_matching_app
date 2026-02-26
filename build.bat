@echo off
REM Build a standalone Windows executable for the launcher using PyInstaller.

SET SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

IF EXIST "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    CALL "%SCRIPT_DIR%venv\Scripts\activate.bat"
)

pyinstaller --noconfirm --onefile --name "PO-Matching-App" launcher.py

echo Build complete. Executable is in the dist folder.

