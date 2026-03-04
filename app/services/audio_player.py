"""Audio playback engine using VLC."""

import os
import time
import threading
import logging
import vlc

logger = logging.getLogger(__name__)


class AudioPlayer:
    """VLC-based audio player with playlist support."""

    def __init__(self, app, volume_controller):
        self.app = app
        self.volume_ctrl = volume_controller
        self.instance = vlc.Instance('--no-video', '--quiet')
        self.list_player = self.instance.media_list_player_new()
        self.player = self.list_player.get_media_player()
        self.media_list = self.instance.media_list_new()
        self.list_player.set_media_list(self.media_list)

        # State
        self._current_playlist = []
        self._current_index = 0
        self._is_playing = False
        self._stop_timer = None
        self._track_volume = self._load_track_volume()  # per-track volume (0–100)
        self._lock = threading.Lock()

        # Event handling
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_track_end)

    def play_files(self, file_paths, start_index=0):
        """Play a list of audio files."""
        with self._lock:
            self._stop_internal()
            self.media_list = self.instance.media_list_new()
            self._current_playlist = []

            for path in file_paths:
                if os.path.isfile(path):
                    media = self.instance.media_new(path)
                    self.media_list.add_media(media)
                    self._current_playlist.append(path)
                else:
                    logger.warning(f"File not found: {path}")

            if not self._current_playlist:
                logger.error("No valid files to play")
                return False

            self.list_player.set_media_list(self.media_list)
            self._current_index = start_index
            self.list_player.play_item_at_index(start_index)
            self._is_playing = True
            self._apply_track_volume()
            logger.info(f"Playing {len(self._current_playlist)} tracks")
            return True

    def play_playlist_by_id(self, playlist_id, db_conn):
        """Load and play a playlist from the database."""
        cursor = db_conn.execute(
            """SELECT s.file_path FROM playlist_songs ps
               JOIN songs s ON ps.song_id = s.id
               WHERE ps.playlist_id = ?
               ORDER BY ps.position""",
            (playlist_id,)
        )
        files = [row['file_path'] for row in cursor.fetchall()]
        if files:
            return self.play_files(files)
        logger.warning(f"Playlist {playlist_id} has no songs")
        return False

    def play_song_by_id(self, song_id, db_conn):
        """Play a single song from the database."""
        cursor = db_conn.execute(
            "SELECT file_path FROM songs WHERE id = ?", (song_id,)
        )
        row = cursor.fetchone()
        if row:
            return self.play_files([row['file_path']])
        logger.warning(f"Song {song_id} not found")
        return False

    def stop(self):
        """Stop playback."""
        with self._lock:
            self._stop_internal()

    def _stop_internal(self):
        """Stop without lock (internal use)."""
        self.list_player.stop()
        self._is_playing = False
        self._cancel_stop_timer()
        logger.info("Playback stopped")

    def pause(self):
        """Toggle pause."""
        self.list_player.pause()
        state = self.player.get_state()
        self._is_playing = state == vlc.State.Playing
        logger.info(f"Pause toggled, playing={self._is_playing}")

    def next_track(self):
        """Skip to next track."""
        self.list_player.next()
        self._current_index = min(
            self._current_index + 1,
            len(self._current_playlist) - 1
        )
        logger.info(f"Next track: index {self._current_index}")

    def previous_track(self):
        """Go to previous track."""
        self.list_player.previous()
        self._current_index = max(self._current_index - 1, 0)
        logger.info(f"Previous track: index {self._current_index}")

    def set_track_volume(self, volume):
        """Set per-track volume (0-100) and persist to DB."""
        self._track_volume = max(0, min(100, volume))
        self._apply_track_volume()
        self._save_track_volume()

    def _apply_track_volume(self):
        """Apply volume to VLC player."""
        # Small delay to let VLC initialize the player
        def _set():
            time.sleep(0.1)
            self.player.audio_set_volume(self._track_volume)
        threading.Thread(target=_set, daemon=True).start()

    def set_stop_timer(self, duration_minutes):
        """Schedule playback to stop after N minutes."""
        self._cancel_stop_timer()
        self._stop_timer = threading.Timer(
            duration_minutes * 60, self.stop
        )
        self._stop_timer.daemon = True
        self._stop_timer.start()
        logger.info(f"Stop timer set for {duration_minutes} minutes")

    def _cancel_stop_timer(self):
        """Cancel any pending stop timer."""
        if self._stop_timer:
            self._stop_timer.cancel()
            self._stop_timer = None

    def _on_track_end(self, event):
        """Handle track end event."""
        if self._current_index < len(self._current_playlist) - 1:
            self._current_index += 1

    def get_status(self):
        """Get current playback status."""
        state = self.player.get_state()
        media = self.player.get_media()
        current_file = ''
        duration = 0
        position = 0

        if media:
            current_file = media.get_mrl()
            duration = self.player.get_length() / 1000  # ms -> sec
            position = self.player.get_time() / 1000

        state_map = {
            vlc.State.NothingSpecial: 'idle',
            vlc.State.Opening: 'loading',
            vlc.State.Buffering: 'loading',
            vlc.State.Playing: 'playing',
            vlc.State.Paused: 'paused',
            vlc.State.Stopped: 'stopped',
            vlc.State.Ended: 'ended',
            vlc.State.Error: 'error',
        }

        return {
            'state': state_map.get(state, 'unknown'),
            'is_playing': state == vlc.State.Playing,
            'current_file': current_file,
            'current_index': self._current_index,
            'playlist_length': len(self._current_playlist),
            'duration_seconds': duration,
            'position_seconds': position,
            'track_volume': self._track_volume,
            'playlist': [os.path.basename(f) for f in self._current_playlist],
        }

    def _load_track_volume(self):
        """Load saved track volume from the settings table."""
        try:
            from app.database import get_db_connection
            conn = get_db_connection(self.app)
            cursor = conn.execute(
                "SELECT value FROM settings WHERE key = 'track_volume'"
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return max(0, min(100, int(row['value'])))
        except Exception as e:
            logger.warning(f"Could not load track volume: {e}")
        return 100

    def _save_track_volume(self):
        """Persist current track volume to the settings table."""
        try:
            from app.database import get_db_connection
            conn = get_db_connection(self.app)
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ('track_volume', str(self._track_volume))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not save track volume: {e}")

