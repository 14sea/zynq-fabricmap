"""The discovery sentinel: `python3 -B -m unittest discover -s b3/tests` must list and count this
test; the B3 test report's removal control runs the same command over a copy with this file removed
and requires exactly one test fewer (docs/b3_architecture.md v0.2.3 §6)."""
import unittest


class Sentinel(unittest.TestCase):
    def test_b3_discovery_sentinel(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
