"""Fine-grained progress read from the tools' own output.

COLMAP and Brush both report where they are, line by line, but the engines
used to ignore it: COLMAP jumped 25 → 50 → 75 → 90 between phases, and Brush
training was estimated from the checkpoint files found on disk (one tick per
``--export-every``). This module turns those lines into fractions. It is
Qt-free so the CLI and the GUI share it, and so it can be tested on recorded
log lines.

Formats below were read from real runs (COLMAP 3.12/4.0 glog output, Brush
release binary with indicatif 0.17). An unknown line simply yields None: the
caller keeps its last value, it never guesses.
"""

import re
import time
from collections.abc import Callable

# CSI sequences (colors, cursor moves, line erase) that indicatif emits when it
# draws on a terminal, plus the lone OSC/charset escapes some terminals add.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


# ── Brush ──────────────────────────────────────────────────────────────────────
# Training bar template, from the binary:
#   [{elapsed}] {bar:40.cyan/blue} {pos:>7}/{len:7} {msg} ({per_sec}, {eta} remaining)
# e.g. "[00:03:12] ████████░░░░   4211/30000   (21.9345/s, 20 minutes remaining)"
# Only the line carrying "remaining" is the training bar; the dataset loading
# bar ("{wide_bar} {pos}/{len}") has no ETA and is left to the log.
_BRUSH_BAR_RE = re.compile(r"(\d+)\s*/\s*(\d+)\b.*\(\s*([\d.]+)\s*[^\s,]*/s\s*,.*remaining\s*\)")


def parse_brush_bar(line: str) -> tuple[int, int, float] | None:
    """(step, total_steps, steps_per_second) from a Brush training bar, or None."""
    match = _BRUSH_BAR_RE.search(strip_ansi(line))
    if not match:
        return None
    pos, total = int(match.group(1)), int(match.group(2))
    if total <= 0 or pos > total:
        return None
    try:
        rate = float(match.group(3))
    except ValueError:
        rate = 0.0
    return pos, total, rate


# ── COLMAP ─────────────────────────────────────────────────────────────────────
# One counter per phase, all "[done/total]":
#   feature_extraction.cc] Processed file [12/684]
#   pairing.cc] Processing image [37/684]     (sequential, then loop detection)
#   pairing.cc] Processing block [2/14, 9/14] (exhaustive)
#   undistortion.cc] Undistorting image [12/684]
_COUNTER_RE = re.compile(r"(?:Processed file|Processing image|Undistorting image) \[(\d+)/(\d+)\]")
_BLOCK_RE = re.compile(r"Processing block \[(\d+)/(\d+), (\d+)/(\d+)\]")
# Incremental mapper: "Registering image #42 (num_reg_frames=43)" on COLMAP 4,
# "Registering image #42 (43)" before. The number in parentheses is the count
# of images registered so far.
_REGISTER_RE = re.compile(r"Registering image #\d+ \((?:\w+=)?(\d+)\)")


def parse_colmap_counter(line: str) -> tuple[int, int] | None:
    """(done, total) for the per-image counters, or None."""
    match = _COUNTER_RE.search(line)
    if not match:
        return None
    done, total = int(match.group(1)), int(match.group(2))
    return (done, total) if total > 0 else None


def exhaustive_block_fraction(line: str) -> float | None:
    """Share of the exhaustive matching already done when a block starts.

    COLMAP walks the full N×N block grid but only matches each image pair
    once, so blocks below the diagonal are near-instant and the diagonal ones
    are half-sized. Counting the grid linearly would race through the empty
    half; weighting by pairs keeps the bar in step with the time spent.
    The line is printed as a block *starts*, so only earlier blocks count.
    """
    match = _BLOCK_RE.search(line)
    if not match:
        return None
    row, n, col, n2 = (int(g) for g in match.groups())
    if n <= 0 or n != n2:
        return None
    # Pairs in the finished rows above (row r holds N - r + 0.5 block-units).
    done = sum(n - r + 0.5 for r in range(1, row))
    # Finished blocks of the current row that lie on or above the diagonal.
    if col > row:
        done += 0.5 + (col - row - 1)
    return min(1.0, done / (n * n / 2))


def parse_registered_count(line: str) -> int | None:
    match = _REGISTER_RE.search(line)
    return int(match.group(1)) if match else None


class PhaseProgress:
    """Maps a phase's own 0-1 fraction onto its slice of the overall bar.

    ``passes`` splits the slice when one command runs several counters in a
    row: sequential matching counts every image, then runs loop detection
    with its own, shorter counter. A counter whose total changes means the
    next pass has begun. Weights come from observed run times (loop detection
    took about a third of sequential matching on a 684-image scene).

    The value never moves backwards inside a phase, and ``emit`` is only
    called when it moved by at least ``min_step`` points.
    """

    def __init__(self, emit: Callable[[float], None], lo: float, hi: float,
                 passes: tuple[float, ...] = (1.0,), min_step: float = 0.1):
        self._emit = emit
        self.lo, self.hi = float(lo), float(hi)
        total = sum(passes) or 1.0
        self._passes = [w / total for w in passes]
        self._pass_index = 0
        self._pass_total: int | None = None
        self._min_step = min_step
        self._value = self.lo
        self._emitted = None
        self._push(self.lo, force=True)

    @property
    def value(self) -> float:
        return self._value

    def counter(self, done: int, total: int) -> None:
        """Feed a [done/total] counter, switching pass when the total changes."""
        if self._pass_total is not None and total != self._pass_total:
            self._pass_index = min(self._pass_index + 1, len(self._passes) - 1)
        self._pass_total = total
        self.fraction(done / total)

    def fraction(self, frac: float) -> None:
        """Feed the current pass's own fraction (0-1)."""
        frac = max(0.0, min(1.0, frac))
        start = sum(self._passes[:self._pass_index])
        overall = start + self._passes[self._pass_index] * frac
        self._push(self.lo + (self.hi - self.lo) * overall)

    def _push(self, value: float, force: bool = False) -> None:
        value = max(self._value, min(self.hi, value))
        self._value = value
        if force or self._emitted is None or value - self._emitted >= self._min_step:
            self._emitted = value
            self._emit(round(value, 2))


class RateLimiter:
    """True at most once per ``interval`` seconds (first call always passes)."""

    def __init__(self, interval: float, clock: Callable[[], float] = time.monotonic):
        self._interval = interval
        self._clock = clock
        self._last: float | None = None

    def ready(self) -> bool:
        now = self._clock()
        if self._last is None or now - self._last >= self._interval:
            self._last = now
            return True
        return False


def integer_steps(callback: Callable[[int], None]) -> Callable[[float], None]:
    """Wrap a progress callback so it only fires when the whole percent changes.

    The engines now report fractional progress many times a second; a CLI
    printing one line per update would scroll endlessly.
    """
    last: list[int | None] = [None]

    def relay(value: float) -> None:
        whole = int(value)
        if whole != last[0]:
            last[0] = whole
            callback(whole)

    return relay
