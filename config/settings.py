"""
إعدادات المشروع / Project settings
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _default_cache_dir() -> Path:
    """Pick the cache folder: env var > D:\\SmartCache (Windows, if D: exists) > ./cache"""
    env = os.environ.get("EXTERNAL_RAM_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32" and Path("D:/").exists():
        return Path(r"D:\SmartCache")
    return BASE_DIR / "cache"


CACHE_DIR = _default_cache_dir()
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

for _dir in (CACHE_DIR, LOGS_DIR, DATA_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# إعدادات المراقبة
RAM_THRESHOLD_PERCENT = 80      # RAM usage (%) that triggers caching
CHECK_INTERVAL_SECONDS = 5      # how often RAM is checked
MIN_SECONDS_BETWEEN_CACHES = 10 # cool-down between two caching actions

# إعدادات الكاش
MAX_CACHE_SIZE_MB = 1024        # hard cap for the whole cache folder
MAX_DUMP_SIZE_MB = 10           # cap for a single simulated dump
CACHE_BLOCK_SIZE_KB = 64        # chunk size when writing dumps
MAX_PROCESSES_TO_CACHE = 3      # max processes kept in the cache
CACHE_MAX_AGE_HOURS = 24        # caches older than this are deleted

# قاعدة البيانات
DB_PATH = DATA_DIR / "performance.db"

# التسجيل
LOG_FILE = LOGS_DIR / "system.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
