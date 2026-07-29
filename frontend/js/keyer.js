// -------- Keyboard/Button Morse Keyer --------
//
// Direct-input alternative to the mic/file pipeline: instead of listening
// to audio and running it through the DSP chain (bandpass -> envelope ->
// adaptive threshold -> K-Means dot/dash clustering), this reads exact
// press-down/press-up timestamps from a keyboard key or on-screen button.
// Because the timing comes straight from the system (performance.now()),
// there is no acoustic noise to fight, so classification is a straight
// comparison against an adaptively-tracked "dot unit" duration instead of
// a signal-processing pipeline.
//
// Timing model (standard Morse ratios, same ones used by backend/app/dsp):
//   dash        ~= 3x dot
//   letter gap  ~= 3x dot (silence between letters)
//   word gap    ~= 7x dot (silence between words)
//
// This mirrors backend/app/dsp/morse_map.py's MORSE_TO_CHAR table so the
// decoded text matches what the audio pipeline would produce for the same
// message.

class MorseKeyer {
  static MORSE_TO_CHAR = {
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D", ".": "E",
    "..-.": "F", "--.": "G", "....": "H", "..": "I", ".---": "J",
    "-.-": "K", ".-..": "L", "--": "M", "-.": "N", "---": "O",
    ".--.": "P", "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X", "-.--": "Y",
    "--..": "Z",
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    ".-.-.-": ".", "--..--": ",", "..--..": "?", ".----.": "'",
    "-.-.--": "!", "-..-.": "/", "-.--.": "(", "-.--.-": ")",
    ".-...": "&", "---...": ":", "-.-.-.": ";", "-...-": "=",
    ".-.-.": "+", "-....-": "-", "..--.-": "_", ".-..-.": '"',
    "...-..-": "$", ".--.-.": "@",
  };

  // Ratio thresholds (in dot units) used to classify a press/gap.
  static DASH_THRESHOLD_UNITS = 2;    // press longer than 2x unit => dash
  static LETTER_GAP_UNITS = 3;        // silence longer than 3x unit => letter boundary
  static WORD_GAP_UNITS = 7;          // silence longer than 7x unit => word boundary
  static DEFAULT_UNIT_MS = 80;        // ~15 WPM, used until we have real samples
  static MAX_UNIT_HISTORY = 8;        // rolling window for adaptive unit estimate

  constructor({ onSymbol, onLetter, onWord, onText, onWpmUpdate, onClear } = {}) {
    this.onSymbol = onSymbol || (() => {});
    this.onLetter = onLetter || (() => {});
    this.onWord = onWord || (() => {});
    this.onText = onText || (() => {});
    this.onWpmUpdate = onWpmUpdate || (() => {});
    this.onClear = onClear || (() => {});
    this._reset();
  }

  _reset() {
    this.pressStartedAt = null;
    this.currentLetter = "";
    this.text = "";
    this.unitMs = null; // null until the first press gives us a real sample
    this.recentDurations = [];
    this.letterGapTimer = null;
    this.wordGapTimer = null;
  }

  /** Call on keydown / pointerdown / touchstart. Ignores repeated presses. */
  press() {
    if (this.pressStartedAt !== null) return;
    clearTimeout(this.letterGapTimer);
    clearTimeout(this.wordGapTimer);
    this.pressStartedAt = performance.now();
  }

  /** Call on keyup / pointerup / touchend. */
  release() {
    if (this.pressStartedAt === null) return;
    const duration = performance.now() - this.pressStartedAt;
    this.pressStartedAt = null;
    this._classifyPress(duration);
    this._armGapTimers();
  }

  _effectiveUnit() {
    return this.unitMs || MorseKeyer.DEFAULT_UNIT_MS;
  }

  _updateUnit(duration) {
    this.recentDurations.push(duration);
    if (this.recentDurations.length > MorseKeyer.MAX_UNIT_HISTORY) {
      this.recentDurations.shift();
    }
    // Dots are the shortest presses an operator sends, so the minimum of
    // recent presses is a solid, self-adapting estimate of "one unit" --
    // the same role the K-Means dot cluster centroid plays in the DSP path.
    this.unitMs = Math.min(...this.recentDurations);
    const wpm = Math.round(1200 / this.unitMs); // PARIS standard: unit(ms) = 1200 / WPM
    this.onWpmUpdate(wpm);
  }

  _classifyPress(duration) {
    const unitBefore = this._effectiveUnit();
    const symbol = duration > unitBefore * MorseKeyer.DASH_THRESHOLD_UNITS ? "-" : ".";
    this.currentLetter += symbol;
    this.onSymbol(symbol, duration);
    this._updateUnit(duration);
  }

  _armGapTimers() {
    const unit = this._effectiveUnit();
    this.letterGapTimer = setTimeout(
      () => this._flushLetter(),
      unit * MorseKeyer.LETTER_GAP_UNITS,
    );
    this.wordGapTimer = setTimeout(
      () => this._flushWord(),
      unit * MorseKeyer.WORD_GAP_UNITS,
    );
  }

  _flushLetter() {
    if (!this.currentLetter) return;
    const char = MorseKeyer.MORSE_TO_CHAR[this.currentLetter] || "";
    this.text += char;
    this.onLetter(this.currentLetter, char);
    this.currentLetter = "";
    this.onText(this.text);
  }

  _flushWord() {
    this._flushLetter();
    if (this.text && !this.text.endsWith(" ")) {
      this.text += " ";
      this.onWord();
      this.onText(this.text);
    }
  }

  /** Manually force whatever is buffered to resolve right now (e.g. a "flush" button). */
  flush() {
    clearTimeout(this.letterGapTimer);
    clearTimeout(this.wordGapTimer);
    this._flushLetter();
  }

  clear() {
    clearTimeout(this.letterGapTimer);
    clearTimeout(this.wordGapTimer);
    this._reset();
    this.onText(this.text);
    this.onClear();
  }
}
