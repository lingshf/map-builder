# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""One hermetic ``dotnet build`` of the C# reference reader per test run, shared by every C# test class.

    from .csharp_build import reader_command
    subprocess.run([*reader_command(), "--validate-many", directory], ...)

The reader is built once per process (guarded by a file lock) into a private temporary directory, outside the
checkout, so parallel suites on one checkout do not share ``bin``/``obj`` (CS2012). The repository ``NuGet.config``
ignores user-level feeds, and the NuGet audit warning (NU1900, an unreachable feed) is neither raised nor fatal.
"""

import atexit
import os
import shutil
import subprocess
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.join(ROOT, "examples", "csharp", "MbmapReader")

BUILD_COUNT = 0   # builds run by this process (the "one build per run" check)

_guard = threading.Lock()
_dll = None
_failure = None   # a failed build is cached too: one attempt per run
_outdir = None


def dotnet_available():
    return shutil.which("dotnet") is not None


class _FileLock:
    """Exclusive advisory lock on a file shared by every suite on the machine; serialises the builds so parallel
    suites do not race on the NuGet caches."""

    def __init__(self, path):
        self.path = path
        self.f = None

    def __enter__(self):
        self.f = open(self.path, "a+b")
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_LOCK, 1)   # blocks for ~10 s, then raises: retry
                    break
                except OSError:
                    continue
        else:
            import fcntl
            fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.f.close()   # closing also drops a flock

def _cleanup():
    if _outdir:
        shutil.rmtree(_outdir, ignore_errors=True)


def reader_dll():
    """Path of the built ``MbmapReader.dll``; builds it on the first call of the run. Raises RuntimeError on failure."""
    global _dll, _outdir, _failure, BUILD_COUNT
    with _guard:
        if _dll is not None:
            return _dll
        if _failure is not None:
            raise RuntimeError(_failure)
        try:
            _outdir = tempfile.mkdtemp(prefix="mbmap-reader-")
            atexit.register(_cleanup)
            # a private copy of the sources: the checkout keeps its own bin/obj (from ``dotnet run``), whose generated
            # .cs files the default globbing would otherwise compile a second time
            src = os.path.join(_outdir, "src")
            shutil.copytree(PROJECT, src, ignore=shutil.ignore_patterns("bin", "obj"))
            out = os.path.join(_outdir, "bin")
            with _FileLock(os.path.join(tempfile.gettempdir(), "mbmap-reader-build.lock")):
                BUILD_COUNT += 1
                build = subprocess.run(
                    ["dotnet", "build", "-c", "Release", "-nologo", "-v", "q", src, "-o", out,
                     f"-p:RestoreConfigFile={os.path.join(ROOT, 'NuGet.config')}", "-p:NuGetAudit=false",
                     "-p:WarningsNotAsErrors=NU1900", "-p:UseSharedCompilation=false"],
                    capture_output=True, text=True)
            if build.returncode != 0:
                raise RuntimeError("dotnet build failed:\n" + build.stdout + build.stderr)
        except Exception as e:   # a launch error (OSError) is cached like a failed build
            _failure = str(e) if isinstance(e, RuntimeError) else f"dotnet build could not run: {e!r}"
            raise RuntimeError(_failure) from e
        _dll = os.path.join(out, "MbmapReader.dll")
        return _dll

def reader_command():
    """argv prefix that runs the shared build of the reader: ``[*reader_command(), *reader_args]``."""
    return ["dotnet", reader_dll()]
