// Wraps getUserMedia + AudioWorkletNode setup for live mic capture.
class AudioCapture {
  constructor(onChunk) {
    this.onChunk = onChunk;
    this.audioContext = null;
    this.workletNode = null;
    this.sourceNode = null;
    this.stream = null;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    this.audioContext = new AudioContext();
    await this.audioContext.audioWorklet.addModule("js/audio-worklet-processor.js");

    this.sourceNode = this.audioContext.createMediaStreamSource(this.stream);
    this.workletNode = new AudioWorkletNode(this.audioContext, "morse-capture-processor");
    this.workletNode.port.onmessage = (event) => this.onChunk(event.data);

    this.sourceNode.connect(this.workletNode);
    // Don't connect workletNode to destination -- we don't want to hear
    // raw mic feedback through the speakers.
  }

  stop() {
    this.sourceNode?.disconnect();
    this.workletNode?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.audioContext?.close();
  }
}
