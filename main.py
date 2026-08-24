#!/usr/bin/env python3
"""NotifySeat entrypoint with automatic dependency check and bootstrap."""
import sys
import subprocess

REQUIRED_PACKAGES = [
    ("requests", "requests>=2.28.0"),
    ("rich", "rich>=13.0.0"),
]


def ensure_dependencies():
    """Checks if required packages are installed, and automatically installs missing ones."""
    missing = []
    for module_name, pip_spec in REQUIRED_PACKAGES:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_spec)

    if missing:
        print(f"\n📦 \033[1;36mNotifySeat\033[0m: Gerekli paketler eksik ({', '.join(missing)}).")
        print("⏳ Paketler otomatik kuruluyor, lütfen birkaç saniye bekleyin...\n")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *missing],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✔ Kurulum tamamlandı! NotifySeat başlatılıyor...\n")
        except Exception as e:
            print(f"⚠️ Otomatik kurulum başarısız oldu: {e}")
            print("Lütfen elle kurulum yapın: pip install -r requirements.txt\n")


if __name__ == "__main__":
    ensure_dependencies()
    from notifyseat.cli.app import main
    main()
