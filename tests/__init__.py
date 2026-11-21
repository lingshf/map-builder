# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 lingshf
"""Test-run guard: a ResourceWarning (a leaked handle) or any exception a finalizer cannot raise (``-W error`` turns the
former into the latter) is recorded and makes the whole run exit 1."""

import atexit
import gc
import os
import sys
import warnings

UNRAISED = []


def _record(unraisable):
    UNRAISED.append(f"{unraisable.exc_type.__name__}: {unraisable.exc_value} (in {unraisable.object!r})")
    sys.__unraisablehook__(unraisable)


_show = warnings.showwarning


def _showwarning(message, category, filename, lineno, *args, **kwargs):
    # unittest resets the filters to "default", which only prints a ResourceWarning: record it as well
    if issubclass(category, ResourceWarning):
        UNRAISED.append(f"{category.__name__}: {message} ({filename}:{lineno})")
    _show(message, category, filename, lineno, *args, **kwargs)


def _fail_on_unraised():
    gc.collect()
    if UNRAISED:
        sys.stderr.write("FAILED: %d unraisable exception(s) in finalizers, e.g. a leaked handle:\n  %s\n"
                         % (len(UNRAISED), "\n  ".join(UNRAISED)))
        sys.stderr.flush()
        os._exit(1)


sys.unraisablehook = _record
warnings.showwarning = _showwarning
atexit.register(_fail_on_unraised)