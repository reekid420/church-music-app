"""SQLite database initialization and helpers."""

import sqlite3
import os
from flask import g, current_app


def get_db():
    """Get a database connection for the current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def close_db(e=None):
    """Close the database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_db_connection(app=None):
    """Get a standalone DB connection (for use outside request context)."""
    _app = app or current_app
    conn = sqlite3.connect(
        _app.config['DATABASE'],
        detect_types=sqlite3.PARSE_DECLTYPES
    )
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    artist TEXT DEFAULT '',
    album TEXT DEFAULT '',
    duration_seconds REAL DEFAULT 0,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_size INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL,
    song_id INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE(playlist_id, song_id)
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    schedule_type TEXT NOT NULL CHECK(schedule_type IN ('recurring', 'one_time', 'automation')),
    playlist_id INTEGER,
    song_id INTEGER,
    -- Recurring fields
    day_of_week TEXT DEFAULT '',
    hour INTEGER DEFAULT 0,
    minute INTEGER DEFAULT 0,
    -- One-time fields
    run_date TEXT DEFAULT '',
    -- Automation fields (recurring with date range)
    start_date TEXT DEFAULT '',
    end_date TEXT DEFAULT '',
    -- Shared fields
    duration_minutes INTEGER DEFAULT 35,
    volume INTEGER DEFAULT 80,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE SET NULL,
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init_db(app):
    """Initialize the database schema."""
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.executescript(SCHEMA)
    # Insert default settings if not exists
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        ('global_volume', '80')
    )
    conn.commit()
    conn.close()
    app.teardown_appcontext(close_db)
