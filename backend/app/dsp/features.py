"""
Section 5.2 of the PRD -- Signal Tokenization & Feature Engineering.
"""
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from scipy.signal import hilbert


def envelope_hilbert(samples: np.ndarray) -> np.ndarray:
    """Analytic-signal envelope via Hilbert transform."""
    analytic = hilbert(samples)
    return np.abs(analytic)


def envelope_rms(samples: np.ndarray, sample_rate: int, window_ms: float = 5.0) -> np.ndarray:
    """Sliding-window RMS envelope, same length as input (edge-padded)."""
    win = max(1, int(sample_rate * window_ms / 1000.0))
    kernel = np.ones(win) / win
    power = samples ** 2
    rms = np.sqrt(np.convolve(power, kernel, mode="same"))
    return rms


def smooth(envelope: np.ndarray, sample_rate: int, window_ms: float = 4.0) -> np.ndarray:
    win = max(1, int(sample_rate * window_ms / 1000.0))
    kernel = np.ones(win) / win
    return np.convolve(envelope, kernel, mode="same")


def noise_gate(envelope: np.ndarray, sample_rate: int, floor_percentile: float = 10) -> np.ndarray:
    """
    Suppress hiss and static by zeroing envelope samples that sit at or
    below the estimated noise floor.  This gives the adaptive threshold
    a cleaner input and prevents micro-flicker between real symbols.
    """
    noise_floor = np.percentile(envelope, floor_percentile)
    return np.where(envelope > noise_floor, envelope, 0.0)


def adaptive_threshold(
    envelope: np.ndarray,
    sample_rate: int,
    window_ms: float = 1500.0,
    hysteresis: float = 0.12,
) -> np.ndarray:
    """
    Adaptive Schmitt-trigger threshold with hysteresis.

    The moving window is deliberately much longer than any single dot/dash
    (>= 1.5s, i.e. several letters) so it tracks slow fading / AGC drift of
    the channel rather than the on/off pattern of individual symbols -- a
    short window would "chase" a sustained dash and misclassify it as
    silence partway through. Within that slowly-varying local range we take
    a threshold near the local floor and add hysteresis so noise near the
    boundary can't cause spurious flicker.
    """
    win = max(1, int(sample_rate * window_ms / 1000.0))
    pad = win // 2
    padded = np.pad(envelope, (pad, pad), mode="edge")
    step = max(1, win // 4)
    local_peak = np.array([
        padded[i:i + win].max() for i in range(0, len(envelope), step)
    ])
    idx = np.linspace(0, len(local_peak) - 1, len(envelope))
    local_peak_full = np.interp(idx, np.arange(len(local_peak)), local_peak)

    noise_floor = np.percentile(envelope, 10)
    threshold_mid = noise_floor + 0.45 * (local_peak_full - noise_floor)
    threshold_hi = threshold_mid * (1 + hysteresis)
    threshold_lo = threshold_mid * (1 - hysteresis)

    mask = np.zeros(len(envelope), dtype=bool)
    state = envelope[0] > threshold_mid[0]
    for i in range(len(envelope)):
        if state:
            state = envelope[i] > threshold_lo[i]
        else:
            state = envelope[i] > threshold_hi[i]
        mask[i] = state
    return mask


@dataclass
class Pulse:
    is_tone: bool          # True = sound on (mark), False = sound off (space)
    duration_s: float


def mask_to_pulses(mask: np.ndarray, sample_rate: int) -> List[Pulse]:
    """Run-length encode a boolean on/off mask into a list of Pulses."""
    if len(mask) == 0:
        return []
    pulses: List[Pulse] = []
    current_state = bool(mask[0])
    run_length = 1
    for value in mask[1:]:
        value = bool(value)
        if value == current_state:
            run_length += 1
        else:
            pulses.append(Pulse(current_state, run_length / sample_rate))
            current_state = value
            run_length = 1
    pulses.append(Pulse(current_state, run_length / sample_rate))
    return pulses


def strip_micro_glitches(pulses: List[Pulse], min_duration_s: float = 0.015) -> List[Pulse]:
    """
    Merge sub-threshold-duration blips (sensor/quantization noise) into the
    neighbouring pulse so they don't get misread as legitimate dots.
    """
    if not pulses:
        return pulses
    cleaned: List[Pulse] = [pulses[0]]
    for pulse in pulses[1:]:
        if pulse.duration_s < min_duration_s and cleaned:
            # extend previous pulse instead of keeping this tiny blip
            prev = cleaned[-1]
            cleaned[-1] = Pulse(prev.is_tone, prev.duration_s + pulse.duration_s)
        else:
            cleaned.append(pulse)
    # second pass merges consecutive same-state pulses created above
    merged: List[Pulse] = [cleaned[0]]
    for pulse in cleaned[1:]:
        if pulse.is_tone == merged[-1].is_tone:
            merged[-1] = Pulse(pulse.is_tone, merged[-1].duration_s + pulse.duration_s)
        else:
            merged.append(pulse)
    return merged


def prune_short_marks(pulses: List[Pulse], min_duration_s: float) -> List[Pulse]:
    """
    Remove tone pulses shorter than min_duration_s (residual micro-glitches
    that survived earlier stripping), merging adjacent silence pulses so
    the remaining pulse sequence stays valid.
    """
    if not pulses:
        return pulses
    pruned: List[Pulse] = []
    for p in pulses:
        if p.is_tone and p.duration_s < min_duration_s:
            continue
        if pruned and not pruned[-1].is_tone and not p.is_tone:
            prev = pruned[-1]
            pruned[-1] = Pulse(False, prev.duration_s + p.duration_s)
        else:
            pruned.append(p)
    return pruned
