"""The setup launcher can distinguish saving, cancellation and failure."""
import contextlib
import io
import unittest
from unittest.mock import patch
import configure


class ConfigureTests(unittest.TestCase):
    def test_declining_online_provider_cancels_without_touching_existing_config(self):
        for previous in ("", "existing-model"):
            with self.subTest(previous=previous), contextlib.redirect_stdout(io.StringIO()), \
                 patch.object(configure, "load_settings", return_value={"model": previous}), \
                 patch("builtins.input", side_effect=["2", "n"]), \
                 patch.object(configure, "prepare_key") as keys, \
                 patch.object(configure, "list_models") as models, \
                 patch.object(configure, "save_settings") as save:
                self.assertEqual(configure.main(), 2)
                keys.assert_not_called()
                models.assert_not_called()
                save.assert_not_called()

    def test_success_returns_zero_only_after_saving(self):
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(configure, "load_settings", return_value={"lm_studio_url": "http://localhost:1234/v1"}), \
             patch("builtins.input", side_effect=["1", "", "1"]), \
             patch.object(configure, "list_models", return_value=["test-chat"]), \
             patch.object(configure, "save_settings") as save:
            self.assertEqual(configure.main(), 0)
            save.assert_called_once_with("http://localhost:1234/v1", "test-chat", provider="lmstudio")

    def test_failed_selection_returns_failure_without_saving(self):
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(configure, "load_settings", return_value={}), \
             patch("builtins.input", side_effect=["99", "n"]), \
             patch.object(configure, "save_settings") as save:
            self.assertEqual(configure.main(), 1)
            save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
