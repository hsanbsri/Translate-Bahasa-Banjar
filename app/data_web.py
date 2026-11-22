"""Ekspor data kamus ke JSON untuk mesin JavaScript (static/mesin.js).

Dipakai oleh server lokal (rute /data/*.json, selalu mencerminkan kamus terkini termasuk
hasil Tinjau Kamus) dan oleh alat/bangun_web.py (berkas statis untuk hosting).
"""

from __future__ import annotations

from .kamus import Kamus
from .mesin import MesinBalik


def baris_kamus(kamus: Kamus) -> list[list[str]]:
    """[indonesia, banjar("a|b"), halus, catatan, kasar] dalam urutan entri.

    Urutan penting: mesin JS memutar ulang penambahan entri dalam urutan ini sehingga
    prioritas indeks balik sama persis dengan versi Python.
    """
    return [
        [e.indonesia, "|".join((e.banjar, *e.varian)), e.banjar_halus, e.catatan, e.banjar_kasar]
        for e in kamus.entri.values()
    ]


def khusus(balik: MesinBalik) -> dict[str, list[str]]:
    return {k: [indo, catatan] for k, (indo, catatan) in balik.khusus.items()}


def kata_id(balik: MesinBalik) -> list[str]:
    return sorted(balik.kata_id)
