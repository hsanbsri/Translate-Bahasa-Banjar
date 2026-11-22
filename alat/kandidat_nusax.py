"""Tarik kandidat pasangan kata Indonesia -> Banjar dari korpus paralel NusaX-MT.

Metode: IBM Model 1 (EM) dilatih dua arah (Indonesia->Banjar dan Banjar->Indonesia);
skor pasangan = akar(p(b|i) * p(i|b)), sehingga hanya pasangan yang saling memilih
yang mendapat skor tinggi. Setiap kandidat disertai satu contoh kalimat.

Sumber data: NusaX-MT (Winata dkk., 2022), lisensi CC-BY-SA 4.0.

Pemakaian:
    python alat/kandidat_nusax.py sumber_data/nusax sumber_data/kandidat_nusax.csv
"""

from __future__ import annotations

import csv
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

POLA = re.compile(r"[a-zà-ÿ]+(?:-[a-zà-ÿ]+)*")
ITERASI = 12
FREK_MIN = 2
SKOR_MIN = 0.15
KANDIDAT_MAKS = 3


def token(teks: str) -> list[str]:
    return POLA.findall(teks.lower())


def muat(folder: Path) -> list[tuple[list[str], list[str], str, str]]:
    pasangan = []
    for nama in ("train.csv", "valid.csv", "test.csv"):
        with open(folder / nama, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                i, b = r["indonesian"].strip(), r["banjarese"].strip()
                if i and b:
                    pasangan.append((token(i), token(b), i, b))
    return pasangan


def ibm1(korpus: list[tuple[list[str], list[str]]]) -> dict[str, dict[str, float]]:
    """t[s][t] = p(t | s). NULL disertakan di sisi sumber."""
    sasaran_vocab = {w for _, tg in korpus for w in tg}
    seragam = 1.0 / max(1, len(sasaran_vocab))
    t: dict[tuple[str, str], float] = defaultdict(lambda: seragam)
    for _ in range(ITERASI):
        hitung: dict[tuple[str, str], float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        for src, tg in korpus:
            src = src + ["<NULL>"]
            for w_t in tg:
                z = sum(t[(w_s, w_t)] for w_s in src)
                for w_s in src:
                    c = t[(w_s, w_t)] / z
                    hitung[(w_s, w_t)] += c
                    total[w_s] += c
        t = defaultdict(float, {(s, tg): c / total[s] for (s, tg), c in hitung.items()})
    hasil: dict[str, dict[str, float]] = defaultdict(dict)
    for (s, tg), p in t.items():
        if p > 0.01:
            hasil[s][tg] = p
    return hasil


def main(folder: str, keluaran: str) -> None:
    data = muat(Path(folder))
    print(f"{len(data)} pasangan kalimat")
    maju = ibm1([(i, b) for i, b, _, _ in data])     # p(b | i)
    mundur = ibm1([(b, i) for i, b, _, _ in data])   # p(i | b)
    frek = Counter(w for i, _, _, _ in data for w in i)

    baris = []
    for w_i, n in frek.most_common():
        if n < FREK_MIN or len(w_i) < 2:
            continue
        skor = {
            w_b: math.sqrt(p * mundur.get(w_b, {}).get(w_i, 0.0))
            for w_b, p in maju.get(w_i, {}).items()
        }
        terbaik = [(w, s) for w, s in sorted(skor.items(), key=lambda x: -x[1]) if s >= SKOR_MIN]
        if not terbaik:
            continue
        terbaik = terbaik[:KANDIDAT_MAKS]
        contoh = next(
            ((ci, cb) for i, b, ci, cb in data if w_i in i and terbaik[0][0] in b),
            ("", ""),
        )
        baris.append({
            "indonesia": w_i,
            "kandidat": "|".join(w for w, _ in terbaik),
            "skor": f"{terbaik[0][1]:.3f}",
            "frek_nusax": n,
            "contoh_id": contoh[0],
            "contoh_bjn": contoh[1],
        })

    with open(keluaran, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0]))
        w.writeheader()
        w.writerows(baris)
    print(f"{len(baris)} kandidat -> {keluaran}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
