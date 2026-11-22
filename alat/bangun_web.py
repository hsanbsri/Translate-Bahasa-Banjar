"""Bangun versi statis untuk hosting gratis (Cloudflare Pages) ke folder web/.

Isi: semua berkas static/ + data kamus dalam JSON (data/*.json) + aturan header Cloudflare.
Versi statis menerjemahkan sepenuhnya di browser; fitur pengelolaan (Tinjau Kamus, usulan)
otomatis disembunyikan karena data/info.json bermode "statis".

Pemakaian:
    ./venv/bin/python -I alat/bangun_web.py          # hasil di web/
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from app import VERSI, data_web  # noqa: E402
from app.kamus import Kamus  # noqa: E402
from app.mesin import MesinBalik  # noqa: E402
from app.sumber import BAHASA  # noqa: E402

KELUAR = AKAR / "web"

# Cloudflare Pages: data & service worker selalu diperiksa ulang agar pembaruan kamus
# langsung sampai ke pengguna; ikon boleh di-cache lama.
HEADERS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin

/sw.js
  Cache-Control: no-cache

/data/*
  Cache-Control: no-cache

/manifest.webmanifest
  Content-Type: application/manifest+json

/ikon/*
  Cache-Control: public, max-age=604800
"""


def tulis_json(lokasi: Path, isi) -> int:
    teks = json.dumps(isi, ensure_ascii=False, separators=(",", ":"))
    lokasi.write_text(teks, encoding="utf-8")
    return len(teks.encode())


def main() -> None:
    if KELUAR.exists():
        shutil.rmtree(KELUAR)
    shutil.copytree(AKAR / "static", KELUAR)
    (KELUAR / "data").mkdir()

    kamus = Kamus.muat()
    balik = MesinBalik(kamus)
    ukuran = {
        "info.json": tulis_json(KELUAR / "data" / "info.json", {"mode": "statis", "versi": VERSI, "bahasa": BAHASA}),
        "kamus.json": tulis_json(KELUAR / "data" / "kamus.json", data_web.baris_kamus(kamus)),
        "khusus.json": tulis_json(KELUAR / "data" / "khusus.json", data_web.khusus(balik)),
        "kata_id_umum.json": tulis_json(KELUAR / "data" / "kata_id_umum.json", data_web.kata_id(balik)),
    }
    (KELUAR / "_headers").write_text(HEADERS, encoding="utf-8")

    print(f"Versi {VERSI}: {len(kamus)} entri kamus, {len(balik.khusus)} entri khusus, "
          f"{len(balik.kata_id)} kata Indonesia umum")
    for nama, n in ukuran.items():
        print(f"  data/{nama:20} {n / 1024:8.1f} KB")
    total = sum(f.stat().st_size for f in KELUAR.rglob("*") if f.is_file())
    print(f"-> {KELUAR} ({total / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
