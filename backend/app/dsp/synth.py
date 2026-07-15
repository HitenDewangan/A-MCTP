"""
Feature Set 4 -- Reverse Synthesis Engine.
Renders plain text back into audible Morse code using a sine-wave
oscillator, with configurable WPM, tone frequency, and sample rate.
Also used internally to generate synthetic test signals for the decoder.
"""
import numpy as np

from .morse_map import text_to_symbols, WORD_GAP_TOKEN


def synthesize(
    text: str,
    wpm: float = 20.0,
    freq_hz: float = 750.0,
    sample_rate: int = 8000,
    noise_amplitude: float = 0.0,
) -> np.ndarray:
    """
    Standard PARIS timing: dot = 1 unit, dash = 3 units, intra-char gap =
    1 unit, inter-char gap = 3 units, inter-word gap = 7 units.
    unit_seconds = 1.2 / wpm.
    """
    unit = 1.2 / wpm
    symbols = text_to_symbols(text)

    chunks = []

    def tone(duration_s: float):
        n = max(1, int(sample_rate * duration_s))
        t = np.arange(n) / sample_rate
        wave = np.sin(2 * np.pi * freq_hz * t)
        # short raised-cosine ramp to avoid audible clicks
        ramp_n = max(1, int(0.005 * sample_rate))
        ramp_n = min(ramp_n, n // 2) if n > 1 else 0
        if ramp_n > 0:
            ramp = 0.5 * (1 - np.cos(np.pi * np.arange(ramp_n) / ramp_n))
            wave[:ramp_n] *= ramp
            wave[-ramp_n:] *= ramp[::-1]
        chunks.append(wave)

    def silence(duration_s: float):
        n = max(1, int(sample_rate * duration_s))
        chunks.append(np.zeros(n))

    words = symbols.split(f" {WORD_GAP_TOKEN} ")
    for wi, word in enumerate(words):
        letters = word.split(" ")
        for li, letter in enumerate(letters):
            for si, sym in enumerate(letter):
                tone(unit if sym == "." else 3 * unit)
                if si < len(letter) - 1:
                    silence(unit)  # intra-character gap
            if li < len(letters) - 1:
                silence(3 * unit)  # inter-character gap
        if wi < len(words) - 1:
            silence(7 * unit)  # inter-word gap

    signal = np.concatenate(chunks) if chunks else np.zeros(1)

    if noise_amplitude > 0:
        rng = np.random.default_rng(seed=1)
        signal = signal + noise_amplitude * rng.standard_normal(len(signal))

    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak

    return signal
