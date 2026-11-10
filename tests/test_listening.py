"""Wake and pause boundaries; no real model or provider needed."""
import io
import unittest
from unittest.mock import patch
from starlette.datastructures import UploadFile
from fastapi.testclient import TestClient
import server
from listening import is_wake, is_pause


class ListeningTests(unittest.TestCase):
    def test_exact_wake_phrase(self):
        for text in ['Hello, Franky!', 'HEY   FRANKIE', 'hello frankie', 'hey franky']:
            self.assertTrue(is_wake(text), text)
        for text in ['', 'hello', 'franky', 'hello franky please', 'hi hello franky',
                     'franky hello', 'hello franky hello frankie', 'say hello franky', 'hello franky what time is it']:
            self.assertFalse(is_wake(text), text)

    def test_pause_is_not_a_substring(self):
        for text in ['Stop listening.', 'Frankie, go to sleep, please!', 'franky stop listening please', 'pause listening']:
            self.assertTrue(is_pause(text), text)
        for text in ['', 'go to sleep now', 'stop listen', 'stop listening to music', 'do not stop listening']:
            self.assertFalse(is_pause(text), text)

    def test_background_speech_never_reaches_chat_or_control_parser(self):
        with patch.object(server, 'recognize', return_value='set volume to zero'), \
             patch.object(server, 'generate_reply') as chat, patch.object(server, 'parse_control') as control:
            self.assertEqual(server.wake(UploadFile(file=io.BytesIO())), {'wake': False, 'pause': False})
            chat.assert_not_called(); control.assert_not_called()

    def test_wake_returns_no_background_transcript(self):
        with patch.object(server, 'recognize', return_value='Hello Franky'):
            self.assertEqual(server.wake(UploadFile(file=io.BytesIO())), {'wake': True, 'pause': False})

    def test_pause_also_works_without_waking_first(self):
        with patch.object(server, 'recognize', return_value='stop listening'):
            self.assertEqual(server.wake(UploadFile(file=io.BytesIO())), {'wake': False, 'pause': True})

    def test_transcription_pause_metadata_and_route(self):
        with patch.object(server, 'recognize', return_value='stop listening'):
            response = TestClient(server.app).post('/v1/audio/transcriptions', files={'file': ('test.wav', b'test')})
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()['pause'], True)

    def test_cues_cache_per_voice(self):
        server.cached_cue.cache_clear()
        with patch('neural_voice.synthesize', return_value=b'\0\0') as synth:
            server.cached_cue('thinking', 'kokoro', 'am_liam')
            server.cached_cue('thinking', 'kokoro', 'am_liam')
            server.cached_cue('thinking', 'kokoro', 'am_adam')
            self.assertEqual(synth.call_count, 2)
        server.cached_cue.cache_clear()

    def test_cue_rejects_arbitrary_text(self):
        response = TestClient(server.app).post('/v1/audio/cue', json={'kind': 'arbitrary'})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
