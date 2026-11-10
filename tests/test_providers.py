import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import credential_store
import providers
from settings import load_settings, save_settings

class ProviderTests(unittest.TestCase):
    def config(self, provider):
        return {"provider": provider, "base_url": "http://local-model:1234/v1", "model": "openrouter/free" if provider == "openrouter" else "test-chat", "max_output_tokens": 1200}

    def test_default_is_local_and_switching_preserves_local_settings(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / "config.json"
            self.assertEqual(load_settings(path)["provider"], "lmstudio")
            save_settings("http://local-model:1234/v1", "local-chat", path)
            save_settings("ignored", "openrouter/free", path, "openrouter")
            cfg = load_settings(path)
            self.assertEqual(cfg["provider"], "openrouter")
            self.assertEqual(cfg["lm_studio_model"], "local-chat")
            self.assertEqual(cfg["base_url"], "https://openrouter.ai/api/v1")
            self.assertNotIn("key", path.read_text().lower())

    def test_openai_parses_text_after_reasoning_and_disables_storage(self):
        response = Mock(status_code=200)
        response.json.return_value = {"status": "completed", "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Hello, friend."}]}]}
        with patch.object(providers, "get_key", return_value="synthetic-test-key"), patch.object(providers.requests, "post", return_value=response) as post:
            self.assertEqual(providers.generate_reply(self.config("openai"), [{"role": "user", "content": "Hi"}]), "Hello, friend.")
            self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/responses")
            self.assertFalse(post.call_args.kwargs["json"]["store"])
            self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_no_fallback_after_rate_limit_and_no_remote_error_echo(self):
        response = Mock(status_code=429)
        response.text = "Sensitive upstream diagnostics must not be returned"
        with patch.object(providers, "get_key", return_value="synthetic-test-key"), patch.object(providers.requests, "post", return_value=response) as post:
            with self.assertRaisesRegex(providers.ProviderError, "rate limit") as error:
                providers.generate_reply(self.config("openrouter"), [{"role": "user", "content": "Hi"}])
            self.assertEqual(post.call_count, 1)
            self.assertNotIn("Sensitive", str(error.exception))

    def test_paid_openrouter_model_rejected_before_network(self):
        cfg = self.config("openrouter"); cfg["model"] = "paid/model"
        with patch.object(providers.requests, "post") as post:
            with self.assertRaises(ValueError): providers.generate_reply(cfg, [])
            post.assert_not_called()

    def test_missing_cloud_key_stops_request(self):
        with patch.object(providers, "get_key", return_value=""), patch.object(providers.requests, "post") as post:
            with self.assertRaisesRegex(providers.ProviderError, "key not configured"):
                providers.generate_reply(self.config("openai"), [])
            post.assert_not_called()

    def test_cloud_key_never_sent_to_local_server(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(credential_store, "ROOT", Path(folder)), patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-test-key"}, clear=True):
            self.assertEqual(providers.headers_for("lmstudio"), {})

    def test_gemini_fixed_https_endpoint_and_chat_contract(self):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "Hello."}}]}
        with patch.object(providers, "get_key", return_value="synthetic-test-key"), patch.object(providers.requests, "post", return_value=response) as post:
            self.assertEqual(providers.generate_reply(self.config("gemini"), []), "Hello.")
            self.assertEqual(post.call_args.args[0], "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")

    def test_incomplete_openai_reply_is_not_spoken(self):
        response = Mock(status_code=200)
        response.json.return_value = {"status": "incomplete", "output": []}
        with patch.object(providers, "get_key", return_value="synthetic-test-key"), patch.object(providers.requests, "post", return_value=response):
            with self.assertRaisesRegex(providers.ProviderError, "did not finish"):
                providers.generate_reply(self.config("openai"), [])

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI integration")
    def test_protected_key_round_trip_without_plaintext_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(credential_store, "ROOT", Path(folder)), patch.dict(os.environ, {}, clear=True):
            credential_store.save_key("openai", "synthetic-test-key")
            self.assertEqual(credential_store.get_key("openai"), "synthetic-test-key")
            self.assertNotIn(b"synthetic-test-key", (Path(folder) / "openai.dpapi").read_bytes())

if __name__ == "__main__": unittest.main()
