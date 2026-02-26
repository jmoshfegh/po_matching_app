from __future__ import annotations

import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def _find_python_executable() -> str:
    """
    Return the path to the current Python executable.
    This works both in a venv and a system install.
    """
    return sys.executable


def main() -> None:
    project_root = Path(__file__).resolve().parent
    app_path = project_root / "app.py"

    python_exe = _find_python_executable()

    # Start Streamlit in headless mode
    cmd = [
        python_exe,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
    ]

    subprocess.Popen(cmd, cwd=str(project_root))

    # Give Streamlit a moment to start, then open browser
    time.sleep(2)
    webbrowser.open("http://localhost:8501")


if __name__ == "__main__":
    main()
