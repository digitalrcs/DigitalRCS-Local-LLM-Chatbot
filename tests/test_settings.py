import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from settings import load_settings, save_settings, validate_url
from configure import available_models

class SettingsTests(unittest.TestCase):
    def test_round_trip_and_environment_override(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "config.json"
            self.assertEqual(load_settings(path)["lm_studio_model"], "")
            save_settings("http://localhost:1234/v1/", "my-chat", path)
            self.assertEqual(load_settings(path)["lm_studio_model"], "my-chat")
            with patch.dict(os.environ, {"LM_STUDIO_MODEL": "override"}):
                self.assertEqual(load_settings(path)["lm_studio_model"], "override")
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_voice_reply_defaults_and_preserved_switches(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "config.json"
            cfg = load_settings(path)
            self.assertEqual(cfg["max_output_tokens"], 1200)
            self.assertIs(cfg["disable_thinking"], True)
            path.write_text(json.dumps({"disable_thinking": False, "max_output_tokens": 256}))
            save_settings("http://localhost:1234/v1", "my-chat", path)
            self.assertIs(load_settings(path)["disable_thinking"], False)
            self.assertEqual(load_settings(path)["max_output_tokens"], 256)
            path.write_text(json.dumps({"disable_thinking": "no"}))
            with self.assertRaises(ValueError):
                load_settings(path)

    def test_invalid_addresses(self):
        for value in ("file:///v1", "http://localhost", "http://user:pass@localhost/v1", "http://localhost/v1?key=test", "http://localhost:bad/v1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_url(value)

    def test_invalid_config_and_empty_model(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "config.json"
            path.write_text("[]")
            with self.assertRaises(ValueError):
                load_settings(path)
            with self.assertRaises(ValueError):
                save_settings("http://localhost:1234/v1", " ", path)

    def test_lists_exact_model_identifiers(self):
        with patch("configure.requests.get") as get:
            get.return_value.status_code = 200
            get.return_value.json.return_value = {"data": [{"id": "my/exact-model"}, {"id": 42}]}
            self.assertEqual(available_models("http://localhost:1234/v1"), ["my/exact-model"])

if __name__ == "__main__":
    unittest.main()
