// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 lingshf
// Runs the Khronos glTF-Validator (npm `gltf-validator`) on a GLB and fails on any
// error, or on any warning about textures, samplers, images or TEXCOORD_0.
// usage: node tools/gltf_validate.js FILE.glb   (D66: glTFast proxy, no Unity Editor in CI)
const fs = require("fs");
const validator = require("gltf-validator");

const path = process.argv[2];
const bytes = new Uint8Array(fs.readFileSync(path));
validator.validateBytes(bytes, { uri: path }).then((report) => {
  const issues = report.issues.messages;
  const relevant = /TEXTURE|SAMPLER|IMAGE|TEXCOORD|UV/i;
  const bad = issues.filter(
    (m) => m.severity === 0 || (m.severity === 1 && (relevant.test(m.code) || relevant.test(m.pointer || "") || relevant.test(m.message)))
  );
  for (const m of issues) console.log(`severity ${m.severity} ${m.code} ${m.pointer || ""}: ${m.message}`);
  console.log(`${path}: ${report.issues.numErrors} error(s), ${report.issues.numWarnings} warning(s), ${bad.length} blocking`);
  process.exit(bad.length ? 1 : 0);
});
