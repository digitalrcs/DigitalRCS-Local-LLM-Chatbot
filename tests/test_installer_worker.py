import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "installer"))
import worker


class InstallerWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "bridge").mkdir()
        (self.root / "bridge/.secrets").mkdir()
        self.worker = worker.Worker(self.root)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.key_root = patch("credential_store.ROOT", self.root / "bridge/.secrets")
        self.key_root.start()
        self.addCleanup(self.key_root.stop)

    def request(self, **changes):
        result = {"provider": "lmstudio", "base_url": "http://127.0.0.1:1234/v1", "model": "test-model", "key": ""}
        result.update(changes)
        return result

    def test_cloud_catalog_requires_explicit_consent(self):
        with patch("providers.list_models") as models:
            with self.assertRaises(worker.SetupError):
                self.worker.models(self.request(provider="openrouter"))
            models.assert_not_called()
        self.assertFalse(self.worker.config.exists())

    def test_cloud_url_fixed_and_temporary_key_restored(self):
        os.environ["GEMINI_API_KEY"] = "original"
        req = self.request(provider="gemini", base_url="http://untrusted.example/v1", key="replacement", online_consent=True)
        with self.worker.provider(req) as config:
            self.assertEqual(config["base_url"], "https://generativelanguage.googleapis.com/v1beta/openai")
            self.assertEqual(os.environ["GEMINI_API_KEY"], "replacement")
        self.assertEqual(os.environ["GEMINI_API_KEY"], "original")

    def test_temporary_key_removed_even_after_failure(self):
        with self.assertRaises(RuntimeError):
            with self.worker.provider(self.request(key="temporary")):
                raise RuntimeError()
        self.assertNotIn("LM_STUDIO_TOKEN", os.environ)

    def test_unknown_model_never_saves_key_or_config(self):
        with patch.object(self.worker, "health", return_value=None), patch("providers.list_models", return_value=["valid"]), patch("credential_store.save_key") as save:
            with self.assertRaises(worker.SetupError):
                self.worker.save_provider(self.request(key="synthetic-key"))
        save.assert_not_called()
        self.assertFalse(self.worker.config.exists())

    def test_upgrade_preserves_budget_voice_and_local_provider(self):
        self.worker.config.write_text(json.dumps({"lm_studio_url": "http://192.168.1.2:1234/v1", "lm_studio_model": "old", "max_output_tokens": 1800, "disable_thinking": False, "public_bridge_url": "http://192.168.1.3:8766"}))
        voice = self.root / "bridge/voice_settings.json"
        voice.write_text('{"voice":"am_liam"}')
        with patch.object(self.worker, "health", return_value=None), patch("providers.list_models", return_value=["test-model"]):
            self.worker.save_provider(self.request())
        saved = json.loads(self.worker.config.read_text())
        self.assertEqual(saved["max_output_tokens"], 1800)
        self.assertFalse(saved["disable_thinking"])
        self.assertEqual(saved["public_bridge_url"], "http://192.168.1.3:8766")
        self.assertEqual(voice.read_text(), '{"voice":"am_liam"}')

    def test_save_failure_restores_encrypted_key_and_settings(self):
        before = '{"lm_studio_model":"old"}'
        self.worker.config.write_text(before)
        key_path = self.root / "bridge/.secrets/lmstudio.dpapi"
        key_path.write_bytes(b"old-encrypted-key")
        def replace_key(*args):
            key_path.write_bytes(b"new-encrypted-key")
        with patch.object(self.worker, "health", return_value=None), patch("providers.list_models", return_value=["test-model"]), patch("credential_store.save_key", side_effect=replace_key), patch("settings.save_settings", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                self.worker.save_provider(self.request(key="new-key"))
        self.assertEqual(key_path.read_bytes(), b"old-encrypted-key")
        self.assertEqual(self.worker.config.read_text(), before)

    def test_configuration_cannot_change_while_bridge_is_running(self):
        with patch.object(self.worker, "health", return_value={"status": "ok"}), patch("providers.list_models") as models:
            with self.assertRaises(worker.SetupError):
                self.worker.save_provider(self.request())
            models.assert_not_called()

    def test_existing_environment_key_cannot_silently_override_new_key(self):
        os.environ["LM_STUDIO_TOKEN"] = "old-value"
        with patch.object(self.worker, "health", return_value=None), patch("providers.list_models", return_value=["test-model"]), patch("credential_store.save_key") as save:
            with self.assertRaises(worker.SetupError):
                self.worker.save_provider(self.request(key="new-value"))
        save.assert_not_called()

    def test_invalid_local_url_never_fetches_models(self):
        with patch("providers.list_models") as models:
            with self.assertRaises(ValueError):
                self.worker.models(self.request(base_url="http://user:secret@host/v1"))
        models.assert_not_called()

    def test_unknown_action_cannot_invoke_arbitrary_method(self):
        with self.assertRaises(worker.SetupError):
            self.worker.dispatch({"action": "provider"})

    def test_generic_errors_never_expose_provider_secrets(self):
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO('{"action":"models","key":"private-example"}\n')), contextlib.redirect_stdout(output), patch.object(worker.Worker, "dispatch", side_effect=RuntimeError("Authorization: private-example")):
            self.assertEqual(worker.main(), 1)
        self.assertNotIn("private-example", output.getvalue())
        self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_start_requires_saved_model_without_spawning(self):
        with patch.object(self.worker, "health", return_value=None), patch("subprocess.Popen") as popen:
            with self.assertRaises(worker.SetupError):
                self.worker.start_bridge({})
        popen.assert_not_called()

    def test_stop_does_not_terminate_a_bridge_it_did_not_start(self):
        with patch.object(self.worker, "health", return_value={"status": "ok"}), patch("subprocess.run") as run:
            with self.assertRaises(worker.SetupError):
                self.worker.stop_bridge({})
        run.assert_not_called()

    def test_bad_shutdown_state_never_writes_request(self):
        self.worker.state.mkdir()
        (self.worker.state / "bridge-instance.json").write_text('{"token":"not-a-run-token"}')
        with self.assertRaises(worker.SetupError):
            self.worker.stop_bridge({})
        self.assertFalse((self.worker.state / "bridge-stop.json").exists())

    def test_models_ready_requires_both_listeners_and_voice_files(self):
        self.assertFalse(self.worker.models_ready())
        for relative in ("kokoro/kokoro-v1.0.onnx", "kokoro/voices-v1.0.bin", "whisper-base.en/model.bin", "whisper-tiny.en/model.bin"):
            path = self.root / "bridge/models" / relative
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(b"fixture")
        self.assertTrue(self.worker.models_ready())

    def test_saved_local_selection_wins_over_inherited_cloud_routing(self):
        os.environ.update(CHAT_PROVIDER="openai", CHAT_MODEL="cloud-model", LM_STUDIO_URL="http://elsewhere:1234/v1", BRIDGE_PUBLIC_URL="http://elsewhere:8766")
        with patch.object(self.worker, "health", return_value=None), patch("providers.list_models", return_value=["test-model"]):
            self.worker.save_provider(self.request())
        effective = self.worker.settings()
        self.assertEqual(effective["provider"], "lmstudio")
        self.assertEqual(effective["model"], "test-model")
        self.assertEqual(effective["base_url"], "http://127.0.0.1:1234/v1")
        self.assertEqual(os.environ["CHAT_PROVIDER"], "openai")  # Parent environment is not changed.

    def test_start_does_not_adopt_another_installation(self):
        with patch.object(self.worker, "health", return_value={"status": "ok", "instance_id": "other"}), patch("subprocess.Popen") as spawn:
            with self.assertRaises(worker.SetupError):
                self.worker.start_bridge({})
        spawn.assert_not_called()

    def test_ready_does_not_report_another_installations_checks(self):
        with patch.object(self.worker, "health", return_value={"status": "ok", "instance_id": "other"}), patch("requests.get") as get:
            with self.assertRaises(worker.SetupError):
                self.worker.check_ready({})
        get.assert_not_called()

    def test_stop_waits_for_process_after_listener_closes(self):
        self.worker.state.mkdir()
        state = {"token": "a" * 32, "instance_id": "b" * 32, "pid": 4242}
        path = self.worker.state / "bridge-instance.json"
        path.write_text(json.dumps(state))
        with patch.object(self.worker, "health", return_value=None), patch("worker.process_alive", return_value=True) as alive:
            def finish(_):
                path.unlink()
                alive.return_value = False
            with patch("worker.time.sleep", side_effect=finish) as wait:
                self.assertTrue(self.worker.stop_bridge({})["stopped"])
        wait.assert_called_once()

    def test_start_child_drops_shell_routing_overrides(self):
        self.worker.config.write_text('{"lm_studio_model":"saved-model"}')
        os.environ.update(CHAT_PROVIDER="openai", CHAT_MODEL="cloud-model", BRIDGE_PUBLIC_URL="http://elsewhere:8766")
        with patch.object(self.worker, "health", return_value=None), patch.object(self.worker, "owned_health", return_value=True), patch("worker.socket.socket") as sock, patch("subprocess.Popen") as spawn:
            self.worker.start_bridge({})
        environment = spawn.call_args.kwargs["env"]
        self.assertFalse(any(name in environment for name in worker.ROUTING_OVERRIDES))

    def test_bundled_whisper_load_avoids_hub_requests(self):
        import server
        directory = self.root / "models/whisper-tiny.en"
        directory.mkdir(parents=True)
        (directory / "model.bin").write_bytes(b"model")
        with patch.object(server, "ROOT", self.root), patch("faster_whisper.WhisperModel") as model:
            server.load_whisper("tiny.en")
        self.assertEqual(model.call_args.args, (str(directory),))
        self.assertTrue(model.call_args.kwargs["local_files_only"])


if __name__ == "__main__":
    unittest.main()
