#!/usr/bin/env python3
"""Bakes split-flap click WAVs for the OpenXR app.

Identical DSP recipe to viewer/sound.js, calibrated against a reference
recording (Pixabay 58766: ~50 % of the energy in 7-12 kHz, centroid ~6 kHz):
  Tick:   3 ms white noise, exp(-t/2ms), highpass 3.5 kHz + peak +6 dB @ ~7.5 kHz
  Paper: 15 ms white noise, exp(-t/6ms), bandpass ~5 kHz Q 0.7, share 0.35
  Weight: sine ~150 Hz, exp(-t/2.8ms) truncated at 25 ms, share 0.12
          (deliberately no tonal knock; viewer/sound.js uses a Web Audio ramp
          over 20 ms here - layers Tick and Paper match exactly)

Output: assets/sound/click_01..05.wav (48 kHz, mono, 16 bit)
"""

import math
import random
import struct
import wave
from pathlib import Path

import numpy as np

SR = 48000
LENGTH = int(0.085 * SR)
OUT_DIR = Path(__file__).resolve().parents[1] / "assets" / "sound"


def biquad(x, b0, b1, b2, a1, a2):
    """Direct form I, normalised coefficients."""
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        y0 = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x[i]
        y2, y1 = y1, y0
        y[i] = y0
    return y


def bandpass(x, f0, q):
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    a0 = 1 + alpha
    return biquad(x, alpha / a0, 0.0, -alpha / a0,
                  (-2 * math.cos(w0)) / a0, (1 - alpha) / a0)


def lowpass(x, f0, q=0.707):
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    a0 = 1 + alpha
    return biquad(x, (1 - cw) / 2 / a0, (1 - cw) / a0, (1 - cw) / 2 / a0,
                  (-2 * cw) / a0, (1 - alpha) / a0)


def highpass(x, f0, q=0.707):
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    a0 = 1 + alpha
    return biquad(x, (1 + cw) / 2 / a0, -(1 + cw) / a0, (1 + cw) / 2 / a0,
                  (-2 * cw) / a0, (1 - alpha) / a0)


def peaking(x, f0, q, gain_db):
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    a0 = 1 + alpha / A
    return biquad(x, (1 + alpha * A) / a0, (-2 * cw) / a0, (1 - alpha * A) / a0,
                  (-2 * cw) / a0, (1 - alpha / A) / a0)


def _burst(rng, seconds, tau):
    n = int(seconds * SR)
    x = np.zeros(LENGTH)
    x[:n] = rng.uniform(-1, 1, n) * np.exp(-np.arange(n) / (tau * SR))
    return x

def make_click(rng):
    t = np.arange(LENGTH) / SR

    # A: bright tick (dominant)
    tick = peaking(highpass(_burst(rng, 0.003, 0.002), 3500.0),
                   rng.uniform(6800, 8300), 1.0, 6.0) * 1.0

    # B: paper texture
    paper = bandpass(_burst(rng, 0.015, 0.006), rng.uniform(4500, 5600), 0.7) * 0.35

    # C: minimal weight
    weight = np.sin(2 * np.pi * rng.uniform(130, 170) * t) * \
        0.12 * np.exp(-t / 0.0028)
    weight[t > 0.025] = 0.0

    out = tick + paper + weight
    peak = np.max(np.abs(out)) or 1.0
    return out / peak * 0.7            # ~-3 dBFS headroom


def write_wav(path, samples):
    data = np.clip(samples * 32767, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260719)
    for i in range(1, 6):
        p = OUT_DIR / f"click_{i:02d}.wav"
        write_wav(p, make_click(rng))
        print(f"{p.name}: {LENGTH / SR * 1000:.0f} ms")
    print(f"-> {OUT_DIR}")


if __name__ == "__main__":
    main()
