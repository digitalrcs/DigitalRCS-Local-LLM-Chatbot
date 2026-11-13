"""Standalone flash guards and command sequencing; never opens a real port."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from installer import flash_robot as flash


class FlashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="franky-installer-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.firmware = self.root / "installer" / "firmware"
        self.firmware.mkdir(parents=True)
        tools = self.root / "installer" / "tools"
        tools.mkdir()
        (tools / "esptool.exe").write_bytes(b"fake tool; never executed")
        self.manifest = {"version": "0.4-test", "chip": "esp32s3", "flash_size": "16MB", "files": []}
        for name, offset, size in [("bootloader.bin", 0, 64), ("partitions.bin", 0x8000, 64),
                                   ("boot_app0.bin", 0xE000, 8192), ("firmware.bin", 0x10000, 128)]:
            content = bytes([len(name)]) * size
            (self.firmware / name).write_bytes(content)
            self.manifest["files"].append({"name": name, "offset": hex(offset), "sha256": hashlib.sha256(content).hexdigest()})
        self.save_manifest()
        self.events = []
        self.probe = "esptool v5.2.0\nChip type: ESP32-S3 (QFN56)\nDetected flash size: 16MB\n"
        self.probe_code = self.backup_code = self.write_code = 0
        self.backup_bytes = 32768
        self.run_calls, self.write_calls = [], []
        self.ports = patch.object(flash, "list_ports", return_value=[{"port": "COM9", "description": "CP210x"}]).start()
        self.run = patch.object(flash.subprocess, "run", side_effect=self.fake_run).start()
        self.popen = patch.object(flash.subprocess, "Popen", side_effect=self.fake_popen).start()
        self.addCleanup(patch.stopall)

    def save_manifest(self):
        (self.firmware / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def fake_run(self, args, **kwargs):
        self.run_calls.append(list(args))
        self.assertNotIn("shell", kwargs)
        if "flash-id" in args:
            return subprocess.CompletedProcess(args, self.probe_code, self.probe, "")
        self.assertIn("read-flash", args)
        if self.backup_code == 0:
            Path(args[-1]).write_bytes(b"\0" * self.backup_bytes)
        return subprocess.CompletedProcess(args, self.backup_code, "Read settings backup.\n", "")

    def fake_popen(self, args, **kwargs):
        self.write_calls.append(list(args))
        self.assertNotIn("shell", kwargs)
        code = self.write_code

        class Process:
            stdout = io.StringIO("Writing at 0x00010000 (50 %)\nHash of data verified.\n")

            def wait(self):
                return code

        return Process()

    def flash(self, port="COM9", confirmed=True):
        return flash.flash_robot(self.root, port, confirmed, self.events.append)

    def assert_not_started(self, result):
        self.assertFalse(result["ok"])
        self.run.assert_not_called()
        self.popen.assert_not_called()

    def test_explicit_la064_confirmation_is_required(self):
        for value in (False, None, "yes", 1):
            with self.subTest(value=value):
                self.assert_not_started(self.flash(confirmed=value))

    def test_port_must_be_strict_and_currently_enumerated(self):
        for port in ("COM0", "COM9 & whoami", "COM9\n", "COM10", "../COM9", None):
            with self.subTest(port=port):
                self.assert_not_started(self.flash(port=port))

    def test_corrupt_image_stops_before_probe(self):
        (self.firmware / "firmware.bin").write_bytes(b"changed")
        self.assert_not_started(self.flash())

    def test_duplicate_or_unsafe_offsets_stop_before_probe(self):
        for offset in ("0x9000", "0x8000", True, "oops"):
            with self.subTest(offset=offset):
                self.manifest["files"][-1]["offset"] = offset
                self.save_manifest()
                self.assert_not_started(self.flash())

    def test_oversize_image_cannot_overlap_nvs(self):
        entry = self.manifest["files"][1]
        data = b"x" * 4097
        (self.firmware / entry["name"]).write_bytes(data)
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        self.save_manifest()
        self.assert_not_started(self.flash())

    def test_merged_images_and_path_traversal_are_refused(self):
        for name in ("merged.bin", "Franky.ino.merged.bin", "../outside.bin", "..\\outside.bin", "C:other.bin"):
            with self.subTest(name=name):
                self.manifest["files"][-1]["name"] = name
                self.save_manifest()
                self.assert_not_started(self.flash())

    def test_wrong_bundle_target_is_refused(self):
        self.manifest["chip"] = "esp32c3"
        self.save_manifest()
        self.assert_not_started(self.flash())

    def test_probe_failure_stops_before_backup_and_write(self):
        self.probe_code = 2
        result = self.flash()
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "probe")
        self.assertEqual(len(self.run_calls), 1)
        self.popen.assert_not_called()

    def test_probe_timeout_does_not_start_backup_or_write(self):
        self.run.side_effect = subprocess.TimeoutExpired("mock esptool", 60)
        result = self.flash()
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "probe")
        self.assertIn("did not respond", result["message"])
        self.popen.assert_not_called()

    def test_wrong_or_unidentified_chip_stops_before_backup(self):
        for chip in ("ESP32-C3", "ESP32", "unknown"):
            with self.subTest(chip=chip):
                self.probe = f"Chip type: {chip}\nDetected flash size: 16MB\n"
                result = self.flash()
                self.assertFalse(result["ok"])
                self.assertEqual(result["stage"], "probe")
                self.assertNotIn("backup", result)
                self.popen.assert_not_called()

    def test_wrong_or_missing_flash_size_stops_before_backup(self):
        for size in ("8MB", "32MB", "16KB", "unknown"):
            with self.subTest(size=size):
                self.probe = f"Chip is ESP32-S3 (revision v0.2)\nDetected flash size: {size}\n"
                result = self.flash()
                self.assertFalse(result["ok"])
                self.assertEqual(result["stage"], "probe")
                self.popen.assert_not_called()

    def test_failed_or_incomplete_backup_prevents_write(self):
        for code, size in ((1, 32768), (0, 32767)):
            with self.subTest(code=code, size=size):
                self.backup_code, self.backup_bytes = code, size
                result = self.flash()
                self.assertFalse(result["ok"])
                self.assertEqual(result["stage"], "backup")
                self.assertNotIn("backup", result)
                self.popen.assert_not_called()

    def test_bundle_changes_during_backup_prevent_write(self):
        original_run = self.fake_run

        def change_after_backup(args, **kwargs):
            result = original_run(args, **kwargs)
            if "read-flash" in args:
                (self.firmware / "firmware.bin").write_bytes(b"changed during backup")
            return result

        self.run.side_effect = change_after_backup
        result = self.flash()
        self.assertFalse(result["ok"])
        self.assertTrue(Path(result["backup"]).is_file())
        self.popen.assert_not_called()

    def test_write_failure_retains_private_settings_backup(self):
        self.write_code = 2
        result = self.flash()
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "write")
        self.assertEqual(Path(result["backup"]).stat().st_size, 32768)
        self.assertEqual(len(self.write_calls), 1)

    def test_success_uses_exact_regions_and_never_erases_all(self):
        result = self.flash()
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "0.4-test")
        backup = Path(result["backup"])
        self.assertTrue(backup.is_relative_to(self.root / "private-backups"))
        self.assertEqual(backup.stat().st_size, 32768)
        probe, read = self.run_calls
        self.assertEqual(probe[-1], "flash-id")
        self.assertEqual(read[-4:-1], ["read-flash", "0x8000", "0x8000"])
        write = self.write_calls[0]
        self.assertEqual(write[-8::2], ["0x0", "0x8000", "0xe000", "0x10000"])
        self.assertEqual([Path(p).name for p in write[-7::2]],
                         ["bootloader.bin", "partitions.bin", "boot_app0.bin", "firmware.bin"])
        for args in [probe, read, write]:
            self.assertEqual(args[args.index("--port") + 1], "COM9")
            self.assertEqual(args[args.index("--baud") + 1], "115200")
            self.assertEqual(args[args.index("--chip") + 1], "esp32s3")
            self.assertFalse({"--erase-all", "-e", "erase-flash", "--force"}.intersection(args))
        self.assertEqual(self.events[-1]["percent"], 100)
        self.assertTrue(all(event["type"] == "progress" for event in self.events))
        percentages = [event["percent"] for event in self.events if "percent" in event]
        self.assertEqual(percentages, sorted(percentages))

    def test_gui_callback_failure_does_not_abort_write(self):
        def closed_gui(_):
            raise RuntimeError("window closed")

        result = flash.flash_robot(self.root, "COM9", True, closed_gui)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.write_calls), 1)

    def test_backup_symlink_outside_installation_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="franky-outside-") as outside:
            try:
                (self.root / "private-backups").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Creating symlinks is unavailable on this machine")
            result = self.flash()
            self.assertFalse(result["ok"])
            self.assertEqual(result["stage"], "backup")
            self.assertEqual(len(self.run_calls), 1)
            self.popen.assert_not_called()


class PortTests(unittest.TestCase):
    def test_port_listing_uses_registry_authority_and_sorts_numerically(self):
        with patch.object(flash, "_registry_ports", return_value={"COM10", "COM9"}), \
             patch.object(flash, "_descriptions", return_value={"COM9": "CP210x", "COM99": "stale"}):
            self.assertEqual(flash.list_ports(), [
                {"port": "COM9", "description": "CP210x"},
                {"port": "COM10", "description": "Serial device"},
            ])

    def test_driver_help_is_official_url_only(self):
        self.assertEqual(flash.driver_help(), "https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers")

    def test_progress_removes_terminal_controls(self):
        self.assertEqual(flash._safe_line("\x1b[31mWriting\x1b[0m\r\n\x07"), "Writing")


if __name__ == "__main__":
    unittest.main()
