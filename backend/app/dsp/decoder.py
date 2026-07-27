"""
Orchestrates: Raw Audio -> Bandpass -> Envelope -> Adaptive Threshold ->
Clustering (ML) -> Language Mapping, per Section 5 of the PRD.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from . import clustering, features, preprocessing
from .morse_map import symbols_to_text, WORD_GAP_TOKEN

# Default half-bandwidth around an auto-detected tone frequency. Narrow
# enough to reject most background noise/hum/music, wide enough to
# tolerate a few Hz of detection jitter and typical CW tone drift.
AUTO_BANDWIDTH_HZ = 70.0
AUTO_SEARCH_LOW_HZ = 300.0
AUTO_SEARCH_HIGH_HZ = 2000.0
AUTO_CANDIDATES = 3


@dataclass
class SymbolEvent:
    """One decoded dot/dash or gap, with its position in time (for the
    waveform overlay required by Feature Set 2)."""
    kind: str          # "dot" | "dash" | "letter_gap" | "word_gap" | "element_gap"
    start_s: float
    end_s: float


@dataclass
class DecodeResult:
    text: str
    symbol_stream: str
    wpm_estimate: float
    events: List[SymbolEvent] = field(default_factory=list)
    warning: Optional[str] = None
    detected_freq_hz: Optional[float] = None  # populated when auto-detection ran


def _run_pipeline(
    samples: np.ndarray,
    sample_rate: int,
    low_hz: float,
    high_hz: float,
) -> Tuple[DecodeResult, float]:
    """
    Runs the full bandpass -> envelope -> threshold -> clustering -> text
    pipeline for one specific frequency band. Returns the result plus the
    fraction of the clip classified as "tone on" (used by decode_audio to
    judge whether this band actually contains the Morse tone, or just
    noise/silence).
    """
    clean = preprocessing.preprocess(samples, sample_rate, low_hz, high_hz)
    envelope = features.smooth(features.envelope_hilbert(clean), sample_rate)
    mask = features.adaptive_threshold(envelope, sample_rate)
    active_fraction = float(np.mean(mask)) if len(mask) else 0.0

    pulses = features.mask_to_pulses(mask, sample_rate)
    pulses = features.strip_micro_glitches(pulses)

    if pulses and not pulses[0].is_tone:
        pulses = pulses[1:]
    if pulses and not pulses[-1].is_tone:
        pulses = pulses[:-1]

    mark_pulses = [p for p in pulses if p.is_tone]
    space_pulses = [p for p in pulses if not p.is_tone]

    if len(mark_pulses) < 1:
        return DecodeResult(
            text="", symbol_stream="", wpm_estimate=0.0,
            warning="Not enough tone activity detected in this frequency band.",
        ), active_fraction

    mark_clusters = clustering.cluster_marks(mark_pulses)
    dot_centroid = mark_clusters.centroids[0]
    wpm = clustering.estimate_wpm(dot_centroid)

    gap_clusters = (
        clustering.cluster_gaps(space_pulses, reference_unit_s=dot_centroid)
        if space_pulses else None
    )

    mark_idx = 0
    space_idx = 0
    t = 0.0
    events: List[SymbolEvent] = []
    symbol_chars: List[str] = []

    for pulse in pulses:
        start = t
        end = t + pulse.duration_s
        if pulse.is_tone:
            label = mark_clusters.labels[mark_idx]
            mark_idx += 1
            if label == 0:
                symbol_chars.append(".")
                events.append(SymbolEvent("dot", start, end))
            else:
                symbol_chars.append("-")
                events.append(SymbolEvent("dash", start, end))
        else:
            if gap_clusters is not None:
                label = gap_clusters.labels[space_idx]
                space_idx += 1
                if label == 0:
                    events.append(SymbolEvent("element_gap", start, end))
                elif label == 1:
                    symbol_chars.append(" ")
                    events.append(SymbolEvent("letter_gap", start, end))
                else:
                    symbol_chars.append(f" {WORD_GAP_TOKEN} ")
                    events.append(SymbolEvent("word_gap", start, end))
        t = end

    symbol_stream = "".join(symbol_chars).strip()
    symbol_stream = " ".join(symbol_stream.split())
    text = symbols_to_text(symbol_stream)

    return DecodeResult(
        text=text,
        symbol_stream=symbol_stream,
        wpm_estimate=wpm,
        events=events,
    ), active_fraction


def decode_audio(
    samples: np.ndarray,
    sample_rate: int,
    low_hz: Optional[float] = None,
    high_hz: Optional[float] = None,
    auto_bandwidth_hz: float = AUTO_BANDWIDTH_HZ,
    search_low_hz: float = AUTO_SEARCH_LOW_HZ,
    search_high_hz: float = AUTO_SEARCH_HIGH_HZ,
) -> DecodeResult:
    """
    Decode Morse audio into text.

    If low_hz/high_hz are both given explicitly, they're honored exactly as
    a manual override (this is the legacy behavior, still useful for a
    power user who already knows their exact tone frequency).

    Otherwise (the default), the tone frequency is auto-detected: the
    spectrum is scanned for candidate CW tone frequencies, and each
    candidate is tried against the full decode pipeline. Whichever
    candidate actually produces plausible Morse timing (marks found, and a
    tone-on duty cycle that looks like real keying rather than noise or
    near-silence) is kept. This is what lets the system decode a real
    recording -- e.g. one pulled from YouTube -- without the user needing
    to know or guess its exact tone frequency in advance.
    """
    if samples.ndim > 1:
        samples = samples.mean(axis=1)  # downmix to mono

    if low_hz is not None and high_hz is not None:
        result, _ = _run_pipeline(samples, sample_rate, low_hz, high_hz)
        return result

    candidates = preprocessing.find_candidate_tone_frequencies(
        samples, sample_rate, search_low_hz, search_high_hz, n_candidates=AUTO_CANDIDATES
    )

    best_result: Optional[DecodeResult] = None
    best_freq: Optional[float] = None
    best_score = -1

    for f0 in candidates:
        lo = max(20.0, f0 - auto_bandwidth_hz)
        hi = f0 + auto_bandwidth_hz
        result, active_fraction = _run_pipeline(samples, sample_rate, lo, hi)
        n_marks = sum(1 for e in result.events if e.kind in ("dot", "dash"))
        # A real CW signal keys on/off with a moderate duty cycle. Near-0%
        # means we're looking at silence/nothing; near-100% means the band
        # is picking up a continuous tone or broadband noise, not keying.
        plausible_duty = 0.01 < active_fraction < 0.75
        score = n_marks if plausible_duty else -1
        if score > best_score:
            best_score = score
            best_result = result
            best_freq = f0

    if best_result is None or best_score <= 0:
        # Nothing looked plausible -- still return the top candidate's
        # (likely empty-with-warning) result so the caller sees a helpful
        # message rather than nothing at all.
        f0 = candidates[0]
        best_result, _ = _run_pipeline(
            samples, sample_rate, max(20.0, f0 - auto_bandwidth_hz), f0 + auto_bandwidth_hz
        )
        best_freq = f0

    best_result.detected_freq_hz = round(best_freq, 1) if best_freq is not None else None
    return best_result
