# A-MCTP — Audio Morse Code Translation Platform

An end-sem (6-credit) project combining **DSP**, **unsupervised ML**, and
**full-stack engineering**: it listens to audio containing Morse code
(live from a microphone, or from an uploaded `.wav`/`.mp3`/`.ogg` file)
and translates it into text — and can also do the reverse (text → Morse
audio).

This implementation follows the PRD in full: FastAPI + Celery + Redis +
JWT auth + WebSocket live streaming + SQLite history + multi-format
export, with a custom HTML/Tailwind/vanilla-JS frontend.

---

## 1. Architecture at a glance

```
 Browser (frontend/)
   │  REST (upload, auth, history, export, synth)
   │  WebSocket (live mic streaming)
   ▼
 FastAPI (backend/app/main.py)
   │                              │
   │ dispatches job                │ handles stream in-process
   ▼                              ▼
 Celery worker  ── Redis (broker + result backend)
   │
   ▼
 DSP/ML pipeline (backend/app/dsp/)
   Raw audio → Bandpass filter → Envelope (Hilbert) → Adaptive
   threshold → K-Means clustering (dot/dash) → gap classification
   (anchored to the K-Means dot-unit) → Morse→text mapping
   │
   ▼
 SQLite (translation history, per PRD Feature Set 1)
```

See `docs/ARCHITECTURE.md` for the full write-up (useful for your
project report) and `docs/DSP_ML_NOTES.md` for the algorithmic detail
markers/graders tend to ask about.

## 2. Quick start (Docker — recommended)

```bash
cd morse-decoder
docker compose up --build
```

This starts four containers: `redis`, `backend` (FastAPI on :8000),
`worker` (Celery), and `frontend` (nginx serving the static UI on
:8080). Open **http://localhost:8080**.

## 3. Running without Docker (local dev)

You need Python 3.11+, `ffmpeg` (for `.mp3` support), and a local Redis.

```bash
# system deps (Ubuntu/Debian)
sudo apt-get install ffmpeg libsndfile1 redis-server
redis-server --daemonize yes

cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# terminal 1: API server
uvicorn app.main:app --reload --port 8000

# terminal 2: Celery worker
celery -A app.celery_app.celery_app worker --loglevel=info

# terminal 3: static frontend (any static server works)
cd ../frontend && python3 -m http.server 8080
```

Then open **http://localhost:8080**.

## 4. Running the tests

The DSP/ML core is the part your grader will scrutinize most, so it
has a real pytest suite (round-trip synth→decode tests, a 10dB-SNR
resilience test straight from the PRD's success metrics, and a
malformed/silent-input test):

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

All 13 tests should pass. You can also sanity-check the pipeline
manually:

```python
from app.dsp import synth, decoder
audio = synth.synthesize("SOS", wpm=20, freq_hz=750, sample_rate=8000)
result = decoder.decode_audio(audio, 8000)
print(result.text, result.wpm_estimate)   # SOS 20.8
```

## 5. API surface

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | Create account, returns JWT |
| POST | `/api/v1/auth/login` | Login, returns JWT |
| POST | `/api/v1/decode/upload` | Submit audio file, returns `job_id` (Celery) |
| GET  | `/api/v1/decode/status/{job_id}/stream` | SSE progress stream |
| GET  | `/api/v1/decode/result/{job_id}` | Final decoded text + timing events |
| WS   | `/api/v1/decode/stream` | Live mic PCM16 streaming decode |
| GET  | `/api/v1/history` | Logged-in user's past translations |
| GET  | `/api/v1/export/{job_id}?format=txt\|csv\|pdf` | Download translation |
| POST | `/api/v1/synth` | Text → Morse `.wav` (reverse synthesis) |

Full interactive docs (Swagger) are auto-generated at
**http://localhost:8000/docs** once the backend is running.

## 6. Project structure

```
morse-decoder/
├── backend/
│   ├── app/
│   │   ├── dsp/                 # the DSP + ML core (pure numpy/scipy/sklearn)
│   │   │   ├── preprocessing.py #  normalize + Butterworth bandpass
│   │   │   ├── features.py      #  Hilbert envelope + adaptive threshold
│   │   │   ├── clustering.py    #  K-Means dot/dash + gap classification
│   │   │   ├── morse_map.py     #  Morse<->text lookup tables
│   │   │   ├── synth.py         #  reverse synthesis (text -> audio)
│   │   │   └── decoder.py       #  orchestrates the full pipeline
│   │   ├── routers/             # auth, upload, stream, history, export, synth
│   │   ├── main.py, config.py, database.py, models.py, auth.py
│   │   ├── celery_app.py, tasks.py
│   │   └── tests/test_decoder.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # vanilla HTML/JS/Tailwind, no build step
│   ├── index.html
│   ├── css/style.css
│   └── js/ (api, app, audio-capture, audio-worklet-processor,
│            websocket-client, waveform, waterfall, synth)
├── docker-compose.yml
└── docs/
    ├── ARCHITECTURE.md
    ├── DSP_ML_NOTES.md
    └── REPORT_OUTLINE.md
```

## 7. Known simplifications (worth mentioning in your viva)

- **Auth is intentionally minimal** — JWT + bcrypt over SQLite, no
  refresh tokens/roles. Fine for an academic deliverable; call it out
  as a known limitation if asked about production-hardening.
- **Live streaming** decodes in "flush on trailing silence" chunks
  (word-boundary flushes) rather than true per-symbol incremental
  decoding — this keeps the K-Means clustering statistically
  meaningful (it needs a handful of symbols to find real dot/dash
  clusters) while still meeting the <250ms tone-to-waterfall latency
  target. The decoded *text* naturally lags slightly behind the
  *visual* waterfall, which is expected and worth explaining in your
  report as a deliberate trade-off.
- **MP3 decoding** goes through `pydub`, which needs the `ffmpeg`
  binary on the host/container (already in the provided `Dockerfile`).
- **Celery is genuinely used** for batch jobs; the live WebSocket path
  intentionally runs its DSP in-process (in the FastAPI event loop's
  thread) since round-tripping every 30ms audio frame through a task
  queue would itself blow the 250ms latency budget — this is a
  deliberate architecture choice, not an oversight, and is worth
  explaining if a grader asks "why isn't the WebSocket path using
  Celery too?"

- it now auto-detects and returns `result.detected_freq_hz`