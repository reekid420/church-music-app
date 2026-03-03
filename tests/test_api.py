"""Tests for REST API endpoints."""

import os
import json
import tempfile
import pytest

# Set up test environment before importing app
os.environ['TESTING'] = '1'

from app import create_app
from app.database import get_db


@pytest.fixture
def app():
    """Create application for testing."""
    # Use a temp directory for test data
    with tempfile.TemporaryDirectory() as tmpdir:
        test_config = {
            'TESTING': True,
            'DATABASE': os.path.join(tmpdir, 'test.db'),
            'MUSIC_DIR': os.path.join(tmpdir, 'music'),
            'DATA_DIR': tmpdir,
        }
        os.makedirs(test_config['MUSIC_DIR'], exist_ok=True)

        app = create_app(test_config)

        with app.app_context():
            yield app


@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()


# ─── Playback API ────────────────────────────────────────────────────────────

class TestPlaybackAPI:
    def test_status_endpoint(self, client):
        """GET /api/status should return playback status."""
        resp = client.get('/api/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'state' in data or 'global_volume' in data

    def test_stop_endpoint(self, client):
        """POST /api/stop should succeed."""
        resp = client.post('/api/stop')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_pause_endpoint(self, client):
        """POST /api/pause should succeed."""
        resp = client.post('/api/pause')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_play_requires_id(self, client):
        """POST /api/play without playlist_id or song_id should fail."""
        resp = client.post('/api/play',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data


# ─── Volume API ──────────────────────────────────────────────────────────────

class TestVolumeAPI:
    def test_get_volume(self, client):
        """GET /api/volume should return current volume."""
        resp = client.get('/api/volume')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'volume' in data

    def test_set_volume(self, client):
        """POST /api/volume should accept volume level."""
        resp = client.post('/api/volume',
                           data=json.dumps({'volume': 50}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['volume'] == 50

    def test_set_track_volume(self, client):
        """POST /api/track-volume should succeed."""
        resp = client.post('/api/track-volume',
                           data=json.dumps({'volume': 75}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['track_volume'] == 75


# ─── Songs API ───────────────────────────────────────────────────────────────

class TestSongsAPI:
    def test_list_songs_empty(self, client):
        """GET /api/songs should return empty list initially."""
        resp = client.get('/api/songs')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_delete_song_not_found(self, client):
        """DELETE /api/songs/999 should return 404."""
        resp = client.delete('/api/songs/999')
        assert resp.status_code == 404

    def test_upload_no_files(self, client):
        """POST /api/songs/upload without files should return 400."""
        resp = client.post('/api/songs/upload')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data


# ─── Playlists API ───────────────────────────────────────────────────────────

class TestPlaylistsAPI:
    def test_list_playlists_empty(self, client):
        """GET /api/playlists should return empty list initially."""
        resp = client.get('/api/playlists')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_create_playlist(self, client):
        """POST /api/playlists should create a playlist."""
        resp = client.post('/api/playlists',
                           data=json.dumps({'name': 'Sunday Worship', 'description': 'Test'}),
                           content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == 'Sunday Worship'
        assert 'id' in data

    def test_create_playlist_no_name(self, client):
        """POST /api/playlists without name should fail."""
        resp = client.post('/api/playlists',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_get_playlist(self, client):
        """GET /api/playlists/<id> should return playlist with songs."""
        # Create first
        resp = client.post('/api/playlists',
                           data=json.dumps({'name': 'Test Playlist'}),
                           content_type='application/json')
        pid = resp.get_json()['id']

        # Get it
        resp = client.get(f'/api/playlists/{pid}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == 'Test Playlist'
        assert 'songs' in data

    def test_get_playlist_not_found(self, client):
        """GET /api/playlists/999 should return 404."""
        resp = client.get('/api/playlists/999')
        assert resp.status_code == 404

    def test_delete_playlist(self, client):
        """DELETE /api/playlists/<id> should succeed."""
        resp = client.post('/api/playlists',
                           data=json.dumps({'name': 'To Delete'}),
                           content_type='application/json')
        pid = resp.get_json()['id']

        resp = client.delete(f'/api/playlists/{pid}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ─── Schedules API ───────────────────────────────────────────────────────────

class TestSchedulesAPI:
    def test_list_schedules(self, client):
        """GET /api/schedules should return schedules and upcoming."""
        resp = client.get('/api/schedules')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'schedules' in data
        assert 'upcoming' in data

    def test_create_schedule_missing_fields(self, client):
        """POST /api/schedules without required fields should fail."""
        resp = client.post('/api/schedules',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400


# ─── Speaker API ─────────────────────────────────────────────────────────────

class TestSpeakerAPI:
    def test_get_speaker_status(self, client):
        """GET /api/speaker should return connected and paired info."""
        resp = client.get('/api/speaker')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'connected' in data
        assert 'paired' in data

    def test_connect_speaker_no_mac(self, client):
        """POST /api/speaker/connect without MAC should fail."""
        resp = client.post('/api/speaker/connect',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_disconnect_speaker_no_mac(self, client):
        """POST /api/speaker/disconnect without MAC should fail."""
        resp = client.post('/api/speaker/disconnect',
                           data=json.dumps({}),
                           content_type='application/json')
        assert resp.status_code == 400


# ─── Page Routes ─────────────────────────────────────────────────────────────

class TestPageRoutes:
    """Test that all HTML pages render without 500 errors."""

    def test_dashboard(self, client):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_library(self, client):
        resp = client.get('/library')
        assert resp.status_code == 200

    def test_schedules(self, client):
        resp = client.get('/schedules')
        assert resp.status_code == 200

    def test_speakers(self, client):
        resp = client.get('/speakers')
        assert resp.status_code == 200

    def test_settings(self, client):
        resp = client.get('/settings')
        assert resp.status_code == 200
