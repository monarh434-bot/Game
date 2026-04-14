import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';

const canvas = document.getElementById('game');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87ceeb);

const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 4, 8);

const light = new THREE.DirectionalLight(0xffffff, 1.2);
light.position.set(6, 10, 4);
scene.add(light);
scene.add(new THREE.AmbientLight(0xffffff, 0.6));

const blockGeo = new THREE.BoxGeometry(1, 1, 1);
const materials = {
  grass: new THREE.MeshLambertMaterial({ color: 0x3cb043 }),
  stone: new THREE.MeshLambertMaterial({ color: 0x888888 }),
  wood: new THREE.MeshLambertMaterial({ color: 0x8b5a2b })
};

const blocks = new Map();
const players = new Map();
let socket = null;
let myId = null;
let mode = "place";
let myPos = { x: 0, y: 2, z: 5 };
let targetCursor = { x: 0, y: 1, z: 0 };

const cursor = new THREE.Mesh(
  new THREE.BoxGeometry(1.02, 1.02, 1.02),
  new THREE.MeshBasicMaterial({ color: 0xffff00, wireframe: true })
);
scene.add(cursor);

function key(x, y, z) { return `${x},${y},${z}`; }
function addLog(msg) {
  const log = document.getElementById('log');
  const div = document.createElement('div');
  div.textContent = msg;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
function setStatus(msg) { document.getElementById('status').textContent = msg; }

function setBlock(x, y, z, blockType) {
  const k = key(x, y, z);
  const old = blocks.get(k);
  if (old) { scene.remove(old); blocks.delete(k); }
  if (blockType === "air") return;
  const mesh = new THREE.Mesh(blockGeo, materials[blockType] || materials.grass);
  mesh.position.set(x, y, z);
  scene.add(mesh);
  blocks.set(k, mesh);
}

function setPlayer(player) {
  if (player.id === myId) return;
  let mesh = players.get(player.id);
  if (!mesh) {
    mesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.7, 1.6, 0.7),
      new THREE.MeshLambertMaterial({ color: 0x3366ff })
    );
    scene.add(mesh);
    players.set(player.id, mesh);
  }
  mesh.position.set(player.x, player.y, player.z);
}

async function loadWorld() {
  const res = await fetch('/api/world');
  const data = await res.json();
  data.blocks.forEach(b => setBlock(b.x, b.y, b.z, b.block_type));
  addLog(`AI mood: ${data.ai.mood} (${data.ai.intensity})`);
}

function connect(nickname) {
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/default/${encodeURIComponent(nickname)}`);
  socket.onopen = () => setStatus('Connected');
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'welcome') {
      myId = data.id;
      data.world.forEach(b => setBlock(b.x, b.y, b.z, b.block_type));
      addLog(`Joined as ${nickname}`);
    } else if (data.type === 'player_sync' || data.type === 'player_join' || data.type === 'player_leave') {
      (data.players || []).forEach(setPlayer);
    } else if (data.type === 'block') {
      setBlock(data.x, data.y, data.z, data.block_type);
    } else if (data.type === 'chat') {
      addLog(`${data.nickname}: ${data.message}`);
    } else if (data.type === 'ai_message' || data.type === 'world_event') {
      addLog(`AI: ${data.message}`);
    }
  };
  socket.onclose = () => setStatus('Disconnected');
}

function move(dx, dz) {
  myPos.x += dx;
  myPos.z += dz;
  camera.position.x = myPos.x;
  camera.position.z = myPos.z + 8;
  camera.lookAt(myPos.x, 0, myPos.z);
  targetCursor = { x: Math.round(myPos.x), y: 1, z: Math.round(myPos.z - 2) };
  cursor.position.set(targetCursor.x, targetCursor.y, targetCursor.z);
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'move', x: myPos.x, y: myPos.y, z: myPos.z }));
  }
}

async function postBlock(blockType) {
  await fetch('/api/block', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ ...targetCursor, block_type: blockType })
  });
  setBlock(targetCursor.x, targetCursor.y, targetCursor.z, blockType);
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'block', ...targetCursor, block_type: blockType }));
  }
}

function animate() {
  requestAnimationFrame(animate);
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
});

document.getElementById('joinBtn').onclick = async () => {
  const nickname = document.getElementById('nickname').value.trim() || 'Builder';
  await fetch('/api/join', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ nickname })
  });
  document.getElementById('joinBox').classList.add('hidden');
  document.getElementById('hud').classList.remove('hidden');
  await loadWorld();
  connect(nickname);
  move(0, 0);
};

document.getElementById('placeBtn').onclick = () => mode = 'place';
document.getElementById('removeBtn').onclick = () => mode = 'remove';
document.getElementById('sendBtn').onclick = () => {
  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'chat', message }));
  }
  input.value = '';
};

document.querySelectorAll('#controls button[data-move]').forEach(btn => {
  btn.addEventListener('click', () => {
    const dir = btn.dataset.move;
    if (dir === 'forward') move(0, -1);
    if (dir === 'back') move(0, 1);
    if (dir === 'left') move(-1, 0);
    if (dir === 'right') move(1, 0);
  });
});

canvas.addEventListener('click', async () => {
  await postBlock(mode === 'place' ? 'wood' : 'air');
});
