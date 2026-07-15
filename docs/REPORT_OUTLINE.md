# Suggested Report Outline

Use this as a skeleton for your end-sem report / documentation
submission — it maps directly onto the PRD's sections so a grader can
trace each requirement to what was actually built.

1. **Introduction & Objective** — copy/adapt PRD §1.
2. **System Architecture** — use `docs/ARCHITECTURE.md` §1-2, and
   include the component diagram (redraw the ASCII one, or ask Claude
   for an SVG version to paste in).
3. **DSP Pipeline** — walk through `docs/DSP_ML_NOTES.md`, plot a
   before/after spectrogram of a noisy recording pre/post bandpass
   filter (a couple of matplotlib figures generated from
   `backend/app/dsp/preprocessing.py` output would look good here).
4. **Machine Learning Component** — explain the K-Means dot/dash
   clustering and the anchored gap classification; include the 10dB
   SNR and ±25% jitter test results from `docs/DSP_ML_NOTES.md` as
   your "validation" section — most rubrics explicitly ask for
   quantified accuracy numbers, and these are real, reproducible ones
   (`pytest tests/ -v`).
5. **Backend Engineering** — FastAPI + Celery + Redis + JWT auth +
   SQLite, why each was chosen (`docs/ARCHITECTURE.md` §1), API
   surface table (`README.md` §5).
6. **Frontend** — dual-panel dark UI, live waterfall + waveform
   overlay, screenshots of both Batch and Live modes in action.
7. **Testing & Results** — pytest output, the manual stress-test
   table, a couple of example decoded transcripts with their source
   audio described (WPM, noise level, message).
8. **Limitations & Future Work** — pull directly from
   `docs/DSP_ML_NOTES.md`'s "Honest limitations" section and
   `README.md` §7; grading panels tend to reward projects that show
   awareness of their own edge cases rather than ones that claim
   perfection.
9. **Conclusion**.

## Screenshots to capture before writing the report

- Batch mode: an uploaded file mid-decode (progress bar visible),
  then the finished waveform-with-overlay + decoded text.
- Live mode: the scrolling waterfall while speaking/keying near the
  mic, plus the growing live transcript.
- The reverse-synthesis panel producing an audio file from typed text.
- `/docs` (Swagger UI) showing the full API surface — graders like
  seeing this, it's evidence the "automatic OpenAPI documentation"
  claim in the PRD's tech-stack table is real.
