"""Antrean tinjauan kandidat kamus.

Kandidat (dari alat/gabung_kandidat.py) ditampilkan satu per satu; keputusan pengguna
dicatat di log CSV dan kata yang disetujui langsung ditambahkan ke kamus (berkas dan
memori), sehingga bentuk turunannya (mis. "tempatnya" setelah "tempat") otomatis hilang
dari antrean.
"""

from __future__ import annotations

import csv
import threading
from datetime import datetime
from pathlib import Path

from .kamus import Entri, Kamus
from .mesin import Mesin

AKAR = Path(__file__).resolve().parent.parent
LOKASI_KANDIDAT = AKAR / "data" / "kandidat.csv"
LOKASI_LOG = AKAR / "data" / "tinjauan.csv"

KEPUTUSAN = {"simpan", "sama", "buang"}
KOLOM_LOG = ["waktu", "indonesia", "keputusan", "banjar", "banjar_halus", "banjar_kasar"]


class Tinjauan:
    def __init__(self, kamus: Kamus, mesin: Mesin, lokasi_kamus: Path,
                 lokasi_kandidat: Path = LOKASI_KANDIDAT, lokasi_log: Path = LOKASI_LOG):
        self.kamus, self.mesin = kamus, mesin
        self.lokasi_kamus = Path(lokasi_kamus)
        self.lokasi_log = Path(lokasi_log)
        self.kunci = threading.Lock()
        self.kandidat: list[dict] = []
        if Path(lokasi_kandidat).exists():
            with open(lokasi_kandidat, encoding="utf-8", newline="") as f:
                self.kandidat = list(csv.DictReader(f))
        self.log: list[dict] = []
        if self.lokasi_log.exists():
            with open(self.lokasi_log, encoding="utf-8", newline="") as f:
                pembaca = csv.DictReader(f)
                self.log = list(pembaca)
            if pembaca.fieldnames != KOLOM_LOG:   # log versi lama: tulis ulang dgn kolom terbaru
                self._tulis_ulang_log()
        self.diputuskan = {r["indonesia"] for r in self.log}

    # ------------------------------------------------------------ antrean
    def _menunggu(self, k: dict) -> bool:
        kata = k["indonesia"]
        return kata not in self.diputuskan and kata not in self.kamus and not self.mesin.kenal(kata)

    def antrian(self, n: int = 20, kecuali: set[str] = frozenset()) -> list[dict]:
        keluar = []
        for k in self.kandidat:
            if k["indonesia"] in kecuali or not self._menunggu(k):
                continue
            keluar.append({
                "indonesia": k["indonesia"],
                "usulan": [u for u in k["usulan"].split("|") if u],
                "sepakat": k.get("sepakat", ""),
                "sumber": k.get("sumber", ""),
                "contoh_id": k.get("contoh_id", ""),
                "contoh_bjn": k.get("contoh_bjn", ""),
            })
            if len(keluar) >= n:
                break
        return keluar

    def statistik(self) -> dict:
        hitung = {x: 0 for x in KEPUTUSAN}
        for r in self.log:
            hitung[r["keputusan"]] = hitung.get(r["keputusan"], 0) + 1
        return {
            "total_kandidat": len(self.kandidat),
            "sisa": sum(1 for k in self.kandidat if self._menunggu(k)),
            "ditinjau": len(self.log),
            **hitung,
            "entri_kamus": len(self.kamus),
        }

    # ------------------------------------------------------------ keputusan
    def putuskan(self, indonesia: str, keputusan: str, banjar: str = "", banjar_halus: str = "",
                 banjar_kasar: str = "") -> None:
        indonesia = indonesia.strip().lower()
        if keputusan not in KEPUTUSAN:
            raise ValueError(f"Keputusan tidak dikenal: {keputusan}")
        if keputusan == "sama":
            banjar = indonesia
        banjar, banjar_halus, banjar_kasar = banjar.strip(), banjar_halus.strip(), banjar_kasar.strip()
        if keputusan == "simpan" and not banjar:
            raise ValueError("Terjemahan Banjar wajib diisi.")
        with self.kunci:
            if indonesia in self.diputuskan:
                raise ValueError(f"'{indonesia}' sudah ditinjau.")
            if keputusan in ("simpan", "sama"):
                if indonesia in self.kamus:
                    raise ValueError(f"'{indonesia}' sudah ada di kamus.")
                self._tambah_ke_kamus(indonesia, banjar, banjar_halus, banjar_kasar)
            rekam = {"waktu": datetime.now().isoformat(timespec="seconds"), "indonesia": indonesia,
                     "keputusan": keputusan, "banjar": banjar if keputusan != "buang" else "",
                     "banjar_halus": banjar_halus, "banjar_kasar": banjar_kasar}
            self._tulis_log(rekam)
            self.log.append(rekam)
            self.diputuskan.add(indonesia)

    def batal(self) -> dict | None:
        """Batalkan keputusan terakhir (termasuk menghapus entri kamus yang ditambahkannya)."""
        with self.kunci:
            if not self.log:
                return None
            terakhir = self.log.pop()
            self.diputuskan.discard(terakhir["indonesia"])
            self._tulis_ulang_log()
            if terakhir["keputusan"] in ("simpan", "sama"):
                self._hapus_dari_kamus(terakhir["indonesia"])
            return terakhir

    # ------------------------------------------------------------ berkas
    def _tambah_ke_kamus(self, indonesia: str, banjar: str, halus: str, kasar: str = "") -> None:
        teks = self.lokasi_kamus.read_text(encoding="utf-8")
        with open(self.lokasi_kamus, "a", encoding="utf-8", newline="") as f:
            if teks and not teks.endswith("\n"):
                f.write("\n")
            csv.writer(f, lineterminator="\n").writerow([indonesia, banjar, halus, ""] + ([kasar] if kasar else []))
        varian = [v.strip() for v in banjar.split("|") if v.strip()]
        self.kamus.tambah(Entri(indonesia, varian[0], tuple(varian[1:]), halus, "", kasar))

    def _hapus_dari_kamus(self, indonesia: str) -> None:
        baris = self.lokasi_kamus.read_text(encoding="utf-8").splitlines(keepends=True)
        for i in range(len(baris) - 1, -1, -1):
            if baris[i].split(",", 1)[0].strip().lower() == indonesia:
                del baris[i]
                break
        self.lokasi_kamus.write_text("".join(baris), encoding="utf-8")
        self.kamus.hapus(indonesia)

    def _tulis_log(self, rekam: dict) -> None:
        baru = not self.lokasi_log.exists()
        with open(self.lokasi_log, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM_LOG, lineterminator="\n")
            if baru:
                w.writeheader()
            w.writerow(rekam)

    def _tulis_ulang_log(self) -> None:
        with open(self.lokasi_log, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=KOLOM_LOG, lineterminator="\n")
            w.writeheader()
            w.writerows(self.log)
