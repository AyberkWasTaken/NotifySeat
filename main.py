#!/usr/bin/env python3
"""NotifySeat entrypoint with automatic dependency check and bootstrap."""
import os
import sys
import subprocess
from pathlib import Path

REQUIRED_PACKAGES = [
    ("requests", "requests>=2.28.0"),
    ("rich", "rich>=13.0.0"),
]


def _find_virtualenv_python():
    """Finds a working Python interpreter from pipx or local .venv."""
    pipx_py = Path.home() / ".local" / "share" / "pipx" / "venvs" / "notifyseat" / "bin" / "python"
    if pipx_py.exists():
        return str(pipx_py)

    local_venv_py = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
    if local_venv_py.exists():
        return str(local_venv_py)

    return None


def ensure_dependencies():
    """Checks if required packages are installed, delegating to pipx or venv if needed."""
    missing = []
    for module_name, pip_spec in REQUIRED_PACKAGES:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_spec)

    if not missing:
        return

    # If missing in system Python, attempt automatic delegation to pipx / .venv
    venv_py = _find_virtualenv_python()
    if venv_py and venv_py != sys.executable:
        os.execv(venv_py, [venv_py, *sys.argv])

    # Fallback bootstrap if running inside an active environment with pip
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return
    except Exception:
        print(
            "\n⚠️ NotifySeat bağımlılıkları sistem Python ortamında bulunamadı.\n"
            "💡 NotifySeat'i doğrudan çalıştırmak için terminalde şunu yazın:\n"
            "   \033[1;32mnotifyseat\033[0m (veya \033[1;32mnotifyseat track\033[0m, \033[1;32mnotifyseat gui\033[0m)\n\n"
            "Geliştirici ortamını bağlamak için:\n"
            "   \033[1;36mpipx install --editable .\033[0m\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    ensure_dependencies()
    from notifyseat.cli.app import main
    main()
