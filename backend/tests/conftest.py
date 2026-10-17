import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# One throw-away data folder per test session (voices, noises, output, exports all land here).  It is removed when the
# session ends — before 2026-10-17 every run left ~125 MB behind in the OS temp folder.
_tmp = tempfile.mkdtemp(prefix="nursing-tts-test-")
os.environ["NURSING_TTS_DATA"] = _tmp


def _cleanup() -> None:
    shutil.rmtree(_tmp, ignore_errors=True)


atexit.register(_cleanup)


def pytest_sessionfinish(session, exitstatus):   # noqa: ARG001
    _cleanup()
