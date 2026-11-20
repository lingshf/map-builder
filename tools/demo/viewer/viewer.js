// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 lingshf
import * as THREE from "three";
import { GLTFLoader } from "./vendor/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "./vendor/jsm/controls/OrbitControls.js";

const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x9fc4e8);
scene.add(new THREE.HemisphereLight(0xcfe4ff, 0x777766, 1.0));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(-300, 500, 250);
scene.add(sun);

const camera = new THREE.PerspectiveCamera(55, 1, 0.5, 20000);
const orbit = new OrbitControls(camera, canvas);
orbit.enableDamping = true;
const flyBox = document.getElementById("fly");
const keys = new Set();
let yaw = 0, pitch = 0, dragging = false;

function resize() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();

addEventListener("keydown", (e) => keys.add(e.code));
addEventListener("keyup", (e) => keys.delete(e.code));
canvas.addEventListener("pointerdown", () => { dragging = true; });
addEventListener("pointerup", () => { dragging = false; });
addEventListener("pointermove", (e) => {
  if (!flyBox.checked || !dragging) return;
  yaw -= e.movementX * 0.003;
  pitch = Math.max(-1.5, Math.min(1.5, pitch - e.movementY * 0.003));
});
flyBox.addEventListener("change", () => {
  orbit.enabled = !flyBox.checked;
  if (flyBox.checked) {
    const d = new THREE.Vector3();
    camera.getWorldDirection(d);
    yaw = Math.atan2(-d.x, -d.z);
    pitch = Math.asin(d.y);
  }
});

function flyStep(dt) {
  camera.rotation.set(pitch, yaw, 0, "YXZ");
  const speed = (keys.has("ShiftLeft") ? 60 : 15) * dt;
  const fwd = new THREE.Vector3(-Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), -Math.cos(yaw) * Math.cos(pitch));
  const right = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
  if (keys.has("KeyW")) camera.position.addScaledVector(fwd, speed);
  if (keys.has("KeyS")) camera.position.addScaledVector(fwd, -speed);
  if (keys.has("KeyD")) camera.position.addScaledVector(right, speed);
  if (keys.has("KeyA")) camera.position.addScaledVector(right, -speed);
  if (keys.has("KeyE")) camera.position.y += speed;
  if (keys.has("KeyQ")) camera.position.y -= speed;
}

function capsule(a, b, r, mat) {
  const group = new THREE.Group();
  const va = new THREE.Vector3(...a), vb = new THREE.Vector3(...b);
  const len = va.distanceTo(vb);
  if (len > 1e-6) {
    const cyl = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 16, 1, true), mat);
    cyl.position.copy(va).lerp(vb, 0.5);
    cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), vb.clone().sub(va).normalize());
    group.add(cyl);
  }
  for (const p of [va, vb]) {
    const s = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), mat);
    s.position.copy(p);
    group.add(s);
  }
  return group;
}

function frame(box) {
  const c = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3()).length();
  camera.position.set(c.x + size * 0.45, c.y + size * 0.4, c.z + size * 0.55);
  orbit.target.copy(c);
  orbit.update();
}

const info = document.getElementById("info");
const list = document.getElementById("probes");

async function main() {
  const [probes, gltf] = await Promise.all([
    fetch("probes.json").then((r) => r.json()),
    new GLTFLoader().loadAsync("map.glb"),
  ]);
  scene.add(gltf.scene);
  const box = new THREE.Box3().setFromObject(gltf.scene);
  frame(box);
  const pp = probes.passage_probes;
  info.textContent = `${probes.name || "map"} | package ${(probes.package_id || "?").slice(0, 19)} | ${pp.length} passage probe(s)`;
  if (!pp.length) list.innerHTML = "<li>none in this package</li>";
  for (const p of pp) {
    const ok = p.result === "PASS";
    const color = ok ? 0x18c24a : p.result === "UNCHECKED" ? 0x888888 : 0xe0212a;
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.55 });
    const pts = p.path_gltf;
    for (let i = 0; i + 1 < pts.length || i === 0; i++) scene.add(capsule(pts[i], pts[Math.min(i + 1, pts.length - 1)], p.radius_m, mat));
    const li = document.createElement("li");
    const status = document.createElement("span");
    status.className = ok ? "pass" : "blocked";
    status.textContent = p.result;
    li.append(status, ` ${p.id} (${p.kind}, r=${p.radius_m} m)`);
    li.title = p.blocked_by.length ? "blocked by " + p.blocked_by.join(", ") : "";
    li.onclick = () => {
      const m = new THREE.Vector3(...pts[Math.floor(pts.length / 2)]);
      camera.position.set(m.x + 15, m.y + 10, m.z + 15);
      orbit.target.copy(m);
      orbit.update();
    };
    list.appendChild(li);
  }
}

let last = performance.now();
renderer.setAnimationLoop((t) => {
  const dt = Math.min((t - last) / 1000, 0.1);
  last = t;
  if (flyBox.checked) flyStep(dt); else orbit.update();
  renderer.render(scene, camera);
});
main().catch((e) => { info.textContent = "failed to load: " + e; });
