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
                        ["notify-send", "-u", "critical", "-a", "NotifySeat", title, message],
                        check=False,
                        timeout=5
                    )
                    return True
                else:
                    # Fallback for Linux terminal
                    print(f"\n\a\033[1;32m[NOTIFYSEAT ALERT] {title}\033[0m\n{message}\n")
                    return True
            elif os_type == "Darwin":  # macOS
                apple_script = f'display notification "{message}" with title "{title}" sound name "Glass"'
                subprocess.run(["osascript", "-e", apple_script], check=False, timeout=5)
                return True
            elif os_type == "Windows":
                # Windows powershell toast fallback
                ps_cmd = f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null; $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); $textNodes = $template.GetElementsByTagName("text"); $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null; $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null; $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("NotifySeat"); $toast = [Windows.UI.Notifications.ToastNotification]::new($template); $notifier.Show($toast);'
                subprocess.run(["powershell", "-Command", ps_cmd], check=False, timeout=5)
                return True
        except Exception as e:
            logger.warning(f"Desktop notification failed: {e}")
            # Fallback stdout
            print(f"\n\a[NOTIFYSEAT] {title}: {message}\n")
            return True

        return True

    def _play_sound(self):
        try:
            # Audible terminal beep
            sys.stdout.write("\a")
            sys.stdout.flush()

            # Linux sound play if available
            if platform.system() == "Linux":
                if shutil.which("paplay"):
                    sound_path = "/usr/share/sounds/freedesktop/stereo/complete.oga"
                    subprocess.run(["paplay", sound_path], check=False, timeout=3, stderr=subprocess.DEVNULL)
                elif shutil.which("aplay"):
                    sound_path = "/usr/share/sounds/alsa/Front_Center.wav"
                    subprocess.run(["aplay", sound_path], check=False, timeout=3, stderr=subprocess.DEVNULL)
        except Exception:
            pass
