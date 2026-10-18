"""
تسجيل أداء النظام والأحداث / Event + performance logging (thread-safe)
"""

import logging
import sqlite3
import threading

import psutil

from config import settings


class PerformanceLogger:
    """Logs to a text file and to SQLite. One connection, protected by a lock,
    so the UI thread and the engine thread can both log safely."""

    def __init__(self):
        self._lock = threading.Lock()
        self._setup_file_logging()
        self._conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        self._setup_database()

    def _setup_file_logging(self):
        root = logging.getLogger()
        if not root.handlers:  # avoid duplicate handlers when created twice
            logging.basicConfig(
                level=getattr(logging, settings.LOG_LEVEL),
                format=settings.LOG_FORMAT,
                handlers=[
                    logging.FileHandler(settings.LOG_FILE, encoding='utf-8'),
                    logging.StreamHandler(),
                ],
            )
        self.logger = logging.getLogger("ExternalRAM")

    def _setup_database(self):
        with self._lock:
            self._conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT,
                    details TEXT,
                    ram_usage REAL,
                    response_time REAL
                )
            ''')
            self._conn.execute('''
                CREATE TABLE IF NOT EXISTS process_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    pid INTEGER,
                    process_name TEXT,
                    memory_usage REAL,
                    action TEXT
                )
            ''')
            self._conn.commit()

    def log_event(self, event_type, details, response_time=None):
        """Record an event in the log file and the database."""
        self.logger.info(f"{event_type}: {details}")
        try:
            ram_usage = psutil.virtual_memory().percent
            with self._lock:
                self._conn.execute(
                    "INSERT INTO performance_log (event_type, details, ram_usage, response_time) "
                    "VALUES (?, ?, ?, ?)",
                    (event_type, details, ram_usage, response_time),
                )
                self._conn.commit()
        except Exception as e:
            self.logger.error(f"خطأ في تسجيل قاعدة البيانات: {e}")

    def log_process_action(self, pid, process_name, memory_usage, action):
        """Record an action taken on a process."""
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO process_history (pid, process_name, memory_usage, action) "
                    "VALUES (?, ?, ?, ?)",
                    (pid, process_name, memory_usage, action),
                )
                self._conn.commit()
        except Exception as e:
            self.logger.error(f"خطأ في تسجيل العملية: {e}")

    def get_statistics(self, limit=100):
        """Latest rows of the performance log."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM performance_log ORDER BY timestamp DESC LIMIT ?", (limit,))
            return cur.fetchall()

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
