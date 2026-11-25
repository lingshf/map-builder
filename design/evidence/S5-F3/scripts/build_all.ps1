# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 lingshf
# S5-F3 step 2 evidence: build every preset before (BaseRoot) and after (HeadRoot) through the CLI and Blender.
param(
    [Parameter(Mandatory)] [string] $HeadRoot,
    [Parameter(Mandatory)] [string] $BaseRoot,
    [Parameter(Mandatory)] [string] $Caches,
    [Parameter(Mandatory)] [string] $Work,
    [Parameter(Mandatory)] [string] $Blender
)
$ErrorActionPreference = 'Continue'
$env:PYTHONHASHSEED = '0'
$build = Join-Path $PSScriptRoot 'build_factoria.py'
New-Item -ItemType Directory -Force "$Work\builds" | Out-Null
foreach ($side in @(@('after', $HeadRoot), @('before', $BaseRoot))) {
    $tag, $root = $side
    foreach ($preset in 'bellevue-factoria', 'munich', 'pittsburgh') {
        $out = "$Work\builds\${tag}_${preset}_cli.mbmap"
        py -3.12 $build cli --root $root --cache $Caches --preset $preset --out $out *> "$out.log"
        "$tag $preset cli exit $LASTEXITCODE"
    }
    foreach ($preset in 'bellevue-factoria', 'munich', 'pittsburgh', 'sample') {
        $out = "$Work\builds\${tag}_${preset}_blender.mbmap"
        & $Blender -b --factory-startup --online-mode --python-exit-code 1 --python $build -- blender --root $root --cache $Caches --preset $preset --out $out *> "$out.log"
        "$tag $preset blender exit $LASTEXITCODE"
    }
}
