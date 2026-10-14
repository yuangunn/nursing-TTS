import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_tmp = tempfile.mkdtemp(prefix="nursing-tts-test-")
os.environ["NURSING_TTS_DATA"] = _tmp
