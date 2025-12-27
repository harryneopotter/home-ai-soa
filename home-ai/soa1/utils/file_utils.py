"""File utilities for monitoring: tailing and file listing helpers."""

from pathlib import Path
from typing import List


def tail_lines(path: Path, lines: int = 200) -> List[str]:
    """Return the last `lines` lines from the file at `path` efficiently.

    This implementation reads a chunk from the end of the file proportional
    to the number of lines requested and falls back to reading the whole file
    for very small files. It aims to avoid loading huge log files into memory.
    """
    if not path.exists() or not path.is_file():
        return []

    # Tune chunk size heuristically
    avg_line_size = 200
    to_read = lines * avg_line_size

    with path.open("rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        if file_size == 0:
            return []
        # If the file is small, read completely
        if file_size <= to_read:
            f.seek(0)
            data = f.read().decode("utf-8", errors="replace")
            return data.splitlines()[-lines:]

        # Otherwise, seek near the end and read
        offset = max(0, file_size - to_read)
        f.seek(offset)
        data = f.read().decode("utf-8", errors="replace")
        lines_out = data.splitlines()
        # If we started mid-line, the first element may be a partial line - that's fine
        return lines_out[-lines:]
