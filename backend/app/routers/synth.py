import io

import numpy as np
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import soundfile as sf

from ..dsp.synth import synthesize
from ..models import SynthesizeRequest

router = APIRouter(prefix="/api/v1/synth", tags=["synth"])


@router.post("")
def synthesize_morse(payload: SynthesizeRequest):
    audio = synthesize(payload.text, wpm=payload.wpm, freq_hz=payload.freq_hz, sample_rate=8000)
    buf = io.BytesIO()
    sf.write(buf, audio.astype(np.float32), 8000, format="WAV")
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=morse_synth.wav"},
    )
