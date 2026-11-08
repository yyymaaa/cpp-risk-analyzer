"""C++ Dependency Risk Analyzer: predicts the change-propagation risk ("blast radius") of C++ files."""
import sys

__version__ = "1.1.0"

# When output is redirected (pipes, CI logs, git hooks), Windows defaults to a legacy code page that
# cannot encode the report's symbols (✔, █, ⚠). Use UTF-8 there; interactive consoles are left to rich.
for _stream in (sys.stdout, sys.stderr):
    try:
        if _stream is not None and not _stream.isatty() and (_stream.encoding or "").lower() not in ("utf-8", "utf8"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass
