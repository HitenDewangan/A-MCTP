import json

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..dsp import decoder, features, preprocessing

router = APIRouter()

SAMPLE_RATE = 8000          # expected client sample rate (PCM16 mono)
FLUSH_SILENCE_S = 1.4       # tail silence long enough to be a safe word boundary
MAX_BUFFER_S = 12.0         # hard cap so a stuck connection can't grow unbounded
WATERFALL_FFT_SIZE = 512


class StreamSession:
    """Per-connection rolling state for the live decoder."""

    def __init__(self):
        self.buffer = np.zeros(0, dtype=np.float32)
        self.accumulated_text = ""

    def append(self, chunk: np.ndarray):
        self.buffer = np.concatenate([self.buffer, chunk])
        max_len = int(MAX_BUFFER_S * SAMPLE_RATE)
        if len(self.buffer) > max_len:
            self.buffer = self.buffer[-max_len:]

    def trailing_silence_s(self) -> float:
        if len(self.buffer) < SAMPLE_RATE // 10:
            return 0.0
        clean = preprocessing.preprocess(self.buffer, SAMPLE_RATE)
        env = features.smooth(features.envelope_hilbert(clean), SAMPLE_RATE)
        mask = features.adaptive_threshold(env, SAMPLE_RATE)

        # sosfiltfilt can ring for a few dozen ms right at the buffer's own
        # boundary (it has no future samples to anchor its edge padding),
        # which can spuriously flag the very last samples as "tone on"
        # even during real silence. Skip that guard band before scanning.
        edge_guard = int(0.05 * SAMPLE_RATE)  # 50ms
        scan_end = len(mask) - 1 - edge_guard
        if scan_end < 0:
            return 0.0
        if mask[scan_end]:
            return 0.0
        idx = scan_end
        count = 0
        while idx >= 0 and not mask[idx]:
            count += 1
            idx -= 1
        return count / SAMPLE_RATE

    def flush_and_decode(self) -> decoder.DecodeResult:
        result = decoder.decode_audio(self.buffer, SAMPLE_RATE)
        self.buffer = np.zeros(0, dtype=np.float32)
        return result


def pcm16_bytes_to_float(raw: bytes) -> np.ndarray:
    ints = np.frombuffer(raw, dtype="<i2")
    return (ints.astype(np.float32)) / 32768.0


def waterfall_frame(chunk: np.ndarray) -> list:
    """Magnitude spectrum for the scrolling waterfall canvas (Feature Set 3)."""
    if len(chunk) < 16:
        return []
    windowed = chunk[-WATERFALL_FFT_SIZE:] if len(chunk) >= WATERFALL_FFT_SIZE else np.pad(
        chunk, (WATERFALL_FFT_SIZE - len(chunk), 0)
    )
    windowed = windowed * np.hanning(len(windowed))
    spectrum = np.abs(np.fft.rfft(windowed))
    spectrum_db = 20 * np.log10(spectrum + 1e-6)
    # downsample to ~64 bins for the UI
    bins = np.array_split(spectrum_db, 64)
    return [float(np.mean(b)) for b in bins]


@router.websocket("/api/v1/decode/stream")
async def decode_stream(websocket: WebSocket):
    await websocket.accept()
    session = StreamSession()
    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"] is not None:
                chunk = pcm16_bytes_to_float(message["bytes"])
                session.append(chunk)

                await websocket.send_text(json.dumps({
                    "type": "waterfall",
                    "bins": waterfall_frame(chunk),
                }))

                silence_s = session.trailing_silence_s()
                if silence_s >= FLUSH_SILENCE_S and len(session.buffer) > SAMPLE_RATE // 4:
                    result = session.flush_and_decode()
                    if result.text:
                        session.accumulated_text += (" " if session.accumulated_text else "") + result.text
                    await websocket.send_text(json.dumps({
                        "type": "partial_result",
                        "new_text": result.text,
                        "accumulated_text": session.accumulated_text,
                        "wpm_estimate": result.wpm_estimate,
                        "warning": result.warning,
                    }))

            elif "text" in message and message["text"] is not None:
                # control messages, e.g. {"action": "flush"} to force a decode now
                try:
                    control = json.loads(message["text"])
                except json.JSONDecodeError:
                    control = {}
                if control.get("action") == "flush" and len(session.buffer) > 0:
                    result = session.flush_and_decode()
                    if result.text:
                        session.accumulated_text += (" " if session.accumulated_text else "") + result.text
                    await websocket.send_text(json.dumps({
                        "type": "partial_result",
                        "new_text": result.text,
                        "accumulated_text": session.accumulated_text,
                        "wpm_estimate": result.wpm_estimate,
                        "warning": result.warning,
                    }))
                elif control.get("action") == "reset":
                    session = StreamSession()

    except WebSocketDisconnect:
        pass
