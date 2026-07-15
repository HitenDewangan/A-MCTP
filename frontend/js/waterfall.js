// Scrolling spectrogram-style waterfall for the live stream mode
// (PRD 4.3: "continuous scrolling live canvas waterfall display").
class Waterfall {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.ctx.fillStyle = "#0f172a";
    this.ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  pushFrame(bins) {
    if (!bins || bins.length === 0) return;
    const { canvas, ctx } = this;
    // shift everything left by 1px
    const imageData = ctx.getImageData(1, 0, canvas.width - 1, canvas.height);
    ctx.putImageData(imageData, 0, 0);

    const min = Math.min(...bins);
    const max = Math.max(...bins);
    const range = Math.max(1, max - min);
    const colStep = canvas.height / bins.length;

    for (let i = 0; i < bins.length; i++) {
      const norm = (bins[i] - min) / range; // 0..1
      const hue = 220 - norm * 220; // blue (low) -> red (high)
      ctx.fillStyle = `hsl(${hue}, 90%, ${20 + norm * 40}%)`;
      const y = canvas.height - (i + 1) * colStep;
      ctx.fillRect(canvas.width - 1, y, 1, colStep + 1);
    }
  }

  reset() {
    this.ctx.fillStyle = "#0f172a";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
  }
}
