"""Streamed conversation: sentence splitting, reasoning removal, frames, endpoint."""
import json
import socket
import struct
import threading
import time
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import conversation
import providers
import server
from conversation import frame, split_sentences, stream_reply_frames
from providers import ReasoningFilter, stream_delta, voice_messages


def read_frames(data):
    """Decode a frame stream into a list of (type, payload) pairs."""
    frames, offset = [], 0
    while offset < len(data):
        kind = chr(data[offset])
        (length,) = struct.unpack_from("<I", data, offset + 1)
        frames.append((kind, data[offset + 5:offset + 5 + length]))
        offset += 5 + length
    return frames


def fake_voice(text):
    return text.encode("utf-8") * 2  # Even length, like PCM16.


class SentenceTests(unittest.TestCase):
    def test_splits_whole_sentences_and_keeps_the_rest(self):
        done, rest = split_sentences("Frogs are amphibians. They live near water! And they")
        self.assertEqual(done, ["Frogs are amphibians.", "They live near water!"])
        self.assertEqual(rest, "And they")

    def test_waits_for_the_next_sentence_to_start(self):
        self.assertEqual(split_sentences("It costs 3.50 dollars. ")[0], [])
        self.assertEqual(split_sentences("Ask Dr. Smith about it.")[0], [])

    def test_joins_very_short_sentences(self):
        done, rest = split_sentences("Hi. I am Franky the frog. Ok")
        self.assertEqual(done, ["Hi. I am Franky the frog."])
        self.assertEqual(rest, "Ok")

    def test_newline_ends_a_sentence(self):
        self.assertEqual(split_sentences("A list item without a stop\nNext")[0], ["A list item without a stop"])


class ReasoningTests(unittest.TestCase):
    def run_filter(self, text, size):
        f, out = ReasoningFilter(), []
        for i in range(0, len(text), size):
            out.append(f.feed(text[i:i + size]))
        out.append(f.finish())
        return "".join(out)

    def test_removes_reasoning_split_anywhere(self):
        text = "<think>secret plan</think>Hello there. <think>more</think>Bye."
        for size in range(1, len(text) + 1):
            with self.subTest(size=size):
                self.assertEqual(self.run_filter(text, size), "Hello there. Bye.")

    def test_unfinished_reasoning_is_never_spoken(self):
        self.assertEqual(self.run_filter("<think>still thinking", 3), "")

    def test_keeps_text_that_only_looks_like_a_tag(self):
        self.assertEqual(self.run_filter("a < b and c <th", 2), "a < b and c <th")

    def test_stray_closing_tag_is_removed(self):
        self.assertEqual(self.run_filter("</think>Answer.", 4), "Answer.")


class ProviderStreamTests(unittest.TestCase):
    config = {"provider": "lmstudio", "base_url": "http://local:1234/v1", "model": "Qwen3-8B",
              "max_output_tokens": 256, "disable_thinking": True}

    def test_no_think_only_for_qwen3_and_input_unchanged(self):
        messages = [{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Hi"}]
        result = voice_messages(self.config, messages)
        self.assertEqual(result[0]["content"], "Be brief. /no_think")
        self.assertEqual(messages[0]["content"], "Be brief.")
        self.assertEqual(voice_messages({**self.config, "model": "gemma-4-12b"}, messages), messages)
        self.assertEqual(voice_messages({**self.config, "disable_thinking": False}, messages), messages)

    def test_stream_delta(self):
        self.assertEqual(stream_delta('data: {"choices":[{"delta":{"content":"Hi"}}]}'), "Hi")
        self.assertEqual(stream_delta('data: {"choices":[{"delta":{"reasoning_content":"x"}}]}'), "")
        self.assertEqual(stream_delta(": keep-alive"), "")
        self.assertIsNone(stream_delta("data: [DONE]"))
        with self.assertRaises(providers.ProviderError):
            stream_delta("data: {broken")

    def test_stream_reply_reads_server_sent_events(self):
        lines = ['data: {"choices":[{"delta":{"content":"<think>x</think>"}}]}', "",
                 'data: {"choices":[{"delta":{"content":"Hello "}}]}',
                 'data: {"choices":[{"delta":{"content":"friend."}}]}', "data: [DONE]"]
        response = Mock(status_code=200)
        response.iter_lines.return_value = lines
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(providers.requests, "post", return_value=response) as post:
            self.assertEqual("".join(providers.stream_reply(self.config, [{"role": "user", "content": "Hi"}])), "Hello friend.")
        payload = post.call_args.kwargs["json"]
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["max_tokens"], 256)
        self.assertEqual(payload["messages"][0], {"role": "system", "content": "/no_think"})

    def test_reasoning_only_stream_is_an_error(self):
        response = Mock(status_code=200)
        response.iter_lines.return_value = ['data: {"choices":[{"delta":{"content":"<think>only"}}]}', 'data: [DONE]']
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(providers.requests, "post", return_value=response):
            with self.assertRaisesRegex(providers.ProviderError, "final answer"):
                list(providers.stream_reply(self.config, []))


class FrameTests(unittest.TestCase):
    def test_frame_layout(self):
        self.assertEqual(frame("E", {}), b"E\x02\x00\x00\x00{}")
        self.assertEqual(frame("T", "Hi"), b"T\x02\x00\x00\x00Hi")

    def test_text_frames_enforce_the_firmware_byte_limit(self):
        for kind in ("J", "T", "E"):
            with self.subTest(kind=kind):
                self.assertEqual(len(frame(kind, b"x" * 8192)), 8197)
                with self.assertRaises(ValueError):
                    frame(kind, b"x" * 8193)
        with self.assertRaises(ValueError):
            frame("H", b"x")

    def test_unicode_reply_fits_its_terminal_frame(self):
        reply = "界" * 1800
        frames = read_frames(b"".join(stream_reply_frames(iter([reply]), fake_voice)))
        self.assertEqual(json.loads(frames[-1][1]), {"reply": reply})
        self.assertTrue(all(len(payload) <= 8192 for kind, payload in frames if kind in {"J", "T", "E"}))

    def test_cue_then_sentences_then_reply(self):
        pieces = iter(["Frogs can jump far. ", "They also ", "swim well."])
        frames = read_frames(b"".join(stream_reply_frames(pieces, fake_voice, cue=b"\x01\x00")))
        self.assertEqual([k for k, _ in frames], ["C", "T", "P", "T", "P", "E"])
        self.assertEqual(frames[1][1], b"Frogs can jump far.")
        self.assertEqual(json.loads(frames[-1][1]), {"reply": "Frogs can jump far. They also swim well."})

    def test_provider_error_before_speech(self):
        def failing():
            raise providers.ProviderError("Provider unavailable or timed out. Check its connection and model.")
            yield ""  # pragma: no cover
        frames = read_frames(b"".join(stream_reply_frames(failing(), fake_voice)))
        self.assertEqual(frames[-1][0], "E")
        self.assertIn("Provider unavailable", json.loads(frames[-1][1])["error"])

    def test_voice_failure_reports_error(self):
        def broken(_):
            raise OSError("model file missing")
        frames = read_frames(b"".join(stream_reply_frames(iter(["One sentence here. "]), broken)))
        self.assertEqual(json.loads(frames[-1][1]), {"error": "Voice service unavailable"})

    def test_failures_after_speech_never_commit_a_successful_reply(self):
        def provider_failure():
            yield "First sentence here. Second sentence"
            raise providers.ProviderError("Provider unavailable")

        for pieces, voice in [
            (provider_failure(), fake_voice),
            (iter(["First sentence here. Second sentence here."]),
             Mock(side_effect=[b"\0\0", OSError("voice unavailable")])),
        ]:
            with self.subTest(voice=type(voice).__name__):
                frames = read_frames(b"".join(stream_reply_frames(pieces, voice)))
                end = json.loads(frames[-1][1])
                self.assertIn("error", end)
                self.assertNotIn("reply", end)
                self.assertEqual(end["partial_reply"], "First sentence here.")

    def test_waiting_for_speech_emits_empty_heartbeats_then_stops(self):
        release = threading.Event()

        def slow_voice(text):
            if not release.wait(3):
                raise TimeoutError("test voice was not released")
            return fake_voice(text)

        stream = stream_reply_frames(iter(["A complete sentence."]), slow_voice)
        try:
            for _ in range(2):
                started = time.monotonic()
                self.assertEqual(next(stream), b"H\0\0\0\0")
                self.assertLess(time.monotonic() - started, 1)
            release.set()
            frames = read_frames(b"".join(stream))
            self.assertEqual([kind for kind, _ in frames], ["T", "P", "E"])
        finally:
            release.set()
            stream.close()

    def test_queued_audio_is_bounded_and_cancellation_releases_workers(self):
        voice = Mock(side_effect=fake_voice)
        stop = threading.Event()
        existing = set(threading.enumerate())
        stream = stream_reply_frames(iter(["Another complete sentence. "] * 40), voice,
                                    stop=stop, cue=b"\0\0")
        self.assertEqual(next(stream)[0:1], b"C")
        workers = [worker for worker in threading.enumerate()
                   if worker not in existing and worker.name in {"franky-chat", "franky-voice"}]
        time.sleep(0.2)  # Leave the client idle while the bounded output fills.
        self.assertLessEqual(voice.call_count, 3)  # Two queued buffers, one pending put.
        stream.close()
        self.assertTrue(stop.is_set())
        calls = voice.call_count
        for worker in workers:
            worker.join(1)
            self.assertFalse(worker.is_alive())
        self.assertEqual(voice.call_count, calls)

    def test_closing_stream_stops_workers(self):
        started = threading.Event()

        def endless():
            started.set()
            while True:
                yield "More words keep coming. "
                time.sleep(0.01)
        stop = threading.Event()
        stream = stream_reply_frames(endless(), fake_voice, stop=stop)
        next(stream)
        stream.close()
        self.assertTrue(stop.is_set())

    def test_spoken_length_is_capped(self):
        long = iter(["This sentence is about forty characters. "] * 100)
        frames = read_frames(b"".join(stream_reply_frames(long, fake_voice)))
        end = json.loads(frames[-1][1])
        self.assertIn("error", end)
        self.assertNotIn("reply", end)
        self.assertLessEqual(len(end.get("partial_reply", "")), conversation.MAX_SPOKEN_CHARACTERS)


class ConverseEndpointTests(unittest.TestCase):
    def post(self, text, messages="[]"):
        with patch.object(server, "recognize", return_value=text), \
             patch.object(server, "stream_reply", return_value=iter(["Frogs are great. ", "Really!"])) as provider, \
             patch.object(server, "synthesize", side_effect=fake_voice), \
             patch.object(server, "LM_MODEL", "test-model"):
            response = TestClient(server.app).post("/v1/converse", files={"file": ("q.wav", b"x")}, data={"messages": messages})
        return response, provider

    def test_question_streams_metadata_cue_and_speech(self):
        history = json.dumps([{"role": "system", "content": "Be brief."}])
        response, provider = self.post("Tell me about frogs", history)
        self.assertEqual(response.status_code, 200)
        frames = read_frames(response.content)
        self.assertEqual([k for k, _ in frames], ["J", "C", "T", "P", "T", "P", "E"])
        self.assertEqual(json.loads(frames[0][1])["text"], "Tell me about frogs")
        sent = provider.call_args.args[1]
        self.assertEqual(sent[-1], {"role": "user", "content": "Tell me about frogs"})
        self.assertEqual(sent[0]["content"], "Be brief.")

    def test_local_phrases_never_call_the_provider(self):
        for text, kinds in [("stop listening", ["J", "C", "E"]), ("thank you", ["J", "T", "P", "E"]),
                            ("volume up", ["J", "E"]), ("", ["J", "E"])]:
            with self.subTest(text=text), patch.object(server, "cached_cue", return_value=b"\0\0"):
                response, provider = self.post(text)
                self.assertEqual([k for k, _ in read_frames(response.content)], kinds)
                provider.assert_not_called()

    def test_rejects_bad_history(self):
        for bad in ["not json", json.dumps([{"role": "tool", "content": "x"}]), json.dumps([{"role": "user", "content": "x"}] * 16)]:
            with self.subTest(bad=bad[:20]):
                self.assertEqual(self.post("hi", bad)[0].status_code, 400)

    def test_local_cue_failures_end_with_an_error_frame(self):
        for text in ("thank you", "stop listening"):
            with self.subTest(text=text), patch.object(server, "cached_cue", side_effect=OSError("missing model")):
                response, provider = self.post(text)
                self.assertEqual(response.status_code, 200)
                frames = read_frames(response.content)
                self.assertEqual(frames[-1][0], "E")
                self.assertIn("error", json.loads(frames[-1][1]))
                self.assertNotIn("reply", json.loads(frames[-1][1]))
                provider.assert_not_called()

    def test_rejects_oversized_metadata_before_starting_the_stream(self):
        response, provider = self.post("界" * 3000)
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()


class WakeModelTests(unittest.TestCase):
    def test_wake_falls_back_to_question_model(self):
        main = object()
        with patch.object(server, "_wake_whisper", None), patch.object(server, "WAKE_STT_MODEL", "tiny.en"), \
             patch.object(server, "load_whisper", side_effect=OSError("offline")), \
             patch.object(server, "recognizer", return_value=main):
            self.assertEqual(server.wake_recognizer(), (main, server._lock))

    def test_wake_uses_its_own_lock(self):
        small = object()
        with patch.object(server, "_wake_whisper", small), patch.object(server, "WAKE_STT_MODEL", "tiny.en"):
            self.assertEqual(server.wake_recognizer(), (small, server._wake_lock))


class Http10Tests(unittest.TestCase):
    """The robot reads the stream with HTTP/1.0, so the reply must not be chunked."""

    def test_streamed_reply_is_plain_bytes_over_http10(self):
        import uvicorn
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        config = uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
        web = uvicorn.Server(config)
        with patch.object(server, "recognize", return_value="Tell me about frogs"), \
             patch.object(server, "stream_reply", return_value=iter(["Frogs are great. ", "Really!"])), \
             patch.object(server, "synthesize", side_effect=fake_voice), \
             patch.object(server, "LM_MODEL", "test-model"):
            thread = threading.Thread(target=web.run, daemon=True)
            thread.start()
            for _ in range(100):
                if web.started:
                    break
                time.sleep(0.05)
            boundary = "b"
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"q.wav\"\r\n"
                    f"Content-Type: audio/wav\r\n\r\nx\r\n--{boundary}--\r\n").encode()
            request = (f"POST /v1/converse HTTP/1.0\r\nHost: test\r\nContent-Type: multipart/form-data; boundary={boundary}\r\n"
                       f"Content-Length: {len(body)}\r\n\r\n").encode() + body
            with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
                client.sendall(request)
                data = b""
                while chunk := client.recv(65536):
                    data += chunk
            web.should_exit = True
            thread.join(5)
        head, _, payload = data.partition(b"\r\n\r\n")
        self.assertIn(b" 200 ", head.split(b"\r\n")[0])
        self.assertNotIn(b"chunked", head.lower())
        self.assertEqual([k for k, _ in read_frames(payload)], ["J", "C", "T", "P", "T", "P", "E"])

    def test_http_disconnect_cancels_workers_and_closes_provider(self):
        import uvicorn
        closed, stops, produced = threading.Event(), [], []

        def fake_provider(config, messages, stop=None):
            stops.append(stop)
            try:
                for i in range(200):
                    if stop.wait(0.02):
                        return
                    produced.append(i)
                    yield "Another complete sentence. "
            finally:
                closed.set()

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        web = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port,
                                           log_level="warning", lifespan="off"))
        with patch.object(server, "recognize", return_value="Tell me about frogs"), \
             patch.object(server, "stream_reply", side_effect=fake_provider), \
             patch.object(server, "synthesize", side_effect=fake_voice), \
             patch.object(server, "cached_cue", return_value=b"\0\0"):
            thread = threading.Thread(target=web.run, daemon=True)
            thread.start()
            try:
                for _ in range(100):
                    if web.started:
                        break
                    time.sleep(0.01)
                self.assertTrue(web.started)
                body = (b'--b\r\nContent-Disposition: form-data; name="file"; filename="q.wav"\r\n'
                        b'Content-Type: audio/wav\r\n\r\nx\r\n--b--\r\n')
                request = (f"POST /v1/converse HTTP/1.0\r\nHost: test\r\n"
                           f"Content-Type: multipart/form-data; boundary=b\r\n"
                           f"Content-Length: {len(body)}\r\n\r\n").encode() + body
                with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                    client.sendall(request)
                    data = b""
                    while b"C\x02\x00\x00\x00\0\0" not in data:
                        chunk = client.recv(65536)
                        self.assertTrue(chunk)
                        data += chunk
                self.assertTrue(closed.wait(2), "Provider did not close after the client disconnected")
                self.assertTrue(stops[0].is_set())
                self.assertLess(len(produced), 10)
            finally:
                web.should_exit = True
                thread.join(3)


if __name__ == "__main__":
    unittest.main()
