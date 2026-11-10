import io
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
import voice_settings as settings
import server

class VoiceSettingsTests(unittest.TestCase):
    def test_new_install_and_invalid_override_default_to_liam(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'SETTINGS_FILE', Path(tmp) / 'voice.json'), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings.load_voice(), 'am_liam')
            with patch.dict(os.environ, {'KOKORO_VOICE': 'invalid'}):
                self.assertEqual(settings.load_voice(), 'am_liam')

    def test_selection_persists_and_invalid_choice_is_rejected(self):
        original = settings.current_voice()
        try:
            with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'SETTINGS_FILE', Path(tmp) / 'voice.json'):
                settings.select_voice('bm_george')
                self.assertEqual(settings.current_voice(), 'bm_george')
                self.assertEqual(settings.load_voice(), 'bm_george')
                with self.assertRaises(ValueError): settings.select_voice('not-a-voice')
                self.assertEqual(settings.load_voice(), 'bm_george')
        finally:
            settings._selected = original

    def test_preview_is_wav_and_does_not_change_selection(self):
        original = settings.current_voice()
        with patch('neural_voice.synthesize', return_value=b'\x01\x00' * 24000) as synth:
            response = server.preview_voice(server.VoiceChoice(voice='bm_george'))
            synth.assert_called_once()
            self.assertEqual(synth.call_args.kwargs['voice'], 'bm_george')
        self.assertEqual(settings.current_voice(), original)
        with wave.open(io.BytesIO(response.body)) as wav:
            self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()), (24000, 1, 2))

if __name__ == '__main__': unittest.main()
