"""System volume control via wpctl (PipeWire/WirePlumber)."""

import subprocess
import logging
import re

logger = logging.getLogger(__name__)


class VolumeController:
    """Control system volume through PipeWire's wpctl."""

    def __init__(self):
        logger.info("Volume controller initialized (wpctl / PipeWire)")

    def get_volume(self):
        """Get the current default sink volume as a percentage."""
        try:
            result = subprocess.run(
                ['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'],
                capture_output=True, text=True, timeout=5
            )
            # Output: "Volume: 0.80" or "Volume: 0.80 [MUTED]"
            match = re.search(r'Volume:\s+([\d.]+)', result.stdout)
            if match:
                return int(float(match.group(1)) * 100)
        except Exception as e:
            logger.error(f"Failed to get volume: {e}")
        return 80  # fallback

    def set_volume(self, percent):
        """Set the default sink volume (0-100)."""
        percent = max(0, min(100, percent))
        try:
            subprocess.run(
                ['wpctl', 'set-volume', '@DEFAULT_AUDIO_SINK@',
                 f'{percent / 100:.2f}'],
                capture_output=True, timeout=5
            )
            logger.info(f"Volume set to {percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False

    def is_muted(self):
        """Check if default sink is muted."""
        try:
            result = subprocess.run(
                ['wpctl', 'get-volume', '@DEFAULT_AUDIO_SINK@'],
                capture_output=True, text=True, timeout=5
            )
            return '[MUTED]' in result.stdout
        except Exception:
            return False

    def toggle_mute(self):
        """Toggle mute on default sink."""
        try:
            subprocess.run(
                ['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@', 'toggle'],
                capture_output=True, timeout=5
            )
            return True
        except Exception as e:
            logger.error(f"Failed to toggle mute: {e}")
            return False
