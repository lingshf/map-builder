#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
# Reproducible `extension build` (D100): a fresh clone stamps every file with its checkout time, and the zip
# records file mtimes, so the build normalises them to the commit time first.
# Usage: tools/build_extension.sh <repo-dir> <output-dir>   (blender must be on PATH)
set -euo pipefail
repo="$1"
out="$2"
commit_time=$(git -C "$repo" log -1 --format=%ct)
# Local time is also baked into the zip's DOS timestamps, so pin the zone.
export TZ=UTC
git -C "$repo" ls-files -z | (cd "$repo" && xargs -0 touch -h -d "@${commit_time}")
find "$repo/map_builder" -type d -exec touch -d "@${commit_time}" {} +
mkdir -p "$out"
blender --command extension build --source-dir "$repo/map_builder" --output-dir "$out"
