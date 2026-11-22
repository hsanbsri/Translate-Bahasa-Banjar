"""Pemuat dan pencari kamus Indonesia -> Banjar (berkas CSV)."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from pathlib import Path

LOKASI_BAKU = Path(__file__).resolve().parent.parent / "data" / "kamus_id_bjn.csv"


def lokasi_kamus() -> Path:
    """Lokasi kamus kerja; bisa diganti lewat env PENERJEMAH_KAMUS (dipakai tes)."""
    return Path(os.environ.get("PENERJEMAH_KAMUS") or LOKASI_BAKU)


@dataclass(frozen=True)
class Entri:
    indonesia: str
    banjar: str                      # varian utama
    varian: tuple[str, ...] = ()     # varian lain (alternatif)
    banjar_halus: str = ""
    catatan: str = ""
    banjar_kasar: str = ""

    def bentuk(self, ragam: str = "biasa") -> str:
        """Bentuk sesuai ragam (biasa/halus/kasar); bila kosong, kembali ke bentuk biasa."""
        if ragam == "halus" and self.banjar_halus:
            return self.banjar_halus
        if ragam == "kasar" and self.banjar_kasar:
            return self.banjar_kasar
        return self.banjar

    @property
    def perlu_cek(self) -> bool:
        return "perlu cek" in self.catatan.lower()


@dataclass
class Kamus:
    entri: dict[str, Entri] = field(default_factory=dict)
    panjang_frasa_maks: int = 1
    # indeks balik: bentuk Banjar -> [(prioritas, urutan, kata Indonesia)]
    balik: dict[str, list[tuple[int, int, str]]] = field(default_factory=dict)
    panjang_frasa_balik_maks: int = 1
    _urutan: int = 0

    @classmethod
    def muat(cls, lokasi: Path | str | None = None) -> "Kamus":
        lokasi = lokasi or lokasi_kamus()
        kamus = cls()
        with open(lokasi, encoding="utf-8", newline="") as f:
            baris = (b for b in f if b.strip() and not b.lstrip().startswith("#"))
            for rek in csv.DictReader(baris):
                kunci = (rek.get("indonesia") or "").strip().lower()
                mentah = (rek.get("banjar") or "").strip()
                if not kunci or not mentah:
                    continue
                varian = [v.strip() for v in mentah.split("|") if v.strip()]
                kamus.tambah(Entri(
                    indonesia=kunci,
                    banjar=varian[0],
                    varian=tuple(varian[1:]),
                    banjar_halus=(rek.get("banjar_halus") or "").strip(),
                    catatan=(rek.get("catatan") or "").strip(),
                    banjar_kasar=(rek.get("banjar_kasar") or "").strip(),
                ))
        return kamus

    def tambah(self, e: Entri) -> None:
        if e.indonesia in self.entri:
            self.hapus(e.indonesia)
        self.entri[e.indonesia] = e
        self.panjang_frasa_maks = max(self.panjang_frasa_maks, len(e.indonesia.split()))
        # bentuk utama paling dipercaya, lalu varian, lalu bentuk halus, lalu kasar
        self._urutan += 1
        bentuk = ([(0, e.banjar)] + [(1, v) for v in e.varian]
                  + ([(2, e.banjar_halus)] if e.banjar_halus else [])
                  + ([(3, e.banjar_kasar)] if e.banjar_kasar else []))
        for prioritas, b in bentuk:
            b = b.lower()
            daftar = self.balik.setdefault(b, [])
            if all(x[2] != e.indonesia for x in daftar):
                daftar.append((prioritas, self._urutan, e.indonesia))
            self.panjang_frasa_balik_maks = max(self.panjang_frasa_balik_maks, len(b.split()))

    def hapus(self, indonesia: str) -> None:
        if self.entri.pop(indonesia, None) is None:
            return
        for b in list(self.balik):
            sisa = [x for x in self.balik[b] if x[2] != indonesia]
            if sisa:
                self.balik[b] = sisa
            else:
                del self.balik[b]

    def cari(self, kata: str) -> Entri | None:
        return self.entri.get(kata.lower())

    def cari_balik(self, bentuk: str) -> list[str]:
        """Kata Indonesia untuk sebuah bentuk Banjar, paling cocok lebih dulu.

        Urutan: kata Indonesia yang sama persis (mis. "rumah"), lalu entri yang bentuk
        utamanya cocok, lalu varian, lalu bentuk halus, lalu kasar; seri diputus urutan di berkas.
        """
        b = bentuk.lower()
        daftar = self.balik.get(b, [])
        return [x[2] for x in sorted(daftar, key=lambda x: (x[2] != b, x[0], x[1]))]

    def ada_balik(self, bentuk: str) -> bool:
        return bentuk.lower() in self.balik

    def __contains__(self, kata: str) -> bool:
        return kata.lower() in self.entri

    def __len__(self) -> int:
        return len(self.entri)

    def telusur(self, q: str, batas: int = 50) -> list[Entri]:
        """Cari entri yang memuat q di kolom Indonesia atau Banjar."""
        q = q.strip().lower()
        if not q:
            return sorted(self.entri.values(), key=lambda e: e.indonesia)[:batas]
        persis, awalan, memuat = [], [], []
        for e in self.entri.values():
            ladang = [e.indonesia, e.banjar.lower(), e.banjar_halus.lower(), e.banjar_kasar.lower(),
                      *(v.lower() for v in e.varian)]
            if q in ladang:
                persis.append(e)
            elif any(x.startswith(q) for x in ladang):
                awalan.append(e)
            elif any(q in x for x in ladang):
                memuat.append(e)
        hasil = persis + sorted(awalan, key=lambda e: e.indonesia) + sorted(memuat, key=lambda e: e.indonesia)
        return hasil[:batas]
