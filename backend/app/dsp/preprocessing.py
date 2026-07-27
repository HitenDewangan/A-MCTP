"""
Section 5.1 of the PRD -- Pre-processing & Filtering Engine.
"""
from typing import List

import numpy as np
from scipy.signal import butter, find_peaks, sosfiltfilt, welch


def normalize(samples: np.ndarray) -> np.ndarray:
    """Scale audio samples uniformly into [-1.0, 1.0]."""
    samples = samples.astype(np.float64)
    peak = np.max(np.abs(samples))
    if peak < 1e-9:
        return samples
    return samples / peak


def noise_blanker(samples: np.ndarray, sample_rate: int, threshold_mult: float = 6.0, window_ms: float = 5.0) -> np.ndarray:
    """
    Clip impulsive noise spikes (clicks, static crashes, compression
    artifacts) before they reach the envelope detector.

    This is standard practice in real CW receivers and decoders (commonly
    listed alongside a bandpass filter and AGC as the three core stages --
    see e.g. the BPF/AGC/noise-blanker chain used by well-regarded CW
    decoder apps and the classic OZ1JHM Arduino/ESP32 CW decoder design).
    A sustained Morse tone is not impulsive -- clipping short spikes well
    above the local RMS removes clicks/static without touching the tone
    itself, unlike a global amplitude clip which would also distort the
    tone during loud passages.
    """
    win = max(1, int(sample_rate * window_ms / 1000.0))
    kernel = np.ones(win) / win
    local_rms = np.sqrt(np.convolve(samples ** 2, kernel, mode="same"))
    ceiling = threshold_mult * (local_rms + 1e-9)
    return np.clip(samples, -ceiling, ceiling)


def agc(samples: np.ndarray, sample_rate: int, window_ms: float = 120.0, target_rms: float = 0.3) -> np.ndarray:
    """
    Automatic gain control: continuously rescales the signal so its local
    loudness stays roughly constant, instead of relying on one global
    peak-normalization for the whole clip.

    Real recordings -- a fading HF signal, a YouTube clip with uneven
    mastering, a phone mic picking up a speaker at varying distance --
    drift in level over time. A single global normalize() call handles
    only the loudest instant in the whole buffer; a quiet passage
    elsewhere can end up too weak for the adaptive threshold to register
    as "tone on" at all. AGC divides by a slowly-varying local RMS
    envelope (smoothed so it tracks fading, not individual dots/dashes)
    so the signal fed to the bandpass filter has a much more consistent
    level throughout.
    """
    win = max(1, int(sample_rate * window_ms / 1000.0))
    kernel = np.ones(win) / win
    local_rms = np.sqrt(np.convolve(samples ** 2, kernel, mode="same"))
    floor = np.percentile(local_rms, 5) + 1e-6  # avoid dividing by near-zero in silent stretches
    gain = target_rms / np.maximum(local_rms, floor)
    gain = np.clip(gain, 0.0, 1.0 / floor)  # cap gain so pure silence isn't blown up into noise
    return samples * gain


def bandpass_filter(
    samples: np.ndarray,
    sample_rate: int,
    low_hz: float = 700.0,
    high_hz: float = 800.0,
    order: int = 4,
) -> np.ndarray:
    """
    4th-order Butterworth bandpass filter centered on the transmitter tone,
    implemented as second-order-sections for numerical stability, applied
    forward+backward (filtfilt) to avoid phase distortion.
    """
    nyquist = 0.5 * sample_rate
    low = max(low_hz / nyquist, 1e-6)
    high = min(high_hz / nyquist, 0.999999)
    sos = butter(order, [low, high], btype="bandpass", output="sos")
    return sosfiltfilt(sos, samples)


def preprocess(samples: np.ndarray, sample_rate: int, low_hz: float = 700.0, high_hz: float = 800.0) -> np.ndarray:
    """
    Full pre-processing chain, in order:
      normalize -> noise blanker -> AGC -> bandpass filter -> re-normalize.

    The blanker runs before AGC so a handful of loud clicks can't skew the
    AGC's level estimate; AGC runs before the bandpass filter so the
    filter (and everything downstream of it) sees a consistently-leveled
    signal rather than one with a few loud/quiet regions.
    """
    x = normalize(samples)
    x = noise_blanker(x, sample_rate)
    x = agc(x, sample_rate)
    x = bandpass_filter(x, sample_rate, low_hz, high_hz)
    x = normalize(x)
    return x


def find_candidate_tone_frequencies(
    samples: np.ndarray,
    sample_rate: int,
    search_low_hz: float = 300.0,
    search_high_hz: float = 2000.0,
    n_candidates: int = 3,
) -> List[float]:
    """
    Estimate where the Morse tone actually sits in the spectrum, instead of
    requiring the user to know or guess it in advance.

    Real-world recordings (radio off-air audio, YouTube CW practice clips,
    etc.) use whatever sidetone/beat-frequency the operator's rig happened
    to produce -- there is no universal "CW frequency". A fixed 700-800 Hz
    band only works by coincidence. This scans a wide search window
    (300-2000 Hz by default, covering the practical range of CW audio
    tones) using Welch's method for a noise-robust power spectral density
    estimate, then returns the strongest local peaks as candidate tone
    frequencies -- ordered by power, strongest first.

    Returning multiple candidates (not just the single loudest bin) matters
    because the single loudest frequency in a noisy clip is sometimes hum,
    voice, or a compression artifact rather than the actual CW tone; the
    caller (decode_audio) tries each candidate against the full decode
    pipeline and keeps whichever one actually produces plausible Morse
    timing, rather than trusting the spectrum alone.
    """
    x = normalize(samples)
    n = len(x)
    if n < 64:
        return [750.0]

    nperseg = min(4096, n)
    freqs, psd = welch(x, fs=sample_rate, nperseg=nperseg)

    band_mask = (freqs >= search_low_hz) & (freqs <= search_high_hz)
    if not np.any(band_mask):
        return [750.0]

    band_freqs = freqs[band_mask]
    band_psd = psd[band_mask]

    # minimum separation between peaks so we don't return several bins
    # that are really the same spectral lobe
    min_distance = max(1, int(len(band_psd) * 0.015))
    peak_idx, _ = find_peaks(band_psd, distance=min_distance)

    if len(peak_idx) == 0:
        # spectrum has no distinct local maxima (e.g. very short/flat
        # buffer) -- fall back to the single strongest bin in-band
        top = int(np.argmax(band_psd))
        return [float(band_freqs[top])]

    order = np.argsort(band_psd[peak_idx])[::-1][:n_candidates]
    return [float(band_freqs[i]) for i in peak_idx[order]]
