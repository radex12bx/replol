"""Keep startup diagnostics available for Windows GUI builds (pythonw)."""
import os
import sys
from pathlib import Path

def prepare_stdio():
    if sys.stdout is not None and sys.stderr is not None:
        return None
    base = Path(os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
    folder = base / 'PRIVSIG' / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    stream = (folder / 'startup.log').open('a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    return stream
