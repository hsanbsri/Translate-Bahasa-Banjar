import csv
import shutil

import pytest

from app.kamus import Kamus
from tests.conftest import KAMUS_UJI
from app.mesin import Mesin, gabung
from app.tinjau import Tinjauan


@pytest.fixture()
def t(tmp_path):
    kamus_csv = tmp_path / "kamus.csv"
    shutil.copy(KAMUS_UJI, kamus_csv)
    kandidat = tmp_path / "kandidat.csv"
    with open(kandidat, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["indonesia", "usulan", "sepakat", "sumber", "prioritas", "contoh_id", "contoh_bjn"])
        w.writerow(["tempat", "wadah|tampat", "wadah", "nusax+nllb", "100", "", ""])
        w.writerow(["tempatnya", "wadahnya", "", "nusax", "90", "", ""])
        w.writerow(["menu", "menu", "", "nusax", "80", "", ""])
        w.writerow(["bni", "bni", "", "nusax", "70", "", ""])
        w.writerow(["tidak", "kada", "kada", "nusax", "60", "", ""])  # sudah di kamus
    kamus = Kamus.muat(kamus_csv)
    return Tinjauan(kamus, Mesin(kamus), kamus_csv, kandidat, tmp_path / "log.csv")


def kata_antrean(t):
    return [x["indonesia"] for x in t.antrian(10)]


def test_antrean_lewati_yang_sudah_di_kamus(t):
    assert kata_antrean(t) == ["tempat", "tempatnya", "menu", "bni"]


def test_simpan_menambah_kamus_dan_menghapus_turunan_dari_antrean(t):
    t.putuskan("tempat", "simpan", "wadah")
    assert gabung(t.mesin.terjemah("tempatnya")) == "wadahnya"
    assert kata_antrean(t) == ["menu", "bni"]
    # tersimpan di berkas: kamus yang dimuat ulang mengenalnya
    assert Kamus.muat(t.lokasi_kamus).cari("tempat").banjar == "wadah"


def test_sama_dan_buang(t):
    t.putuskan("menu", "sama")
    t.putuskan("bni", "buang")
    assert t.kamus.cari("menu").banjar == "menu"
    assert "bni" not in t.kamus
    s = t.statistik()
    assert (s["sama"], s["buang"], s["ditinjau"]) == (1, 1, 2)


def test_batal_mengembalikan_keadaan(t):
    isi_awal = t.lokasi_kamus.read_text(encoding="utf-8")
    t.putuskan("tempat", "simpan", "wadah", "wadah")
    assert t.batal()["indonesia"] == "tempat"
    assert "tempat" not in t.kamus
    assert t.lokasi_kamus.read_text(encoding="utf-8") == isi_awal
    assert kata_antrean(t)[0] == "tempat"


def test_log_bertahan_setelah_dimuat_ulang(t):
    t.putuskan("bni", "buang")
    t2 = Tinjauan(t.kamus, t.mesin, t.lokasi_kamus,
                  t.lokasi_log.parent / "kandidat.csv", t.lokasi_log)
    assert "bni" not in kata_antrean(t2)


def test_validasi(t):
    with pytest.raises(ValueError):
        t.putuskan("tempat", "simpan", "")
    t.putuskan("tempat", "simpan", "wadah")
    with pytest.raises(ValueError):
        t.putuskan("tempat", "simpan", "wadah")


def test_simpan_bentuk_kasar(t):
    t.putuskan("tempat", "simpan", "wadah", "", "wadah kasar")
    assert t.kamus.cari("tempat").bentuk("kasar") == "wadah kasar"
    assert Kamus.muat(t.lokasi_kamus).cari("tempat").banjar_kasar == "wadah kasar"


def test_log_versi_lama_dimigrasi(t):
    t.lokasi_log.write_text("waktu,indonesia,keputusan,banjar,banjar_halus\n2026-01-01,bni,buang,,\n", encoding="utf-8")
    t2 = Tinjauan(t.kamus, t.mesin, t.lokasi_kamus, t.lokasi_log.parent / "kandidat.csv", t.lokasi_log)
    assert t.lokasi_log.read_text(encoding="utf-8").splitlines()[0].endswith("banjar_kasar")
    assert "bni" not in kata_antrean(t2)
