import json

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

from ..dsp import decoder, features, preprocessing

router = APIRouter()

SAMPLE_RATE = 8000          # expected client sample rate (PCM16 mono)
FLUSH_SILENCE_S = 1.4       # tail silence long enough to be a safe word boundary
MAX_BUFFER_S = 12.0         # hard cap so a stuck connection can't grow unbounded
WATERFALL_FFT_SIZE = 512


INTERIM_DECODE_S = 1.0         # re-decode the rolling buffer at least this often
INTERIM_MIN_TONE_S = 0.15       # ignore sub-second blips for interim previews


class StreamSession:
    """Per-connection rolling state for the live decoder."""

    def __init__(self):
        self.buffer = np.zeros(0, dtype=np.float32)
        self.accumulated_text = ""
        self._last_interim_s = 0.0
        self._committed_buffer_len = 0

    def append(self, chunk: np.ndarray):
        self.buffer = np.concatenate([self.buffer, chunk])
        max_len = int(MAX_BUFFER_S * SAMPLE_RATE)
        if len(self.buffer) > max_len:
            self.buffer = self.buffer[-max_len:]

    def trailing_silence_s(self) -> float:
        # Calculate exactly how many samples we need to look back:
        # FLUSH_SILENCE_S + 50ms edge guard + a small buffer margin (e.g., 200ms)
        lookback_s = FLUSH_SILENCE_S + 0.05 + 0.20
        lookback_samples = int(lookback_s * SAMPLE_RATE)

        if len(self.buffer) < lookback_samples:
            return 0.0

        # ONLY process the tail end of the buffer!
        tail_buffer = self.buffer[-lookback_samples:]

        # This used to always filter a hardcoded 700-800 Hz band regardless
        # of the tone's real frequency -- for any recording sent at a
        # different pitch, this check was filtering pure noise/silence the
        # entire time, which could make it flush constantly (or never).
        # Auto-detect a single best-guess frequency here (cheap: one Welch
        # PSD call, no multi-candidate decode retries needed just to find a
        # band to look at) so silence detection tracks whatever tone is
        # actually present, the same as the real decode does.
        candidates = preprocessing.find_candidate_tone_frequencies(
            tail_buffer, SAMPLE_RATE, n_candidates=1
        )
        f0 = candidates[0]
        low_hz = max(20.0, f0 - decoder.AUTO_BANDWIDTH_HZ)
        high_hz = f0 + decoder.AUTO_BANDWIDTH_HZ

        clean = preprocessing.preprocess(tail_buffer, SAMPLE_RATE, low_hz, high_hz)
        env = features.smooth(features.envelope_hilbert(clean), SAMPLE_RATE)
        mask = features.adaptive_threshold(env, SAMPLE_RATE)

        # sosfiltfilt can ring for a few dozen ms right at the buffer's own
        # boundary (it has no future samples to anchor its edge padding),
        # which can spuriously flag the very last samples as "tone on"
        # even during real silence. Skip that guard band before scanning.
        edge_guard = int(0.05 * SAMPLE_RATE)  # 50ms
        scan_end = len(mask) - 1 - edge_guard
        if scan_end < 0 or mask[scan_end]:
            return 0.0

        idx = scan_end
        count = 0
        while idx >= 0 and not mask[idx]:
            count += 1
            idx -= 1

        return count / SAMPLE_RATE

    def _append_text(self, new_text: str):
        if new_text:
            self.accumulated_text += (" " if self.accumulated_text else "") + new_text

    def interim_decode(self) -> decoder.DecodeResult:
        """Live preview: decode the rolling buffer WITHOUT clearing it, so the
        operator sees the message build up in real time as they key. The
        trailing, not-yet-terminated word is intentionally included as a
        provisional preview."""
        return decoder.decode_audio(self.buffer, SAMPLE_RATE)

    def flush_and_decode(self) -> decoder.DecodeResult:
        result = decoder.decode_audio(self.buffer, SAMPLE_RATE)
        self.buffer = np.zeros(0, dtype=np.float32)
        self._committed_buffer_len = 0
        self._last_interim_s = 0.0
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
            # Starlette delivers a disconnect event as a normal receive
            # message. Exit immediately so a second receive is never made.
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                chunk = pcm16_bytes_to_float(message["bytes"])
                session.append(chunk)

                await websocket.send_text(json.dumps({
                    "type": "waterfall",
                    "bins": waterfall_frame(chunk),
                }))

                # Real-time feel: while audio is flowing, re-decode the rolling
                # buffer on a throttle so the operator sees the message build
                # up live (the trailing word is a provisional preview).
                now_s = len(session.buffer) / SAMPLE_RATE
                silence_s = session.trailing_silence_s()

                if silence_s < FLUSH_SILENCE_S:
                    if now_s - session._last_interim_s >= INTERIM_DECODE_S and len(session.buffer) > SAMPLE_RATE // 4:
                        result = await asyncio.to_thread(session.interim_decode)
                        if result.text:
                            await websocket.send_text(json.dumps({
                                "type": "partial_result",
                                "new_text": result.text,
                                "accumulated_text": session.accumulated_text + (" " if session.accumulated_text else "") + result.text,
                                "wpm_estimate": result.wpm_estimate,
                                "detected_freq_hz": result.detected_freq_hz,
                                "warning": result.warning,
                                "interim": True,
                            }))
                        session._last_interim_s = now_s
                else:
                    # Sustained silence -> the current word/phrase is finished.
                    # Commit the buffer exactly once, then clear it so we don't
                    # re-flush on every subsequent silent chunk.
                    if len(session.buffer) > SAMPLE_RATE // 4:
                        result = await asyncio.to_thread(session.flush_and_decode)
                        if result.text:
                            session._append_text(result.text)
                        await websocket.send_text(json.dumps({
                            "type": "partial_result",
                            "new_text": result.text,
                            "accumulated_text": session.accumulated_text,
                            "wpm_estimate": result.wpm_estimate,
                            "detected_freq_hz": result.detected_freq_hz,
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
                        "detected_freq_hz": result.detected_freq_hz,
                        "warning": result.warning,
                    }))
                elif control.get("action") == "reset":
                    session = StreamSession()

    except WebSocketDisconnect:
        pass
