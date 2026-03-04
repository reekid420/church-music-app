#!/usr/bin/env python3
"""Entry point for the Church Bell System."""

import logging
from logging.handlers import RotatingFileHandler
from app import create_app


class QuietRequestFilter(logging.Filter):
    """Suppress noisy HTTP request logs (e.g. polling endpoints)."""

    # Substrings that mark a log line as unimportant
    _NOISY = (
        'GET /api/status',
        'GET /api/volume',
        'GET /api/default-volume',
        'GET /api/schedules',
        'GET /api/speaker',
        'GET /api/songs',
        'GET /api/playlists',
        'GET /static/',
        'POST /api/volume/live',
    )

    def filter(self, record):
        msg = record.getMessage()
        return not any(s in msg for s in self._NOISY)


# ── Logging setup ────────────────────────────────────────────────────────────

# Rotating file handler: ~50 KB ≈ 1000 lines, keep 3 backup
file_handler = RotatingFileHandler(
    'data/church_bells.log',
    maxBytes=50_000,
    backupCount=3,
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(
    logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
)

logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler],
)

# Silence noisy werkzeug request logs (only show warnings+)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Filter out polling-endpoint noise from our own app loggers
logging.getLogger().addFilter(QuietRequestFilter())

app = create_app()

if __name__ == '__main__':
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=False
    )
