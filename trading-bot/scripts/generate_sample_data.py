#!/usr/bin/env python3
"""Regenerate the bundled synthetic sample dataset (data/sample/SYNTH.csv)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.data import generate_synthetic

out = Path(__file__).resolve().parent.parent / "data" / "sample" / "SYNTH.csv"
out.parent.mkdir(parents=True, exist_ok=True)
df = generate_synthetic()
df.to_csv(out)
print(f"wrote {len(df)} bars to {out}")
