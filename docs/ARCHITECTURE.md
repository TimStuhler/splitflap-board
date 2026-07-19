# Architecture

## What this project is

This is a parametric split-flap board generator (6×22). The
actual deliverable is **not** a program but an **app contract**: a GLB
(`export/splitflap_6x22.glb`) plus an atlas PNG plus the rules for how a
consuming (e.g. OpenXR) app animates flips from them. `README.md` is the
normative contract documentation (node names, card semantics, the UV formula,
flap ordering) — any change to names, custom properties, or the UV convention
must be reflected there as well.

There is no build system, no test suite, and no linter. Verification is
visual, via the viewer or via Blender renders.

## Commands

```bash
./viewer/serve.sh                # http://localhost:8123/viewer/ (static HTTP server)
python3 tools/gen_click_wavs.py  # bakes assets/sound/click_01..05.wav (needs numpy)
```

The viewer uses a vendored copy of Three.js (`viewer/vendor/`, checked into
the repository) via an import map — no CDN, no npm. New
`three/addons/...` imports need the corresponding file placed manually under
`viewer/vendor/addons/`.

From the browser console: `window.__viewer.spell(['','HI','','','',''])`,
`__viewer.spellGrid(grid)`, `__viewer.sound`.

## The Blender side

`blender/splitflap/` runs **inside** Blender, not as a command-line script.
The iteration cycle is:

```python
import sys; sys.path.insert(0, "<repo>/blender")
import splitflap; splitflap.reload_all()      # reload submodules in dependency order
splitflap.build_all(with_atlas=True)          # atlas bake + board + look-dev
```

`build_all` is destructive: `board.build()` deletes the `Splitflap`
collection entirely and rebuilds it from scratch. `lookdev.setup()` only
touches `SF_LookDev` (backdrop, camera, light) — that part is **not** included
in the export.

There is no script for the GLB export — it is done manually in Blender.
Hidden objects are not selectable, so the rotors must be unhidden before a
`use_selection` export, otherwise 132 nodes end up missing from the GLB.

## Architecture

Data flow: `charset.FLAPS` (64 cards) is used by `atlas.build_atlas()` to
render the 8×8 atlas PNG. `board.build()` then builds geometry whose UVs all
sit on atlas cell 0 — displaying a given character is purely a UV offset. The
index lives in custom properties (`uv_index`, `uv_front`/`uv_back`), which
drive UVWarp modifiers in Blender and survive into the GLB as `extras` for the
consuming app to read. The export contains no baked-in offsets.

The geometry is deliberately instancing-friendly: all 264 static cards share
the mesh `SF_Card`, and all 132 rotors share `SF_CardRotor`. Geometry is built
via the `_Acc` class in `board.py`, using quads/tris with a `want_normal` flag
instead of booleans or modifiers.

`viewer/main.js` is the reference implementation of the contract, not just a
demo — its flip state machine (`startStep`/`tickCell`) is what a consuming app
is expected to reproduce. `demo.py::spell()` implements the same logic as
Blender keyframes.

### Duplicated definitions that must stay in sync

There is no shared source across the language boundary, so the following
pairs will drift unless maintained together:

| What | Python | JS |
|---|---|---|
| Character set (64 flaps, order = flip sequence) | `charset.py::FLAPS` | `main.js` const `FLAPS` |
| Flip kinematics (−5° → +175°, bounce) | `demo.py` | `main.js` |
| Click DSP recipe | `tools/gen_click_wavs.py` | `viewer/sound.js` |

### UV sign convention

This is the most common source of mistakes. `du = (i % 8)/8` always holds.
The sign of the row offset depends on convention:

- **Blender / GL** (v points up): `dv = -(i // 8)/8` — used by the driver in
  `board.py` and by `charset.uv_offset()`
- **glTF** (v points down, which is how it sits in the GLB):
  `dv = +(i // 8)/8` — used by `main.js::matFor()`

## Blender pitfalls

The most important one: never call `animation_data_clear()` on flap objects.
The UVWarp drivers hang off the same `animation_data`, so clearing it removes
them too; `demo.clear_animation()` only resets `ad.action = None` instead.

Other things worth knowing:

- Vertex groups live on the mesh data, not the object. Since meshes are
  shared (`SF_Card`, `SF_CardRotor`), create each vertex group once, not once
  per object.
- Manually set custom properties only take effect through the drivers after
  `obj.update_tag()` plus a `scene.frame_set(...)`.
- Measure font metrics from a reference glyph rather than guessing from the
  em size.

## Language and identifiers

The codebase and its documentation are written in English. Identifiers —
node names, custom properties, materials, and meshes prefixed `SF_` — are
part of the public contract and must not be renamed.
