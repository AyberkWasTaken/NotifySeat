# 🚅 NotifySeat

> **Local-First Public Transport Seat & Cancellation Notifier**

NotifySeat is a **100% local, privacy-focused transport seat availability and cancellation radar**. It runs directly on your local computer (leaving your machine on to monitor) without requiring any cloud servers, backend hosting, or third-party subscription fees.

---

## 🌟 Key Features

- 🚆 **Multi-Transport Provider Engine**:
  - **TCDD Trains (YHT & Mainline)**: Direct integration with EYBİS / TCDD ticketing system with wagon breakdowns (Pulman, Business, Yataklı).
  - **Flights**: Monitors Pegasus Airlines, Turkish Airlines (THY), SunExpress, and AJet routes with seat tracking and direct booking links.
  - **Intercity Buses**: Tracks bus routes and passenger cancellation openings across Pamukkale, Kamil Koç, Metro, and Obilet.
  - **Live Demo & Simulation Mode**: Built-in test simulator to verify cancellation alerts instantly.
- 🔔 **Multi-Channel Instant Notifications**:
  - **Desktop / OS Native**: Instant system notifications + audible audio chimes.
  - **Telegram Bot**: Instant rich alerts with direct booking button.
  - **Discord Webhook**: Embedded cards with route info and seat counts.
  - **SMTP Email**: Formatted HTML & plain text alerts (Gmail, Outlook, custom SMTP).
  - **SMS**: Netgsm & Twilio API support.
  - **Custom Webhook**: JSON payloads to Home Assistant, Zapier, IFTTT, n8n.
- 💻 **Dual Interface**:
  - **Interactive CLI**: Rich terminal tables, interactive wizard, live log stream, background daemon.
  - **Modern Local Web GUI**: Embedded web dashboard with live stats, glassmorphic UI, in-browser Web Audio alerts, and settings manager.
- 🛡️ **Anti-Ban & Smart Jitter**: Randomized polling intervals and human-like request headers to prevent rate limits.

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/ayberk/NotifySeat.git
cd NotifySeat

# (Optional) Install rich for beautiful terminal formatting
pip install -r requirements.txt
```

### 2. Instant Live Demo

See seat cancellation detection and alert dispatch in action immediately:

```bash
python3 main.py demo
```

### 3. Launch Local Web GUI Dashboard

```bash
python3 main.py gui
```

Open **`http://127.0.0.1:8080`** in your browser to access the full graphical dashboard.

---

## 🖥️ CLI Commands Reference

| Command | Description |
|---|---|
| `python3 main.py track -i` | Launch interactive wizard to add a new route to monitor |
| `python3 main.py track --from "İstanbul(Söğütlüçeşme)" --to "Ankara Gar" --date 2026-09-15` | Add a route directly with flags |
| `python3 main.py list` | List all configured route tracking tasks |
| `python3 main.py run` / `start` | Start the background monitoring engine |
| `python3 main.py gui [--port 8080]` | Start the local web dashboard server |
| `python3 main.py test-notify <channel>` | Test alerts (`desktop`, `telegram`, `discord`, `email`, `sms`) |
| `python3 main.py pause <task_id>` | Pause monitoring for a specific task |
| `python3 main.py resume <task_id>` | Resume monitoring for a specific task |
| `python3 main.py delete <task_id>` | Delete a tracking task |
| `python3 main.py demo` | Run live simulation of a passenger cancelling a seat |

---

## ⚙️ Configuration & Notifications

Configuration is stored securely on your local disk at `~/.notifyseat/config.json` and SQLite database at `~/.notifyseat/notifyseat.db`.

### Telegram Bot Setup:
1. Talk to `@BotFather` on Telegram to create a bot and get your token.
2. Send a message to your bot and get your chat ID (via `@userinfobot`).
3. Configure via Web GUI Settings or `~/.notifyseat/config.json`:
   ```json
   "telegram": {
     "enabled": true,
     "bot_token": "YOUR_BOT_TOKEN",
     "chat_id": "YOUR_CHAT_ID"
   }
   ```
4. Test with: `python3 main.py test-notify telegram`

### Discord Webhook Setup:
1. In Discord, go to Server Settings ➔ Integrations ➔ Webhooks ➔ New Webhook.
2. Copy Webhook URL and paste into Web GUI Settings or `config.json`.
3. Test with: `python3 main.py test-notify discord`

---

## 🏗️ Architecture

```
notifyseat/
├── core/             # Data models, SQLite database, config manager, logger
├── notifiers/        # Desktop, Telegram, Discord, Email, SMS, Webhook
├── providers/        # TCDD Train, Flight (THY/Pegasus), Bus, Simulation
├── engine/           # Multi-threaded background scheduler & worker
├── cli/              # Rich interactive terminal application & wizard
├── web/              # Local FastAPI/HTTP Web Dashboard & REST API
│   ├── static/       # CSS styles & client JavaScript (Web Audio synthesis)
│   └── templates/    # HTML5 Single Page Application
├── tests/            # Full unit & integration test suite
└── main.py           # Universal entrypoint
```

---

## 🔒 Privacy & Local-First Philosophy

- **Zero Cloud**: Runs 100% locally on your computer.
- **Zero Subscriptions**: Free forever.
- **Zero Telemetry**: Your search routes, travel dates, and credentials never leave your machine.
