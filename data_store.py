"""
Shared, thread-safe, process-safe access to display-data.json.

This fixes the two bugs that were causing the empty/corrupt JSON:

1. The old code did `open(path, 'w')` and then `json.dump(...)`. Opening in
   'w' mode truncates the file to zero bytes IMMEDIATELY, before any new
   data is written. If the process died or was killed mid-write (crash,
   pm2 restart, power blip on a Pi), the file was left empty.
   -> Fixed by writing to a temp file first, then atomically renaming it
      over the real file with os.replace(). A reader always sees either
      the fully-old or fully-new file, never a half-written one.

2. garbage_collection.py, octranspo_gtfs.py, and the Flask app were all
   separate processes doing read-modify-write on the same file with no
   coordination. If two of them overlapped, one could read stale data
   and stomp on the other's changes, or read the file while it was
   mid-truncation.
   -> Fixed with a cross-process file lock (the `filelock` package) around
      every read-modify-write cycle, plus a plain thread lock for callers
      within the same process.
"""

import json
import os
import tempfile
import threading
from datetime import datetime

from filelock import FileLock

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "display-data.json")
LOCK_PATH = DATA_PATH + ".lock"

_thread_lock = threading.Lock()
_file_lock = FileLock(LOCK_PATH, timeout=10)

DEFAULT_DATA = {
    "99": [], "70": [], "74": [], "110": [], "73": [], "198": [], "299": [], "283": [],
    "date": "", "garbage": False, "yard": False, "green": False, "blue": False, "black": False,
}


def _atomic_write(path, data):
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic on POSIX / same filesystem
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _load_locked():
    if not os.path.exists(DATA_PATH):
        _atomic_write(DATA_PATH, DEFAULT_DATA)
        return dict(DEFAULT_DATA)
    try:
        with open(DATA_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        # Recover from a corrupt file left by an old crash instead of dying.
        print("data_store: display-data.json was corrupt, resetting to defaults")
        _atomic_write(DATA_PATH, DEFAULT_DATA)
        return dict(DEFAULT_DATA)


def read_data():
    """Read the whole data file. Creates/repairs it with defaults if missing or corrupt."""
    with _thread_lock, _file_lock:
        return _load_locked()


def last_updated():
    """Return the datetime the data file was last written, or None if it doesn't exist yet."""
    try:
        return datetime.fromtimestamp(os.path.getmtime(DATA_PATH))
    except OSError:
        return None


def update_data(mutate_fn):
    """
    Read-modify-write the data file safely across threads and processes.
    `mutate_fn(data_dict)` should mutate the dict in place.
    Returns the resulting dict.
    """
    with _thread_lock, _file_lock:
        data = _load_locked()
        mutate_fn(data)
        _atomic_write(DATA_PATH, data)
        return data