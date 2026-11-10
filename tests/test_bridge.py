"""Behavior checks; no model requests or downloads needed."""
import io
import unittest
import wave
from unittest.mock import patch, Mock
from fastapi import HTTPException
from starlette.datastructures import UploadFile
import server

class BridgeTests(unittest.TestCase):
    def test_rejects_non_wav(self):
        with self.assertRaises(HTTPException) as e:
            server.transcribe(UploadFile(file=io.BytesIO(b'not audio')))
        self.assertEqual(e.exception.status_code, 400)

    def test_rejects_wrong_sample_rate(self):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b'\0' * 4800)
        with self.assertRaises(HTTPException) as e:
            server.transcribe(UploadFile(file=io.BytesIO(buf.getvalue())))
        self.assertEqual(e.exception.status_code, 400)

    def reply(self, content):
        response = Mock()
        response.json.return_value = {'choices': [{'message': {'content': content}}]}
        with patch.object(server, "LM_MODEL", "test-model"), patch.object(server.requests, 'post', return_value=response):
            return server.chat(server.Chat(messages=[server.Message(role='user', content='Hello')]))

    def test_removes_reasoning(self):
        self.assertEqual(self.reply('<think>private reasoning</think> Hello!')['choices'][0]['message']['content'], 'Hello!')

    def test_rejects_empty_and_incomplete_answers(self):
        for answer in ('', None, '<think>unfinished', '<think>only reasoning</think>'):
            with self.subTest(answer=answer), self.assertRaises(HTTPException) as e:
                self.reply(answer)
            self.assertEqual(e.exception.status_code, 502)

if __name__ == '__main__':
    unittest.main()
