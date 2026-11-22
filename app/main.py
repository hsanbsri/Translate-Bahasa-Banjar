"""Server web: API terjemah + halaman antarmuka.

Jalankan:  ./venv/bin/uvicorn app.main:app --reload
Buka:      http://127.0.0.1:8000
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import VERSI, data_web, sumber
from .kamus import Kamus, lokasi_kamus
from .mesin import Mesin, MesinBalik, gabung
from .saran import Penyimpan
from .tinjau import Tinjauan

AKAR = Path(__file__).resolve().parent.parent

# PWA: manifest harus dikirim dengan tipe yang benar agar aplikasi bisa dipasang
mimetypes.add_type("application/manifest+json", ".webmanifest")

kamus = Kamus.muat()
mesin = Mesin(kamus)
mesin_balik = MesinBalik(kamus)
penyimpan = Penyimpan()
tinjauan = Tinjauan(kamus, mesin, lokasi_kamus())

app = FastAPI(title="Penerjemah Banjar", version=VERSI)


class PermintaanTerjemah(BaseModel):
    teks: str = Field(..., max_length=sumber.BATAS_KARAKTER)
    sumber: str = "auto"       # kode bahasa, "auto", atau "bjn"
    sasaran: str = "bjn"       # "bjn" atau kode bahasa
    ragam: Literal["biasa", "halus", "kasar"] = "biasa"


class PermintaanSaran(BaseModel):
    teks_indonesia: str = Field(..., min_length=1, max_length=sumber.BATAS_KARAKTER)
    hasil_mesin: str = Field(..., max_length=sumber.BATAS_KARAKTER)
    usulan: str = Field(..., min_length=1, max_length=sumber.BATAS_KARAKTER)
    catatan: str = Field("", max_length=1000)
    arah: Literal["ke_banjar", "dari_banjar"] = "ke_banjar"
    teks_asal: str = Field("", max_length=sumber.BATAS_KARAKTER)


@app.get("/api/info")
def info():
    return {"versi": app.version, "jumlah_entri_kamus": len(kamus), "bahasa": sumber.BAHASA,
            "banjar": BANJAR}


BANJAR = "bjn"


@app.post("/api/terjemah")
def terjemah(p: PermintaanTerjemah):
    if (p.sumber == BANJAR) == (p.sasaran == BANJAR):
        raise HTTPException(400, "Salah satu bahasa (asal atau tujuan) harus Banjar.")
    try:
        if p.sasaran == BANJAR:
            # bahasa apa pun -> Indonesia -> Banjar
            teks_id, terdeteksi = sumber.ke_indonesia(p.teks, p.sumber)
            segmen = mesin.terjemah(teks_id, p.ragam)
            hasil = gabung(segmen)
            tak_dikenal = sorted({s.asal.lower() for s in segmen if s.jenis == "tak_dikenal"})
            dianggap_sama = []
            penyimpan.catat_tak_dikenal(tak_dikenal)
        else:
            # Banjar -> Indonesia -> bahasa tujuan
            if len(p.teks) > sumber.BATAS_KARAKTER:
                raise ValueError(f"Teks terlalu panjang (maks {sumber.BATAS_KARAKTER} karakter).")
            terdeteksi = BANJAR
            segmen = mesin_balik.terjemah(p.teks)
            teks_id = gabung(segmen)
            hasil = sumber.dari_indonesia(teks_id, p.sasaran) if p.sasaran != "id" else teks_id
            tak_dikenal = sorted({s.asal.lower() for s in segmen if s.jenis == "tak_dikenal"})
            dianggap_sama = sorted({s.asal.lower() for s in segmen if s.jenis == "sama"})
            # kata yang "dianggap sama" juga dicatat: asumsi itu perlu diverifikasi penutur
            penyimpan.catat_tak_dikenal(tak_dikenal + dianggap_sama, bahasa=BANJAR)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except sumber.GalatLayananLuar as e:
        raise HTTPException(502, str(e))

    return {
        "arah": "ke_banjar" if p.sasaran == BANJAR else "dari_banjar",
        "sumber": p.sumber,
        "sasaran": p.sasaran,
        "sumber_terdeteksi": terdeteksi,
        "teks_indonesia": teks_id,
        "hasil": hasil,
        # segmen = keluaran mesin aturan (Banjar bila ke_banjar, Indonesia bila dari_banjar)
        "segmen": [s.ke_dict() for s in segmen],
        "segmen_adalah_hasil": p.sasaran in (BANJAR, "id"),
        "tak_dikenal": tak_dikenal,
        "dianggap_sama": dianggap_sama,
    }


@app.get("/api/kamus")
def cari_kamus(q: str = "", batas: int = 50):
    return [
        {
            "indonesia": e.indonesia,
            "banjar": e.banjar,
            "varian": list(e.varian),
            "banjar_halus": e.banjar_halus,
            "banjar_kasar": e.banjar_kasar,
            "catatan": e.catatan,
        }
        for e in kamus.telusur(q, min(batas, 500))
    ]


@app.post("/api/saran")
def kirim_saran(p: PermintaanSaran):
    sid = penyimpan.simpan_saran(p.teks_indonesia, p.hasil_mesin, p.usulan, p.catatan, p.arah, p.teks_asal)
    return {"id": sid, "pesan": "Terima kasih, usulan tersimpan."}


@app.get("/api/saran")
def lihat_saran():
    return penyimpan.daftar_saran()


@app.get("/api/kata-tak-dikenal")
def lihat_tak_dikenal(bahasa: Literal["id", "bjn"] = "id"):
    return penyimpan.daftar_tak_dikenal(bahasa=bahasa)


# ------------------------------------------------------------------ tinjau kamus
class PermintaanTinjau(BaseModel):
    indonesia: str = Field(..., min_length=1, max_length=100)
    keputusan: Literal["simpan", "sama", "buang"]
    banjar: str = Field("", max_length=200)
    banjar_halus: str = Field("", max_length=200)
    banjar_kasar: str = Field("", max_length=200)


@app.get("/api/tinjau/antrian")
def antrian_tinjau(n: int = 20, kecuali: str = ""):
    lewati = {k for k in kecuali.split(",") if k}
    return {"item": tinjauan.antrian(min(n, 100), lewati), "statistik": tinjauan.statistik()}


@app.post("/api/tinjau")
def putuskan_tinjau(p: PermintaanTinjau):
    try:
        tinjauan.putuskan(p.indonesia, p.keputusan, p.banjar, p.banjar_halus, p.banjar_kasar)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"statistik": tinjauan.statistik()}


@app.post("/api/tinjau/batal")
def batal_tinjau():
    terakhir = tinjauan.batal()
    if terakhir is None:
        raise HTTPException(400, "Tidak ada keputusan untuk dibatalkan.")
    return {"dibatalkan": terakhir, "statistik": tinjauan.statistik()}


# ------------------------------------------------------------------ data untuk mesin JavaScript
# Alamat yang sama dipakai versi statis (alat/bangun_web.py menulis berkas dengan nama ini),
# sehingga antarmuka tidak perlu tahu apakah ia berjalan di server ini atau di hosting statis.
@app.get("/data/info.json")
def data_info():
    return {"mode": "server", "versi": app.version, "bahasa": sumber.BAHASA}


@app.get("/data/kamus.json")
def data_kamus():
    return data_web.baris_kamus(kamus)


@app.get("/data/khusus.json")
def data_khusus():
    return data_web.khusus(mesin_balik)


@app.get("/data/kata_id_umum.json")
def data_kata_id():
    return data_web.kata_id(mesin_balik)


class LaporanTakDikenal(BaseModel):
    kata: list[str] = Field(..., max_length=500)
    bahasa: Literal["id", "bjn"] = "id"


@app.post("/api/kata-tak-dikenal")
def lapor_tak_dikenal(p: LaporanTakDikenal):
    penyimpan.catat_tak_dikenal([k[:100] for k in p.kata if k.strip()], bahasa=p.bahasa)
    return {"dicatat": len(p.kata)}


app.mount("/", StaticFiles(directory=AKAR / "static", html=True), name="static")
