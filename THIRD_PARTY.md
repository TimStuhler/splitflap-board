# Third-Party Notices

This project is licensed under the MIT License (see `LICENSE`). It bundles or
depends on the following third-party material.

## Three.js

- **Version:** r180
- **License:** MIT
- **Usage:** Vendored unmodified under `viewer/vendor/` (see
  `viewer/vendor/README.md` for the exact file list and provenance). Not
  patched or altered in any way.
- **Upstream:** https://github.com/mrdoob/three.js

```
The MIT License

Copyright © 2010-2025 three.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Liberation Sans Bold

- **License:** SIL Open Font License, Version 1.1
- **Usage:** Used only as a rendering input to bake the font atlas
  (`assets/atlas/flap_atlas.png`) in `blender/splitflap/atlas.py`. The OFL
  places no restriction on documents or images produced using the font, so the
  baked atlas PNG carries no OFL obligations of its own. The font file itself
  is **not** redistributed in this repository — `atlas.py` loads it from the
  system, falling back to DejaVu Sans Bold if Liberation Sans Bold is not
  installed.
- **Upstream:** https://github.com/liberationfonts/liberation-fonts

## Trademarks

This project is an independent hobby project. It is not affiliated with,
sponsored by, or endorsed by any manufacturer of split-flap displays. Any
third-party product names or trademarks are the property of their respective
owners.

## Sound

Every click sound is synthesised at runtime from filtered noise and a sine
tone (`viewer/sound.js`), or baked offline the same way
(`tools/gen_click_wavs.py`). No audio sample material is included or
redistributed. A freely licensed reference recording (Pixabay 58766) was used
solely during development to calibrate the target spectrum of the synthesis —
it is not part of this repository.
