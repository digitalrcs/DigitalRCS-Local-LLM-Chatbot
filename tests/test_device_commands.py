import unittest
from device_commands import parse_control

class ControlsTests(unittest.TestCase):
    def test_supported_commands(self):
        cases = [
            ("Franky can you increase volume 10%", "volume", "delta", 10),
            ("decrease brightness by twenty percent", "brightness", "delta", -20),
            ("set volume to zero", "volume", "set", 0),
            ("increase brightness", "brightness", "delta", 10),
            ("set brightness to one hundred percent", "brightness", "set", 100),
            ("what is the brightness?", "brightness", "query", 0),
            ("Could you please set the volume to fifty-five percent?", "volume", "set", 55),
            ("Hey Frankie, turn the screen brightness down by five percent.", "brightness", "delta", -5),
            ("Please make it louder", "volume", "delta", 10),
            ("turn it down", "volume", "delta", -10),
        ]
        for text, target, mode, value in cases:
            with self.subTest(text=text):
                self.assertEqual(parse_control(text), dict(target=target, mode=mode, value=value))

    def test_invalid_amounts(self):
        for amount in ("101", "one thousand", "-10.5", "-5", ".5", "10.5", "ten five"):
            with self.subTest(amount=amount):
                self.assertIn("error", parse_control("increase volume " + amount + "%"))

    def test_noncommands_do_not_execute(self):
        for text in ("don't increase volume", "please do not lower brightness",
                     "how do I increase volume", "the volume is too low", "tell me a story",
                     "if I say increase volume will you do it", "set volume to 50 and brightness to 20"):
            with self.subTest(text=text):
                result = parse_control(text)
                self.assertTrue(result is None or "error" in result)

if __name__ == '__main__':
    unittest.main()
