"""
Pytest suite for the DSP + ML decoding pipeline. Run with:
    cd backend && pytest tests/ -v
"""
import numpy as np
import pytest

from app.dsp import synth, decoder
from app.dsp.morse_map import symbols_to_text, text_to_symbols

SAMPLE_RATE = 8000


@pytest.mark.parametrize("text,wpm,noise", [
    ("SOS", 20, 0.0),
    ("HELLO WORLD", 18, 0.02),
    ("CLAUDE IS ON DUTY", 25, 0.05),
    ("THE QUICK BROWN FOX", 15, 0.03),
    ("CQ CQ DE VU2XYZ K", 22, 0.04),
    ("TEST 12345", 30, 0.06),
    ("A", 20, 0.0),
    ("PARIS PARIS PARIS", 12, 0.02),
    ("73 GOOD NIGHT DE 9W2ABC", 24, 0.04),
])
def test_round_trip_synth_then_decode(text, wpm, noise):
    audio = synth.synthesize(text, wpm=wpm, freq_hz=750, sample_rate=SAMPLE_RATE, noise_amplitude=noise)
    result = decoder.decode_audio(audio, SAMPLE_RATE)
    assert result.text == text
    # WPM estimate should be within ~25% of the true sending speed
    assert abs(result.wpm_estimate - wpm) / wpm < 0.3


def test_decode_at_10db_snr_floor():
    """PRD Section 7 success metric: decode reliably down to 10 dB SNR."""
    text = "HELLO WORLD"
    rng = np.random.default_rng(7)
    audio = synth.synthesize(text, wpm=18, freq_hz=750, sample_rate=SAMPLE_RATE)
    sig_power = np.mean(audio ** 2)
    noise_power = sig_power / (10 ** (10 / 10))  # 10 dB SNR
    noisy = audio + rng.normal(0, np.sqrt(noise_power), len(audio))
    result = decoder.decode_audio(noisy, SAMPLE_RATE)
    assert result.text == text


def test_decode_survives_amplitude_fade():
    """AGC stage: a deep mid-message fade (down to ~12% amplitude) should
    still decode correctly, not just silently lose the faded letters."""
    text = "CQ CQ DE TEST"
    audio = synth.synthesize(text, wpm=20, freq_hz=800, sample_rate=SAMPLE_RATE, noise_amplitude=0.02)
    n = len(audio)
    fade = np.ones(n)
    fade[n // 3: 2 * n // 3] = np.linspace(1.0, 0.12, (2 * n // 3) - (n // 3))
    faded = audio * fade
    faded = faded / np.max(np.abs(faded))
    result = decoder.decode_audio(faded, SAMPLE_RATE)
    assert result.text == text


def test_decode_survives_impulsive_click_noise():
    """Noise blanker stage: sharp clicks/static (3-6x the tone's own
    amplitude) should be suppressed rather than corrupting the envelope."""
    text = "HELLO WORLD"
    audio = synth.synthesize(text, wpm=18, freq_hz=750, sample_rate=SAMPLE_RATE, noise_amplitude=0.02)
    rng = np.random.default_rng(5)
    clicks = np.zeros(len(audio))
    for p in rng.integers(0, len(audio), 40):
        clicks[p] = rng.choice([-1, 1]) * rng.uniform(3.0, 6.0)
    noisy = audio + clicks
    noisy = noisy / np.max(np.abs(noisy))
    result = decoder.decode_audio(noisy, SAMPLE_RATE)
    assert result.text == text


def test_decode_auto_detects_frequency_outside_legacy_band():
    """Auto-detection: must find and decode a tone well outside the old
    hardcoded 700-800 Hz band, with no frequency hint given."""
    text = "CQ DE TEST"
    audio = synth.synthesize(text, wpm=18, freq_hz=1100, sample_rate=SAMPLE_RATE, noise_amplitude=0.04)
    result = decoder.decode_audio(audio, SAMPLE_RATE)  # no low_hz/high_hz passed
    assert result.text == text
    assert result.detected_freq_hz is not None
    assert abs(result.detected_freq_hz - 1100) < 15


def test_empty_or_silent_audio_does_not_crash():
    silence = np.zeros(SAMPLE_RATE)  # 1s of pure silence
    result = decoder.decode_audio(silence, SAMPLE_RATE)
    assert result.text == ""
    assert result.warning is not None


def test_morse_map_round_trip():
    text = "HELLO WORLD 123"
    symbols = text_to_symbols(text)
    assert symbols_to_text(symbols) == text


def test_wpm_estimate_paris_standard():
    from app.dsp.clustering import estimate_wpm
    # unit = 1.2 / wpm  =>  wpm = 1.2 / unit
    assert estimate_wpm(0.06) == pytest.approx(20.0, abs=0.1)
    assert estimate_wpm(0.04) == pytest.approx(30.0, abs=0.1)
