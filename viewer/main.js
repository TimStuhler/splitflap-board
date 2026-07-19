// Split-flap viewer: loads export/splitflap_6x22.glb and drives the flips
// EXACTLY as the OpenXR app has to (app contract: see README):
//   - UV offset du=(i%8)/8, dv=+(i//8)/8 on top of atlas cell 0 (glTF convention)
//   - rotor: local X rotation -5deg -> +175deg, one UV swap at 90deg
//   - FlapTop already shows the next glyph when the flip starts,
//     FlapBot changes on landing
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RectAreaLightUniformsLib } from 'three/addons/lights/RectAreaLightUniformsLib.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { sound } from './sound.js';

// --- character set: identical to blender/splitflap/charset.py ---------------
const CHIPS = ['chip:red', 'chip:orange', 'chip:yellow', 'chip:green',
               'chip:blue', 'chip:violet', 'chip:white', 'chip:black'];
const FLAPS = [' ', ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ', ...'1234567890',
               ...'!@#$()-+&=;:\'"%,./?', ...CHIPS];
const N = FLAPS.length; // 64
const IDX = new Map(FLAPS.map((f, i) => [f, i]));
const ATLAS = 8;

const REST = THREE.MathUtils.degToRad(-5);
const LAND = THREE.MathUtils.degToRad(175);
const BOUNCE = THREE.MathUtils.degToRad(3);

// --- scene --------------------------------------------------------------
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.getElementById('app').appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x202226);
const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.05, 20);
camera.position.set(-0.25, 0.05, 1.35);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 0);
controls.enableDamping = true;

// Lighting similar to look-dev: warm key upper left, cool fill right.
// RectAreaLights only work AFTER the LTC textures are initialised!
RectAreaLightUniformsLib.init();
const key = new THREE.RectAreaLight(0xfff7ea, 9.0, 0.7, 0.45);
key.position.set(-0.7, 0.55, 1.15); key.lookAt(0, 0, 0); scene.add(key);
const fill = new THREE.RectAreaLight(0xeaf2ff, 2.5, 0.6, 0.6);
fill.position.set(0.9, 0.05, 0.95); fill.lookAt(0, 0, 0); scene.add(fill);
scene.add(new THREE.AmbientLight(0x50555c, 0.5));
const spot = new THREE.DirectionalLight(0xffffff, 1.0);
spot.position.set(-0.5, 0.8, 1.5); scene.add(spot);

// Environment: soft studio sheen on the satin black (as in look-dev)
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment()).texture;
scene.environmentIntensity = 0.35;

// wall behind the board
const wall = new THREE.Mesh(
  new THREE.PlaneGeometry(4, 3),
  new THREE.MeshStandardMaterial({ color: 0xd8d4cc, roughness: 0.95 }));
wall.position.z = -0.068;
scene.add(wall);

// --- load the GLB, index the cells ------------------------------------------
const stats = document.getElementById('stats');
const cells = [];          // cells[r][c] = cell state
let rows = 0, cols = 0;
const matCache = new Map(); // flap index -> material (shared by all cards)
let faceBase = null;        // original SF_Flap_Face from the GLB

function matFor(i) {
  if (!matCache.has(i)) {
    const m = faceBase.clone();
    m.map = faceBase.map.clone();
    // NOTE on convention: the GLB stores UVs in glTF convention (v points DOWN,
    // textures with flipY=false) -> the row offset is POSITIVE.
    // (In Blender/GL convention it would be -row/8.)
    m.map.offset.set((i % ATLAS) / ATLAS, Math.floor(i / ATLAS) / ATLAS);
    matCache.set(i, m);
  }
  return matCache.get(i);
}

// A flap node is a group of 2 meshes (two material primitives).
function faceMeshOf(node) {
  let hit = null;
  node.traverse(o => {
    if (o.isMesh && o.material?.name === 'SF_Flap_Face') hit = o;
  });
  return hit;
}

new GLTFLoader().load('../export/splitflap_6x22.glb', (gltf) => {
  scene.add(gltf.scene);
  const root = gltf.scene.getObjectByName('SplitflapBoard');
  rows = root.userData.sf_rows; cols = root.userData.sf_cols;

  for (let r = 0; r < rows; r++) {
    cells.push([]);
    for (let c = 0; c < cols; c++) {
      const sfx = `r${r}_c${String(c).padStart(2, '0')}`;
      const top = gltf.scene.getObjectByName(`FlapTop_${sfx}`);
      const bot = gltf.scene.getObjectByName(`FlapBot_${sfx}`);
      const rot = gltf.scene.getObjectByName(`Rotor_${sfx}`);
      if (!faceBase) faceBase = faceMeshOf(top).material;
      const cell = {
        top: faceMeshOf(top), bot: faceMeshOf(bot),
        rot, rotFace: faceMeshOf(rot),
        cur: top.userData.uv_index ?? 0,
        target: top.userData.uv_index ?? 0,
        phase: 0,           // 0..1 within the running flip
        pan: (c / (cols - 1)) * 1.2 - 0.6,   // stereo position of the column
        speed: 0.92 + Math.random() * 0.16,  // "motor tolerance" +/-8 %
        startDelay: 0,
      };
      rot.visible = false;  // contract: rotors start hidden
      cell.top.material = matFor(cell.cur);
      cell.bot.material = matFor(cell.cur);
      cells[r].push(cell);
    }
  }
  stats.textContent =
    `GLB ok: ${rows}×${cols} cells · ${renderer.info.memory.geometries} geometries`;
}, undefined, (e) => { stats.textContent = 'GLB error: ' + e; });

// --- flip state machine (identical to the Blender demo logic) ---------------
let flipMs = 67;
const BOUNCE_MS = 70;

function startStep(cell) {
  const nxt = (cell.cur + 1) % N;
  cell.top.material = matFor(nxt);           // next glyph behind the rotor
  cell.rotFace.material = matFor(cell.cur);  // rotor front: previous glyph
  cell.rot.visible = true;
  cell.rot.rotation.x = REST;
  cell.phase = 0;
  cell.swapped = false;
  sound.click(cell.pan, { release: true });  // quiet trigger tick
}

function tickCell(cell, dt) {
  if (cell.cur === cell.target && !cell.rot.visible) return;
  if (cell.startDelay > 0) { cell.startDelay -= dt; return; }
  if (!cell.rot.visible) { startStep(cell); return; }

  const nxt = (cell.cur + 1) % N;
  const last = nxt === cell.target;

  if (cell.bouncing) {
    cell.phase += dt / BOUNCE_MS;
    if (cell.phase >= 1) {
      cell.rot.visible = false; cell.bouncing = false;
    } else {
      cell.rot.rotation.x = LAND - BOUNCE * Math.sin(cell.phase * Math.PI);
    }
    return;
  }

  cell.phase += dt / (flipMs * cell.speed);
  const t = Math.min(cell.phase, 1);
  const e = last ? t * t : t;                 // final fall: gravity
  cell.rot.rotation.x = REST + (LAND - REST) * e;

  // Past 90deg only the back is visible -> ONE UV swap is enough
  if (!cell.swapped && cell.rot.rotation.x > Math.PI / 2) {
    cell.rotFace.material = matFor(nxt);
    cell.swapped = true;
  }
  if (t >= 1) {
    cell.bot.material = matFor(nxt);          // landing: the bottom card changes
    cell.cur = nxt;
    sound.click(cell.pan);                    // card impact
    if (last) { cell.bouncing = true; cell.phase = 0; }
    else startStep(cell);
  }
}

// --- text -> target indices --------------------------------------------------
function _setTarget(cell, target) {
  if (cell.target === target) return;
  cell.target = target;
  // Start offset: smears the first salvo (desynchronises from flip 1 onwards)
  if (!cell.rot.visible) cell.startDelay = Math.random() * flipMs * 1.5;
}

function spell(lines) {
  if (!cells.length) return;
  for (let r = 0; r < rows; r++) {
    const text = (lines[r] || '').toUpperCase().slice(0, cols);
    const start = Math.floor((cols - text.length) / 2);
    for (let c = 0; c < cols; c++) {
      const ch = text[c - start] ?? ' ';
      _setTarget(cells[r][c], IDX.get(ch) ?? 0);
    }
  }
}

function spellGrid(grid) {
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++)
      _setTarget(cells[r][c], grid[r][c]);
}

// --- UI -----------------------------------------------------------------
const ta = document.getElementById('text');
document.getElementById('go').onclick = () => spell(ta.value.split('\n'));
ta.addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && !ev.shiftKey && ta.value.split('\n').length >= 6) {
    ev.preventDefault(); spell(ta.value.split('\n'));
  }
});
document.getElementById('quote').onclick = () => {
  ta.value = "\nAND NOW THAT YOU\nDON'T HAVE TO BE\nPERFECT, YOU CAN\nBE GOOD\n";
  spell(ta.value.split('\n'));
};
document.getElementById('clear').onclick = () => { ta.value = ''; spell([]); };
document.getElementById('chips').onclick = () => {
  const g = [];
  for (let r = 0; r < rows; r++) {
    g.push([]);
    for (let c = 0; c < cols; c++) {
      g[r].push(Math.random() < 0.35 ? 56 + Math.floor(Math.random() * 6) : 0);
    }
  }
  spellGrid(g);
};
const msSlider = document.getElementById('ms');
msSlider.oninput = () => {
  flipMs = +msSlider.value;
  document.getElementById('msLabel').textContent = flipMs;
};

// Sound: init after the first user gesture (autoplay policy), UI wiring
addEventListener('pointerdown', () => sound.init(), { once: false });
addEventListener('keydown', () => sound.init(), { once: false });
const sndCheck = document.getElementById('snd');
sndCheck.onchange = () => sound.setEnabled(sndCheck.checked);
const volSlider = document.getElementById('vol');
volSlider.oninput = () => sound.setVolume(+volSlider.value / 100);

// --- loop ---------------------------------------------------------------
// For console/automation: window.__viewer.spell(['','HI','','','',''])
window.__viewer = { camera, controls, spell, spellGrid, cells, sound };

let prev = performance.now();
renderer.setAnimationLoop((now) => {
  const dt = Math.min(now - prev, 50); prev = now;
  for (const row of cells) for (const cell of row) tickCell(cell, dt);
  controls.update();
  renderer.render(scene, camera);
});
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
