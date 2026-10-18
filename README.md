Last year, I worked on a project consisting of a PC-based program and a folder to be placed on an external hard drive. The program was designed to reduce the load on the system RAM by offloading some files from open applications onto the external hard drive. I worked on it with great passion—only for a friend to point out that this concept already exists on computers! Haha.
<p align="center">
  <img src="assets/logo.gif" alt="External RAM logo" width="260">
</p>

<h1 align="center">External RAM</h1>

<p align="center">
  <em>A RAM-relief tool that watches your memory and offloads the hungriest app to an external drive.</em><br>
  <img alt="python" src="https://img.shields.io/badge/python-3.9%2B-blue">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey">
  <img alt="status" src="https://img.shields.io/badge/status-learning%20prototype-orange">
</p>

---

## What is it?

**External RAM** (internal name: *Smart SSD Virtual RAM*) is a Python program that

1. checks your RAM usage every few seconds,
2. when usage goes above a threshold (default **80%**), picks the process using the most memory,
3. writes a cache folder for it on an external drive, and
4. cleans that cache up automatically when the process ends, after 24 hours, or when the cache gets too big.

It ships with a small dark desktop widget (Tkinter) that shows live RAM usage and the size of the disk cache.

> **Fun fact:** operating systems already do this! It is called *virtual memory* (Windows **pagefile**, Linux/macOS **swap**).
> This project started as an independent re-invention of that idea and is kept as a learning project.

## Honest status

| Part | State |
| --- | --- |
| RAM monitoring, process selection, cache folders, auto-cleanup, logging, UI | Working |
| Actually moving a process's memory pages to the drive | **Not implemented.** The transfer step is a *simulation*: it writes placeholder bytes (capped at 10 MB) so the whole pipeline can be tested. Your apps' real memory is not touched, so RAM usage will not drop. |

To get a real RAM-relief effect today, let the OS do it: put the Windows pagefile on the external drive
(*System Properties → Advanced → Performance → Virtual memory*) or add a swap file on Linux. Keep in mind
that an external HDD is far slower than RAM, so an SSD is strongly recommended.

## Quick start

```bash
pip install -r requirements.txt

python ui/main_window.py       # desktop widget (starts the engine too)
python main.py                 # headless / terminal mode
python debug_processes.py      # list top memory consumers, or watch RAM live
python -m unittest discover tests
```

Press `Ctrl+C` (terminal) or the **✕** button (widget) to stop; the engine cleans up its cache on exit.

## Choosing the cache drive

The cache folder is chosen in this order:

1. the `EXTERNAL_RAM_CACHE_DIR` environment variable, e.g. `set EXTERNAL_RAM_CACHE_DIR=E:\SmartCache`
2. `D:\SmartCache` on Windows, if a `D:` drive exists
3. a `cache/` folder next to the program

Only folders created by this program are ever deleted; other files you keep on the drive are left alone.

## Settings (`config/settings.py`)

| Setting | Default | Meaning |
| --- | --- | --- |
| `RAM_THRESHOLD_PERCENT` | 80 | RAM usage that triggers caching |
| `CHECK_INTERVAL_SECONDS` | 5 | How often RAM is checked |
| `MIN_SECONDS_BETWEEN_CACHES` | 10 | Cool-down between two caching actions |
| `MAX_PROCESSES_TO_CACHE` | 3 | Oldest cache is dropped beyond this |
| `MAX_CACHE_SIZE_MB` | 1024 | Hard cap for the whole cache folder |
| `MAX_DUMP_SIZE_MB` | 10 | Cap for one simulated dump |
| `CACHE_MAX_AGE_HOURS` | 24 | Auto-delete age |

## Project layout

```
main.py                  engine: monitoring loop
ui/main_window.py        Tkinter widget
core/memory_monitor.py   RAM / swap readings (psutil)
core/process_manager.py  finds the top memory process, skips system ones
core/cache_manager.py    cache folders, cleanup, size cap, restore
core/performance_logger.py  text log + SQLite history
config/settings.py       all tunables
debug_processes.py       diagnostic tool
tests/test_cache.py      unit tests
assets/sticker.svg|png   the sticker
```

## What was fixed in this version

- **Deadlock:** re-caching an already cached process froze the program (non-reentrant lock). Fixed with an `RLock`.
- **Database errors:** the old logs show 3,484 *"SQLite objects created in a thread…"* errors. The logger now uses one shared, lock-protected connection.
- **Log spam:** `HIGH_RAM` was logged every 5 s (3,500+ rows). Now at most once a minute; the RAM log timers no longer depend on the clock landing on an exact second.
- **Cache growth:** `MAX_CACHE_SIZE_MB` existed but was never used. It is now enforced; restoring a process now removes its cached copy.
- **Safety:** shutdown used to delete *everything* in the cache folder and startup deleted unknown folders; now only the program's own folders are touched. Cache metadata uses JSON instead of `pickle` (loading pickle from disk can execute code).
- **Wrong targets:** system helpers (`MemCompression`, `Registry`, `vmmem`, Defender…) and the program itself are no longer picked as "top process".
- **Process suspend on Windows** used `SuspendThread` on a process handle (invalid); now uses `psutil`.
- **Portability:** hard-coded `D:\SmartCache` (which crashed when no `D:` existed) replaced by the lookup above; folders are created with `parents=True`.
- **Threads:** signal handlers are only installed on the main thread; the engine stops instantly instead of waiting out its sleep; the UI waits for cleanup on exit.
- `debug_processes.py` printed a wrong percentage column; empty `tests/test_cache.py` now has real tests; bare `except:` blocks replaced.

## Roadmap

- Real offloading (Windows working-set trimming / pagefile placement)
- Pause/resume buttons and a process whitelist in the UI
- Arabic/English language switch

## License

Personal learning project. Add the license of your choice.
