// -------- Auth --------
const authPanel = document.getElementById("auth-panel");
const authStatus = document.getElementById("auth-status");

document.getElementById("login-btn").addEventListener("click", async () => {
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;
  try {
    const { access_token } = await Api.login(username, password);
    Api.setToken(access_token);
    authStatus.textContent = `Signed in as ${username}`;
    refreshHistory();
  } catch (e) {
    authStatus.textContent = e.message;
  }
});

document.getElementById("register-btn").addEventListener("click", async () => {
  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;
  try {
    const { access_token } = await Api.register(username, password);
    Api.setToken(access_token);
    authStatus.textContent = `Account created, signed in as ${username}`;
    refreshHistory();
  } catch (e) {
    authStatus.textContent = e.message;
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  Api.setToken(null);
  authStatus.textContent = "Signed out (anonymous session).";
  document.getElementById("history-list").innerHTML = "";
});

if (Api.token) authStatus.textContent = "Signed in (session restored).";

// -------- Mode toggle --------
const modeLive = document.getElementById("mode-live");
const modeBatch = document.getElementById("mode-batch");
const livePanel = document.getElementById("live-panel");
const batchPanel = document.getElementById("batch-panel");
const modeGlider = document.getElementById("mode-glider");

function setMode(mode) {
  const isLive = mode === "live";
  livePanel.classList.toggle("hidden", !isLive);
  batchPanel.classList.toggle("hidden", isLive);
  modeLive.classList.toggle("active", isLive);
  modeBatch.classList.toggle("active", !isLive);
  modeGlider.classList.toggle("live", isLive);
}
modeLive.addEventListener("click", () => setMode("live"));
modeBatch.addEventListener("click", () => setMode("batch"));
setMode("batch");

// -------- Batch upload --------
const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const terminalOutput = document.getElementById("terminal-output");
const wpmLabel = document.getElementById("wpm-label");
const waveformCanvas = document.getElementById("waveform-canvas");

let currentJobId = null;

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return alert("Choose a .wav, .mp3, or .ogg file first.");

  terminalOutput.textContent = "";
  progressBar.style.width = "0%";
  progressLabel.textContent = "Uploading...";

  const { job_id } = await Api.uploadAudio(
    file,
    parseFloat(document.getElementById("low-hz").value),
    parseFloat(document.getElementById("high-hz").value),
  );
  currentJobId = job_id;

  const es = new EventSource(Api.statusStreamUrl(job_id));
  es.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    if (payload.progress != null) {
      progressBar.style.width = `${payload.progress}%`;
      progressLabel.textContent = `${payload.stage || payload.state} (${payload.progress}%)`;
    }
    if (payload.state === "SUCCESS" || payload.state === "FAILURE") {
      es.close();
      const result = await Api.getResult(job_id);
      renderBatchResult(result, file);
      refreshHistory();
    }
  };
});

async function renderBatchResult(result, file) {
  terminalOutput.textContent = result.decoded_text || `(no text decoded) ${result.warning || ""}`;
  wpmLabel.textContent = result.wpm_estimate ? `${result.wpm_estimate} WPM` : "--";

  // draw waveform overlay using decoded events if available
  const arrayBuffer = await file.arrayBuffer();
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  try {
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    drawWaveformOverlay(waveformCanvas, audioBuffer, result.events, audioBuffer.duration);
  } catch (e) {
    drawWaveformOverlay(waveformCanvas, null, result.events, 1);
  }

  document.getElementById("export-txt").href = Api.exportUrl(result.job_id, "txt");
  document.getElementById("export-csv").href = Api.exportUrl(result.job_id, "csv");
  document.getElementById("export-pdf").href = Api.exportUrl(result.job_id, "pdf");
}

// -------- Live stream --------
const startLiveBtn = document.getElementById("start-live-btn");
const stopLiveBtn = document.getElementById("stop-live-btn");
const liveTerminal = document.getElementById("live-terminal");
const liveWpmLabel = document.getElementById("live-wpm-label");
const waterfallCanvas = document.getElementById("waterfall-canvas");
const waterfall = new Waterfall(waterfallCanvas);

let streamClient = null;
const liveIndicator = document.getElementById("live-indicator");

startLiveBtn.addEventListener("click", async () => {
  liveTerminal.textContent = "";
  waterfall.reset();
  streamClient = new MorseStreamClient({
    onOpen: () => {
      startLiveBtn.disabled = true;
      stopLiveBtn.disabled = false;
      liveIndicator.classList.add("on");
    },
    onClose: () => {
      startLiveBtn.disabled = false;
      stopLiveBtn.disabled = true;
      liveIndicator.classList.remove("on");
    },
    onWaterfall: (bins) => waterfall.pushFrame(bins),
    onPartialResult: (msg) => {
      liveTerminal.textContent = msg.accumulated_text || "";
      if (msg.wpm_estimate) liveWpmLabel.textContent = `${msg.wpm_estimate} WPM`;
    },
  });
  try {
    await streamClient.start();
  } catch (e) {
    alert("Microphone access failed: " + e.message);
  }
});

stopLiveBtn.addEventListener("click", () => {
  streamClient?.forceFlush();
  setTimeout(() => streamClient?.stop(), 500);
});

document.getElementById("copy-live-btn").addEventListener("click", () => {
  navigator.clipboard.writeText(liveTerminal.textContent);
});
document.getElementById("copy-batch-btn").addEventListener("click", () => {
  navigator.clipboard.writeText(terminalOutput.textContent);
});

// -------- Reverse synthesis --------
document.getElementById("synth-btn").addEventListener("click", async () => {
  const text = document.getElementById("synth-text").value.trim();
  const wpm = parseFloat(document.getElementById("synth-wpm").value) || 20;
  const freq = parseFloat(document.getElementById("synth-freq").value) || 750;
  if (!text) return;
  const audioEl = document.getElementById("synth-audio");
  await playSynthesizedMorse(text, wpm, freq, audioEl);
});

// -------- History --------
async function refreshHistory() {
  const list = document.getElementById("history-list");
  if (!Api.token) {
    list.innerHTML = '<li class="history-empty">Sign in above to start saving your translation history.</li>';
    return;
  }
  try {
    const items = await Api.getHistory();
    list.innerHTML = items.map((it) => `
      <li class="history-item">
        <div class="history-item-top">
          <span class="history-filename">${it.original_filename || it.source_type}</span>
          <span class="history-status">${it.status}</span>
        </div>
        <div class="history-text">${it.decoded_text || ""}</div>
      </li>
    `).join("") || '<li class="history-empty">No translations yet — decode something to see it here.</li>';
  } catch (e) {
    list.innerHTML = `<li class="history-empty" style="color:var(--danger);">${e.message}</li>`;
  }
}
refreshHistory();

// -------- Icons --------
if (window.lucide) lucide.createIcons();
