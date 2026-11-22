"""Penerjemahan bahasa lain <-> bahasa Indonesia (bahasa perantara) lewat layanan luar.

Penyedia dicoba berurutan sampai ada yang berhasil (atur lewat env PENERJEMAH_PENYEDIA,
default "mymemory,google"):

- mymemory : API publik MyMemory (gratis, tanpa kunci; kuota harian per alamat IP,
             bisa diperbesar dengan env MYMEMORY_EMAIL). Maks 500 byte per permintaan,
             jadi teks dipecah per kalimat.
- google   : endpoint publik Google Translate (tidak resmi, sering menolak klien
             non-peramban). Hanya cadangan.

Bila bahasa sumber sudah Indonesia, tahap ini dilewati sehingga aplikasi tetap luring.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

BATAS_KARAKTER = 4500
WAKTU_TUNGGU = 15  # detik
BATAS_BYTE_POTONGAN = 450

BAHASA = {
    "auto": "Deteksi otomatis",
    "id": "Indonesia",
    "en": "Inggris",
    "ar": "Arab",
    "ms": "Melayu",
    "jw": "Jawa",
    "su": "Sunda",
    "zh-CN": "Mandarin",
    "ja": "Jepang",
    "ko": "Korea",
    "nl": "Belanda",
    "de": "Jerman",
    "fr": "Prancis",
    "es": "Spanyol",
    "ru": "Rusia",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnam",
    "tr": "Turki",
}


class GalatLayananLuar(RuntimeError):
    pass


# ---------------------------------------------------------------- pemecah teks

def potong(teks: str, batas: int = BATAS_BYTE_POTONGAN) -> list[str]:
    """Pecah teks per kalimat menjadi potongan <= batas byte UTF-8 (spasi ikut terbawa)."""
    kalimat = re.findall(r"[^.!?。！？\n]*[.!?。！？\n]+\s*|[^.!?。！？\n]+\s*$", teks) or [teks]
    potongan, kini = [], ""
    for k in kalimat:
        while len(k.encode()) > batas:                  # kalimat tunggal terlalu panjang
            bagian = k.encode()[:batas].decode("utf-8", "ignore")
            sela = bagian.rfind(" ")
            bagian = bagian[: sela + 1] if sela > 0 else bagian
            if kini:
                potongan.append(kini)
                kini = ""
            potongan.append(bagian)
            k = k[len(bagian):]
        if len((kini + k).encode()) > batas:
            potongan.append(kini)
            kini = k
        else:
            kini += k
    if kini:
        potongan.append(kini)
    return [p for p in potongan if p.strip()]


def _ambil_json(req: urllib.request.Request):
    with urllib.request.urlopen(req, timeout=WAKTU_TUNGGU) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- penyedia

KODE_MYMEMORY = {"auto": "Autodetect", "jw": "jv"}


def _mymemory(teks: str, sumber: str, sasaran: str = "id") -> tuple[str, str]:
    kode = KODE_MYMEMORY.get(sumber, sumber)
    kode_ke = KODE_MYMEMORY.get(sasaran, sasaran)
    hasil, terdeteksi = [], None
    for p in potong(teks):
        isi = p.strip()
        param = {"q": isi, "langpair": f"{kode}|{kode_ke}"}
        if os.environ.get("MYMEMORY_EMAIL"):
            param["de"] = os.environ["MYMEMORY_EMAIL"]
        url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(param)
        d = _ambil_json(urllib.request.Request(url, headers={"User-Agent": "PenerjemahBanjar/0.1"}))
        if int(d.get("responseStatus", 0)) != 200:
            raise GalatLayananLuar(f"MyMemory: {d.get('responseDetails') or d.get('responseStatus')}")
        data = d["responseData"]
        terdeteksi = terdeteksi or data.get("detectedLanguage")
        spasi_akhir = p[len(p.rstrip()):]
        hasil.append(data["translatedText"] + spasi_akhir)
    if sumber != "auto":
        terdeteksi = sumber
    return "".join(hasil), (terdeteksi or sumber).split("-")[0].lower()


def _google(teks: str, sumber: str, sasaran: str = "id") -> tuple[str, str]:
    kueri = urllib.parse.urlencode({"client": "gtx", "sl": sumber, "tl": sasaran, "dt": "t"})
    req = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single?" + kueri,
        data=urllib.parse.urlencode({"q": teks}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
    )
    data = _ambil_json(req)
    hasil = "".join(b[0] for b in data[0] if b and b[0])
    terdeteksi = data[2] if len(data) > 2 and isinstance(data[2], str) else sumber
    return hasil, terdeteksi


PENYEDIA = {"mymemory": _mymemory, "google": _google}


def terjemah_luar(teks: str, sumber: str, sasaran: str) -> tuple[str, str]:
    """Kembalikan (teks_terjemahan, kode_bahasa_sumber_terdeteksi)."""
    if sumber not in BAHASA:
        raise ValueError(f"Bahasa sumber tidak didukung: {sumber}")
    if sasaran not in BAHASA or sasaran == "auto":
        raise ValueError(f"Bahasa tujuan tidak didukung: {sasaran}")
    if len(teks) > BATAS_KARAKTER:
        raise ValueError(f"Teks terlalu panjang (maks {BATAS_KARAKTER} karakter).")
    if sumber == sasaran or not teks.strip():
        return teks, sumber

    urutan = os.environ.get("PENERJEMAH_PENYEDIA", "mymemory,google").split(",")
    galat = []
    for nama in (n.strip() for n in urutan):
        if nama not in PENYEDIA:
            continue
        try:
            return PENYEDIA[nama](teks, sumber, sasaran)
        except Exception as exc:
            galat.append(f"{nama}: {exc}")
    raise GalatLayananLuar(
        f"Gagal menerjemahkan {BAHASA.get(sumber, sumber)} -> {BAHASA.get(sasaran, sasaran)} ("
        + "; ".join(galat) + "). Periksa koneksi internet; terjemahan Banjar <-> Indonesia tetap bisa luring."
    )


def ke_indonesia(teks: str, sumber: str = "auto") -> tuple[str, str]:
    """Bahasa apa pun -> Indonesia. Kembalikan (teks_indonesia, kode_terdeteksi)."""
    if sumber == "id" or not teks.strip():
        if len(teks) > BATAS_KARAKTER:
            raise ValueError(f"Teks terlalu panjang (maks {BATAS_KARAKTER} karakter).")
        return teks, "id"
    return terjemah_luar(teks, sumber, "id")


def dari_indonesia(teks: str, sasaran: str) -> str:
    """Indonesia -> bahasa lain."""
    return terjemah_luar(teks, "id", sasaran)[0]
