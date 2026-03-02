/**
 * Church Bell System — Core JavaScript
 * Shared utilities, API helpers, and global UI logic.
 */

// ─── API Helpers ──────────────────────────────────────────

async function api(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiPost(url, data = {}) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

async function apiPut(url, data = {}) {
    const res = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

// ─── Toast Notifications ──────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${escHtml(message)}`;
    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 4000);
}

// ─── Confirm Dialog ───────────────────────────────────────

function showConfirm(title, message) {
    return new Promise(resolve => {
        const modal = document.getElementById('confirmModal');
        document.getElementById('confirmTitle').textContent = title;
        document.getElementById('confirmMessage').textContent = message;
        modal.style.display = 'flex';

        const onOk = () => { cleanup(); resolve(true); };
        const onCancel = () => { cleanup(); resolve(false); };

        function cleanup() {
            modal.style.display = 'none';
            document.getElementById('confirmOk').removeEventListener('click', onOk);
            document.getElementById('confirmCancel').removeEventListener('click', onCancel);
        }

        document.getElementById('confirmOk').addEventListener('click', onOk);
        document.getElementById('confirmCancel').addEventListener('click', onCancel);
    });
}

// ─── HTML Escaping ────────────────────────────────────────

function escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ─── Global Volume ────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const slider = document.getElementById('globalVolumeSlider');
    const valueEl = document.getElementById('globalVolumeValue');

    if (slider) {
        // Load current volume
        api('/api/volume').then(data => {
            slider.value = data.volume;
            valueEl.textContent = data.volume + '%';
        }).catch(() => { });

        // Debounced volume changes
        let volumeTimeout;
        slider.addEventListener('input', () => {
            valueEl.textContent = slider.value + '%';
            clearTimeout(volumeTimeout);
            volumeTimeout = setTimeout(() => {
                apiPost('/api/volume', { volume: parseInt(slider.value) });
            }, 300);
        });
    }

    // Mobile menu
    const menuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
        // Close sidebar on clicking outside
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('open') &&
                !sidebar.contains(e.target) &&
                !menuBtn.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    }
});
