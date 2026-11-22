"""Usulkan padanan Banjar untuk kata dasar Indonesia yang paling sering dipakai, memakai NLLB-200.

1. Daftar frekuensi kata Indonesia (FrequencyWords/OpenSubtitles, CC-BY-SA 4.0) di-stem
   dengan Sastrawi; hanya kata dasar yang ada di kamus kata dasar Sastrawi yang dipakai.
2. Tiap kata diterjemahkan NLLB-200 (ind_Latn -> bjn_Latn); diambil 3 hasil beam teratas.

Model NLLB berlisensi CC-BY-NC 4.0: hanya dipakai untuk membuat DRAF kandidat yang
kemudian diperiksa manusia; model tidak disertakan dalam aplikasi.

Pemakaian (CPU):
    venv-alat/bin/python alat/kandidat_nllb.py --jumlah 2500 \
        --tambahan sumber_data/kandidat_nusax.csv --keluaran sumber_data/kandidat_nllb.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from collections import Counter
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
MODEL = "facebook/nllb-200-distilled-600M"
POLA_BERSIH = re.compile(r"[^a-zà-ÿ\- ]")


def kata_dasar_teratas(lokasi_frek: Path, jumlah: int, kecuali: set[str]) -> list[tuple[str, int]]:
    from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
    import Sastrawi
    kamus_dasar = set(
        (Path(Sastrawi.__file__).parent / "Stemmer" / "data" / "kata-dasar.txt")
        .read_text(encoding="utf-8").split()
    )
    stemmer = StemmerFactory().create_stemmer()
    hitung: Counter[str] = Counter()
    for baris in lokasi_frek.read_text(encoding="utf-8").splitlines():
        bagian = baris.split()
        if len(bagian) != 2 or not bagian[0].isalpha():
            continue
        dasar = stemmer.stem(bagian[0])
        if dasar in kamus_dasar and len(dasar) >= 2:
            hitung[dasar] += int(bagian[1])
    return [(k, n) for k, n in hitung.most_common() if k not in kecuali][:jumlah]


# Partikel/kata sambung yang sering ditempelkan NLLB saat menerjemahkan kata tunggal.
PENGISI = {"tuh", "jua", "aja", "nang", "lawan", "gasan", "ada", "itu", "kan"}


def bersihkan(teks: str) -> str:
    kata = POLA_BERSIH.sub(" ", teks.lower()).split()
    while len(kata) > 1 and kata[-1] in PENGISI:
        kata.pop()
    while len(kata) > 1 and kata[0] in PENGISI:
        kata.pop(0)
    return " ".join(kata)


def terjemahkan(kata: list[str], ukuran_batch: int, utas: int) -> dict[str, list[str]]:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    torch.set_num_threads(utas)
    tok = AutoTokenizer.from_pretrained(MODEL, src_lang="ind_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL).eval()
    bos = tok.convert_tokens_to_ids("bjn_Latn")
    hasil: dict[str, list[str]] = {}
    mulai = time.time()
    for i in range(0, len(kata), ukuran_batch):
        potong = kata[i:i + ukuran_batch]
        masuk = tok(potong, return_tensors="pt", padding=True)
        with torch.inference_mode():
            keluar = model.generate(
                **masuk, forced_bos_token_id=bos, num_beams=5,
                num_return_sequences=3, max_new_tokens=12,
            )
        teks = tok.batch_decode(keluar, skip_special_tokens=True)
        for j, k in enumerate(potong):
            unik = []
            for t in teks[j * 3:(j + 1) * 3]:
                t = bersihkan(t)
                if t and t not in unik and len(t.split()) <= 3:
                    unik.append(t)
            hasil[k] = unik
        selesai = i + len(potong)
        laju = selesai / (time.time() - mulai)
        print(f"\r{selesai}/{len(kata)} kata ({laju:.1f} kata/detik)", end="", flush=True)
    print()
    return hasil


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jumlah", type=int, default=2500)
    ap.add_argument("--frekuensi", default=str(AKAR / "sumber_data/frekuensi/id_50k.txt"))
    ap.add_argument("--tambahan", help="CSV kandidat NusaX; kolom 'indonesia' ikut diterjemahkan")
    ap.add_argument("--keluaran", default=str(AKAR / "sumber_data/kandidat_nllb.csv"))
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--utas", type=int, default=8, help="jumlah thread CPU")
    a = ap.parse_args()

    import sys
    sys.path.insert(0, str(AKAR))
    from app.kamus import Kamus
    sudah = set(Kamus.muat().entri)

    daftar = kata_dasar_teratas(Path(a.frekuensi), a.jumlah, sudah)
    frek = dict(daftar)
    if a.tambahan:
        with open(a.tambahan, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                frek.setdefault(r["indonesia"], 0)
    kata = [k for k in frek if k not in sudah]
    print(f"{len(kata)} kata akan diterjemahkan")

    hasil = terjemahkan(kata, a.batch, a.utas)
    with open(a.keluaran, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["indonesia", "kandidat", "frek_subtitle"])
        for k in kata:
            w.writerow([k, "|".join(hasil.get(k, [])), frek[k]])
    print(f"-> {a.keluaran}")


if __name__ == "__main__":
    main()
