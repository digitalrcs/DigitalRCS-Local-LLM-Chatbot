"""Advertised LAN addresses do not alter provider settings or server binding."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import host_config
import server
from settings import load_settings, save_settings, save_public_bridge_url, validate_public_bridge_url


class HostConfigTests(unittest.TestCase):
    def test_accepts_empty_or_canonical_ipv4_and_dns_origins(self):
        for given, expected in [
            ("", ""), ("  ", ""),
            ("http://192.168.5.250:8766/", "http://192.168.5.250:8766"),
            ("http://AI-SERVER:8766", "http://ai-server:8766"),
            ("http://ai-server.home.arpa:8766", "http://ai-server.home.arpa:8766"),
        ]:
            with self.subTest(given=given):
                self.assertEqual(validate_public_bridge_url(given), expected)

    def test_rejects_unusable_or_secret_bearing_addresses(self):
        for value in [None, 123, "https://server:8766", "http://server", "http://server:80",
                      "http://user:secret@server:8766", "http://@server:8766",
                      "http://server:8766/v1", "http://server:8766//", "http://server:8766?",
                      "http://server:8766?token=synthetic", "http://server:8766#",
                      "http://local\nhost:8766", "http://server:bad", "http://localhost:8766",
                      "http://LOCALHOST.:8766", "http://foo.localhost:8766", "http://127.0.0.1:8766",
                      "http://127.2.3.4:8766", "http://0.0.0.0:8766", "http://127.1:8766",
                      "http://2130706433:8766", "http://0177.0.0.1:8766", "http://0x7f.0.0.1:8766",
                      "http://0x7f000001:8766", "http://[::1]:8766", "http://[::]:8766",
                      "http://[::ffff:127.0.0.1]:8766", "http://[fd00::1]:8766",
                      "http://bad_host:8766", "http://-host:8766", "http://host..lan:8766",
                      "http://" + "a." * 70 + "lan:8766"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_public_bridge_url(value)

    def test_address_edit_preserves_provider_and_all_other_saved_fields(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "config.json"
            before = {"provider": "openrouter", "model": "openrouter/free", "lm_studio_model": "local-chat",
                      "lm_studio_url": "http://127.0.0.1:1234/v1", "max_output_tokens": 384, "custom": "retained"}
            path.write_text(json.dumps(before), encoding="utf-8")
            save_public_bridge_url("http://192.168.5.250:8766/", path)
            expected = {**before, "public_bridge_url": "http://192.168.5.250:8766"}
            self.assertEqual(json.loads(path.read_text()), expected)
            self.assertEqual(load_settings(path)["public_bridge_url"], expected["public_bridge_url"])
            with self.assertRaises(ValueError):
                save_public_bridge_url("http://localhost:8766", path)
            self.assertEqual(json.loads(path.read_text()), expected)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_provider_changes_preserve_saved_address_without_persisting_env_override(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "config.json"
            save_settings("http://127.0.0.1:1234/v1", "local-chat", path)
            save_public_bridge_url("http://192.168.5.250:8766", path)
            with patch.dict(os.environ, {"BRIDGE_PUBLIC_URL": "http://other-server:8766"}):
                self.assertEqual(load_settings(path)["public_bridge_url"], "http://other-server:8766")
                save_settings("ignored", "openrouter/free", path, provider="openrouter")
            cfg = load_settings(path)
            self.assertEqual(cfg["provider"], "openrouter")
            self.assertEqual(cfg["model"], "openrouter/free")
            self.assertEqual(cfg["lm_studio_model"], "local-chat")
            self.assertEqual(cfg["public_bridge_url"], "http://192.168.5.250:8766")
            with patch.dict(os.environ, {"BRIDGE_PUBLIC_URL": "http://localhost:8766"}), self.assertRaises(ValueError):
                load_settings(path)

    def test_cli_show_set_clear_and_no_configuration(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            path = Path(folder) / "config.json"
            self.assertEqual(host_config.main(["--show"], path), 1)
            self.assertFalse(path.exists())
            save_settings("http://127.0.0.1:1234/v1", "local-chat", path)
            before = path.read_bytes()
            self.assertEqual(host_config.main(["--show"], path), 0)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(host_config.main(["--url", "http://192.168.5.250:8766"], path), 0)
            self.assertEqual(load_settings(path)["public_bridge_url"], "http://192.168.5.250:8766")
            self.assertEqual(host_config.main(["--clear"], path), 0)
            self.assertEqual(load_settings(path)["public_bridge_url"], "")

    def test_voices_and_health_expose_only_selected_safe_address_fields(self):
        settings = {"provider": "lmstudio", "lm_studio_url": "http://127.0.0.1:1234/v1",
                    "public_bridge_url": "http://192.168.5.250:8766", "private_test_field": "do-not-expose"}
        with patch.object(server, "_settings", settings):
            client = TestClient(server.app)
            for route in ("/voices", "/health"):
                result = client.get(route).json()
                self.assertEqual(result["public_bridge_url"], settings["public_bridge_url"])
                self.assertEqual(result["lm_studio_url"], settings["lm_studio_url"])
                self.assertNotIn("private_test_field", result)
                self.assertNotIn("do-not-expose", str(result))


if __name__ == "__main__":
    unittest.main()
