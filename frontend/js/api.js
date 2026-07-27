const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : ""; // same-origin in production behind a reverse proxy

const Api = {
  token: localStorage.getItem("amctp_token") || null,
  sessionId: localStorage.getItem("amctp_session_id") || crypto.randomUUID(),

  init() {
    localStorage.setItem("amctp_session_id", this.sessionId);
  },

  setToken(token) {
    this.token = token;
    if (token) localStorage.setItem("amctp_token", token);
    else localStorage.removeItem("amctp_token");
  },

  headers(extra = {}) {
    const h = { "X-Session-Id": this.sessionId, ...extra };
    if (this.token) h["Authorization"] = `Bearer ${this.token}`;
    return h;
  },

  async register(username, password) {
    const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Registration failed");
    return res.json();
  },

  async login(username, password) {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Login failed");
    return res.json();
  },

  async uploadAudio(file, lowHz, highHz, autoDetect = true) {
    const form = new FormData();
    form.append("file", file);
    form.append("auto_detect", autoDetect ? "true" : "false");
    if (!autoDetect) {
      if (lowHz != null) form.append("low_hz", lowHz);
      if (highHz != null) form.append("high_hz", highHz);
    }
    const res = await fetch(`${API_BASE}/api/v1/decode/upload`, {
      method: "POST",
      headers: this.headers(),
      body: form,
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
    return res.json();
  },

  statusStreamUrl(jobId) {
    return `${API_BASE}/api/v1/decode/status/${jobId}/stream`;
  },

  async getResult(jobId) {
    const res = await fetch(`${API_BASE}/api/v1/decode/result/${jobId}`, { headers: this.headers() });
    if (!res.ok) throw new Error("Could not fetch result");
    return res.json();
  },

  async getHistory() {
    const res = await fetch(`${API_BASE}/api/v1/history`, { headers: this.headers() });
    if (!res.ok) throw new Error("Could not fetch history");
    return res.json();
  },

  async getProfile() {
    const res = await fetch(`${API_BASE}/api/v1/profile`, { headers: this.headers() });
    if (!res.ok) throw new Error((await res.json()).detail || "Could not fetch profile");
    return res.json();
  },

  async updateProfile(profile) {
    const res = await fetch(`${API_BASE}/api/v1/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...this.headers() },
      body: JSON.stringify(profile),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Could not save profile");
    return res.json();
  },

  exportUrl(jobId, format) {
    return `${API_BASE}/api/v1/export/${jobId}?format=${format}`;
  },

  async synthesize(text, wpm, freqHz) {
    const res = await fetch(`${API_BASE}/api/v1/synth`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers() },
      body: JSON.stringify({ text, wpm, freq_hz: freqHz }),
    });
    if (!res.ok) throw new Error("Synthesis failed");
    return res.blob();
  },

  wsUrl() {
    const base = API_BASE || window.location.origin;
    return base.replace(/^http/, "ws") + "/api/v1/decode/stream";
  },
};

Api.init();
