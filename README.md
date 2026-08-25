# 🚅 NotifySeat

> **Local-First Public Transport Seat & Cancellation Notifier**  
> *Instant cancellation radar for TCDD High-Speed Trains, Flights, and Intercity Buses.*

[![PyPI version](https://img.shields.io/pypi/v/notifyseat.svg)](https://pypi.org/project/notifyseat/)
[![Python Versions](https://img.shields.io/pypi/pyversions/notifyseat.svg)](https://pypi.org/project/notifyseat/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows | macOS | Linux](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://pypi.org/project/notifyseat/)
[![Local First](https://img.shields.io/badge/Privacy-100%25%20Local--First-brightgreen)]()

---

**NotifySeat** is a 100% local, privacy-focused seat availability and passenger cancellation radar. When tickets on popular routes are sold out, NotifySeat continuously monitors availability in the background and sends instant multi-channel alerts (Desktop, WhatsApp, Telegram, Discord, Email, SMS) the moment someone cancels their ticket and a seat becomes available.

---

## 🌟 Key Features

- 🚆 **Multi-Transport Support**:
  - **TCDD Trains (YHT & Mainline)**: Real-time EYBİS integration with wagon and class breakdown (Pulman, Business, Yataklı).
  - **Flights**: Monitors Pegasus Airlines, Turkish Airlines (THY), AJet, and SunExpress with direct booking links.
  - **Intercity Buses**: Tracks seat openings across Pamukkale, Kamil Koç, Metro, and Obilet.
  - **Simulation & Test Engine**: Built-in simulator to test and verify cancellation alerts instantly.
- 🔔 **Multi-Channel Instant Notifications**:
  - **Desktop / OS Native**: Windows Toast Notifications, macOS AppleScript alerts, Linux `notify-send`, and audible audio chimes.
  - **WhatsApp**: Instant messages sent directly to your phone.
  - **Telegram Bot**: Rich alerts with inline booking buttons.
  - **Discord Webhook**: Embedded rich cards with route details and seat counts.
  - **SMTP Email**: Formatted HTML & plain text alerts (Gmail, Outlook, custom SMTP).
  - **SMS**: Netgsm and Twilio API support.
  - **Custom Webhooks**: JSON payloads for Home Assistant, Zapier, IFTTT, n8n.
- 💻 **Dual Interface**:
  - **Modern Local Web GUI**: Glassmorphic dashboard with live Server-Sent Events (SSE) updates, audio synthesis alerts, and graphical task manager.
  - **Rich Interactive CLI**: Terminal wizard, colored status tables, and live scan logs.
- 🛡️ **Anti-Ban & Smart Jitter**: Randomized polling intervals and human-like request headers to avoid rate limits.
- 🔒 **100% Local-First & Private**: Runs entirely on your computer. Zero cloud server fees, zero telemetry, and your search routes/credentials never leave your machine.

---

## 🚀 Quick Start

### 1. Installation

Install globally via `pip`:

```bash
pip install --upgrade notifyseat
```

*Or install from source:*

```bash
git clone https://github.com/ayberk/NotifySeat.git
cd NotifySeat
pip install -e .
```

---

### 2. Launch the Local Web GUI Dashboard

NotifySeat includes a built-in local web dashboard:

```bash
notifyseat gui
```

Open **`http://127.0.0.1:8080`** in your browser to manage routes, configure notifications, and view real-time radar scans.

---

### 3. Interactive CLI Wizard

Create a tracking route in seconds using the interactive terminal wizard:

```bash
notifyseat track -i
```

Start the background monitoring engine:

```bash
notifyseat run
```

---

## 🖥️ CLI Commands Reference

| Command | Description |
|---|---|
| `notifyseat gui [--port 8080]` | Launch the local Web GUI dashboard |
| `notifyseat track -i` | Launch interactive wizard to add a new route to monitor |
| `notifyseat track --from "İstanbul" --to "Ankara" --date 2026-09-15` | Add a tracking task directly via arguments |
| `notifyseat list` | List all monitored routes and their current status |
| `notifyseat check [task_id]` | Trigger an immediate live scan for a specific route (or all) |
| `notifyseat run` / `notifyseat start` | Start the background monitoring engine |
| `notifyseat logs` / `notifyseat history` | View recent scan logs and seat findings |
| `notifyseat config` | Interactive setup wizard for WhatsApp and Email notifications |
| `notifyseat test-notify [channel]` | Test alerts (`desktop`, `whatsapp`, `telegram`, `discord`, `email`, `sms`) |
| `notifyseat pause <task_id>` | Pause monitoring for a route |
| `notifyseat resume <task_id>` | Resume monitoring for a route |
| `notifyseat delete <task_id>` | Delete a tracking route |

---

## ⚙️ Notification Channels Setup

Configuration is stored securely on your local disk at `~/.notifyseat/config.json` (and SQLite database at `~/.notifyseat/notifyseat.db`). You can configure them via the **Web GUI Settings** or CLI:

### 📱 WhatsApp Setup:
1. Run `notifyseat config` or open **Web GUI Settings**.
2. Follow the 1-click prompt to activate the free CallMeBot WhatsApp gateway.
3. Enter your phone number and API key.

### ✈️ Telegram Bot Setup:
1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram and get your Bot Token.
2. Obtain your Chat ID using [@userinfobot](https://t.me/userinfobot).
3. Set your token and chat ID in the Web GUI or `~/.notifyseat/config.json`:
   ```json
   "telegram": {
     "enabled": true,
     "bot_token": "YOUR_BOT_TOKEN",
     "chat_id": "YOUR_CHAT_ID"
   }
   ```
4. Test with: `notifyseat test-notify telegram`

### 🎮 Discord Webhook Setup:
1. In Discord: **Server Settings** ➔ **Integrations** ➔ **Webhooks** ➔ **New Webhook**.
2. Copy the Webhook URL and save it via the Web GUI or `config.json`.
3. Test with: `notifyseat test-notify discord`

### 📧 Email Setup (Gmail / SMTP):
1. For Gmail: Generate an [App Password](https://myaccount.google.com/apppasswords).
2. Configure SMTP host (`smtp.gmail.com`), port (`587`), email address, and App Password in Web GUI.
3. Test with: `notifyseat test-notify email`

---

## 🏗️ Architecture

```text
notifyseat/
├── core/             # Data models, SQLite database layer, configuration manager, logger
├── notifiers/        # Desktop, WhatsApp, Telegram, Discord, Email, SMS, Webhook
├── providers/        # TCDD Train (EYBİS), Flight (THY/Pegasus/AJet), Bus, Simulator
├── engine/           # Multi-threaded background scheduler, backoff logic, and worker
├── cli/              # Rich interactive terminal application and command parser
├── web/              # Local HTTP Web Dashboard & REST API
│   ├── static/       # CSS stylesheets & client JavaScript (Live SSE, Web Audio)
│   └── templates/    # HTML5 Single Page Dashboard
└── tests/            # Automated test suite
```

---

## 🔒 Privacy & Local-First Philosophy

- **Zero Cloud Infrastructure**: Runs 100% locally on your computer.
- **No Recurring Fees**: Free and open source forever.
- **Zero Telemetry / Data Collection**: Your search queries, passenger information, and notification credentials never leave your personal machine.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.
