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

// -------- Dialog auth experience --------
const authModal = document.getElementById("auth-modal");
const authForm = document.getElementById("auth-form");
const authError = document.getElementById("auth-error");
const modalUsername = document.getElementById("modal-auth-username");
const modalPassword = document.getElementById("modal-auth-password");
let authMode = "login";

authPanel.querySelectorAll("input, #login-btn, #register-btn").forEach((element) => element.classList.add("legacy-auth-control"));
const authActions = document.createElement("div");
authActions.className = "auth-actions";
authActions.innerHTML = `<button id="open-login-btn" class="btn-secondary"><i data-lucide="log-in"></i> Sign in</button>
  <button id="open-register-btn" class="btn"><i data-lucide="sparkles"></i> Create account</button>`;
authPanel.prepend(authActions);
const profileButton = document.createElement("button");
profileButton.id = "open-profile-btn";
profileButton.className = "profile-trigger hidden";
profileButton.innerHTML = '<span id="header-avatar" class="header-avatar">OP</span><span>Profile</span>';
authPanel.prepend(profileButton);

function setAuthUi(signedIn, message) {
  authStatus.textContent = message || (signedIn ? "Signed in" : "Guest operator");
  authActions.classList.toggle("hidden", signedIn);
  document.getElementById("logout-btn").classList.toggle("hidden", !signedIn);
  profileButton.classList.toggle("hidden", !signedIn);
}
function openAuth(mode) {
  authMode = mode;
  const registering = mode === "register";
  document.getElementById("auth-modal-title").textContent = registering ? "Create your operator profile" : "Welcome back";
  document.getElementById("auth-modal-copy").textContent = registering ? "Save every decoded transmission and make this console yours." : "Sign in to keep your decoded transmissions together.";
  document.getElementById("auth-submit-btn").innerHTML = registering ? '<i data-lucide="user-plus"></i> Create account' : '<i data-lucide="log-in"></i> Sign in';
  document.getElementById("auth-switch-copy").textContent = registering ? "Already have an account?" : "New to A-MCTP?";
  document.getElementById("auth-switch-btn").textContent = registering ? "Sign in instead" : "Create an account";
  authError.textContent = "";
  authModal.classList.remove("hidden");
  document.body.classList.add("modal-open");
  if (window.lucide) lucide.createIcons();
  setTimeout(() => modalUsername.focus(), 100);
}
function closeAuth() { authModal.classList.add("hidden"); document.body.classList.remove("modal-open"); }
document.getElementById("open-login-btn").addEventListener("click", () => openAuth("login"));
document.getElementById("open-register-btn").addEventListener("click", () => openAuth("register"));
document.getElementById("close-auth-btn").addEventListener("click", closeAuth);
document.querySelector("[data-auth-close]").addEventListener("click", closeAuth);
document.getElementById("auth-switch-btn").addEventListener("click", () => openAuth(authMode === "login" ? "register" : "login"));
document.getElementById("toggle-password-btn").addEventListener("click", (event) => {
  const visible = modalPassword.type === "password";
  modalPassword.type = visible ? "text" : "password";
  event.currentTarget.innerHTML = `<i data-lucide="${visible ? "eye-off" : "eye"}"></i>`;
  if (window.lucide) lucide.createIcons();
});
authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = document.getElementById("auth-submit-btn");
  authError.textContent = "";
  submit.disabled = true;
  try {
    const { access_token } = authMode === "login" ? await Api.login(modalUsername.value.trim(), modalPassword.value) : await Api.register(modalUsername.value.trim(), modalPassword.value);
    Api.setToken(access_token);
    setAuthUi(true, `Signed in as ${modalUsername.value.trim()}`);
    closeAuth();
    refreshHistory();
  } catch (error) { authError.textContent = error.message; }
  finally { submit.disabled = false; }
});
document.getElementById("logout-btn").addEventListener("click", () => setAuthUi(false, "Guest operator"));
setAuthUi(Boolean(Api.token), Api.token ? "Signed in (session restored)" : "Guest operator");

// -------- Operator profile --------
const profileModal = document.getElementById("profile-modal");
const profileForm = document.getElementById("profile-form");
const profileError = document.getElementById("profile-error");
function initials(value) {
  return (value || "OP").trim().split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "OP";
}
function fillProfile(profile) {
  document.getElementById("profile-display-name").value = profile.display_name || "";
  document.getElementById("profile-callsign").value = profile.callsign || "";
  document.getElementById("profile-bio").value = profile.bio || "";
  document.getElementById("profile-wpm").value = profile.preferred_wpm;
  document.getElementById("profile-low-hz").value = profile.low_hz;
  document.getElementById("profile-high-hz").value = profile.high_hz;
  document.getElementById("profile-username").textContent = `@${profile.username}`;
  const avatar = initials(profile.display_name || profile.username);
  document.getElementById("profile-avatar").textContent = avatar;
  document.getElementById("header-avatar").textContent = avatar;
}
async function openProfile() {
  profileError.textContent = "";
  try {
    fillProfile(await Api.getProfile());
    profileModal.classList.remove("hidden");
    document.body.classList.add("modal-open");
  } catch (error) { authStatus.textContent = error.message; }
}
function closeProfile() { profileModal.classList.add("hidden"); document.body.classList.remove("modal-open"); }
profileButton.addEventListener("click", openProfile);
document.getElementById("close-profile-btn").addEventListener("click", closeProfile);
document.querySelector("[data-profile-close]").addEventListener("click", closeProfile);
profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const saveButton = document.getElementById("profile-save-btn");
  const profile = {
    display_name: document.getElementById("profile-display-name").value,
    callsign: document.getElementById("profile-callsign").value,
    bio: document.getElementById("profile-bio").value,
    preferred_wpm: Number(document.getElementById("profile-wpm").value),
    low_hz: Number(document.getElementById("profile-low-hz").value),
    high_hz: Number(document.getElementById("profile-high-hz").value),
  };
  if (profile.low_hz >= profile.high_hz) { profileError.textContent = "Low cutoff must be below high cutoff."; return; }
  saveButton.disabled = true;
  profileError.textContent = "";
  try {
    const saved = await Api.updateProfile(profile);
    fillProfile(saved);
    document.getElementById("low-hz").value = saved.low_hz;
    document.getElementById("high-hz").value = saved.high_hz;
    document.getElementById("synth-wpm").value = saved.preferred_wpm;
    authStatus.textContent = "Profile saved";
    closeProfile();
  } catch (error) { profileError.textContent = error.message; }
  finally { saveButton.disabled = false; }
});

// -------- Mode toggle --------
const modeLive = document.getElementById("mode-live");
const modeBatch = document.getElementById("mode-batch");
const modeKeyer = document.getElementById("mode-keyer");
const livePanel = document.getElementById("live-panel");
const batchPanel = document.getElementById("batch-panel");
const keyerPanel = document.getElementById("keyer-panel");
const modeGlider = document.getElementById("mode-glider");
const signalLens = document.getElementById("signal-lens");

function setMode(mode) {
  const isLive = mode === "live";
  const isBatch = mode === "batch";
  const isKeyer = mode === "keyer";
  livePanel.classList.toggle("hidden", !isLive);
  batchPanel.classList.toggle("hidden", !isBatch);
  keyerPanel.classList.toggle("hidden", !isKeyer);
  signalLens.classList.toggle("hidden", !isBatch);
  modeLive.classList.toggle("active", isLive);
  modeBatch.classList.toggle("active", isBatch);
  modeKeyer.classList.toggle("active", isKeyer);
  modeGlider.classList.toggle("live", isLive);
  modeGlider.classList.toggle("keyer", isKeyer);
}
modeLive.addEventListener("click", () => setMode("live"));
modeBatch.addEventListener("click", () => setMode("batch"));
modeKeyer.addEventListener("click", () => setMode("keyer"));
setMode("batch");

// -------- Batch upload --------
const fileInput = document.getElementById("file-input");
const uploadBtn = document.getElementById("upload-btn");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const terminalOutput = document.getElementById("terminal-output");
const wpmLabel = document.getElementById("wpm-label");
const freqLabel = document.getElementById("freq-label");
const waveformCanvas = document.getElementById("waveform-canvas");
const autoDetectCheckbox = document.getElementById("auto-detect-freq");
const manualFreqFields = document.getElementById("manual-freq-fields");

function syncAutoDetectUI() {
  const auto = autoDetectCheckbox.checked;
  manualFreqFields.style.opacity = auto ? "0.4" : "1";
  manualFreqFields.style.pointerEvents = auto ? "none" : "auto";
}
autoDetectCheckbox.addEventListener("change", syncAutoDetectUI);
syncAutoDetectUI();

let currentJobId = null;

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return alert("Choose a .wav, .mp3, or .ogg file first.");

  terminalOutput.textContent = "";
  progressBar.style.width = "0%";
  progressLabel.textContent = "Uploading...";
  freqLabel.textContent = "--";
  showLensEmpty();

  const autoDetect = autoDetectCheckbox.checked;
  const { job_id } = await Api.uploadAudio(
    file,
    parseFloat(document.getElementById("low-hz").value),
    parseFloat(document.getElementById("high-hz").value),
    autoDetect,
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
  freqLabel.textContent = result.detected_freq_hz ? `${result.detected_freq_hz} Hz` : "--";

  // draw waveform overlay using decoded events if available
  const arrayBuffer = await file.arrayBuffer();
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  try {
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
    drawWaveformOverlay(waveformCanvas, audioBuffer, result.events, audioBuffer.duration);
  } catch (e) {
    drawWaveformOverlay(waveformCanvas, null, result.events, 1);
  }

  renderSignalLens(result);

  document.getElementById("export-txt").href = Api.exportUrl(result.job_id, "txt");
  document.getElementById("export-csv").href = Api.exportUrl(result.job_id, "csv");
  document.getElementById("export-pdf").href = Api.exportUrl(result.job_id, "pdf");
}

function setLensStatus(state, label) {
  const el = document.getElementById("lens-status");
  el.className = `lens-status ${state}`;
  el.innerHTML = `<i data-lucide="${state === "error" ? "alert-triangle" : state === "mapped" ? "badge-check" : "circle-dot-dashed"}"></i> ${label}`;
}

function showLensEmpty() {
  document.getElementById("lens-results").classList.add("hidden");
  document.getElementById("lens-empty").classList.remove("hidden");
  setLensStatus("", "Awaiting signal");
  document.getElementById("lens-subtitle").textContent =
    "Upload a signal and this panel will map its dots, dashes, and gaps into an explainable decoding story.";
}

function renderSignalLens(result) {
  const events = result.events || [];
  let dots = events.filter((event) => event.kind === "dot").length;
  let dashes = events.filter((event) => event.kind === "dash").length;
  let elementGaps = events.filter((event) => event.kind === "element_gap").length;
  let letterGaps = events.filter((event) => event.kind === "letter_gap").length;
  let wordGaps = events.filter((event) => event.kind === "word_gap").length;
  let haveEvents = events.length > 0;

  const stream = result.symbol_stream || "";
  
  // Fix the split logic: Morse words are separated by " / "
  const streamWords = stream.split(" / ").filter(Boolean);
  // Morse letters inside words are separated by single spaces " "
  const streamLetters = stream.split(" ").filter(ch => ch && ch !== "/");
  
  const streamDots = (stream.match(/\./g) || []).length;
  const streamDashes = (stream.match(/-/g) || []).length;

  if (!haveEvents && stream) {
    dots = streamDots;
    dashes = streamDashes;
    // Standard calculation rules for explicit stream gaps
    wordGaps = Math.max(0, streamWords.length - 1);
    letterGaps = Math.max(0, streamLetters.length - streamWords.length);
  }
  const totalSymbols = dots + dashes;

  document.getElementById("lens-empty").classList.add("hidden");
  document.getElementById("lens-results").classList.remove("hidden");
  document.getElementById("lens-subtitle").textContent =
    "Your timing pattern has been separated into symbols and pauses for a transparent decoding trail.";

  if (result.error) {
    setLensStatus("error", "Decode failed");
    document.getElementById("lens-wpm").textContent = "--";
    document.getElementById("lens-symbols").textContent = "0";
    document.getElementById("lens-words").textContent = "0";
    document.getElementById("lens-timeline").innerHTML = "";
    document.getElementById("lens-explanation").textContent =
      `The decoder could not finish: ${result.error}${result.warning ? ` — ${result.warning}` : ""}. Check the audio contains a clean CW tone and the cutoff filters isolate it.`;
    if (window.lucide) lucide.createIcons();
    return;
  }

  setLensStatus("mapped", "Signal mapped");
  document.getElementById("lens-wpm").textContent = result.wpm_estimate ? `${result.wpm_estimate}` : "--";
  document.getElementById("lens-symbols").textContent = `${totalSymbols}`;
  
  // Calculate total words correctly regardless of whether data comes from events or stream fallback
  const totalWords = streamWords.length || 1;
  document.getElementById("lens-words").textContent = `${totalWords}`;

  const timeline = document.getElementById("lens-timeline");
  timeline.innerHTML = "";
  if (haveEvents) {
    events.forEach((event) => {
      const segment = document.createElement("span");
      segment.className = `lens-segment ${event.kind}`;
      const dur = event.end_s - event.start_s;
      segment.title = `${event.kind.replace(/_/g, " ")} · ${dur.toFixed(3)}s`;
      const duration = Math.max(5, Math.min(42, dur * 90));
      segment.style.setProperty("--segment-width", `${duration}px`);
      timeline.appendChild(segment);
    });
  } else if (stream) {
    // Fixed: We parse gaps directly instead of skipping spaces entirely
    // By matching chunks of dots/dashes, slashes, or individual spaces
    const tokens = stream.match(/\.|-|\s\/\s|\s/g) || [];
    
    tokens.forEach((token) => {
      let kind = "dot";
      if (token === "-") kind = "dash";
      else if (token === " / ") kind = "word_gap";
      else if (token === " ") kind = "letter_gap";
      
      const segment = document.createElement("span");
      segment.className = `lens-segment ${kind}`;
      segment.title = kind.replace(/_/g, " ");
      timeline.appendChild(segment);
    });
  } else {
    timeline.innerHTML = '<span style="color:var(--ink-faint);font-size:0.82rem;">No discrete pulses were detected — the signal may be silent or outside the filter band.</span>';
  }

  const text = result.decoded_text && result.decoded_text.trim() ? result.decoded_text.trim() : "no readable text";
  const streamNote = stream ? ` (symbol stream “${stream}”)` : "";
  const wpmNote = result.wpm_estimate ? ` at approximately ${result.wpm_estimate} WPM` : "";
  const sourceNote = haveEvents
    ? "K-Means clustering on those durations"
    : "the unsupervised timing model";
    
  if (totalSymbols === 0 && !stream) {
    document.getElementById("lens-explanation").textContent =
      "No tone activity was detected in this signal. Check the frequency band and signal-to-noise ratio of the recording.";
  } else {
    document.getElementById("lens-explanation").innerHTML =
      `<strong>Signal Lens</strong> found ${dots} short pulse${dots === 1 ? "" : "s"} and ${dashes} long pulse${dashes === 1 ? "" : "s"}, ` +
      `separated by ${letterGaps} letter gap${letterGaps === 1 ? "" : "s"} and ${wordGaps} word gap${wordGaps === 1 ? "" : "s"}. ` +
      `${sourceNote} — not a fixed speed table — resolved them to “${text}”${streamNote}${wpmNote}.`;
  }
  if (window.lucide) lucide.createIcons();
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
      liveTerminal.classList.toggle("live-preview", Boolean(msg.interim));
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

// -------- Keyer (keyboard/button Morse input, no audio involved) --------
const keyerPaddle = document.getElementById("keyer-paddle");
const keyerLamp = document.getElementById("keyer-lamp-indicator");
const keyerTerminal = document.getElementById("keyer-terminal");
const keyerWpmLabel = document.getElementById("keyer-wpm-label");
const keyerCurrentSymbol = document.getElementById("keyer-current-symbol");

const keyer = new MorseKeyer({
  onSymbol: (symbol) => { keyerCurrentSymbol.textContent += symbol; },
  onLetter: () => { keyerCurrentSymbol.textContent = ""; },
  onWord: () => { keyerCurrentSymbol.textContent = ""; },
  onText: (text) => { keyerTerminal.textContent = text; },
  onWpmUpdate: (wpm) => { keyerWpmLabel.textContent = `${wpm} WPM`; },
  onClear: () => { keyerWpmLabel.textContent = "--"; },
});

function keyerPress() {
  keyerPaddle.classList.add("active");
  keyerLamp.classList.add("on");
  keyer.press();
}
function keyerRelease() {
  keyerPaddle.classList.remove("active");
  keyerLamp.classList.remove("on");
  keyer.release();
}

keyerPaddle.addEventListener("mousedown", keyerPress);
keyerPaddle.addEventListener("mouseup", keyerRelease);
keyerPaddle.addEventListener("mouseleave", () => {
  if (keyerPaddle.classList.contains("active")) keyerRelease();
});
keyerPaddle.addEventListener("touchstart", (event) => { event.preventDefault(); keyerPress(); }, { passive: false });
keyerPaddle.addEventListener("touchend", (event) => { event.preventDefault(); keyerRelease(); }, { passive: false });

// Spacebar keying, only while the keyer panel is active and focus isn't in a text field.
document.addEventListener("keydown", (event) => {
  if (keyerPanel.classList.contains("hidden") || event.code !== "Space" || event.repeat) return;
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  event.preventDefault();
  keyerPress();
});
document.addEventListener("keyup", (event) => {
  if (keyerPanel.classList.contains("hidden") || event.code !== "Space") return;
  const tag = document.activeElement && document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return;
  event.preventDefault();
  keyerRelease();
});

document.getElementById("keyer-flush-btn").addEventListener("click", () => keyer.flush());
document.getElementById("keyer-clear-btn").addEventListener("click", () => {
  keyer.clear();
  keyerCurrentSymbol.textContent = "";
});
document.getElementById("copy-keyer-btn").addEventListener("click", () => {
  navigator.clipboard.writeText(keyerTerminal.textContent);
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

// -------- Signal Lens guided initial state --------
showLensEmpty();

// -------- Icons --------
if (window.lucide) lucide.createIcons();
