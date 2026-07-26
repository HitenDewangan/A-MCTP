"""
Section 5.1 of the PRD -- Pre-processing & Filtering Engine.
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt


def normalize(samples: np.ndarray) -> np.ndarray:
    """Scale audio samples uniformly into [-1.0, 1.0]."""
    samples = samples.astype(np.float64)
    peak = np.max(np.abs(samples))
    if peak < 1e-9:
        return samples
    return samples / peak


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


def highpass_filter(
    samples: np.ndarray,
    sample_rate: int,
    cutoff_hz: float = 150.0,
    order: int = 4,
) -> np.ndarray:
    """
    4th-order Butterworth high-pass filter to remove line hum (50/60 Hz),
    rumble, and DC before band-passing.
    """
    nyquist = 0.5 * sample_rate
    low = max(cutoff_hz / nyquist, 1e-6)
    sos = butter(order, low, btype="highpass", output="sos")
    return sosfiltfilt(sos, samples)


def preprocess(samples: np.ndarray, sample_rate: int, low_hz: float = 700.0, high_hz: float = 800.0) -> np.ndarray:
    """Full pre-processing chain: normalize -> highpass -> bandpass -> re-normalize."""
    x = normalize(samples)
    x = highpass_filter(x, sample_rate)
    x = bandpass_filter(x, sample_rate, low_hz, high_hz)
    x = normalize(x)
    return x
