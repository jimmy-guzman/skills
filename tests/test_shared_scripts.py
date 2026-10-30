"""Scripts shipped in more than one skill must stay byte-identical.

Each skill installs on its own, so a shared script is copied, not linked.
Edit one copy, then copy it over the others.
"""

import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
SHARED = [["review-changes/scripts/snapshot.py", "revise-changes/scripts/snapshot.py"]]


class SharedScripts(unittest.TestCase):
    def test_copies_are_identical(self):
        for first, *rest in SHARED:
            for other in rest:
                with self.subTest(other=other):
                    self.assertEqual((SKILLS / first).read_bytes(), (SKILLS / other).read_bytes(), f"{other} drifted from {first}")


if __name__ == "__main__":
    unittest.main()
