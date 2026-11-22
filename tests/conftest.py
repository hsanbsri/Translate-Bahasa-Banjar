"""Tes memakai salinan kamus tetap (tests/kamus_uji.csv), bukan kamus kerja di data/
yang terus bertambah lewat Tinjau Kamus."""

import os
from pathlib import Path

KAMUS_UJI = Path(__file__).parent / "kamus_uji.csv"
os.environ["PENERJEMAH_KAMUS"] = str(KAMUS_UJI)
