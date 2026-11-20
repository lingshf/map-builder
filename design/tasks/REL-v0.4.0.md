# REL-v0.4.0: release candidate for sprint 3 (non-rectangular roofs, textures)

Owner: release manager · after S3-REVIEW blockers close · D28, D29, D32, D63

## Scope

The RC PR includes:

* `CHANGELOG.md`;
* `docs/user` (the textures toggle, CLI `--no-textures`, roof support matrix);
* `docs/flows`;
* `docs/demo/v0.4.0` (tools/demo presets munich-altstadt and pittsburgh, textured vs
  untextured, plus roof before/after on Munich);
* `docs/releases/v0.4.0.md`;
* `GENERATOR_VERSION = "0.4.0"`, with the D50 drift guard kept green.

## Acceptance criteria

1. Munich and Pittsburgh are built with default settings (textures on), via the CLI and via
   headless Blender. All four are strictly VALID, the C# reader loads each one, and all of
   their probes pass.
2. Build times are medians of 3 runs (D32), compared with v0.3.0.
3. The release notes state:
   * the Munich built-as-tagged roof count;
   * the roof shapes still rectangle-only;
   * format 2.1.0 with optional textures (2.x readers keep working);
   * the CC0 texture provenance.
4. Assets:
   * `map_builder-0.4.0.zip`, a G4 zip install that passes in Blender and includes the
     textures;
   * `munich-altstadt-0.4.0.mbmap`;
   * `pittsburgh-0.4.0.mbmap`.

Close order (D63): S3-REVIEW → RC → demo → short close check by design → coordinator retro →
tag.

## Conflict domain

Release-manager docs, `core/__init__.py` (version only), `docs/demo/v0.4.0/**`.
