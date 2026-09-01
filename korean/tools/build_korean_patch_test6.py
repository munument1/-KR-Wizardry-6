#!/usr/bin/env python3
"""Compatibility wrapper; production compact-roster fixes now live in build_korean_patch_release.py."""
from __future__ import annotations

import build_korean_patch_release as release


if __name__ == "__main__":
    raise SystemExit(release.main())
