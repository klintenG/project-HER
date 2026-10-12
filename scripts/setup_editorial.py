"""Explicit one-time open-source alignment-model download; never a paid call."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import config
from faster_whisper import WhisperModel
WhisperModel(os.getenv('HER_ALIGNMENT_MODEL','small'),device='cpu',compute_type='int8',download_root=str(config.ASSETS_DIR/'alignment'),cpu_threads=4)
print('Local editorial alignment model ready.')
