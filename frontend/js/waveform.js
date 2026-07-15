// Renders a static waveform with dot/dash/letter/word markers beneath it,
// per PRD 4.2's "synchronous waveform overlay" requirement.
function drawWaveformOverlay(canvas, audioBuffer, events, totalDurationS) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // background
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, w, h);

  // waveform
  if (audioBuffer) {
    const channel = audioBuffer.getChannelData(0);
    const step = Math.ceil(channel.length / w);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x < w; x++) {
      let min = 1.0, max = -1.0;
      for (let j = 0; j < step; j++) {
        const idx = x * step + j;
        if (idx >= channel.length) break;
        const v = channel[idx];
        if (v < min) min = v;
        if (v > max) max = v;
      }
      const yMin = (0.5 - min * 0.4) * h * 0.6;
      const yMax = (0.5 - max * 0.4) * h * 0.6;
      ctx.moveTo(x, yMin);
      ctx.lineTo(x, yMax);
    }
    ctx.stroke();
  }

  // symbol overlay strip
  const overlayTop = h * 0.65;
  const overlayHeight = h * 0.3;
  const colors = {
    dot: "#22c55e",
    dash: "#f59e0b",
    letter_gap: "#64748b",
    word_gap: "#ef4444",
    element_gap: "transparent",
  };
  (events || []).forEach((ev) => {
    if (ev.kind === "element_gap") return;
    const x1 = (ev.start_s / totalDurationS) * w;
    const x2 = (ev.end_s / totalDurationS) * w;
    ctx.fillStyle = colors[ev.kind] || "#94a3b8";
    ctx.fillRect(x1, overlayTop, Math.max(1, x2 - x1), overlayHeight);
  });

  // legend
  ctx.font = "11px monospace";
  let lx = 8;
  const legend = [["dot", "Dot"], ["dash", "Dash"], ["letter_gap", "Letter gap"], ["word_gap", "Word gap"]];
  legend.forEach(([key, label]) => {
    ctx.fillStyle = colors[key];
    ctx.fillRect(lx, h - 16, 10, 10);
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(label, lx + 14, h - 7);
    lx += 14 + ctx.measureText(label).width + 14;
  });
}
