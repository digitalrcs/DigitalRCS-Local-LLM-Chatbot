"""Provider stream regressions using real Requests decoding and synthetic SSE."""
import io
import json
import threading
import unittest
from unittest.mock import Mock, patch

import requests
import providers


class ProviderStreamRegressionTests(unittest.TestCase):
    config = {"provider": "lmstudio", "base_url": "http://local-model:1234/v1",
              "model": "google/gemma-4-12b-qat", "max_output_tokens": 1200,
              "disable_thinking": True}

    @staticmethod
    def event(content=None, reason=None, **delta):
        if content is not None:
            delta["content"] = content
        return "data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": reason}]}, ensure_ascii=False)

    @staticmethod
    def response(lines):
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "text/event-stream"
        response.encoding = requests.utils.get_encoding_from_headers(response.headers)
        response.raw = io.BytesIO(("\n\n".join(lines) + "\n\n").encode("utf-8"))
        return response

    def test_utf8_without_charset_survives_real_requests_stream_decoding(self):
        expected = "Café déjà vu — it's 20°C."
        response = self.response([self.event(expected), "data: [DONE]"])
        with patch.object(providers.requests, "post", return_value=response), \
             patch.object(providers, "headers_for", return_value={}):
            self.assertEqual("".join(providers.stream_reply(self.config, [])), expected)
        self.assertTrue(response.raw.closed)

    def test_eof_after_partial_text_is_not_success(self):
        response = self.response([self.event("Only the beginning")])
        with patch.object(providers.requests, "post", return_value=response), \
             patch.object(providers, "headers_for", return_value={}):
            reply = providers.stream_reply(self.config, [])
            self.assertEqual(next(reply), "Only the beginning")
            with self.assertRaisesRegex(providers.ProviderError, "before the reply completed"):
                next(reply)

    def test_explicit_stop_can_end_a_stream_without_done_marker(self):
        response = self.response([self.event("A complete answer.", reason="stop")])
        with patch.object(providers.requests, "post", return_value=response), \
             patch.object(providers, "headers_for", return_value={}):
            self.assertEqual("".join(providers.stream_reply(self.config, [])), "A complete answer.")

    def test_reasoning_exhaustion_explains_output_budget(self):
        response = self.response([self.event(reasoning_content="Synthetic reasoning"),
                                  self.event(reason="length"), "data: [DONE]"])
        with patch.object(providers.requests, "post", return_value=response) as post, \
             patch.object(providers, "headers_for", return_value={}):
            with self.assertRaisesRegex(providers.ProviderError, "max_output_tokens"):
                list(providers.stream_reply(self.config, []))
            post.assert_called_once()

    def test_nonstream_output_limit_is_not_a_complete_answer(self):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "Unfinished"}, "finish_reason": "length"}]}
        with patch.object(providers.requests, "post", return_value=response), \
             patch.object(providers, "headers_for", return_value={}):
            with self.assertRaisesRegex(providers.ProviderError, "output limit"):
                providers.generate_reply(self.config, [])

    def test_stop_before_request_does_not_contact_provider(self):
        stop = threading.Event(); stop.set()
        with patch.object(providers.requests, "post") as post:
            self.assertEqual(list(providers.stream_reply(self.config, [], stop=stop)), [])
            post.assert_not_called()

    def test_stop_during_reasoning_closes_without_waiting_for_answer(self):
        stop = threading.Event()
        def lines(**kwargs):
            yield self.event(reasoning_content="Synthetic reasoning")
            stop.set()
            yield self.event(reasoning_content="Still reasoning")
            self.fail("Provider continued after cancellation")
        response = Mock(status_code=200)
        response.iter_lines.side_effect = lines
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(providers.requests, "post", return_value=response), \
             patch.object(providers, "headers_for", return_value={}):
            self.assertEqual(list(providers.stream_reply(self.config, [], stop=stop)), [])
        response.__exit__.assert_called_once()

    def test_usage_event_is_ignored_and_malformed_choices_are_safe_errors(self):
        self.assertEqual(providers.stream_delta('data: {"choices":[],"usage":{"total_tokens":12}}'), "")
        for value in [None, [], {"choices": [1]}, {"choices": [{"delta": "bad"}]}]:
            with self.subTest(value=value), self.assertRaises(providers.ProviderError):
                providers.stream_delta("data: " + json.dumps(value))


if __name__ == "__main__":
    unittest.main()
