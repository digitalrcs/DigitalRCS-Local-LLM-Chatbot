"""Readiness remains responsive without inference, secrets or real providers."""
import threading
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from readiness import ReadinessMonitor
import neural_voice
import providers
import server


class ReadinessTests(unittest.TestCase):
    def test_progress_failure_and_recovery_are_cached_and_safe(self):
        probe = Mock(side_effect=[RuntimeError("private upstream detail"), "Model loaded"])
        monitor = ReadinessMonitor({"recognition": (probe, "Repair speech files")})
        self.assertEqual(monitor.snapshot()["status"], "starting")
        self.assertFalse(monitor.check_once("recognition"))
        result = monitor.snapshot()
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["checks"]["recognition"]["message"], "Repair speech files")
        self.assertNotIn("private", str(result))
        self.assertTrue(monitor.check_once("recognition"))
        self.assertEqual(monitor.snapshot()["status"], "ready")
        result["checks"]["recognition"]["status"] = "modified"
        self.assertEqual(monitor.snapshot()["checks"]["recognition"]["status"], "ready")

    def test_loading_workers_do_not_block_dashboard_or_repeat_probes_on_get(self):
        entered, release = threading.Event(), threading.Event()

        def slow_probe():
            entered.set()
            release.wait(2)
            return "Loaded"

        probe = Mock(side_effect=slow_probe)
        monitor = ReadinessMonitor({"recognition": (probe, "Unavailable")})
        monitor.start()
        try:
            self.assertTrue(entered.wait(1))
            with patch.object(server, "_readiness", monitor):
                client = TestClient(server.app)
                for _ in range(3):
                    response = client.get("/ready")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["status"], "starting")
            self.assertEqual(probe.call_count, 1)
        finally:
            monitor.stop()
            release.set()
            for worker in monitor._threads:
                worker.join(1)

    def test_chat_rechecks_while_successful_speech_model_is_loaded_once(self):
        twice = threading.Event()
        calls = 0

        def chat_probe():
            nonlocal calls
            calls += 1
            if calls >= 2:
                twice.set()
            return "Listed"

        voice = Mock(return_value="Loaded")
        monitor = ReadinessMonitor({"voice": (voice, "Unavailable"), "chat": (chat_probe, "Unavailable")}, interval=0.01)
        monitor.start()
        try:
            self.assertTrue(twice.wait(1))
            self.assertEqual(voice.call_count, 1)
        finally:
            monitor.stop()
            for worker in monitor._threads:
                worker.join(1)

    def test_lifespan_starts_and_stops_background_monitor(self):
        monitor = Mock()
        monitor.snapshot.return_value = {"status": "starting", "checks": {}}
        with patch.object(server, "_readiness", None), patch.object(server, "make_readiness", return_value=monitor):
            with TestClient(server.app) as client:
                monitor.start.assert_called_once()
                self.assertEqual(client.get("/ready").status_code, 200)
                self.assertEqual(client.get("/health").json()["status"], "ok")
            monitor.stop.assert_called_once()

    def test_chat_checks_listing_only_with_short_timeout(self):
        response = Mock(status_code=200)
        response.json.return_value = {"data": [{"id": "test-chat"}]}
        with patch.object(server, "LM_MODEL", "test-chat"), \
             patch.object(server, "_settings", {"provider": "lmstudio"}), \
             patch.object(providers, "get_key", return_value=""), \
             patch.object(providers.requests, "get", return_value=response) as get, \
             patch.object(providers.requests, "post") as post:
            self.assertIn("has not been tested", server.check_chat())
            self.assertEqual(get.call_args.kwargs["timeout"], (2, 4))
            self.assertFalse(get.call_args.kwargs["allow_redirects"])
            post.assert_not_called()

    def test_cloud_check_does_not_claim_quota_or_generation_access(self):
        with patch.object(server, "LM_MODEL", "test-chat"), \
             patch.object(server, "_settings", {"provider": "openai"}), \
             patch.object(server, "list_models", return_value=["test-chat"]):
            self.assertIn("quota and billing have not been tested", server.check_chat())

    def test_missing_or_unlisted_model_is_degraded(self):
        with patch.object(server, "LM_MODEL", ""), patch.object(server, "list_models") as models:
            with self.assertRaises(ValueError):
                server.check_chat()
            models.assert_not_called()
        with patch.object(server, "LM_MODEL", "missing"), patch.object(server, "list_models", return_value=[]):
            monitor = server.make_readiness()
            self.assertFalse(monitor.check_once("chat"))
            self.assertEqual(monitor.snapshot()["status"], "degraded")

    def test_voice_preparation_does_not_generate_audio(self):
        model = Mock()
        with patch.object(server, "TTS_ENGINE", "kokoro"), patch.object(neural_voice, "_model", model):
            self.assertIn("loaded", server.prepare_voice())
            model.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
