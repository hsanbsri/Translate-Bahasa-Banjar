"""Gabungkan kandidat NusaX dan NLLB menjadi antrean tinjauan data/kandidat.csv.

Urutan antrean = seberapa sering kata dipakai (frekuensi per sejuta token, diambil
yang terbesar dari daftar subtitle atau korpus NusaX), sehingga kata paling umum
ditinjau lebih dulu. Usulan yang disepakati kedua sumber ditaruh paling depan.

Pemakaian:
    python alat/gabung_kandidat.py sumber_data/kandidat_nusax.csv sumber_data/kandidat_nllb.csv \
        sumber_data/frekuensi/id_50k.txt data/kandidat.csv
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def baca(lokasi: str) -> dict[str, dict]:
    with open(lokasi, encoding="utf-8", newline="") as f:
        return {r["indonesia"]: r for r in csv.DictReader(f)}


def total_token(lokasi_frek: str) -> int:
    total = 0
    for baris in Path(lokasi_frek).read_text(encoding="utf-8").splitlines():
        bagian = baris.split()
        if len(bagian) == 2 and bagian[1].isdigit():
            total += int(bagian[1])
    return total


def main(nusax: str, nllb: str, frek: str, keluaran: str) -> None:
    a, b = baca(nusax), baca(nllb)
    tot_sub = total_token(frek)
    tot_nusax = sum(int(r["frek_nusax"]) for r in a.values())

    baris = []
    for kata in set(a) | set(b):
        u_nusax = [x for x in a.get(kata, {}).get("kandidat", "").split("|") if x]
        u_nllb = [x for x in b.get(kata, {}).get("kandidat", "").split("|") if x]
        sepakat = [x for x in u_nusax if x in u_nllb]
        usulan = list(dict.fromkeys(sepakat + u_nusax + u_nllb))
        if not usulan:
            continue
        f_sub = int(b.get(kata, {}).get("frek_subtitle") or 0) / tot_sub * 1e6
        f_nusax = int(a.get(kata, {}).get("frek_nusax") or 0) / tot_nusax * 1e6
        sumber = "+".join(n for n, u in (("nusax", u_nusax), ("nllb", u_nllb)) if u)
        baris.append({
            "indonesia": kata,
            "usulan": "|".join(usulan[:5]),
            "sepakat": sepakat[0] if sepakat else "",
            "sumber": sumber,
            "prioritas": f"{max(f_sub, f_nusax):.1f}",
            "contoh_id": a.get(kata, {}).get("contoh_id", ""),
            "contoh_bjn": a.get(kata, {}).get("contoh_bjn", ""),
        })
    baris.sort(key=lambda r: -float(r["prioritas"]))

    with open(keluaran, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0]))
        w.writeheader()
        w.writerows(baris)
    n_sepakat = sum(1 for r in baris if r["sepakat"])
    print(f"{len(baris)} kandidat ({n_sepakat} disepakati kedua sumber) -> {keluaran}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
