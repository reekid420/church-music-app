"""Service initialization."""

# Global service instances
audio_player = None
scheduler_service = None
bluetooth_manager = None
volume_controller = None


def init_services(app):
    """Initialize all background services."""
    global audio_player, scheduler_service, bluetooth_manager, volume_controller

    from app.services.volume import VolumeController
    from app.services.audio_player import AudioPlayer
    from app.services.bluetooth import BluetoothManager
    from app.services.scheduler import SchedulerService

    volume_controller = VolumeController()
    audio_player = AudioPlayer(app, volume_controller)
    bluetooth_manager = BluetoothManager()
    scheduler_service = SchedulerService(app, audio_player)
