# 🔔 Church Bell System

A simple web-based speaker control system for a church. Upload music, create playlists, schedule playback, and control a Bluetooth speaker — all from any phone, tablet, or computer on the local network.

## Features

- **Music Library** — Upload `.mp3` and `.flac` files, organize into playlists
- **Playback Controls** — Play, pause, skip, stop with a large, easy-to-use interface
- **Scheduling** — Set recurring (e.g. every Sunday), one-time, or automation schedules
- **Bluetooth Speaker** — Connect to a single BT speaker and route all audio to it
- **Volume Control** — Global system volume via PipeWire/`wpctl` + per-track volume
- **Mobile Friendly** — Responsive dark UI designed for non-technical users
- **Auto-start** — Runs as a systemd service, survives reboots

## Requirements

- **OS:** Debian 13 (Trixie) with GNOME
- **Python:** 3.13+
- **Audio:** PipeWire + WirePlumber (Debian 13 default)
- **Bluetooth:** BlueZ

## Quick Start

### 1. Install system packages

```bash
sudo apt install vlc bluetooth bluez pipewire-audio wireplumber python3-pip python3-venv
```

### 2. Clone and set up

```bash
cd /home/$USER
git clone <repo-url> church-music-app
cd church-music-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run

```bash
python3 run.py
```

Open **http://localhost:5000** in your browser.

### 4. (Optional) Install as a systemd service

```bash
sudo cp systemd/church-bells@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now church-bells@$USER
```

The app will auto-start on boot and restart on crash.

## Usage

| Page | What it does |
|------|-------------|
| **Dashboard** | Shows current playback, speaker status, quick play, upcoming schedules |
| **Music Library** | Upload songs, create/edit playlists |
| **Schedules** | Create recurring, one-time, or date-range automation schedules |
| **Speakers** | Connect/disconnect your Bluetooth speaker |
| **Settings** | View system info, set default volume, emergency stop |

### Connecting a Bluetooth Speaker

1. Turn on your speaker and put it in pairing mode
2. Go to the **Speakers** page
3. Click **Scan for Speakers**
4. Click **Connect** next to your speaker
5. The speaker becomes the default audio output automatically

### Creating a Schedule

1. Go to the **Schedules** page
2. Click **New Schedule**
3. Choose a type:
   - **Recurring** — plays weekly (e.g., every Sunday at 10:30 AM)
   - **One-time** — plays once at a specific date/time
   - **Automation** — plays daily within a date range
4. Select a playlist and set the duration
5. Save — it will run automatically

## API Endpoints

All endpoints are under `/api/`. See [PLAN.md](PLAN.md) for the full API reference.

Key endpoints:
- `GET /api/status` — current playback status
- `POST /api/play` — start playback
- `POST /api/stop` — stop playback
- `GET /api/speaker` — speaker connection status
- `GET /api/schedules` — list all schedules

## Project Structure

```
church-music-app/
├── run.py                  # Entry point
├── app/
│   ├── __init__.py         # Flask app factory
│   ├── config.py           # Configuration
│   ├── database.py         # SQLite helpers
│   ├── routes/
│   │   ├── api.py          # REST API
│   │   └── views.py        # Page routes
│   ├── services/
│   │   ├── audio_player.py # VLC playback engine
│   │   ├── scheduler.py    # APScheduler integration
│   │   ├── bluetooth.py    # Bluetooth + wpctl sink
│   │   └── volume.py       # Volume (wpctl-only)
│   ├── static/             # CSS + JS
│   └── templates/          # HTML pages
├── music/                  # Uploaded audio files
├── data/                   # SQLite database
├── tests/                  # Unit tests
└── systemd/                # Service file
```

## Running Tests

```bash
source venv/bin/activate
python3 -m pytest tests/ -v
```

## License

MIT
