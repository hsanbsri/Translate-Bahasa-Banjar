"""Uji kesamaan: mesin JavaScript (static/mesin.js) harus menghasilkan segmen yang identik
dengan mesin Python untuk ribuan kata & kalimat buatan (dan korpus NusaX bila tersedia).
"""

from __future__ import annotations

import csv
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from app import data_web, morfologi
from app.kamus import Kamus
from app.mesin import Mesin, MesinBalik

AKAR = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js tidak terpasang")

AWALAN_ID = ["me", "ber", "di", "ter", "ke", "se"]
AKHIRAN_ID = ["", "kan", "an", "i", "nya", "ku", "mu", "lah", "kah", "kannya", "inya"]
AKHIRAN_BJN = ["", "akan", "an", "i", "nya", "ku", "mu", "lah", "kah", "akannya"]
PARTIKEL = ["am", "ai", "pang", "neh"]


def _ragam_huruf(kata: str) -> list[str]:
    return [kata, kata.capitalize(), kata.upper()]


def kalimat_uji(kamus: Kamus, balik: MesinBalik) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    acak = random.Random(20261122)
    ke_banjar: list[str] = []
    dari_banjar: list[str] = []

    # --- kata Indonesia dengan imbuhan
    dasar_id = [k for k in kamus.entri if " " not in k]
    for d in dasar_id:
        for ak in AKHIRAN_ID:
            ke_banjar.append(d + ak)
            ke_banjar.append(morfologi.nasal_indonesia(d) + ak)
            for aw in AWALAN_ID[1:]:
                ke_banjar.append(aw + d + ak)
    ke_banjar += ["mengirim", "memakan", "menanti", "menulis", "belajar", "bekerja", "menyapu", "melihat"]

    # --- bentuk Banjar dengan imbuhan & ejaan santai
    bentuk_bjn = sorted({b for b in kamus.balik if " " not in b})
    for b in bentuk_bjn:
        for ak in AKHIRAN_BJN:
            for aw in ["", "ba", "di", "ta", "ka", "sa"]:
                dari_banjar.append(aw + b + ak)
                dari_banjar.append((aw + b + ak).replace("a", "e", 1))
            dari_banjar.append(morfologi.nasal_banjar(b) + ak)
        dari_banjar.append(f"ba{b}an")
    dari_banjar += ["bemainan", "bedarahan", "bajualan", "tabrakan", "semalam", "laptop", "xyzq"]

    # --- kalimat acak: huruf besar, tanda baca, frasa, kata ulang, penguat, partikel
    kata_id = list(kamus.entri) + ["sangat", "komputer", "Martapura", "anak-anak"]
    kata_bjn = list(kamus.balik) + ["banar", "bemainan", "laptop"] + PARTIKEL
    tanda = ["", "", "", ",", ".", "!", "?", " -", "…", " (x)", " 12"]
    for _ in range(1500):
        n = acak.randint(1, 9)
        ke_banjar.append(" ".join(acak.choice(_ragam_huruf(acak.choice(kata_id))) + acak.choice(tanda)
                                  for _ in range(n)))
        dari_banjar.append(" ".join(acak.choice(_ragam_huruf(acak.choice(kata_bjn))) + acak.choice(tanda)
                                    for _ in range(n)))
    for p in PARTIKEL:
        dari_banjar += [f"{p.capitalize()}, ulun litak banar.", f"inya garing {p}.", f"Inya garing. {p.capitalize()}, kayapa ikam?",
                        f"{p} {p} ulun", f"nyaman {p}, tagal larang."]

    # --- korpus NusaX (bila sudah diunduh lewat alat/, tidak ada di repo)
    nusax = AKAR / "sumber_data" / "nusax"
    for nama in ("train.csv", "valid.csv", "test.csv"):
        if (nusax / nama).exists():
            with open(nusax / nama, encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    ke_banjar.append(r["indonesian"])
                    dari_banjar.append(r["banjarese"])

    pasangan = [(t, ragam) for t in ke_banjar for ragam in ("biasa", "halus", "kasar")]
    kenal = dasar_id[:300] + ke_banjar[:2000]
    return pasangan, dari_banjar, kenal


def test_mesin_js_identik_dengan_python():
    kamus = Kamus.muat()
    mesin = Mesin(kamus)
    balik = MesinBalik(kamus, lokasi_khusus=Path(__file__).parent / "kamus_bjn_khusus_uji.csv")
    ke_banjar, dari_banjar, kenal = kalimat_uji(kamus, balik)

    masuk = {
        "kamus": data_web.baris_kamus(kamus),
        "khusus": data_web.khusus(balik),
        "kata_id": data_web.kata_id(balik),
        "ke_banjar": ke_banjar,
        "dari_banjar": dari_banjar,
        "kenal": kenal,
    }
    proses = subprocess.run([NODE, str(Path(__file__).parent / "paritas_node.mjs")],
                            input=json.dumps(masuk), capture_output=True, text=True, check=True)
    js = json.loads(proses.stdout)

    def py(segmen):
        return [s.ke_dict() for s in segmen]

    beda = []
    for (teks, ragam), hasil_js in zip(ke_banjar, js["ke_banjar"]):
        hasil_py = py(mesin.terjemah(teks, ragam))
        if hasil_py != hasil_js:
            beda.append(("ke_banjar", ragam, teks, hasil_py, hasil_js))
    for teks, hasil_js in zip(dari_banjar, js["dari_banjar"]):
        hasil_py = py(balik.terjemah(teks))
        if hasil_py != hasil_js:
            beda.append(("dari_banjar", "", teks, hasil_py, hasil_js))
    for kata, hasil_js in zip(kenal, js["kenal"]):
        if mesin.kenal(kata) != hasil_js:
            beda.append(("kenal", "", kata, mesin.kenal(kata), hasil_js))

    total = len(ke_banjar) + len(dari_banjar) + len(kenal)
    assert not beda, f"{len(beda)} dari {total} kasus berbeda; contoh pertama: {beda[:3]}"
    print(f"\n{total} kasus identik")
