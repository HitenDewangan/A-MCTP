"""
Section 5.3 of the PRD -- Clustering & Machine Learning Translation Module.

Rigid fixed-ratio timing (dash = 3x dot, letter gap = 3x dot, etc.) breaks
down on hand-keyed / noisy audio where operator timing drifts. Instead we
let K-Means discover the two natural clusters in "tone on" durations (dot
vs dash) and the three natural clusters in "tone off" durations (element
gap, letter gap, word gap), so the decoder self-calibrates to whatever
speed (WPM) the operator is actually sending at.
"""
from dataclasses import dataclass
from typing import List

import numpy as np
from sklearn.cluster import KMeans

from .features import Pulse


@dataclass
class ClusterResult:
    labels: np.ndarray          # cluster id (0..k-1) per input duration, sorted by centroid ascending
    centroids: List[float]      # sorted ascending


def _round_for_uniqueness(durations: np.ndarray, decimals: int = 3) -> int:
    """Count 'meaningfully distinct' duration values, ignoring floating
    point / sample-quantization noise, so we don't ask K-Means for more
    clusters than the data actually contains."""
    return len(np.unique(np.round(durations, decimals)))


def _cluster_durations(durations: np.ndarray, k: int) -> ClusterResult:
    X = durations.reshape(-1, 1)
    n_unique = _round_for_uniqueness(durations)
    effective_k = max(1, min(k, n_unique))
    km = KMeans(n_clusters=effective_k, n_init=10, random_state=42)
    raw_labels = km.fit_predict(X)
    centroids = km.cluster_centers_.flatten()

    # remap so label 0 = shortest duration cluster, label k-1 = longest
    order = np.argsort(centroids)
    remap = {old: new for new, old in enumerate(order)}
    labels = np.array([remap[l] for l in raw_labels])
    sorted_centroids = sorted(centroids.tolist())

    while len(sorted_centroids) < k:
        sorted_centroids.append(sorted_centroids[-1] * 3 if sorted_centroids else 0.06)

    return ClusterResult(labels=labels, centroids=sorted_centroids)


def cluster_marks(mark_pulses: List[Pulse]) -> ClusterResult:
    """K=2 clustering of 'tone on' durations -> {0: dot, 1: dash}."""
    durations = np.array([p.duration_s for p in mark_pulses])
    return _cluster_durations(durations, k=2)


def cluster_gaps(space_pulses: List[Pulse], reference_unit_s: float) -> ClusterResult:
    """
    Classify 'tone off' durations into {0: intra-char element gap,
    1: inter-char letter gap, 2: inter-word gap}, anchored to the dot-unit
    duration already established (via K-Means, see cluster_marks) for this
    transmission -- rather than re-clustering gaps from scratch.

    A flat, un-anchored K-Means over gap durations is unreliable here: a
    short message may contain zero word-gaps, so forcing K=3 (or even a
    hierarchical 2-then-2 split) onto one or two real populations
    misclassifies letter boundaries in exactly the messages that most need
    to be correct (single-word callsigns, etc.).

    Instead we reuse the transmission's own self-calibrated dot-length
    (itself the product of unsupervised clustering on the marks) and bucket
    each gap against the standard PARIS ratio boundaries -- the midpoints
    between 1/3/7 units, i.e. 2 units and 5 units. This keeps the system
    adaptive to whatever WPM the operator is actually sending at (unlike a
    hard-coded absolute-millisecond threshold) while remaining robust when
    a whole gap category is entirely absent from the sample.
    """
    durations = np.array([p.duration_s for p in space_pulses])
    unit = reference_unit_s if reference_unit_s > 0 else (
        float(np.min(durations)) if len(durations) else 0.06
    )

    intra_hi = 2.0 * unit   # boundary between element gap and letter gap
    inter_hi = 5.0 * unit   # boundary between letter gap and word gap

    labels = np.where(durations < intra_hi, 0, np.where(durations < inter_hi, 1, 2))

    # report observed centroids per bucket (falling back to the ideal
    # PARIS ratio when a bucket has no members) for diagnostics/telemetry.
    def _centroid(bucket_label: int, fallback: float) -> float:
        bucket = durations[labels == bucket_label]
        return float(bucket.mean()) if len(bucket) else fallback

    centroids = [
        _centroid(0, unit),
        _centroid(1, unit * 3),
        _centroid(2, unit * 7),
    ]
    return ClusterResult(labels=labels, centroids=centroids)


def estimate_wpm(dot_centroid_s: float) -> float:
    """PARIS standard: WPM = 1.2 / dot_duration_seconds."""
    if dot_centroid_s <= 0:
        return 0.0
    return round(1.2 / dot_centroid_s, 1)
