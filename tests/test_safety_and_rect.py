import unittest
from desktop_harness.safety import is_protected_process
from desktop_harness.capture import clip_rect


class TestSafetyAndRect(unittest.TestCase):
    def test_protected_process_detection(self):
        self.assertTrue(is_protected_process("explorer.exe"))
        self.assertTrue(is_protected_process("CSRSS.EXE"))
        self.assertTrue(is_protected_process("svchost.exe"))
        self.assertFalse(is_protected_process("notepad.exe"))
        self.assertFalse(is_protected_process(""))

    def test_rect_clipping_within_screen_bounds(self):
        clipped = clip_rect(100, 100, 500, 400, 1920, 1080)
        self.assertEqual(clipped, (100.0, 100.0, 500.0, 400.0))

        # Out of bounds clamping
        clipped_overflow = clip_rect(1800, 1000, 500, 400, 1920, 1080)
        self.assertEqual(clipped_overflow, (1800.0, 1000.0, 120.0, 80.0))


if __name__ == '__main__':
    unittest.main()
