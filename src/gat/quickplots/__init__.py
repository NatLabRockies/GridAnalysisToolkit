import os
import sys

import matplotlib

# macOS's native "macosx" backend can spin up a Dock icon whose window never
# actually renders/responds -- a well-known Cocoa integration issue that
# depends on how Python itself was installed. Must happen before any pyplot
# import (switching backends after a Figure already exists doesn't migrate
# it), so this runs at package import time. Scoped to macOS only, skipped
# under CI, and only overrides the specific problematic default -- an
# explicit user/env backend choice (MPLBACKEND or an earlier matplotlib.use()
# call) is left alone.
#
# Prefer QtAgg over TkAgg: Apple's Command Line Tools Python links tkinter
# against Apple's own bundled Tcl/Tk, stuck at 8.5.9 for over a decade --
# long unpatched and known to render a blank canvas for matplotlib figures on
# modern macOS. QtAgg (via PySide6, if installed) doesn't depend on that
# system Tk at all. Falls back to TkAgg if no Qt binding is available.
if (
    sys.platform == "darwin"
    and not os.environ.get("CI")
    and matplotlib.get_backend().lower() == "macosx"
):
    for candidate in ("QtAgg", "TkAgg"):
        try:
            matplotlib.use(candidate)
            break
        except Exception:
            continue

from .dispatch import *
from .transmission import *
from .multi_system import *
