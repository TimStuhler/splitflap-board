# Vendored Three.js

- **Version:** r180
- **Origin:** https://github.com/mrdoob/three.js (release `r180`)
- **License:** MIT — see `/THIRD_PARTY.md` for the full text

## Files

```
three.module.js                      three.core.js
addons/controls/OrbitControls.js     addons/loaders/GLTFLoader.js
addons/lights/RectAreaLightUniformsLib.js
addons/lights/RectAreaLightTexturesLib.js
addons/environments/RoomEnvironment.js
addons/utils/BufferGeometryUtils.js
```

All files are unmodified copies of the upstream release.

## Why vendored

The viewer (`viewer/`) is meant to run directly from a bare `git clone`: open
`viewer/index.html` via a static file server and it works, with no `npm
install`, no CDN, and no network access at runtime. Vendoring the exact
Three.js files the viewer imports (resolved through the import map in
`viewer/index.html`) is what makes that possible.

## Update procedure

1. Download the desired Three.js release (e.g. from GitHub Releases or the npm
   tarball).
2. Copy `build/three.module.js` and `build/three.core.js` into this directory,
   replacing the existing copies.
3. Copy the needed files from `examples/jsm/**` into `addons/`, preserving
   their sub-paths (e.g. `examples/jsm/controls/OrbitControls.js` →
   `addons/controls/OrbitControls.js`). Only copy the files listed above —
   don't vendor the whole `examples/jsm/` tree.
4. Update the version noted here and in `/THIRD_PARTY.md`.
5. Verify the import map in `viewer/index.html` still resolves to the copied
   paths, and load the viewer to confirm nothing broke.
