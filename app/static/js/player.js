/**
 * Church Bell System — Player Controls
 * Handles Now Playing UI updates and playback control buttons.
 */

let playerPollInterval = null;
let currentPlaybackState = null;
let lastSyncTime = 0;
let animationFrameId = null;

function renderPlayback() {
    if (currentPlaybackState && currentPlaybackState.is_playing && currentPlaybackState.duration_seconds > 0) {
        const now = performance.now();
        const elapsedSinceSync = (now - lastSyncTime) / 1000;
        let currentPos = currentPlaybackState.position_seconds + elapsedSinceSync;
        if (currentPos > currentPlaybackState.duration_seconds) currentPos = currentPlaybackState.duration_seconds;

        const pct = (currentPos / currentPlaybackState.duration_seconds) * 100;
        const progressEl = document.getElementById('progressFill');
        const elapsedEl = document.getElementById('timeElapsed');
        if (progressEl) progressEl.style.width = pct + '%';
        if (elapsedEl) elapsedEl.textContent = formatTime(currentPos);
    }
    animationFrameId = requestAnimationFrame(renderPlayback);
}

function initPlayer() {
    // Playback control buttons
    const btnPlay = document.getElementById('btnPlayPause');
    const btnStop = document.getElementById('btnStop');
    const btnNext = document.getElementById('btnNext');
    const btnPrev = document.getElementById('btnPrevious');
    const trackVol = document.getElementById('trackVolumeSlider');
    const trackVolVal = document.getElementById('trackVolumeValue');

    if (btnPlay) {
        btnPlay.addEventListener('click', async () => {
            try {
                await apiPost('/api/pause');
            } catch (e) {
                showToast('Playback control failed', 'error');
            }
        });
    }

    if (btnStop) {
        btnStop.addEventListener('click', async () => {
            try {
                await apiPost('/api/stop');
                showToast('Stopped', 'success');
            } catch (e) {
                showToast('Stop failed', 'error');
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', async () => {
            try { await apiPost('/api/next'); } catch (e) { }
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener('click', async () => {
            try { await apiPost('/api/previous'); } catch (e) { }
        });
    }

    if (trackVol) {
        let tvTimeout;
        trackVol.addEventListener('input', () => {
            trackVolVal.textContent = trackVol.value + '%';
            clearTimeout(tvTimeout);
            tvTimeout = setTimeout(() => {
                apiPost('/api/track-volume', { volume: parseInt(trackVol.value) });
            }, 200);
        });
    }

    // Poll for status every 2 seconds
    updatePlayerStatus();
    playerPollInterval = setInterval(updatePlayerStatus, 2000);

    if (!animationFrameId) {
        animationFrameId = requestAnimationFrame(renderPlayback);
    }
}

async function updatePlayerStatus() {
    try {
        const status = await api('/api/status');
        const titleEl = document.getElementById('npTitle');
        const artistEl = document.getElementById('npArtist');
        const progressEl = document.getElementById('progressFill');
        const elapsedEl = document.getElementById('timeElapsed');
        const totalEl = document.getElementById('timeTotal');
        const btnPlay = document.getElementById('btnPlayPause');
        const miniStatus = document.getElementById('miniStatus');

        if (!titleEl) return;

        if (status.is_playing || status.state === 'paused') {
            // Extract filename from path
            let name = status.current_file || 'Unknown';
            // Clean up VLC's file:// prefix
            if (name.startsWith('file://')) {
                name = decodeURIComponent(name.split('/').pop());
            }
            // Remove extension for display
            name = name.replace(/\.(mp3|flac|wav|ogg)$/i, '');

            titleEl.textContent = name;
            artistEl.textContent = `Track ${status.current_index + 1} of ${status.playlist_length}`;

            // Sync state for animation loop
            currentPlaybackState = status;
            lastSyncTime = performance.now();

            // Progress (Initial sync, animation handles the rest while playing)
            if (status.duration_seconds > 0) {
                const pct = (status.position_seconds / status.duration_seconds) * 100;
                progressEl.style.width = pct + '%';
            }
            elapsedEl.textContent = formatTime(status.position_seconds);
            totalEl.textContent = formatTime(status.duration_seconds);

            // Button state
            btnPlay.textContent = status.state === 'paused' ? '▶' : '⏸';
            btnPlay.title = status.state === 'paused' ? 'Resume' : 'Pause';

            // Mini status in sidebar
            if (miniStatus) {
                miniStatus.textContent = status.state === 'paused' ? '⏸ Paused' : '▶ Playing';
                miniStatus.style.color = status.state === 'paused' ? 'var(--warning)' : 'var(--success)';
            }
        } else {
            currentPlaybackState = null;
            titleEl.textContent = 'Nothing Playing';
            artistEl.textContent = 'Select a song or playlist to begin';
            progressEl.style.width = '0%';
            elapsedEl.textContent = '0:00';
            totalEl.textContent = '0:00';
            btnPlay.textContent = '▶';
            btnPlay.title = 'Play';

            if (miniStatus) {
                miniStatus.textContent = 'Not Playing';
                miniStatus.style.color = '';
            }
        }

        // Update global volume if present
        if (status.global_volume !== undefined) {
            const gSlider = document.getElementById('globalVolumeSlider');
            const gVal = document.getElementById('globalVolumeValue');
            if (gSlider && !gSlider.matches(':active')) {
                gSlider.value = status.global_volume;
                gVal.textContent = status.global_volume + '%';
            }
        }

        // Update track volume
        const tvSlider = document.getElementById('trackVolumeSlider');
        if (tvSlider && !tvSlider.matches(':active')) {
            tvSlider.value = status.track_volume || 100;
            const tvVal = document.getElementById('trackVolumeValue');
            if (tvVal) tvVal.textContent = (status.track_volume || 100) + '%';
        }
    } catch (e) {
        // Silent fail — server might be restarting
    }
}

function formatTime(seconds) {
    if (!seconds || seconds < 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}
