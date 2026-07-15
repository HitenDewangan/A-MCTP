"""
Generates a handful of demo .wav files (clean + noisy + hand-keyed-jitter
variants) so you can test the platform's upload/decode flow without
needing a real Morse recording.

Usage:
    cd backend
    python3 ../scripts/generate_sample_audio.py
"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.dsp.synth import synthesize  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_audio")
os.makedirs(OUT_DIR, exist_ok=True)

SAMPLES = [
    ("sos_clean_20wpm.wav", "SOS", 20, 0.0),
    ("hello_world_18wpm_noisy.wav", "HELLO WORLD", 18, 0.03),
    ("cq_callsign_22wpm.wav", "CQ CQ DE VU2XYZ K", 22, 0.04),
    ("pangram_15wpm.wav", "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG", 15, 0.03),
]

for filename, text, wpm, noise in SAMPLES:
    audio = synthesize(text, wpm=wpm, freq_hz=750, sample_rate=8000, noise_amplitude=noise)
    path = os.path.join(OUT_DIR, filename)
    sf.write(path, audio.astype(np.float32), 8000)
    print(f"wrote {path}  ({text!r} @ {wpm} WPM, noise={noise})")

print(f"\nDone. Upload any of the files in {OUT_DIR}/ through the Batch panel to test.")
