// Runs on the audio rendering thread. Downsamples from the browser's
// native AudioContext sample rate (usually 44.1/48kHz) down to the
// TARGET_SAMPLE_RATE the backend DSP pipeline expects (8kHz -- plenty of
// bandwidth for a ~700-800Hz CW tone), then posts Int16 PCM chunks back to
// the main thread in ~20-50ms windows per the PRD's streaming spec.

const TARGET_SAMPLE_RATE = 8000;

class MorseCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.inputSampleRate = sampleRate; // global provided by AudioWorkletGlobalScope
    this.decimationFactor = Math.max(1, Math.round(this.inputSampleRate / TARGET_SAMPLE_RATE));
    this.accumulator = [];
    this.chunkTargetSamples = Math.round(TARGET_SAMPLE_RATE * 0.03); // ~30ms windows
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channelData = input[0];
    if (!channelData) return true;

    for (let i = 0; i < channelData.length; i += this.decimationFactor) {
      // simple decimation (adequate for a narrowband ~750Hz tone well
      // under the downsampled Nyquist of 4kHz)
      this.accumulator.push(channelData[i]);
    }

    if (this.accumulator.length >= this.chunkTargetSamples) {
      const floatChunk = this.accumulator.splice(0, this.accumulator.length);
      const int16 = new Int16Array(floatChunk.length);
      for (let i = 0; i < floatChunk.length; i++) {
        const s = Math.max(-1, Math.min(1, floatChunk[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}

registerProcessor("morse-capture-processor", MorseCaptureProcessor);
