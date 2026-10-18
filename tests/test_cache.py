"""Basic tests for CacheManager. Run:  python -m unittest discover tests"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["EXTERNAL_RAM_CACHE_DIR"] = tempfile.mkdtemp(prefix="extram_test_")

from config import settings  # noqa: E402
from core.cache_manager import CacheManager  # noqa: E402


def fake_process(pid=os.getpid(), name="demo app.exe"):
    return {"pid": pid, "name": name, "memory_rss": 2 * 1024 * 1024, "memory_percent": 1.5}


class CacheManagerTests(unittest.TestCase):
    def setUp(self):
        self.cm = CacheManager()

    def tearDown(self):
        self.cm.cleanup_all()

    def test_cache_and_restore(self):
        self.assertTrue(self.cm.cache_process(fake_process()))
        self.assertEqual(self.cm.get_cache_info()["total_cached"], 1)
        self.assertTrue(self.cm.restore_process(os.getpid()))
        self.assertEqual(self.cm.get_cache_info()["total_cached"], 0)  # copy removed after restore

    def test_recaching_same_pid_does_not_deadlock(self):
        self.assertTrue(self.cm.cache_process(fake_process()))
        t0 = time.time()
        self.assertTrue(self.cm.cache_process(fake_process()))  # used to hang forever
        self.assertLess(time.time() - t0, 5)

    def test_size_cap_evicts_oldest(self):
        old = settings.MAX_CACHE_SIZE_MB
        settings.MAX_CACHE_SIZE_MB = 3  # each dump is ~2 MB
        try:
            self.cm.cache_process(fake_process(pid=os.getpid(), name="a"))
            time.sleep(1.1)
            self.cm.cache_process(fake_process(pid=os.getppid(), name="b"))
            names = [p["name"] for p in self.cm.list_cached_processes()]
            self.assertEqual(names, ["b"])
        finally:
            settings.MAX_CACHE_SIZE_MB = old

    def test_unrelated_files_are_not_deleted(self):
        keep = settings.CACHE_DIR / "my_holiday_photo.jpg"
        keep.write_bytes(b"precious")
        self.cm.cache_process(fake_process())
        self.cm.cleanup_all()
        self.assertTrue(keep.exists())
        keep.unlink()

    def test_filename_sanitizing(self):
        self.assertEqual(self.cm._sanitize_filename('a/b:c*?.exe'), "a_b_c__.exe")


if __name__ == "__main__":
    unittest.main()
