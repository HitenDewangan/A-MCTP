import os
from datetime import datetime

import numpy as np

from .celery_app import celery_app
from .database import SessionLocal, TranslationJob
from .dsp import decoder


def _load_audio(filepath: str):
    """
    Load .wav/.ogg via libsndfile (soundfile). .mp3 needs ffmpeg-backed
    decoding via pydub, since libsndfile does not support MPEG natively.
    """
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".mp3":
        from pydub import AudioSegment
        seg = AudioSegment.from_file(filepath, format="mp3")
        sr = seg.frame_rate
        samples = np.array(seg.get_array_of_samples()).astype(np.float32)
        if seg.channels > 1:
            samples = samples.reshape((-1, seg.channels))
        samples = samples / (2 ** (8 * seg.sample_width - 1))
        return samples, sr
    else:
        import soundfile as sf
        samples, sr = sf.read(filepath, always_2d=False)
        return samples, sr


@celery_app.task(bind=True, name="app.tasks.decode_upload_task")
def decode_upload_task(self, job_id: str, filepath: str, low_hz: float = None, high_hz: float = None):
    db = SessionLocal()
    try:
        job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
        if not job:
            return {"error": "job not found"}

        job.status = "PROCESSING"
        db.commit()
        self.update_state(state="PROCESSING", meta={"stage": "loading_audio", "progress": 10})

        samples, sr = _load_audio(filepath)
        self.update_state(state="PROCESSING", meta={"stage": "filtering", "progress": 35})

        result = decoder.decode_audio(samples, sr, low_hz=low_hz, high_hz=high_hz)
        self.update_state(state="PROCESSING", meta={"stage": "clustering", "progress": 75})

        job.status = "DONE"
        job.decoded_text = result.text
        job.symbol_stream = result.symbol_stream
        job.wpm_estimate = result.wpm_estimate
        job.detected_freq_hz = result.detected_freq_hz
        job.warning = result.warning
        job.completed_at = datetime.utcnow()
        db.commit()

        self.update_state(state="SUCCESS", meta={"stage": "done", "progress": 100})
        return {
            "text": result.text,
            "symbol_stream": result.symbol_stream,
            "wpm_estimate": result.wpm_estimate,
            "warning": result.warning,
            "detected_freq_hz": result.detected_freq_hz,
            "events": [{"kind": e.kind, "start_s": e.start_s, "end_s": e.end_s} for e in result.events],
        }
    except Exception as exc:  # noqa: BLE001
        job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error = str(exc)
            db.commit()
        self.update_state(state="FAILURE", meta={"stage": "error", "error": str(exc)})
        raise
    finally:
        db.close()
        try:
            os.remove(filepath)
        except OSError:
            pass
