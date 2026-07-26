"""
Orchestrates: Raw Audio -> Bandpass -> Envelope -> Adaptive Threshold ->
Clustering (ML) -> Language Mapping, per Section 5 of the PRD.
"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from . import clustering, features, preprocessing
from .morse_map import symbols_to_text, WORD_GAP_TOKEN


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


def decode_audio(
    samples: np.ndarray,
    sample_rate: int,
    low_hz: float = 700.0,
    high_hz: float = 800.0,
) -> DecodeResult:
    if samples.ndim > 1:
        samples = samples.mean(axis=1)  # downmix to mono

    clean = preprocessing.preprocess(samples, sample_rate, low_hz, high_hz)
    envelope = features.smooth(features.envelope_hilbert(clean), sample_rate)
    envelope = features.noise_gate(envelope, sample_rate)
    mask = features.adaptive_threshold(envelope, sample_rate)
    pulses = features.mask_to_pulses(mask, sample_rate)
    pulses = features.strip_micro_glitches(pulses)

    # Leading/trailing silence is just recording head/tail room, not a
    # meaningful separator -- drop it so it can't distort gap clustering.
    if pulses and not pulses[0].is_tone:
        pulses = pulses[1:]
    if pulses and not pulses[-1].is_tone:
        pulses = pulses[:-1]

    mark_pulses = [p for p in pulses if p.is_tone]
    space_pulses = [p for p in pulses if not p.is_tone]

    if len(mark_pulses) < 1:
        return DecodeResult(
            text="", symbol_stream="", wpm_estimate=0.0,
            warning="Not enough tone activity detected to decode. Check "
                    "the frequency band and SNR of the recording.",
        )

    mark_clusters = clustering.cluster_marks(mark_pulses)
    dot_centroid = mark_clusters.centroids[0]

    min_dot_s = max(0.35 * dot_centroid, 0.018)
    pulses = features.prune_short_marks(pulses, min_dot_s)
    if not pulses:
        return DecodeResult(
            text="", symbol_stream="", wpm_estimate=0.0,
            warning="Not enough tone activity detected to decode. Check "
                    "the frequency band and SNR of the recording.",
        )

    mark_pulses = [p for p in pulses if p.is_tone]
    space_pulses = [p for p in pulses if not p.is_tone]

    if len(mark_pulses) < 1:
        return DecodeResult(
            text="", symbol_stream="", wpm_estimate=0.0,
            warning="Not enough tone activity detected to decode. Check "
                    "the frequency band and SNR of the recording.",
        )

    wpm = clustering.estimate_wpm(dot_centroid)

    gap_clusters = (
        clustering.cluster_gaps(space_pulses, reference_unit_s=dot_centroid)
        if space_pulses else None
    )

    # rebuild an ordered timeline of (pulse, cluster_label_or_None)
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
                    # no separator needed within a letter
                elif label == 1:
                    symbol_chars.append(" ")
                    events.append(SymbolEvent("letter_gap", start, end))
                else:
                    symbol_chars.append(f" {WORD_GAP_TOKEN} ")
                    events.append(SymbolEvent("word_gap", start, end))
        t = end

    symbol_stream = "".join(symbol_chars).strip()
    # collapse any accidental double letter-separators
    symbol_stream = " ".join(symbol_stream.split())
    text = symbols_to_text(symbol_stream)

    return DecodeResult(
        text=text,
        symbol_stream=symbol_stream,
        wpm_estimate=wpm,
        events=events,
    )
