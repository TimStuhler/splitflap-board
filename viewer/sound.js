// Split-flap click synthesis, pure Web Audio - no assets.
//
// DSP recipe, calibrated against a reference recording (Pixabay 58766, spectrum:
// ~50 % of the energy in 7-12 kHz, centroid ~6 kHz, 200-3000 Hz nearly empty,
// ~17 clicks/s):
//   A "tick":   3 ms white noise, envelope exp(-t/2ms),
//               highpass 3500 Hz + peaking +6 dB @ 7500 Hz, share 1.0
//   B "paper":  15 ms white noise, envelope exp(-t/6ms),
//               bandpass 5000 Hz (Q 0.7), share 0.35
//   C "weight": sine ~150 Hz, exponential decay to silence over 20 ms, share 0.12
//   Per trigger: random playback rate +/-12 %, level +/-3 dB, stereo pan per column.
//   Master: compressor + 5 % short convolution reverb (120 ms).
//
// tools/gen_click_wavs.py bakes the same recipe offline for the app-side WAVs.
// Layers A and B match exactly; layer C differs by implementation - here it is a
// Web Audio ramp over 20 ms, there an analytic exp(-t/2.8ms) truncated at 25 ms.
// Both are inaudible on their own and only add a trace of body.

const SR = 48000;
const N_VARIANTS = 8;
const CLICK_LEN = Math.floor(0.085 * SR);

class SplitflapSound {
  constructor() {
    this.ctx = null;
    this.buffers = [];
    this.enabled = true;
    this.volume = 0.6;
    this.recent = [];          // voice cap: timestamps of recent clicks
    this.played = 0;           // debug counter
  }

  /** Call after the first user gesture (autoplay policy). */
  async init() {
    if (this.ctx) {
      if (this.ctx.state === 'suspended') this.ctx.resume();
      return;
    }
    this.ctx = new AudioContext({ sampleRate: SR });

    // master: bus -> compressor -> destination, plus a small parallel room
    this.bus = this.ctx.createGain();
    this.bus.gain.value = this.volume;
    const comp = this.ctx.createDynamicsCompressor();
    comp.threshold.value = -18; comp.ratio.value = 4;
    comp.attack.value = 0.002; comp.release.value = 0.08;
    this.bus.connect(comp);
    comp.connect(this.ctx.destination);

    const verb = this.ctx.createConvolver();
    verb.buffer = this._impulse(0.12, 3.5);
    const wet = this.ctx.createGain();
    wet.gain.value = 0.05;
    this.bus.connect(verb); verb.connect(wet); wet.connect(comp);

    this.buffers = await Promise.all(
      Array.from({ length: N_VARIANTS }, (_, i) => this._bake(i)));
  }

  _impulse(seconds, decay) {
    const n = Math.floor(seconds * SR);
    const buf = new AudioBuffer({ numberOfChannels: 2, length: n, sampleRate: SR });
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch);
      for (let i = 0; i < n; i++)
        d[i] = (Math.random() * 2 - 1) * Math.exp(-decay * i / n / 0.3);
    }
    return buf;
  }

  async _bake(seed) {
    const off = new OfflineAudioContext(1, CLICK_LEN, SR);
    const rnd = (a, b) => a + ((Math.sin(seed * 12.9898 + 78.233) * 43758.5453) % 1 + 1) % 1 * (b - a);

    const noiseBurst = (len, tau) => {
      const buf = new AudioBuffer({ numberOfChannels: 1, length: Math.floor(len * SR), sampleRate: SR });
      const d = buf.getChannelData(0);
      for (let i = 0; i < d.length; i++)
        d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (tau * SR));
      const src = off.createBufferSource();
      src.buffer = buf;
      return src;
    };

    // A: bright tick (dominant) - highpass + presence peak
    const tick = noiseBurst(0.003, 0.002);
    const hp = off.createBiquadFilter();
    hp.type = 'highpass';
    hp.frequency.value = 3500;
    const peak = off.createBiquadFilter();
    peak.type = 'peaking';
    peak.frequency.value = rnd(6800, 8300);
    peak.Q.value = 1.0;
    peak.gain.value = 6;
    const ga = off.createGain();
    ga.gain.value = 1.0;
    tick.connect(hp); hp.connect(peak); peak.connect(ga); ga.connect(off.destination);

    // B: paper texture (a short "shk")
    const paper = noiseBurst(0.015, 0.006);
    const bp = off.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = rnd(4500, 5600);
    bp.Q.value = 0.7;
    const gb = off.createGain();
    gb.gain.value = 0.35;
    paper.connect(bp); bp.connect(gb); gb.connect(off.destination);

    // C: minimal weight (deliberately no tonal knock!)
    const osc = off.createOscillator();
    osc.type = 'sine';
    osc.frequency.value = rnd(130, 170);
    const gc = off.createGain();
    gc.gain.setValueAtTime(0.12, 0);
    gc.gain.exponentialRampToValueAtTime(0.0001, 0.02);
    osc.connect(gc); gc.connect(off.destination);

    tick.start(0);
    paper.start(0);
    osc.start(0); osc.stop(0.025);
    return off.startRendering();
  }

  /**
   * Play one flap click.
   * @param pan   -1..1 (column position)
   * @param opts  {release: true} = quiet trigger tick instead of a landing
   */
  click(pan = 0, opts = {}) {
    if (!this.ctx || !this.enabled || !this.buffers.length) return;
    const now = performance.now();
    this.recent = this.recent.filter(t => now - t < 50);
    if (this.recent.length >= 40) return;      // voice cap: the rest is inaudible anyway
    this.recent.push(now);

    const src = this.ctx.createBufferSource();
    src.buffer = this.buffers[(Math.random() * this.buffers.length) | 0];
    src.playbackRate.value = (opts.release ? 1.5 : 1.0) * (0.91 + Math.random() * 0.36);
    const g = this.ctx.createGain();
    g.gain.value = (opts.release ? 0.18 : 0.7) * (0.75 + Math.random() * 0.45);
    const p = this.ctx.createStereoPanner();
    p.pan.value = Math.max(-1, Math.min(1, pan + (Math.random() - 0.5) * 0.1));
    src.connect(g); g.connect(p); p.connect(this.bus);
    src.start(this.ctx.currentTime + Math.random() * 0.008);   // jitter
    this.played++;
  }

  setEnabled(v) { this.enabled = v; }

  setVolume(v) {
    this.volume = v;
    if (this.bus) this.bus.gain.value = v;
  }
}

export const sound = new SplitflapSound();
