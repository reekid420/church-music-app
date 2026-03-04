"""REST API endpoints."""

import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from mutagen import File as MutagenFile

from app.database import get_db
import app.services as services

api_bp = Blueprint('api', __name__)


# ─── Playback ────────────────────────────────────────────────────────────────

@api_bp.route('/play', methods=['POST'])
def play():
    """Play a playlist or song."""
    data = request.get_json(silent=True) or {}
    db = get_db()

    playlist_id = data.get('playlist_id')
    song_id = data.get('song_id')
    duration = data.get('duration_minutes')

    if playlist_id:
        success = services.audio_player.play_playlist_by_id(playlist_id, db)
    elif song_id:
        success = services.audio_player.play_song_by_id(song_id, db)
    else:
        return jsonify({'error': 'Provide playlist_id or song_id'}), 400

    if success and duration:
        services.audio_player.set_stop_timer(int(duration))

    return jsonify({'success': success})


@api_bp.route('/stop', methods=['POST'])
def stop():
    """Stop playback immediately."""
    services.audio_player.stop()
    return jsonify({'success': True})


@api_bp.route('/pause', methods=['POST'])
def pause():
    """Toggle pause."""
    services.audio_player.pause()
    return jsonify({'success': True})


@api_bp.route('/next', methods=['POST'])
def next_track():
    """Skip to next track."""
    services.audio_player.next_track()
    return jsonify({'success': True})


@api_bp.route('/previous', methods=['POST'])
def previous_track():
    """Go to previous track."""
    services.audio_player.previous_track()
    return jsonify({'success': True})


@api_bp.route('/status', methods=['GET'])
def status():
    """Get current playback status."""
    player_status = services.audio_player.get_status()
    player_status['global_volume'] = services.volume_controller.get_volume()
    return jsonify(player_status)


# ─── Volume ──────────────────────────────────────────────────────────────────

@api_bp.route('/volume', methods=['POST'])
def set_volume():
    """Set global system volume."""
    data = request.get_json(silent=True) or {}
    vol = data.get('volume', 80)
    success = services.volume_controller.set_volume(int(vol))

    # Save to settings
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ('global_volume', str(vol))
    )
    db.commit()
    return jsonify({'success': success, 'volume': vol})


@api_bp.route('/volume', methods=['GET'])
def get_volume():
    """Get current global volume."""
    vol = services.volume_controller.get_volume()
    return jsonify({'volume': vol})


@api_bp.route('/volume/live', methods=['POST'])
def set_volume_live():
    """Set system volume immediately without persisting to DB.

    Used during slider drag for instant feedback.
    """
    data = request.get_json(silent=True) or {}
    vol = data.get('volume', 80)
    success = services.volume_controller.set_volume(int(vol))
    return jsonify({'success': success, 'volume': vol})


@api_bp.route('/track-volume', methods=['POST'])
def set_track_volume():
    """Set per-track volume (VLC internal) and persist."""
    data = request.get_json(silent=True) or {}
    vol = data.get('volume', 100)
    services.audio_player.set_track_volume(int(vol))
    return jsonify({'success': True, 'track_volume': vol})


@api_bp.route('/default-volume', methods=['GET'])
def get_default_volume():
    """Get the default playback volume used by schedules."""
    db = get_db()
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'default_volume'"
    ).fetchone()
    vol = int(row['value']) if row else 80
    return jsonify({'volume': vol})


@api_bp.route('/default-volume', methods=['POST'])
def set_default_volume():
    """Set the default playback volume used by schedules."""
    data = request.get_json(silent=True) or {}
    vol = max(0, min(100, int(data.get('volume', 80))))
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ('default_volume', str(vol))
    )
    db.commit()
    return jsonify({'success': True, 'volume': vol})


# ─── Songs ───────────────────────────────────────────────────────────────────

@api_bp.route('/songs', methods=['GET'])
def list_songs():
    """List all songs in the library."""
    db = get_db()
    cursor = db.execute(
        "SELECT * FROM songs ORDER BY title ASC"
    )
    songs = [dict(row) for row in cursor.fetchall()]
    return jsonify(songs)


@api_bp.route('/songs/upload', methods=['POST'])
def upload_songs():
    """Upload one or more audio files."""
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    uploaded = []
    errors = []

    music_dir = current_app.config['MUSIC_DIR']
    supported = current_app.config['SUPPORTED_FORMATS']

    for f in files:
        filename = secure_filename(f.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in supported:
            errors.append(f"{filename}: unsupported format ({ext})")
            continue

        filepath = os.path.join(music_dir, filename)

        # Handle duplicate filenames
        counter = 1
        base, extension = os.path.splitext(filename)
        while os.path.exists(filepath):
            filename = f"{base}_{counter}{extension}"
            filepath = os.path.join(music_dir, filename)
            counter += 1

        f.save(filepath)

        # Extract metadata
        meta = _extract_metadata(filepath)
        meta['filename'] = filename
        meta['file_path'] = filepath
        meta['format'] = ext.lstrip('.')
        meta['file_size'] = os.path.getsize(filepath)

        db = get_db()
        try:
            cursor = db.execute(
                """INSERT INTO songs (filename, title, artist, album,
                   duration_seconds, format, file_path, file_size)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meta['filename'],
                    meta.get('title', filename),
                    meta.get('artist', ''),
                    meta.get('album', ''),
                    meta.get('duration', 0),
                    meta['format'],
                    meta['file_path'],
                    meta['file_size'],
                )
            )
            db.commit()
            meta['id'] = cursor.lastrowid
            uploaded.append(meta)
        except Exception as e:
            errors.append(f"{filename}: {str(e)}")

    return jsonify({
        'uploaded': uploaded,
        'errors': errors,
        'count': len(uploaded)
    })


@api_bp.route('/songs/<int:song_id>', methods=['DELETE'])
def delete_song(song_id):
    """Delete a song from the library."""
    db = get_db()
    cursor = db.execute("SELECT file_path FROM songs WHERE id = ?", (song_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({'error': 'Song not found'}), 404

    # Delete file
    try:
        if os.path.exists(row['file_path']):
            os.remove(row['file_path'])
    except Exception:
        pass

    db.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    db.commit()
    return jsonify({'success': True})


# ─── Playlists ───────────────────────────────────────────────────────────────

@api_bp.route('/playlists', methods=['GET'])
def list_playlists():
    """List all playlists."""
    db = get_db()
    cursor = db.execute("SELECT * FROM playlists ORDER BY name ASC")
    playlists = [dict(row) for row in cursor.fetchall()]

    # Include song count
    for p in playlists:
        cursor = db.execute(
            "SELECT COUNT(*) as count FROM playlist_songs WHERE playlist_id = ?",
            (p['id'],)
        )
        p['song_count'] = cursor.fetchone()['count']

    return jsonify(playlists)


@api_bp.route('/playlists', methods=['POST'])
def create_playlist():
    """Create a new playlist."""
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO playlists (name, description) VALUES (?, ?)",
            (name, data.get('description', ''))
        )
        db.commit()
        return jsonify({'id': cursor.lastrowid, 'name': name})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@api_bp.route('/playlists/<int:playlist_id>', methods=['PUT'])
def update_playlist(playlist_id):
    """Update a playlist (name, description, or songs)."""
    data = request.get_json(silent=True) or {}
    db = get_db()

    if 'name' in data or 'description' in data:
        fields = []
        values = []
        if 'name' in data:
            fields.append('name = ?')
            values.append(data['name'])
        if 'description' in data:
            fields.append('description = ?')
            values.append(data['description'])
        fields.append('updated_at = CURRENT_TIMESTAMP')
        values.append(playlist_id)
        db.execute(
            f"UPDATE playlists SET {', '.join(fields)} WHERE id = ?",
            values
        )

    if 'song_ids' in data:
        # Replace all songs in the playlist
        db.execute(
            "DELETE FROM playlist_songs WHERE playlist_id = ?",
            (playlist_id,)
        )
        for i, song_id in enumerate(data['song_ids']):
            db.execute(
                """INSERT INTO playlist_songs (playlist_id, song_id, position)
                   VALUES (?, ?, ?)""",
                (playlist_id, song_id, i)
            )

    db.commit()
    return jsonify({'success': True})


@api_bp.route('/playlists/<int:playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    """Get a playlist with its songs."""
    db = get_db()
    cursor = db.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
    playlist = cursor.fetchone()
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404

    playlist = dict(playlist)
    cursor = db.execute(
        """SELECT s.*, ps.position FROM playlist_songs ps
           JOIN songs s ON ps.song_id = s.id
           WHERE ps.playlist_id = ?
           ORDER BY ps.position""",
        (playlist_id,)
    )
    playlist['songs'] = [dict(row) for row in cursor.fetchall()]
    return jsonify(playlist)


@api_bp.route('/playlists/<int:playlist_id>', methods=['DELETE'])
def delete_playlist(playlist_id):
    """Delete a playlist."""
    db = get_db()
    db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    db.commit()
    return jsonify({'success': True})


# ─── Schedules ───────────────────────────────────────────────────────────────

@api_bp.route('/schedules', methods=['GET'])
def list_schedules():
    """List all schedules."""
    schedules = services.scheduler_service.get_all_schedules()
    upcoming = services.scheduler_service.get_upcoming_jobs()
    return jsonify({'schedules': schedules, 'upcoming': upcoming})


@api_bp.route('/schedules', methods=['POST'])
def create_schedule():
    """Create a new schedule."""
    data = request.get_json(silent=True) or {}
    required = ['name', 'schedule_type']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    schedule_id = services.scheduler_service.add_schedule(data)
    if schedule_id:
        return jsonify({'id': schedule_id, 'success': True})
    return jsonify({'error': 'Failed to create schedule'}), 500


@api_bp.route('/schedules/<int:schedule_id>', methods=['PUT'])
def update_schedule(schedule_id):
    """Update an existing schedule."""
    data = request.get_json(silent=True) or {}
    success = services.scheduler_service.update_schedule(schedule_id, data)
    return jsonify({'success': success})


@api_bp.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete a schedule."""
    success = services.scheduler_service.delete_schedule(schedule_id)
    return jsonify({'success': success})


# ─── Speaker / Bluetooth ───────────────────────────────────────────────────

@api_bp.route('/speaker', methods=['GET'])
def get_speaker():
    """Get current speaker connection status."""
    connected = services.bluetooth_manager.get_connected_speaker()
    paired = services.bluetooth_manager.get_paired_devices()
    return jsonify({
        'connected': connected,
        'paired': paired
    })


@api_bp.route('/speaker/scan', methods=['POST'])
def scan_speakers():
    """Scan for Bluetooth devices."""
    data = request.get_json(silent=True) or {}
    duration = data.get('duration', 10)
    devices = services.bluetooth_manager.scan(duration=duration)
    return jsonify({'devices': devices})


@api_bp.route('/speaker/connect', methods=['POST'])
def connect_speaker():
    """Connect to a Bluetooth speaker and set as default audio sink."""
    data = request.get_json(silent=True) or {}
    mac = data.get('mac')
    if not mac:
        return jsonify({'error': 'MAC address required'}), 400

    # Pair and connect (connect() also sets default sink)
    services.bluetooth_manager.pair(mac)
    success = services.bluetooth_manager.connect(mac)

    return jsonify({'success': success})


@api_bp.route('/speaker/disconnect', methods=['POST'])
def disconnect_speaker():
    """Disconnect the Bluetooth speaker."""
    data = request.get_json(silent=True) or {}
    mac = data.get('mac')
    if not mac:
        return jsonify({'error': 'MAC address required'}), 400

    success = services.bluetooth_manager.disconnect(mac)
    return jsonify({'success': success})


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_metadata(filepath):
    """Extract audio metadata using mutagen."""
    meta = {
        'title': os.path.splitext(os.path.basename(filepath))[0],
        'artist': '',
        'album': '',
        'duration': 0
    }
    try:
        audio = MutagenFile(filepath, easy=True)
        if audio:
            meta['title'] = str(audio.get('title', [meta['title']])[0])
            meta['artist'] = str(audio.get('artist', [''])[0])
            meta['album'] = str(audio.get('album', [''])[0])
            if hasattr(audio, 'info') and audio.info:
                meta['duration'] = audio.info.length
    except Exception:
        pass
    return meta
