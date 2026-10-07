"""Interactive Terminal Wizard for NotifySeat."""
import os
import sys
import calendar
from datetime import datetime, timedelta, date
from typing import Optional, List, Any, Dict

try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        readline = None

from notifyseat.core.models import TrackingTask, TransportType, TaskStatus
from notifyseat.core.config import ConfigManager
from notifyseat.providers.registry import registry
from notifyseat.providers.tcdd import TCDD_STATIONS, normalize_tr


class StationTabCompleter:
    """Provides smart prefix-prioritized TAB autocompletion for train stations."""
    def __init__(self, candidates: List[Any]):
        self.station_names = []
        for c in candidates:
            if isinstance(c, dict):
                name = c.get("name", "")
                if name:
                    self.station_names.append(name)
            elif isinstance(c, str):
                self.station_names.append(c)
        self.matches = []

    def complete(self, text: str, state: int):
        if state == 0:
            if text:
                q_norm = normalize_tr(text)
                starts_with = []
                word_starts = []
                contains = []
                for name in self.station_names:
                    n_norm = normalize_tr(name)
                    if n_norm.startswith(q_norm):
                        starts_with.append(name)
                    elif any(normalize_tr(w).startswith(q_norm) for w in name.replace("(", " ").replace(")", " ").split()):
                        word_starts.append(name)
                    elif q_norm in n_norm:
                        contains.append(name)
                
                # Combine distinct matches in ranked order
                seen = set()
                self.matches = []
                for item in starts_with + word_starts + contains:
                    if item not in seen:
                        seen.add(item)
                        self.matches.append(item)
            else:
                self.matches = self.station_names[:]
        try:
            return self.matches[state]
        except IndexError:
            return None


def _read_key_cross_platform() -> str:
    """Reads a single keypress, arrow key, function key (F1-F12), or special key cross-platform."""
    if os.name == 'nt':  # Windows
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):
            ch2 = msvcrt.getch()
            mapping = {
                b'H': 'UP',
                b'P': 'DOWN',
                b'K': 'LEFT',
                b'M': 'RIGHT',
                b';': 'F1',
                b'<': 'F2',
                b'=': 'F3',
                b'>': 'F4',
                b'?': 'F5',
                b'@': 'F6',
                b'A': 'F7',
                b'B': 'F8',
                b'C': 'F9',
                b'D': 'F10',
                b'S': 'DELETE',
            }
            return mapping.get(ch2, '')
        elif ch in (b'\r', b'\n'):
            return 'ENTER'
        elif ch == b' ':
            return 'SPACE'
        elif ch == b'\x1b':
            return 'ESC'
        elif ch in (b'a', b'A'):
            return 'ALL'
        elif ch in (b'k', b'K'):
            return 'UP'
        elif ch in (b'j', b'J'):
            return 'DOWN'
        elif ch in (b'd', b'D'):
            return 'DELETE'
        elif ch in (b'p', b'P'):
            return 'PAUSE'
        elif ch in (b'c', b'C'):
            return 'CHECK'
        elif ch in (b'r', b'R'):
            return 'RUN'
        elif ch in (b'q', b'Q'):
            return 'QUIT'
        elif ch == b'\x03':  # Ctrl+C
            raise KeyboardInterrupt
        return ch.decode(errors='ignore')
    else:  # Unix (Linux / macOS)
        import select
        fd = sys.stdin.fileno()
        try:
            raw = os.read(fd, 32)
        except Exception:
            return ''
        if not raw:
            return ''

        # If it's a lone escape byte, check if trailing escape sequence bytes follow shortly (50ms)
        if raw == b'\x1b':
            r, _, _ = select.select([fd], [], [], 0.05)
            if r:
                try:
                    raw += os.read(fd, 31)
                except Exception:
                    pass
            else:
                return 'ESC'

        seq = raw.decode(errors='ignore')

        # Arrow keys
        if seq in ('\x1b[A', '\x1bOA'): return 'UP'
        if seq in ('\x1b[B', '\x1bOB'): return 'DOWN'
        if seq in ('\x1b[C', '\x1bOC'): return 'RIGHT'
        if seq in ('\x1b[D', '\x1bOD'): return 'LEFT'

        # Function keys (F1 - F12 across xterm, vt100, rxvt, Linux console)
        if seq in ('\x1bOP', '\x1b[11~', '\x1b[[A', '\x1b[1;2P'): return 'F1'
        if seq in ('\x1bOQ', '\x1b[12~', '\x1b[[B', '\x1b[1;2Q'): return 'F2'
        if seq in ('\x1bOR', '\x1b[13~', '\x1b[[C', '\x1b[1;2R'): return 'F3'
        if seq in ('\x1bOS', '\x1b[14~', '\x1b[[D', '\x1b[1;2S'): return 'F4'
        if seq in ('\x1b[15~', '\x1b[[E', '\x1b[15;2~'): return 'F5'
        if seq in ('\x1b[17~', '\x1b[17;2~'): return 'F6'
        if seq in ('\x1b[18~', '\x1b[18;2~'): return 'F7'
        if seq in ('\x1b[19~', '\x1b[19;2~'): return 'F8'
        if seq in ('\x1b[20~', '\x1b[20;2~'): return 'F9'
        if seq in ('\x1b[21~', '\x1b[21;2~'): return 'F10'
        if seq in ('\x1b[23~', '\x1b[23;2~'): return 'F11'
        if seq in ('\x1b[24~', '\x1b[24;2~'): return 'F12'

        # Special keys
        if seq in ('\x1b[3~',): return 'DELETE'
        if seq == '\x1b': return 'ESC'
        if seq.startswith('\x1b'): return ''  # Unrecognized escape, do NOT return ESC!

        # Normal single characters
        if seq in ('\r', '\n'): return 'ENTER'
        if seq == ' ': return 'SPACE'
        if seq in ('a', 'A'): return 'ALL'
        if seq in ('k', 'K'): return 'UP'
        if seq in ('j', 'J'): return 'DOWN'
        if seq in ('d', 'D'): return 'DELETE'
        if seq in ('p', 'P'): return 'PAUSE'
        if seq in ('c', 'C'): return 'CHECK'
        if seq in ('r', 'R'): return 'RUN'
        if seq in ('q', 'Q'): return 'QUIT'
        if seq == '\x03': raise KeyboardInterrupt
        return seq


def prompt_choice(prompt: str, choices: List[str], default_idx: int = 0) -> int:
    """
    Renders a flicker-free, scrollable terminal single-select menu with dynamic arrow navigation.
    Cross-platform support for Windows, Linux, and macOS.
    Controls: Up/Down arrows (or j/k) to navigate, Enter to submit, 1-9 for fast jump.
    """
    if not choices:
        return 0
    if not sys.stdin.isatty():
        print(f"\n\033[1;36m? {prompt}\033[0m")
        for i, choice in enumerate(choices):
            prefix = "➔" if i == default_idx else " "
            print(f"  {prefix} \033[1;33m[{i+1}]\033[0m {choice}")
        try:
            val = input(f"\nSelect option [1-{len(choices)}] (default {default_idx+1}): ").strip()
            if not val:
                return default_idx
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return idx
        except Exception:
            return default_idx
        return default_idx

    cursor = default_idx if 0 <= default_idx < len(choices) else 0
    num_opts = len(choices)
    window_size = min(8, num_opts)
    total_render_lines = window_size + 2  # hint line + items + scroll status line

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    def render(first_render=False):
        if not first_render:
            sys.stdout.write(f"\033[{total_render_lines}A")

        if cursor < window_size // 2:
            start_idx = 0
        elif cursor >= num_opts - window_size // 2:
            start_idx = max(0, num_opts - window_size)
        else:
            start_idx = cursor - window_size // 2
        end_idx = min(start_idx + window_size, num_opts)

        # Header hint line (bright visible silver)
        sys.stdout.write(f"\r\033[K\033[38;5;248m  (↑/↓: Gezin, Enter: Seç, 1-{min(9, num_opts)}: Hızlı Tuş)\033[0m\n")

        for idx in range(start_idx, end_idx):
            is_active = (idx == cursor)
            ptr = "\033[1;36m❯\033[0m " if is_active else "  "
            radio = "\033[1;36m(●)\033[0m" if is_active else "\033[38;5;245m(○)\033[0m"
            text_color = "\033[1;37m" if is_active else "\033[37m"
            text = choices[idx]
            sys.stdout.write(f"\r\033[K{ptr}{radio} {text_color}{text}\033[0m\n")

        # Scroll indicator line
        more_up = "▲ " if start_idx > 0 else "  "
        more_down = "▼ " if end_idx < num_opts else "  "
        if num_opts > window_size:
            sys.stdout.write(f"\r\033[K\033[38;5;248m  {more_up}{start_idx + 1}-{end_idx} / {num_opts} seçenek {more_down}\033[0m\n")
        else:
            sys.stdout.write(f"\r\033[K\n")
        sys.stdout.flush()

    print(f"\n\033[1;36m? {prompt}\033[0m")
    render(first_render=True)

    if os.name == 'nt':
        os.system('')  # Enable ANSI in Windows terminal
        fd = None
        old_settings = None
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)

    try:
        while True:
            key = _read_key_cross_platform()
            if key in ('UP', 'k', 'K'):
                cursor = (cursor - 1) % num_opts
                render()
            elif key in ('DOWN', 'j', 'J'):
                cursor = (cursor + 1) % num_opts
                render()
            elif key in ('ENTER', 'SPACE'):
                break
            elif key in ('ESC', 'QUIT', 'F10'):
                # Return default or current on ESC
                break
            elif isinstance(key, str) and key.isdigit():
                digit_val = int(key) - 1
                if 0 <= digit_val < num_opts:
                    cursor = digit_val
                    render()
    finally:
        if old_settings is not None and fd is not None:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Restore cursor
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()

    return cursor


def prompt_text(prompt: str, default: str = "") -> str:
    default_str = f" [{default}]" if default else ""
    C_CYAN = "\001\033[1;36m\002"
    C_RESET = "\001\033[0m\002"
    try:
        val = input(f"{C_CYAN}? {prompt}:{C_RESET}{default_str} ").strip()
        return val if val else default
    except EOFError:
        return default
    except KeyboardInterrupt:
        raise KeyboardInterrupt


def prompt_station(prompt: str) -> str:
    C_CYAN = "\001\033[1;36m\002"
    C_RESET = "\001\033[0m\002"
    if readline is not None:
        try:
            completer = StationTabCompleter(TCDD_STATIONS)
            readline.set_completer(completer.complete)
            readline.set_completer_delims("")
            readline.parse_and_bind("set completion-ignore-case on")
            readline.parse_and_bind("set show-all-if-ambiguous on")
            readline.parse_and_bind("tab: complete")
        except Exception:
            pass
    while True:
        try:
            val = input(f"{C_CYAN}? {prompt}:{C_RESET} ").strip()
            if val:
                return val
        except EOFError:
            return ""
        except KeyboardInterrupt:
            raise KeyboardInterrupt


def prompt_multi_checkbox(title: str, options: List[str], initial_selected: Optional[List[bool]] = None) -> List[int]:
    """
    Renders a flicker-free, scrollable terminal multi-select menu with checkbox toggles.
    Cross-platform support for Windows, Linux, and macOS.
    Controls: Up/Down arrows (or j/k) to navigate, Space to toggle, 'a' for all/none, Enter to submit.
    """
    if not sys.stdin.isatty() or len(options) == 0:
        return list(range(len(options)))

    selected = list(initial_selected) if initial_selected else [True] * len(options)
    cursor = 0
    num_opts = len(options)

    # Window size: show up to 8 items at a time to strictly prevent terminal scrolling/duplication
    window_size = min(8, num_opts)
    total_render_lines = window_size + 2  # hint line + items + scroll status line

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    def render(first_render=False):
        if not first_render:
            sys.stdout.write(f"\033[{total_render_lines}A")

        # Determine visible window based on cursor position
        if cursor < window_size // 2:
            start_idx = 0
        elif cursor >= num_opts - window_size // 2:
            start_idx = max(0, num_opts - window_size)
        else:
            start_idx = cursor - window_size // 2
        end_idx = min(start_idx + window_size, num_opts)

        # Header status line (visible silver)
        selected_count = sum(selected)
        sys.stdout.write(f"\r\033[K\033[38;5;248m  (↑/↓: navigate, Space: toggle, 'a': all, Enter: confirm | {selected_count}/{num_opts} selected)\033[0m\n")

        for idx in range(start_idx, end_idx):
            is_active = (idx == cursor)
            is_checked = selected[idx]

            ptr = "\033[1;36m❯\033[0m " if is_active else "  "
            chk = "\033[1;32m[✔]\033[0m" if is_checked else "\033[38;5;245m[ ]\033[0m"
            text = options[idx]

            sys.stdout.write(f"\r\033[K{ptr}{chk} {text}\n")

        # Scroll indicator line (visible silver)
        more_up = "▲ " if start_idx > 0 else "  "
        more_down = "▼ " if end_idx < num_opts else "  "
        sys.stdout.write(f"\r\033[K\033[38;5;248m  {more_up}Showing {start_idx + 1}-{end_idx} of {num_opts} trains {more_down}\033[0m\n")
        sys.stdout.flush()

    print(f"\n\033[1;36m{title}\033[0m")
    render(first_render=True)

    if os.name == 'nt':
        os.system('')  # Enable ANSI in Windows terminal
        fd = None
        old_settings = None
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)

    try:
        while True:
            key = _read_key_cross_platform()
            if key == 'UP':
                cursor = (cursor - 1) % num_opts
                render()
            elif key == 'DOWN':
                cursor = (cursor + 1) % num_opts
                render()
            elif key == 'SPACE':
                selected[cursor] = not selected[cursor]
                render()
            elif key == 'ALL':
                all_checked = all(selected)
                selected = [not all_checked] * num_opts
                render()
            elif key == 'ENTER':
                break
    finally:
        if old_settings is not None and fd is not None:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        # Restore cursor
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()

    return [i for i, s in enumerate(selected) if s]


def prompt_calendar_date(title: str = "Select Travel Date", default_date: Optional[date] = None) -> str:
    """
    Renders an interactive terminal visual calendar picker with arrow key navigation.
    Controls:
      ← / → : previous / next day
      ↑ / ↓ : previous / next week (+- 7 days)
      [ / ] or < / > : previous / next month
      Enter : confirm selected date
      t / T : jump to tomorrow
    """
    today = datetime.now().date()
    max_date = today + timedelta(days=120)

    if default_date:
        curr_date = default_date if isinstance(default_date, date) else default_date.date()
    else:
        curr_date = today + timedelta(days=1)

    if not sys.stdin.isatty():
        return curr_date.strftime("%d-%m-%Y")

    TURKISH_MONTHS = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    TURKISH_DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

    def _add_month(d: date, delta: int) -> date:
        year = d.year
        month = d.month + delta
        while month > 12:
            month -= 12
            year += 1
        while month < 1:
            month += 12
            year -= 1
        max_days = calendar.monthrange(year, month)[1]
        day = min(d.day, max_days)
        new_d = date(year, month, day)
        if new_d < today:
            return today
        if new_d > max_date:
            return max_date
        return new_d

    # Total fixed lines rendered: 10
    total_render_lines = 10

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    def render(first_render=False):
        if not first_render:
            sys.stdout.write(f"\033[{total_render_lines}A")

        weeks = calendar.monthcalendar(curr_date.year, curr_date.month)
        while len(weeks) < 6:
            weeks.append([0] * 7)

        lines = []
        lines.append("\033[38;5;248m  (←/→: Gün, ↑/↓: Hafta, [/]: Ay, Enter: Onayla)\033[0m")
        m_str = f"{TURKISH_MONTHS[curr_date.month]} {curr_date.year}"
        lines.append(f"        \033[1;36m◀   {m_str:^14}   ▶\033[0m")
        lines.append("  \033[1;34m Pzt   Sal   Çar   Per   Cum   Cmt   Paz\033[0m")

        for w in weeks:
            w_strs = []
            for day_num in w:
                if day_num == 0:
                    w_strs.append("    ")
                else:
                    d = date(curr_date.year, curr_date.month, day_num)
                    if d == curr_date:
                        w_strs.append(f"\033[1;30;46m {day_num:02d} \033[0m")
                    elif d < today:
                        w_strs.append(f"\033[38;5;243m {day_num:02d} \033[0m")
                    elif d == today:
                        w_strs.append(f"\033[1;33m {day_num:02d} \033[0m")
                    else:
                        w_strs.append(f"\033[1;37m {day_num:02d} \033[0m")
            lines.append("  " + "  ".join(w_strs))

        day_name = TURKISH_DAY_NAMES[curr_date.weekday()]
        diff = (curr_date - today).days
        diff_str = "Bugün" if diff == 0 else ("Yarın" if diff == 1 else f"{diff} gün sonra")
        formatted_d = curr_date.strftime("%d-%m-%Y")
        lines.append(f"  ❯ \033[1;32mSeçilen Tarih:\033[0m \033[1;37m{formatted_d}\033[0m \033[38;5;248m({day_name} - {diff_str})\033[0m")

        output = "\n".join(["\r\033[K" + line for line in lines]) + "\n"
        sys.stdout.write(output)
        sys.stdout.flush()

    print(f"\n\033[1;36m📅 {title}:\033[0m")
    render(first_render=True)

    if os.name == 'nt':
        os.system('')
        fd = None
        old_settings = None
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)

    try:
        while True:
            key = _read_key_cross_platform()
            if key == 'LEFT':
                new_d = curr_date - timedelta(days=1)
                if new_d >= today:
                    curr_date = new_d
                    render()
            elif key == 'RIGHT':
                new_d = curr_date + timedelta(days=1)
                if new_d <= max_date:
                    curr_date = new_d
                    render()
            elif key == 'UP':
                new_d = curr_date - timedelta(days=7)
                if new_d >= today:
                    curr_date = new_d
                    render()
            elif key == 'DOWN':
                new_d = curr_date + timedelta(days=7)
                if new_d <= max_date:
                    curr_date = new_d
                    render()
            elif key in ('[', '<', 'p', 'P'):
                curr_date = _add_month(curr_date, -1)
                render()
            elif key in (']', '>', 'n', 'N'):
                curr_date = _add_month(curr_date, 1)
                render()
            elif key in ('t', 'T'):
                curr_date = today + timedelta(days=1)
                render()
            elif key == 'ENTER':
                break
    finally:
        if old_settings is not None and fd is not None:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    formatted_result = curr_date.strftime("%d-%m-%Y")
    day_name = TURKISH_DAY_NAMES[curr_date.weekday()]
    print(f"\r\033[K✔ Selected Travel Date: \033[1;32m{formatted_result}\033[0m \033[38;5;248m({day_name})\033[0m")
    return formatted_result


def print_wizard_header():
    print("\n" + "=" * 55)
    print("       🚀 \033[1;32mNOTIFYSEAT - NEW TCDD TRAIN TRACKER\033[0m")
    print("=" * 55)


def interactive_create_task() -> Optional[TrackingTask]:
    """Guides the user through an interactive setup wizard to configure a route tracker."""
    print_wizard_header()

    print("\n\033[1;36m📌 Major Stations & YHT Corridors:\033[0m")
    print("  • \033[1;37mİstanbul\033[0m (Söğütlüçeşme, Halkalı, Pendik, Bostancı, Bakırköy)")
    print("  • \033[1;37mAnkara\033[0m (Ankara Gar, Eryaman YHT, Polatlı YHT)")
    print("  • \033[1;37mEskişehir, Konya, Karaman, Sivas, Yozgat, Kırıkkale\033[0m")
    print("  • \033[1;37mKocaeli / Sakarya / Bilecik\033[0m (İzmit YHT, Gebze, Arifiye, Bilecik YHT, Bozüyük YHT)")
    print("  • \033[1;37mİzmir (Basmane), Kütahya\033[0m\n")

    provider = registry.get(TransportType.TCDD)

    raw_origin = prompt_station("Enter Departure Station")
    raw_dest = prompt_station("Enter Arrival Station")

    # Intelligent fuzzy matching (e.g. 'ankaragar' -> 'Ankara Gar', 'sogutlucesme' -> 'İstanbul(Söğütlüçeşme)', 'basmane' -> 'İzmir (Basmane)')
    res_orig = provider.get_station_by_name(raw_origin)
    res_dest = provider.get_station_by_name(raw_dest)
    origin = res_orig["name"] if res_orig else raw_origin
    destination = res_dest["name"] if res_dest else raw_dest

    print(f"\n✔ Selected Route: \033[1;32m{origin} ➔ {destination}\033[0m")

    # Interactive Visual Calendar Date Picker
    date_str = prompt_calendar_date("Select Travel Date")

    # Live Train Fetching & Interactive Checkbox Selection
    print(f"\n🔍 Querying scheduled train services for {date_str} from TCDD...")
    scheduled_trains = provider.get_scheduled_trains(origin, destination, date_str)

    time_filter = None
    if scheduled_trains:
        option_labels = []
        for train in scheduled_trains:
            dep = train.departure_time or "??"
            arr = train.arrival_time or ""
            route_times = f"{dep} ➔ {arr}" if arr else dep
            train_num = train.service_id or train.service_name.split()[0]
            train_label = f"YHT {train_num}" if "yht" not in train_num.lower() and train_num.isdigit() else train_num

            if train.total_available_seats > 0:
                short_classes = []
                for cls_k, cnt in train.class_breakdown.items():
                    if cnt > 0:
                        abbr = "Bus" if "business" in cls_k.lower() else "Eko"
                        short_classes.append(f"{cnt} {abbr}")
                bd_summary = f"({', '.join(short_classes)})" if short_classes else ""
                seat_str = f"\033[1;32m🟢 {train.total_available_seats} Seats {bd_summary}\033[0m"
            else:
                seat_str = "\033[1;31m🔴 Sold Out\033[0m"

            price_str = f" - {train.price:.0f} {train.currency}" if train.price else ""
            option_labels.append(f"\033[1m{route_times:<14}\033[0m | {train_label:<10} | {seat_str}{price_str}")

        title = f"🚆 Select Trains to Track on {date_str} ({origin} ➔ {destination}):"
        chosen_indices = prompt_multi_checkbox(title, option_labels)

        if not chosen_indices or len(chosen_indices) == len(scheduled_trains):
            time_filter = None
            selected_summary = "All Scheduled Trains"
            initial_seats = sum(t.total_available_seats for t in scheduled_trains)
        else:
            chosen_trains = [scheduled_trains[i] for i in chosen_indices]
            time_filter = ", ".join([t.departure_time for t in chosen_trains if t.departure_time])
            selected_summary = f"{len(chosen_trains)} Train(s) ({time_filter})"
            initial_seats = sum(t.total_available_seats for t in chosen_trains)
    else:
        initial_seats = 0
        print("\n\033[1;33m⚠️ Could not retrieve live timetable. Fallback to manual window:\033[0m")
        time_choices = [
            "Any Time (Check all journeys of the day)",
            "Morning (05:00 - 12:00)",
            "Afternoon (12:00 - 18:00)",
            "Evening (18:00 - 24:00)",
            "Specific Time (e.g. 08:30)"
        ]
        tm_idx = prompt_choice("Preferred Departure Time Window:", time_choices, default_idx=0)
        if tm_idx == 1:
            time_filter = "morning"
        elif tm_idx == 2:
            time_filter = "afternoon"
        elif tm_idx == 3:
            time_filter = "evening"
        elif tm_idx == 4:
            time_filter = prompt_text("Enter specific departure hour (HH:MM)", default="08:30")
        selected_summary = time_filter.title() if time_filter else "All Day"

    # Dynamic Notification Channel Selection
    cfg = ConfigManager().get()
    wa_info = f" ({cfg.whatsapp.phone_number})" if cfg.whatsapp.enabled and cfg.whatsapp.phone_number else ""
    em_info = f" ({cfg.email.recipient_email})" if cfg.email.enabled and cfg.email.recipient_email else ""

    ch_options = [
        "🔊 Masaüstü Bildirimi & Sesli Alarm (Varsayılan)",
        f"📱 WhatsApp Bildirimleri (CallMeBot){wa_info}",
        f"📧 E-posta Bildirimleri (SMTP){em_info}"
    ]
    initial_ch = [True, bool(cfg.whatsapp.enabled and cfg.whatsapp.phone_number), bool(cfg.email.enabled and cfg.email.recipient_email)]
    ch_indices = prompt_multi_checkbox(
        "🔔 Bildirim Almak İstediğiniz Kanalları Seçin:",
        ch_options,
        initial_selected=initial_ch
    )

    chosen_channels = []
    if 0 in ch_indices:
        chosen_channels.append("desktop")
    if 1 in ch_indices:
        chosen_channels.append("whatsapp")
        if not (cfg.whatsapp.enabled and cfg.whatsapp.phone_number):
            print("\033[1;33m⚠️ Not: WhatsApp seçildi ancak henüz ayarlanmadı. 'notifyseat config' ile bağlayabilirsiniz.\033[0m")
    if 2 in ch_indices:
        chosen_channels.append("email")
        if not (cfg.email.enabled and cfg.email.recipient_email):
            print("\033[1;33m⚠️ Not: E-posta seçildi ancak henüz ayarlanmadı. 'notifyseat config' ile bağlayabilirsiniz.\033[0m")

    if not chosen_channels:
        chosen_channels = ["desktop"]

    task = TrackingTask(
        transport_type=TransportType.TCDD,
        origin=origin,
        destination=destination,
        date=date_str,
        time_filter=time_filter,
        check_interval_seconds=90,
        notification_channels=chosen_channels,
        status=TaskStatus.ACTIVE,
        last_found_seats=initial_seats,
        last_checked_at=datetime.now().isoformat()
    )

    print("\n\033[1;32m✔ Route tracker configured successfully!\033[0m")
    print(f"  • Route: {task.origin} ➔ {task.destination}")
    print(f"  • Date: {task.display_date}")
    print(f"  • Window / Trains: {selected_summary}")
    print(f"  • Channels: {', '.join(chosen_channels).upper()}")
    print(f"  • Radar: Checks every ~1.5 minutes with anti-ban protection\n")
    return task


def open_url_quietly(url: str):
    """Opens a URL in default browser without letting subprocess stderr leak into the terminal."""
    import subprocess
    import shutil
    import sys
    try:
        if sys.platform.startswith("linux") and shutil.which("xdg-open"):
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        else:
            import webbrowser
            webbrowser.open(url)
    except Exception:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


def interactive_config(config_mgr):
    """Interactive wizard to configure Email and WhatsApp notifications with auto-browser opening."""
    from notifyseat.notifiers.whatsapp import normalize_phone_number
    cfg = config_mgr.get()

    print("\n\033[1;36m==================================================\033[0m")
    print("\033[1;36m        🔔 NotifySeat Notification Setup          \033[0m")
    print("\033[1;36m==================================================\033[0m")
    print("Receive instant seat cancellation alerts on your phone or inbox.\n")

    wa_status = f"🟢 ENABLED ({cfg.whatsapp.phone_number})" if cfg.whatsapp.enabled and cfg.whatsapp.phone_number else "⚪ DISABLED"
    em_status = f"🟢 ENABLED ({cfg.email.recipient_email})" if cfg.email.enabled and cfg.email.recipient_email else "⚪ DISABLED"

    options = [
        f"📱 Configure WhatsApp (Direct WhatsApp alerts to your phone) [{wa_status}]",
        f"📧 Configure Email (Gmail / Outlook / Custom SMTP) [{em_status}]",
        "⚡ Test All Configured Notification Channels",
        "🚪 Exit Setup"
    ]

    choice = prompt_choice("Select an option:", options, default_idx=0)

    if choice == 0:
        # WhatsApp Setup
        print("\n\033[1;32m--- 📱 WhatsApp Direct Alert Setup (CallMeBot) ---\033[0m\n")
        print("To allow NotifySeat to send WhatsApp alerts to your phone, CallMeBot needs 1 verification message:")
        print("  • Message to send: \033[1;33mI allow callmebot to send me messages\033[0m")
        print("  • Bot Phone Number: \033[1;36m+34 623 78 95 80\033[0m\n")

        wa_choices = [
            "🌐 Open WhatsApp Web / Desktop app automatically on this computer",
            "📲 I will send the message manually from my mobile phone WhatsApp"
        ]
        w_mode = prompt_choice("How would you like to authorize WhatsApp?", wa_choices, default_idx=0)

        if w_mode == 0:
            open_url_quietly("https://wa.me/34623789580?text=I+allow+callmebot+to+send+me+messages")
            print("\n🌐 Opened WhatsApp link with pre-filled message.")
        else:
            print("\n📲 Please open WhatsApp on your phone:")
            print("  1. Message \033[1;36m+34 623 78 95 80\033[0m")
            print("  2. Send: \033[1;33mI allow callmebot to send me messages\033[0m")
            print("  3. CallMeBot will reply with your API Key (e.g. 123456).\n")

        phone_raw = prompt_text("Enter your WhatsApp Phone Number (e.g. 05051234567 or +905051234567):", default=cfg.whatsapp.phone_number or "")
        phone = normalize_phone_number(phone_raw)
        apikey = prompt_text("Enter the API Key sent to you by CallMeBot (e.g. 1234567):", default=cfg.whatsapp.apikey)

        if phone and apikey:
            cfg.whatsapp.phone_number = phone
            cfg.whatsapp.apikey = apikey.strip()
            cfg.whatsapp.enabled = True
            config_mgr.save(cfg)
            print(f"\n\033[1;32m✔ WhatsApp configuration saved for {phone}!\033[0m")

            test_now = prompt_text("Send an instant test WhatsApp alert to your phone? (Y/n):", default="y").lower().startswith("y")
            if test_now:
                from notifyseat.notifiers.whatsapp import WhatsAppNotifier
                wn = WhatsAppNotifier(cfg.whatsapp)
                print("⏳ Sending test WhatsApp alert...")
                if wn.test():
                    print(f"\033[1;32m✔ Test WhatsApp message SENT successfully to {phone}!\033[0m\n")
                else:
                    print("\033[1;31m✖ WhatsApp delivery failed. Please verify your phone number and API key.\033[0m\n")

    elif choice == 1:
        # Email Setup
        print("\n\033[1;32m--- 📧 Email (SMTP) Alert Setup ---\033[0m")
        providers = ["Gmail (smtp.gmail.com)", "Outlook / Hotmail (smtp.office365.com)", "Custom SMTP Server"]
        p_idx = prompt_choice("Choose Email Provider:", providers, default_idx=0)

        if p_idx == 0:
            # Gmail
            print("\n👉 For Gmail, Google requires a 16-character 'App Password'.")
            print("We will open your Google Account App Passwords page in your browser.")
            open_g = prompt_text("Open Google App Passwords page now? (Y/n):", default="y").lower().startswith("y")
            if open_g:
                open_url_quietly("https://myaccount.google.com/apppasswords")
                print("🌐 Opened Google App Passwords in your browser.")

            email_addr = prompt_text("Enter your Gmail address (e.g. user@gmail.com):", default=cfg.email.username or "")
            app_pass = prompt_text("Enter your 16-character Google App Password:", default=cfg.email.password or "")
            recipient = prompt_text("Enter recipient email (where alerts will arrive):", default=email_addr)

            if email_addr and app_pass:
                cfg.email.smtp_host = "smtp.gmail.com"
                cfg.email.smtp_port = 587
                cfg.email.use_tls = True
                cfg.email.username = email_addr.strip()
                cfg.email.password = app_pass.strip().replace(" ", "")
                cfg.email.sender_email = email_addr.strip()
                cfg.email.recipient_email = recipient.strip()
                cfg.email.enabled = True
                config_mgr.save(cfg)
                print("\n\033[1;32m✔ Gmail configuration saved!\033[0m")

                test_e = prompt_text("Send an instant test email right now? (Y/n):", default="y").lower().startswith("y")
                if test_e:
                    from notifyseat.notifiers.email import EmailNotifier
                    en = EmailNotifier(cfg.email)
                    print("⏳ Sending test email...")
                    if en.test():
                        print(f"\033[1;32m✔ Test email SENT successfully to {recipient}!\033[0m\n")
                    else:
                        print("\033[1;31m✖ Email delivery failed. Please check your address and App Password.\033[0m\n")

        elif p_idx == 1:
            # Outlook
            email_addr = prompt_text("Enter your Outlook / Hotmail address:", default=cfg.email.username or "")
            pass_val = prompt_text("Enter your Outlook password / app password:", default=cfg.email.password or "")
            recipient = prompt_text("Enter recipient email:", default=email_addr)

            if email_addr and pass_val:
                cfg.email.smtp_host = "smtp.office365.com"
                cfg.email.smtp_port = 587
                cfg.email.use_tls = True
                cfg.email.username = email_addr.strip()
                cfg.email.password = pass_val.strip()
                cfg.email.sender_email = email_addr.strip()
                cfg.email.recipient_email = recipient.strip()
                cfg.email.enabled = True
                config_mgr.save(cfg)
                print("\n\033[1;32m✔ Outlook configuration saved!\033[0m")

        elif p_idx == 2:
            # Custom SMTP
            host = prompt_text("SMTP Host (e.g. mail.domain.com):", default=cfg.email.smtp_host)
            port = int(prompt_text("SMTP Port (e.g. 587 or 465):", default=str(cfg.email.smtp_port)))
            user = prompt_text("Username / Email:", default=cfg.email.username)
            password = prompt_text("Password:", default=cfg.email.password)
            recip = prompt_text("Recipient Email:", default=cfg.email.recipient_email or user)

            cfg.email.smtp_host = host
            cfg.email.smtp_port = port
            cfg.email.username = user
            cfg.email.password = password
            cfg.email.sender_email = user
            cfg.email.recipient_email = recip
            cfg.email.enabled = True
            config_mgr.save(cfg)
            print("\n\033[1;32m✔ Custom SMTP configuration saved!\033[0m")

    elif choice == 2:
        from notifyseat.notifiers.manager import NotificationManager
        mgr = NotificationManager(cfg)
        print("\n⏳ Testing all active notification channels...")
        res = mgr.test_all()
        for ch, ok in res.items():
            if ok:
                print(f"  \033[1;32m✔ [{ch.upper()}] Notification SUCCESSFUL!\033[0m")
            else:
                print(f"  \033[1;31m✖ [{ch.upper()}] Notification FAILED.\033[0m")
        print()


def interactive_task_manager(db, config_mgr=None):
    """
    Renders an interactive, dynamic task management dashboard with keyboard shortcuts.
    Shortcuts:
      F2 / Space / p : Durdur / Başlat (Toggle Pause / Active)
      F3 / c         : Şimdi Kontrol Et (Live check selected task)
      F4 / d         : Görevi Sil (Delete selected task)
      F5 / r         : Radarı Başlat (Start background monitoring engine)
      F10 / q / Esc  : Çıkış / Exit
      Enter          : İşlem menüsünü aç veya seçimi onayla
      ↑ / ↓ (or k/j) : Rotalar arasında gezin
    """
    tasks = db.list_tasks()
    if not tasks:
        print("\n\033[1;33m⚠️ Henüz kayıtlı rota bulunamadı.\033[0m")
        print("Yeni bir rota eklemek için: \033[1;32mnotifyseat track -i\033[0m\n")
        return

    cursor = 0
    message_banner = ""
    message_color = "\033[1;32m"

    if not sys.stdin.isatty():
        print("\n--- Kayıtlı Rotalar ---")
        for t in tasks:
            print(f"[{t.id}] {t.origin} ➔ {t.destination} ({t.display_date}) | {t.status} | Koltuk: {t.last_found_seats}")
        return

    window_size = 8
    last_render_lines = 0

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    if os.name == 'nt':
        os.system('')
        fd = None
        old_settings = None
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)

    try:
        first_render = True
        while True:
            total_items = len(tasks) + 1  # tasks + 1 exit option
            if cursor >= total_items:
                cursor = max(0, total_items - 1)

            num_tasks = len(tasks)
            vis_window = min(window_size, num_tasks)
            if cursor < num_tasks:
                if cursor < vis_window // 2:
                    start_idx = 0
                elif cursor >= num_tasks - vis_window // 2:
                    start_idx = max(0, num_tasks - vis_window)
                else:
                    start_idx = cursor - vis_window // 2
                end_idx = min(start_idx + vis_window, num_tasks)
            else:
                start_idx = max(0, num_tasks - vis_window)
                end_idx = num_tasks

            lines = []
            lines.append("╭─────────────────────────────────────────────────────────────────────────────╮")
            lines.append("│ 🚆 \033[1;36mNotifySeat - Rota Yönetim Paneli\033[0m                                         │")
            lines.append("╰─────────────────────────────────────────────────────────────────────────────╯")

            if message_banner:
                lines.append(f" {message_color}{message_banner}\033[0m")
            else:
                lines.append(f" \033[38;5;248mToplam {len(tasks)} adet takip edilen rota listeleniyor:\033[0m")

            lines.append("")

            # Render visible tasks
            for idx in range(start_idx, end_idx):
                t = tasks[idx]
                is_active = (idx == cursor)
                ptr = "\033[1;36m❯\033[0m " if is_active else "  "

                if t.status == TaskStatus.ACTIVE:
                    status_badge = "\033[1;32m🟢 AKTİF   \033[0m"
                elif t.status == TaskStatus.PAUSED:
                    status_badge = "\033[1;33m⏸ DURDURULDU\033[0m"
                elif t.status == TaskStatus.FOUND:
                    status_badge = "\033[1;32m✔ BULUNDU \033[0m"
                else:
                    status_badge = f"\033[1;31m{t.status:<10}\033[0m"

                if t.last_found_seats > 0:
                    seats_badge = f"\033[1;32m🟢 {t.last_found_seats:>2} Koltuk\033[0m"
                else:
                    seats_badge = "\033[1;31m🔴 Dolu    \033[0m"

                route_str = f"{t.origin} ➔ {t.destination}"
                if len(route_str) > 28:
                    route_str = route_str[:26] + ".."

                window_str = (t.time_filter or "Tüm Gün").title()
                if len(window_str) > 10:
                    window_str = window_str[:9] + "."

                row_style = "\033[1;37m" if is_active else "\033[37m"
                task_line = f"{ptr}{row_style}[{t.id}] {route_str:<28} │ {t.display_date} │ {window_str:<10} │ {status_badge} │ {seats_badge}\033[0m"
                lines.append(task_line)

            # Scroll indicator
            more_up = "▲ " if start_idx > 0 else "  "
            more_down = "▼ " if end_idx < num_tasks else "  "
            if num_tasks > vis_window:
                lines.append(f"  \033[38;5;248m{more_up}{start_idx + 1}-{end_idx} / {num_tasks} rota gösteriliyor {more_down}\033[0m")

            # Exit row
            is_exit_active = (cursor == num_tasks)
            exit_ptr = "\033[1;36m❯\033[0m " if is_exit_active else "  "
            exit_style = "\033[1;31m" if is_exit_active else "\033[38;5;248m"
            lines.append(f"{exit_ptr}{exit_style}[🚪 Çıkış / Exit]\033[0m")

            # Shortcut toolbar line
            lines.append("")
            lines.append("─────────────────────────────────────────────────────────────────────────────")
            lines.append(
                " \033[1;33m[F2/Space]\033[0m Durdur/Başlat  "
                "\033[1;33m[F3/c]\033[0m Şimdi Tara  "
                "\033[1;33m[F4/d]\033[0m Sil  "
                "\033[1;33m[F5/r]\033[0m Radar  "
                "\033[1;33m[F10/q/Esc]\033[0m Çıkış"
            )

            # In-place terminal render
            if not first_render:
                sys.stdout.write(f"\033[{last_render_lines}A")
            output = "\n".join(["\r\033[K" + l for l in lines]) + "\n"
            sys.stdout.write(output)
            sys.stdout.flush()
            last_render_lines = len(lines)
            first_render = False

            message_banner = ""

            key = _read_key_cross_platform()

            if key in ('UP', 'k', 'K'):
                cursor = (cursor - 1) % total_items
            elif key in ('DOWN', 'j', 'J'):
                cursor = (cursor + 1) % total_items
            elif key in ('F10', 'QUIT', 'ESC'):
                break
            elif key == 'ENTER':
                if cursor == num_tasks:
                    break
                else:
                    curr_task = tasks[cursor]
                    if old_settings is not None and fd is not None:
                        import termios
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    sys.stdout.write("\033[?25h\n")
                    sys.stdout.flush()

                    pause_label = "▶ Görevi Aktif Et (Resume)" if curr_task.status == TaskStatus.PAUSED else "⏸ Görevi Durdur (Pause)"
                    act_opts = [
                        "🔍 Şimdi Kontrol Et (Live Check)",
                        pause_label,
                        "🗑️ Bu Görevi Sil (Delete)",
                        "↩ Geri Dön"
                    ]
                    act_choice = prompt_choice(f"Görev [{curr_task.id}] {curr_task.origin} ➔ {curr_task.destination} için işlem:", act_opts)

                    if act_choice == 0:
                        from notifyseat.cli.app import cmd_check_now
                        from notifyseat.core.config import ConfigManager
                        cfg_mgr = config_mgr or ConfigManager()
                        cmd_check_now(db, cfg_mgr, task_id=curr_task.id)
                        input("\n\033[38;5;248mListeye dönmek için Enter'a basın...\033[0m")
                    elif act_choice == 1:
                        new_st = TaskStatus.ACTIVE if curr_task.status == TaskStatus.PAUSED else TaskStatus.PAUSED
                        db.update_task_status(curr_task.id, new_st)
                        curr_task.status = new_st
                        message_banner = f"✔ Görev [{curr_task.id}] durumu güncellendi: {new_st}"
                    elif act_choice == 2:
                        db.delete_task(curr_task.id)
                        tasks.pop(cursor)
                        if not tasks:
                            print("\n\033[1;32m✔ Görev silindi. Başka rota kalmadı.\033[0m\n")
                            break
                        cursor = min(cursor, len(tasks) - 1)
                        message_banner = f"✔ Görev [{curr_task.id}] silindi."

                    first_render = True
                    sys.stdout.write("\033[?25l")
                    sys.stdout.flush()
                    if old_settings is not None and fd is not None:
                        import termios, tty
                        tty.setraw(fd)

            elif key in ('F2', 'PAUSE', 'SPACE'):
                if cursor < num_tasks:
                    curr_task = tasks[cursor]
                    new_st = TaskStatus.ACTIVE if curr_task.status == TaskStatus.PAUSED else TaskStatus.PAUSED
                    db.update_task_status(curr_task.id, new_st)
                    curr_task.status = new_st
                    status_name = "Aktif edildi" if new_st == TaskStatus.ACTIVE else "Durduruldu"
                    message_banner = f"✔ [{curr_task.id}] {curr_task.origin} ➔ {curr_task.destination}: {status_name}"
                    message_color = "\033[1;32m" if new_st == TaskStatus.ACTIVE else "\033[1;33m"

            elif key in ('F4', 'DELETE'):
                if cursor < num_tasks:
                    curr_task = tasks[cursor]
                    db.delete_task(curr_task.id)
                    deleted_id = curr_task.id
                    tasks.pop(cursor)
                    if not tasks:
                        sys.stdout.write("\033[?25h\n")
                        print(f"\n\033[1;32m✔ Görev [{deleted_id}] silindi. Listeniz artık boş.\033[0m\n")
                        break
                    cursor = min(cursor, len(tasks) - 1)
                    message_banner = f"✔ Görev [{deleted_id}] başarıyla silindi."
                    message_color = "\033[1;32m"

            elif key in ('F3', 'CHECK'):
                if cursor < num_tasks:
                    curr_task = tasks[cursor]
                    if old_settings is not None and fd is not None:
                        import termios
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    sys.stdout.write("\033[?25h\n")
                    sys.stdout.flush()

                    from notifyseat.cli.app import cmd_check_now
                    from notifyseat.core.config import ConfigManager
                    cfg_mgr = config_mgr or ConfigManager()
                    cmd_check_now(db, cfg_mgr, task_id=curr_task.id)
                    input("\n\033[38;5;248mListeye dönmek için Enter'a basın...\033[0m")

                    first_render = True
                    sys.stdout.write("\033[?25l")
                    sys.stdout.flush()
                    if old_settings is not None and fd is not None:
                        import termios, tty
                        tty.setraw(fd)

            elif key in ('F5', 'RUN'):
                if old_settings is not None and fd is not None:
                    import termios
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                sys.stdout.write("\033[?25h\n")
                sys.stdout.flush()
                import argparse
                from notifyseat.cli.app import cmd_run
                from notifyseat.core.config import ConfigManager
                cfg_mgr = config_mgr or ConfigManager()
                dummy_args = argparse.Namespace()
                cmd_run(db, cfg_mgr, dummy_args)
                break

    finally:
        if old_settings is not None and fd is not None:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
