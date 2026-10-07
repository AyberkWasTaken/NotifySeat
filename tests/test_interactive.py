"""Unit tests for interactive menus and prompt_choice."""
import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
from notifyseat.cli.interactive import (
    prompt_choice,
    prompt_multi_checkbox,
    _read_key_cross_platform,
    interactive_task_manager
)
from notifyseat.core.models import TrackingTask, TaskStatus, TransportType


class TestInteractiveMenus(unittest.TestCase):

    def test_prompt_choice_empty(self):
        res = prompt_choice("Empty test", [])
        self.assertEqual(res, 0)

    @patch("sys.stdin.isatty", return_value=False)
    @patch("builtins.input", return_value="2")
    def test_prompt_choice_non_interactive_selection(self, mock_input, mock_isatty):
        choices = ["Option A", "Option B", "Option C"]
        res = prompt_choice("Pick one", choices, default_idx=0)
        self.assertEqual(res, 1)

    @patch("sys.stdin.isatty", return_value=False)
    @patch("builtins.input", return_value="")
    def test_prompt_choice_non_interactive_default(self, mock_input, mock_isatty):
        choices = ["Option A", "Option B", "Option C"]
        res = prompt_choice("Pick one", choices, default_idx=2)
        self.assertEqual(res, 2)

    @patch("sys.stdin.isatty", return_value=True)
    @patch("notifyseat.cli.interactive._read_key_cross_platform")
    @patch("os.name", "posix")
    @patch("termios.tcgetattr", return_value=[])
    @patch("termios.tcsetattr", return_value=None)
    @patch("tty.setraw", return_value=None)
    def test_prompt_choice_interactive_arrows(self, mock_setraw, mock_tcset, mock_tcget, mock_key, mock_isatty):
        mock_key.side_effect = ["DOWN", "DOWN", "ENTER"]
        choices = ["Item 1", "Item 2", "Item 3", "Item 4"]
        res = prompt_choice("Choose item", choices, default_idx=0)
        self.assertEqual(res, 2)

    @patch("sys.stdin.isatty", return_value=True)
    @patch("notifyseat.cli.interactive._read_key_cross_platform")
    @patch("os.name", "posix")
    @patch("termios.tcgetattr", return_value=[])
    @patch("termios.tcsetattr", return_value=None)
    @patch("tty.setraw", return_value=None)
    def test_prompt_choice_interactive_digit_jump(self, mock_setraw, mock_tcset, mock_tcget, mock_key, mock_isatty):
        mock_key.side_effect = ["3", "ENTER"]
        choices = ["First", "Second", "Third", "Fourth"]
        res = prompt_choice("Jump test", choices, default_idx=0)
        self.assertEqual(res, 2)

    @patch("sys.stdin.isatty", return_value=False)
    def test_prompt_multi_checkbox_non_interactive(self, mock_isatty):
        options = ["Train 1", "Train 2"]
        res = prompt_multi_checkbox("Select trains", options)
        self.assertEqual(res, [0, 1])

    def test_interactive_task_manager_empty(self):
        mock_db = MagicMock()
        mock_db.list_tasks.return_value = []
        interactive_task_manager(mock_db)

    @patch("sys.stdin.isatty", return_value=False)
    def test_interactive_task_manager_non_interactive(self, mock_isatty):
        mock_db = MagicMock()
        t = TrackingTask(id="1", origin="Ankara Gar", destination="Eskişehir", date="28-10-2026")
        mock_db.list_tasks.return_value = [t]
        interactive_task_manager(mock_db)

    @patch("sys.stdin.isatty", return_value=True)
    @patch("notifyseat.cli.interactive._read_key_cross_platform")
    @patch("os.name", "posix")
    @patch("termios.tcgetattr", return_value=[])
    @patch("termios.tcsetattr", return_value=None)
    @patch("tty.setraw", return_value=None)
    def test_interactive_task_manager_toggle_and_exit(self, mock_setraw, mock_tcset, mock_tcget, mock_key, mock_isatty):
        mock_db = MagicMock()
        t = TrackingTask(id="1", origin="Ankara Gar", destination="Eskişehir", date="28-10-2026", status=TaskStatus.ACTIVE)
        mock_db.list_tasks.return_value = [t]
        # Simulate pressing F2 (pause) then F10 (exit)
        mock_key.side_effect = ["F2", "F10"]
        interactive_task_manager(mock_db)
        mock_db.update_task_status.assert_called_with("1", TaskStatus.PAUSED)

    @patch("os.name", "posix")
    @patch("sys.stdin.fileno", return_value=0)
    @patch("os.read")
    def test_read_key_cross_platform_sequences(self, mock_read, mock_fileno):
        # UP arrow
        mock_read.return_value = b'\x1b[A'
        self.assertEqual(_read_key_cross_platform(), 'UP')

        # DOWN arrow
        mock_read.return_value = b'\x1b[B'
        self.assertEqual(_read_key_cross_platform(), 'DOWN')

        # F2 key
        mock_read.return_value = b'\x1bOQ'
        self.assertEqual(_read_key_cross_platform(), 'F2')

        # F4 key (VT100)
        mock_read.return_value = b'\x1bOS'
        self.assertEqual(_read_key_cross_platform(), 'F4')

        # F4 key (xterm / linux)
        mock_read.return_value = b'\x1b[14~'
        self.assertEqual(_read_key_cross_platform(), 'F4')

        # F5 key
        mock_read.return_value = b'\x1b[15~'
        self.assertEqual(_read_key_cross_platform(), 'F5')

        # F10 key
        mock_read.return_value = b'\x1b[21~'
        self.assertEqual(_read_key_cross_platform(), 'F10')

        # Unrecognized escape sequence should not return ESC (prevents unintended loop exits)
        mock_read.return_value = b'\x1b[99~'
        self.assertEqual(_read_key_cross_platform(), '')


if __name__ == "__main__":
    unittest.main()
