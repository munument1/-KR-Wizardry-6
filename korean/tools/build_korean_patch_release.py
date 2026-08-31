#!/usr/bin/env python3
"""Release entry point that extends the stable renderer build with full SCENARIO localization."""
from __future__ import annotations

import build_korean_patch as stable
from scenario_localization import patch_scenario_strings

# Keep the runtime-tested WFONT0/WFONT1..4 renderer implementation byte-for-byte
# in build_korean_patch.py. Only replace its SCENARIO patch callback.
stable.patch_scenario_items = patch_scenario_strings

if __name__ == "__main__":
    raise SystemExit(stable.main())
