"""Installer asset reruns retain source provenance without stale model/tool records."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "installer_assets", Path(__file__).resolve().parents[1] / "scripts/prepare-installer-assets.py"
)
assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assets)


class InstallerAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.manifest = self.directory / "assets.json"

    def source(self):
        name = "PyAV-18.1.0-build-source.zip"
        archive = self.directory / name
        archive.write_bytes(b"synthetic source archive")
        return {"name": name, "sha256": assets.sha(archive), "url": "https://example.org/source.zip",
                "license": "test attribution", "revision": "pinned-test-revision"}

    def write_records(self, records):
        self.manifest.write_text(json.dumps({"assets": records}), encoding="utf-8")

    def test_first_run_has_no_retained_records(self):
        self.assertEqual(assets.preserved_source_assets(self.directory), [])

    def test_verified_sources_keep_metadata_without_old_models_or_tools(self):
        source = self.source()
        self.write_records([source, {"name": "whisper-base.en", "files": [{"name": "stale.bin"}]},
                            {"name": "vc_redist.x64.exe", "sha256": "old"},
                            {"name": "Franky-0.4.0-firmware-sources.zip", "sha256": "superseded"}])
        self.assertEqual(assets.preserved_source_assets(self.directory), [source])

    def test_missing_or_changed_source_fails_without_altering_manifest(self):
        source = self.source()
        self.write_records([source])
        before = self.manifest.read_bytes()
        archive = self.directory / source["name"]
        archive.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            assets.preserved_source_assets(self.directory)
        archive.unlink()
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            assets.preserved_source_assets(self.directory)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_duplicate_source_record_is_rejected(self):
        source = self.source()
        self.write_records([source, dict(source)])
        with self.assertRaisesRegex(ValueError, "Duplicate curated"):
            assets.preserved_source_assets(self.directory)


if __name__ == "__main__":
    unittest.main()
