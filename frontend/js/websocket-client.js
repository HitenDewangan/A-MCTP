class MorseStreamClient {
  constructor({ onWaterfall, onPartialResult, onOpen, onClose }) {
    this.onWaterfall = onWaterfall;
    this.onPartialResult = onPartialResult;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.ws = null;
    this.capture = null;
  }

  async start() {
    this.ws = new WebSocket(Api.wsUrl());
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => this.onOpen?.();
    this.ws.onclose = () => this.onClose?.();
    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "waterfall") this.onWaterfall?.(msg.bins);
      if (msg.type === "partial_result") this.onPartialResult?.(msg);
    };

    this.capture = new AudioCapture((buffer) => {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(buffer);
    });
    await this.capture.start();
  }

  forceFlush() {
    this.ws?.send(JSON.stringify({ action: "flush" }));
  }

  reset() {
    this.ws?.send(JSON.stringify({ action: "reset" }));
  }

  stop() {
    this.capture?.stop();
    this.ws?.close();
  }
}
