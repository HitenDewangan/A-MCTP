# Architecture

## 1. Why this stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | native async, auto OpenAPI docs, first-class WebSocket support needed for live streaming |
| DSP | NumPy + SciPy | vectorized array math; `scipy.signal` gives production-grade IIR filter design (`butter`) and zero-phase filtering (`sosfiltfilt`) instead of hand-rolled convolution |
| ML | scikit-learn `KMeans` | the timing-classification problem (dot vs dash; which gap is which) is fundamentally 1-D unsupervised clustering — no labels exist, and the "correct" cluster boundary shifts with operator speed (WPM), so a fixed threshold is the wrong tool |
| Async jobs | Celery + Redis | file decoding of a 25MB recording can take a few seconds; doing it inline would block the API worker and violate the "responsive UI" requirement |
| DB | SQLite via SQLAlchemy | zero-ops for an academic deployment; the ORM layer means swapping to Postgres later is a one-line `DATABASE_URL` change |
| Auth | JWT (python-jose) + bcrypt (passlib) | stateless — no server-side session store needed, works cleanly with the SPA-style frontend |

## 2. Two execution paths

### 2.1 Batch (file upload)

```
POST /api/v1/decode/upload
  → save file to disk
  → create TranslationJob row (status=QUEUED)
  → Celery apply_async(decode_upload_task)
  → return job_id immediately (202-style, but modeled as 200 w/ job_id)

Client polls:
  GET /api/v1/decode/status/{job_id}/stream   (Server-Sent Events)
  GET /api/v1/decode/result/{job_id}          (final payload)
```

The Celery task (`app/tasks.py::decode_upload_task`) does the actual
work: load audio (`soundfile` for wav/ogg, `pydub`+ffmpeg for mp3) →
run the shared `decoder.decode_audio()` pipeline → write results back
to the DB row → clean up the temp file.

### 2.2 Live (microphone streaming)

```
Browser:
  getUserMedia → AudioWorkletNode (js/audio-worklet-processor.js)
    downsamples native 44.1/48kHz → 8kHz, packs Int16 PCM,
    posts ~30ms chunks to the main thread
  → WebSocket send(ArrayBuffer) to /api/v1/decode/stream

Server (app/routers/stream.py):
  on each binary frame:
    - append to a per-connection rolling buffer
    - compute an FFT magnitude frame → send back as {"type":"waterfall"}
      (this round-trip is what has to stay under ~250ms)
    - check trailing silence duration
        if >= 1.4s (a safe word-boundary heuristic) and buffer has
        enough audio: run the full decode_audio() pipeline on the
        buffered chunk, append its text to the session's running
        transcript, send {"type":"partial_result"}, clear the buffer
```

This deliberately does **not** try to decode symbol-by-symbol as bits
arrive — K-Means needs a handful of dot/dash samples to find a
meaningful cluster boundary, and re-running it on every 30ms frame
would be wasteful and noisy. Flushing on a word-boundary silence gap
is the natural unit here: humans/software also pause between words.

## 3. The DSP/ML pipeline in detail

```
raw samples
  → normalize to [-1, 1]                          (preprocessing.py)
  → 4th-order Butterworth bandpass (700-800Hz)     (preprocessing.py)
  → Hilbert-transform envelope, light smoothing    (features.py)
  → adaptive Schmitt-trigger threshold             (features.py)
      (long window + hysteresis so a sustained dash
       isn't mistaken for silence partway through it)
  → run-length encode into (is_tone, duration) pulses
  → K-Means (K=2) on "tone on" durations            (clustering.py)
      → shortest-centroid cluster = dot, other = dash
      → dot centroid ⇒ estimated WPM (PARIS standard: WPM = 1.2/dot_s)
  → classify "tone off" gaps using thresholds anchored to the
    K-Means-derived dot-unit (< 2 units = intra-char,
    2-5 units = inter-char/letter, > 5 units = inter-word)
  → assemble the dot/dash/gap sequence into a Morse symbol stream
  → dictionary lookup → plain text                 (morse_map.py)
```

**Why gap classification is unit-anchored rather than its own flat
K-Means pass:** a short transmission may contain zero inter-word gaps
(e.g. a single-word callsign). Forcing K=3 (or even a 2-stage
hierarchical K-Means) onto data that only contains 1-2 real
populations causes K-Means to split quantization noise into a bogus
extra cluster, corrupting letter boundaries in exactly the messages
that most need to be right. Anchoring to the already-established dot
duration (itself a genuine K-Means output) keeps the system adaptive
to actual sending speed while staying robust when a category is
simply absent from the sample — this trade-off is worth a paragraph
in your report; it's a real design decision, not a hand-wave.

## 4. Data model

```
User            1 ──< TranslationJob
  id                    id (== Celery task_id)
  username              owner_id / session_id
  hashed_password       source_type ("upload"|"stream")
                        original_filename
                        status (QUEUED/PROCESSING/DONE/FAILED)
                        decoded_text, symbol_stream, wpm_estimate
                        warning, error
                        created_at, completed_at
```

Anonymous (unauthenticated) uploads are still tracked by
`session_id` (a client-generated UUID sent in the `X-Session-Id`
header) but don't appear in `/api/v1/history`, which requires a JWT.
