r"""Regression test for cross-platform ffmpeg metadata path handling in grade.py.

Bug: `grade.py --analyze` crashed on Windows because the signalstats metadata
filter embedded a temp path (e.g. C:\Users\me\Temp\stats.txt), and the ':' and
'\' in that path collide with ffmpeg filtergraph delimiters, so ffmpeg exited
with an error. Fix: _metadata_filter_target() returns the file's directory (to
use as ffmpeg's cwd) and the bare filename (to put in the filter), so no path
separator or drive colon ever reaches the filtergraph parser. These tests pin
that invariant.
"""
import sys
import unittest
from pathlib import Path

# Import the helper module directly from helpers/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "helpers"))
import grade  # noqa: E402


class MetadataFilterTargetTest(unittest.TestCase):
    def test_filter_value_has_no_delimiters(self):
        # The bare filename must contain no ':' or path separator — those are
        # exactly the chars that break an ffmpeg filtergraph.
        _, name = grade._metadata_filter_target(r"C:\Users\me\AppData\Local\Temp\stats.txt")
        self.assertEqual(name, "stats.txt")
        self.assertNotIn(":", name)
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)

    def test_cwd_plus_name_roundtrips(self):
        # cwd joined with the bare filename must point back at the original file.
        original = str(Path("/tmp/sub/stats.txt"))
        cwd, name = grade._metadata_filter_target(original)
        self.assertEqual(str(Path(cwd) / name), original)

    def test_posix_filename_is_bare(self):
        cwd, name = grade._metadata_filter_target("/var/folders/xy/stats.txt")
        self.assertEqual(name, "stats.txt")
        self.assertEqual(cwd, str(Path("/var/folders/xy")))


if __name__ == "__main__":
    unittest.main()
