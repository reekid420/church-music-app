"""Bluetooth speaker management via bluetoothctl."""

import subprocess
import logging
import os
import re

import threading
import time

logger = logging.getLogger(__name__)


class BluetoothManager:
    """Manage Bluetooth speaker connections using bluetoothctl."""

    def __init__(self):
        self._lock = threading.Lock()

    def get_connected_devices(self):
        """List currently connected Bluetooth devices."""
        try:
            result = subprocess.run(
                ['bluetoothctl', 'devices', 'Connected'],
                capture_output=True, text=True, timeout=10
            )
            return self._parse_devices(result.stdout)
        except Exception as e:
            logger.error(f"Failed to list connected devices: {e}")
            return []

    def get_paired_devices(self):
        """List all paired Bluetooth devices."""
        try:
            result = subprocess.run(
                ['bluetoothctl', 'devices', 'Paired'],
                capture_output=True, text=True, timeout=10
            )
            return self._parse_devices(result.stdout)
        except Exception as e:
            logger.error(f"Failed to list paired devices: {e}")
            return []

    def scan(self, duration=10):
        """Scan for nearby Bluetooth devices.

        Runs bluetoothctl scan to refresh BlueZ's device cache, then
        queries the full device list and filters out already-paired devices.
        """
        # 1. Run scan to refresh BlueZ's internal device cache
        try:
            env = os.environ.copy()
            env['LANG'] = 'C'
            proc = subprocess.Popen(
                ['bluetoothctl'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            proc.stdin.write('scan on\n')
            proc.stdin.flush()
            time.sleep(duration)
            proc.stdin.write('scan off\n')
            proc.stdin.write('quit\n')
            proc.stdin.flush()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        except Exception as e:
            logger.error(f"Bluetooth scan failed: {e}")

        # 2. Get all devices BlueZ now knows about (refreshed by the scan)
        all_devices = {}
        try:
            result = subprocess.run(
                ['bluetoothctl', 'devices'],
                capture_output=True, text=True, timeout=10
            )
            for dev in self._parse_devices(result.stdout):
                all_devices[dev['mac']] = dev['name']
        except Exception:
            pass

        # 3. Get paired devices so we can exclude them from results
        paired_macs = set(d['mac'] for d in self.get_paired_devices())

        # 4. Return unpaired devices that have a real name (skip raw MAC-only entries)
        results = []
        for mac, name in all_devices.items():
            if mac in paired_macs:
                continue
            # Skip devices whose name is just a MAC address (unnamed)
            if re.match(r'^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$', name):
                continue
            results.append({'mac': mac, 'name': name})

        logger.info(
            f"Scan complete: {len(results)} unpaired devices "
            f"({len(all_devices)} total in cache, {len(paired_macs)} paired excluded)"
        )
        return results

    def connect(self, mac_address):
        """Connect to a Bluetooth device and set it as default audio sink."""
        with self._lock:
            try:
                # Trust the device first
                subprocess.run(
                    ['bluetoothctl', 'trust', mac_address],
                    capture_output=True, text=True, timeout=10
                )
                # Then connect
                result = subprocess.run(
                    ['bluetoothctl', 'connect', mac_address],
                    capture_output=True, text=True, timeout=15
                )
                success = 'Connection successful' in result.stdout
                if success:
                    logger.info(f"Connected to {mac_address}")
                    # Give PipeWire a moment to register the new sink
                    time.sleep(3)
                    self._set_as_default_sink(mac_address)
                else:
                    logger.warning(f"Failed to connect to {mac_address}: {result.stdout}")
                return success
            except Exception as e:
                logger.error(f"Connect failed: {e}")
                return False

    def disconnect(self, mac_address):
        """Disconnect from a Bluetooth device."""
        with self._lock:
            try:
                result = subprocess.run(
                    ['bluetoothctl', 'disconnect', mac_address],
                    capture_output=True, text=True, timeout=10
                )
                success = 'Successful disconnected' in result.stdout or \
                          'successful' in result.stdout.lower()
                logger.info(f"Disconnected from {mac_address}: {success}")
                return success
            except Exception as e:
                logger.error(f"Disconnect failed: {e}")
                return False

    def pair(self, mac_address):
        """Pair with a Bluetooth device."""
        with self._lock:
            try:
                result = subprocess.run(
                    ['bluetoothctl', 'pair', mac_address],
                    capture_output=True, text=True, timeout=20
                )
                success = 'Pairing successful' in result.stdout or \
                          'already exists' in result.stdout.lower()
                logger.info(f"Paired with {mac_address}: {success}")
                return success
            except Exception as e:
                logger.error(f"Pair failed: {e}")
                return False

    def remove(self, mac_address):
        """Remove/unpair a Bluetooth device."""
        with self._lock:
            try:
                result = subprocess.run(
                    ['bluetoothctl', 'remove', mac_address],
                    capture_output=True, text=True, timeout=10
                )
                return 'Device has been removed' in result.stdout
            except Exception as e:
                logger.error(f"Remove failed: {e}")
                return False

    def get_device_info(self, mac_address):
        """Get info about a specific device."""
        try:
            result = subprocess.run(
                ['bluetoothctl', 'info', mac_address],
                capture_output=True, text=True, timeout=10
            )
            info = {'mac': mac_address}
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('Name:'):
                    info['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('Connected:'):
                    info['connected'] = 'yes' in line.lower()
                elif line.startswith('Paired:'):
                    info['paired'] = 'yes' in line.lower()
                elif line.startswith('Trusted:'):
                    info['trusted'] = 'yes' in line.lower()
                elif line.startswith('Icon:'):
                    info['icon'] = line.split(':', 1)[1].strip()
            return info
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")
            return {'mac': mac_address}

    def auto_connect_paired(self):
        """Attempt to connect to the first available paired speaker on startup."""
        paired = self.get_paired_devices()
        for device in paired:
            mac = device['mac']
            info = self.get_device_info(mac)
            if info.get('connected', False):
                logger.info(f"Already connected to {device['name']} ({mac})")
                # Ensure it's the default sink
                self._set_as_default_sink(mac)
                return device
            else:
                logger.info(f"Auto-connecting to {device['name']} ({mac})...")
                if self.connect(mac):
                    return device
        logger.info("No paired speakers available for auto-connect")
        return None

    def _set_as_default_sink(self, mac_address):
        """Find the PipeWire sink for a BT device and set it as default."""
        try:
            # Get wpctl status output
            result = subprocess.run(
                ['wpctl', 'status'],
                capture_output=True, text=True, timeout=10
            )
            # Convert MAC to the format PipeWire uses (underscores or dots)
            mac_variants = [
                mac_address.replace(':', '_').lower(),
                mac_address.replace(':', '.').lower(),
                mac_address.lower(),
            ]
            # Parse wpctl status for sink IDs
            # Lines look like: " *  46. Device Name [vol: 0.80]"
            #                  "    46. Device Name [vol: 0.80]"
            for line in result.stdout.split('\n'):
                line_lower = line.lower()
                if any(mac_var in line_lower for mac_var in mac_variants) or \
                   'bluez' in line_lower or 'bluetooth' in line_lower:
                    # Extract the node ID number
                    match = re.search(r'\s+(\d+)\.\s+', line)
                    if match:
                        sink_id = match.group(1)
                        subprocess.run(
                            ['wpctl', 'set-default', sink_id],
                            capture_output=True, text=True, timeout=5
                        )
                        logger.info(f"Set BT speaker as default sink (wpctl ID: {sink_id})")
                        return True
            logger.warning("Could not find BT speaker sink in wpctl status")
        except Exception as e:
            logger.error(f"Failed to set default sink: {e}")
        return False

    def get_connected_speaker(self):
        """Get the currently connected BT speaker (first one found)."""
        connected = self.get_connected_devices()
        if connected:
            info = self.get_device_info(connected[0]['mac'])
            return info
        return None

    def _parse_devices(self, output):
        """Parse bluetoothctl device listing output."""
        devices = []
        for line in output.strip().split('\n'):
            # Format: "Device XX:XX:XX:XX:XX:XX DeviceName"
            match = re.match(
                r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)',
                line.strip()
            )
            if match:
                devices.append({
                    'mac': match.group(1),
                    'name': match.group(2).strip()
                })
        return devices
