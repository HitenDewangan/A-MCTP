# DSP & ML Notes (for the project report / viva)

## Why K-Means and not a fixed WPM ratio?

Standard "PARIS" timing defines Morse ratios as 1 unit (dot) : 3 units
(dash) : 1 unit (intra-char gap) : 3 units (inter-char/letter gap) : 7
units (inter-word gap), where `unit_seconds = 1.2 / WPM`.

A naive decoder hard-codes an assumed WPM and classifies every pulse
against those fixed thresholds. That's brittle for two reasons the
PRD explicitly calls out:

1. **You don't know the sender's WPM in advance** — it has to be
   estimated *from* the recording, not assumed.
2. **Hand-keyed Morse has human timing jitter** — a real operator's
   "dot" might vary ±25% around its ideal duration from one keystroke
   to the next.

K-Means sidesteps both: given the set of observed "tone on" pulse
durations in *this* recording, K=2 clustering finds the two natural
groups (whatever their absolute durations are) and reports their
centroids. The shorter centroid is, by definition, "this operator's
dot", and `WPM = 1.2 / dot_centroid_seconds` falls out for free. No
assumption about sending speed is baked into the algorithm.

## Why the adaptive threshold uses a long window + hysteresis

An earlier (and much more naive) version of the adaptive threshold
used a short moving-average window (~120ms) to track the local
noise floor. That's a bug, not a feature: 120ms is comparable to (or
shorter than) a *single dash* at slow-to-moderate WPM, so the "local
mean" itself rises during a sustained tone and the threshold ends up
*chasing the signal it's supposed to be detecting* — a long dash gets
mistaken for silence partway through it.

The fix: use a window that's deliberately much longer than any single
symbol (≥1.5s, i.e. several letters), so it tracks only the slow
channel-level drift (fading, AGC), not individual dots/dashes. Within
that slowly-varying envelope, hysteresis (a Schmitt trigger with two
thresholds, not one) prevents noise sitting right at the boundary
from causing spurious on/off flicker mid-symbol.

## Why gap classification is anchored to the K-Means dot-unit

See `docs/ARCHITECTURE.md` §3 — short version: a flat K=3 (or
2-stage-hierarchical) K-Means over gap durations breaks down when a
transmission has zero examples of one category (most commonly: no
word gaps, in a single-word message like a callsign). The fix used
here reuses the already-estimated dot-unit (a genuine K-Means output
from the *marks*, not a hard-coded constant) and classifies each gap
by which multiple of that unit it's closest to. This keeps the
"adaptive to actual sending speed" property the PRD asks for, while
being robust to missing categories — which a purely automatic
re-clustering of gaps is not.

## Validated behavior (see `backend/tests/test_decoder.py`)

- Round-trip synth→decode across 9 messages, WPM 12-30, with up to 6%
  additive Gaussian noise: **all pass**, including a single-letter
  message ("A"), where K-Means only has 1 observed mark duration (an
  inherent ambiguity for single-symbol messages, noted directly in
  the code).
- **10dB SNR floor** (the PRD's stated resilience target,
  §7): decodes "HELLO WORLD" correctly at exactly 10dB SNR.
- **±25% hand-keyed timing jitter** (the PRD's stated clustering
  accuracy target, §7), tested across 4 messages × 5 random seeds
  with zero added noise: **20/20 pass**.
- Combined 10dB SNR *and* random jitter across the same messages:
  **12/12 pass** in the extended manual stress test.

## Honest limitations to mention if asked

- A message with **exactly one mark** (e.g. a lone "T" or "E") is
  fundamentally ambiguous to a clustering-based decoder: with only one
  observed duration, K-Means (K=1 effective) has no second cluster to
  compare against, so it defaults to classifying it as a dot. This
  is a structural limitation of *any* unsupervised approach on a
  single data point, not a bug — a rule-based fallback (e.g. "assume
  20 WPM if no other reference exists") could resolve this specific
  edge case at the cost of reintroducing the fixed-WPM assumption the
  rest of the system deliberately avoids.
- Very short recordings (a handful of symbols) give K-Means little to
  work with, so WPM estimates on short clips carry more variance than
  on longer ones — this is visible in the wider WPM-estimate tolerance
  used in the parametrized tests for short messages.
