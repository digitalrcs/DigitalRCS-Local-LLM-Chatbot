import unittest
import numpy as np
from neural_voice import pcm16

class PcmTests(unittest.TestCase):
    def test_clips_and_encodes_little_endian(self):
        raw = pcm16(np.array([-2., -1., 0., 1., 2.]), 24000)
        self.assertEqual(raw, b'\x01\x80\x01\x80\x00\x00\xff\x7f\xff\x7f')

    def test_rejects_invalid_audio(self):
        for value, rate in [(np.array([]), 24000), (np.zeros((2, 5)), 24000),
                            (np.array([np.nan]), 24000), (np.array([np.inf]), 24000),
                            (np.array([0.]), 22050), (np.array([True]), 24000),
                            (np.array([1]), 24000)]:
            with self.subTest(value=value, rate=rate), self.assertRaises(ValueError):
                pcm16(value, rate)

    def test_duration_limit(self):
        self.assertEqual(len(pcm16(np.zeros(24000 * 60), 24000)), 2880000)
        with self.assertRaises(ValueError):
            pcm16(np.zeros(24000 * 60 + 1), 24000)

if __name__ == '__main__':
    unittest.main()
