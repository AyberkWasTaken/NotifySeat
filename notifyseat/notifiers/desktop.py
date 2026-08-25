"""Desktop & System sound notification provider."""
import subprocess
import shutil
import platform
import sys
from typing import Optional, Dict, Any
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import DesktopConfig
from notifyseat.core.logger import logger


class DesktopNotifier(BaseNotifier):
    """Sends native desktop notifications and sound alerts."""

    def __init__(self, config: DesktopConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "desktop"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled:
            return False

        success = self._send_desktop_notification(title, message)
        if self.config.sound_enabled:
            self._play_sound()
        return success

    def test(self) -> bool:
        return self.send(
            title="NotifySeat - Test Alert",
            message="This is a test desktop alert from NotifySeat! System is working properly."
        )

    def _send_desktop_notification(self, title: str, message: str) -> bool:
        os_type = platform.system()
        try:
            if os_type == "Linux":
                if shutil.which("notify-send"):
                    subprocess.run(
                        ["notify-send", "-u", "normal", "-a", "NotifySeat", "-i", "dialog-information", title, message],
                        check=False,
                        timeout=5,
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL
                    )
                    return True
                else:
                    print(f"\n\a\033[1;32m[NOTIFYSEAT ALERT] {title}\033[0m\n{message}\n")
                    return True
            elif os_type == "Darwin":  # macOS
                import json
                apple_script = f'display notification {json.dumps(message)} with title {json.dumps(title)} sound name "Glass"'
                subprocess.run(["osascript", "-e", apple_script], check=False, timeout=5, stderr=subprocess.DEVNULL)
                return True
            elif os_type == "Windows":
                # Escape double quotes and special characters for PowerShell
                win_title = title.replace('`', '``').replace('"', '`"').replace("'", "''")
                win_msg = message.replace('`', '``').replace('"', '`"').replace("'", "''")
                ps_cmd = (
                    f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; '
                    f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); '
                    f'$textNodes = $template.GetElementsByTagName("text"); '
                    f'$textNodes.Item(0).AppendChild($template.CreateTextNode("{win_title}")) > $null; '
                    f'$textNodes.Item(1).AppendChild($template.CreateTextNode("{win_msg}")) > $null; '
                    f'$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("NotifySeat"); '
                    f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template); '
                    f'$notifier.Show($toast);'
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False, timeout=5, stderr=subprocess.DEVNULL)
                return True
        except Exception as e:
            logger.warning(f"Desktop notification failed: {e}")
            print(f"\n\a[NOTIFYSEAT] {title}: {message}\n")
            return True

        return True

    def _play_sound(self):
        try:
            # Audible terminal bell
            sys.stdout.write("\a")
            sys.stdout.flush()

            os_type = platform.system()
            if os_type == "Windows":
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except Exception:
                    pass
            elif os_type == "Darwin":  # macOS
                if shutil.which("afplay") and os.path.exists("/System/Library/Sounds/Glass.aiff"):
                    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False, timeout=3, stderr=subprocess.DEVNULL)
            elif os_type == "Linux":
                import os
                candidate_sounds = [
                    "/usr/share/sounds/Oxygen-Sys-App-Positive.ogg",
                    "/usr/share/sounds/freedesktop/stereo/complete.oga",
                    "/usr/share/sounds/speech-dispatcher/test.wav",
                    "/usr/share/sounds/alsa/Front_Center.wav"
                ]
                sound_file = next((s for s in candidate_sounds if os.path.exists(s)), None)
                if sound_file:
                    if shutil.which("pw-play"):
                        subprocess.run(["pw-play", sound_file], check=False, timeout=3, stderr=subprocess.DEVNULL)
                    elif shutil.which("paplay"):
                        subprocess.run(["paplay", sound_file], check=False, timeout=3, stderr=subprocess.DEVNULL)
                    elif shutil.which("aplay") and sound_file.endswith(".wav"):
                        subprocess.run(["aplay", sound_file], check=False, timeout=3, stderr=subprocess.DEVNULL)
        except Exception:
            pass
