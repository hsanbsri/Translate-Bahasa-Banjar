import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def klien(tmp_path, monkeypatch):
    monkeypatch.setenv("PENERJEMAH_DB", str(tmp_path / "uji.db"))
    from app import saran, main
    importlib.reload(saran)
    importlib.reload(main)
    return TestClient(main.app), main


def test_terjemah_indonesia_luring(klien):
    c, _ = klien
    r = c.post("/api/terjemah", json={"teks": "Saya mau tidur", "sumber": "id"})
    assert r.status_code == 200
    assert r.json()["hasil"] == "Aku handak guring"


def test_terjemah_lewat_perantara(klien, monkeypatch):
    c, main = klien
    monkeypatch.setattr(main.sumber, "ke_indonesia", lambda t, s: ("Ibu membeli ikan", "en"))
    d = c.post("/api/terjemah", json={"teks": "Mother buys fish", "sumber": "auto"}).json()
    assert d["sumber_terdeteksi"] == "en"
    assert d["hasil"] == "Uma manukar iwak"


def test_galat_layanan_luar_jadi_502(klien, monkeypatch):
    c, main = klien

    def gagal(t, s):
        raise main.sumber.GalatLayananLuar("putus")

    monkeypatch.setattr(main.sumber, "ke_indonesia", gagal)
    assert c.post("/api/terjemah", json={"teks": "hello", "sumber": "en"}).status_code == 502


def test_kata_tak_dikenal_tercatat_dan_saran_tersimpan(klien):
    c, _ = klien
    c.post("/api/terjemah", json={"teks": "saya punya komputer", "sumber": "id"})
    assert c.get("/api/kata-tak-dikenal").json()[0]["kata"] == "komputer"

    r = c.post("/api/saran", json={"teks_indonesia": "a", "hasil_mesin": "b", "usulan": "c"})
    assert r.status_code == 200
    assert c.get("/api/saran").json()[0]["usulan"] == "c"


def test_potong_teks_menjaga_isi_dan_batas():
    from app.sumber import potong
    teks = "Kalimat pertama. Kalimat kedua!  " + ("kata " * 200) + "Akhir?"
    hasil = potong(teks, batas=100)
    assert "".join(hasil) == teks
    assert all(len(p.encode()) <= 100 for p in hasil)


def test_cari_kamus(klien):
    c, _ = klien
    hasil = c.get("/api/kamus", params={"q": "tulak"}).json()
    assert hasil[0]["indonesia"] in {"pergi", "berangkat"}


def test_banjar_ke_indonesia_luring(klien):
    c, _ = klien
    d = c.post("/api/terjemah", json={"teks": "Uma manukar iwak", "sumber": "bjn", "sasaran": "id"}).json()
    assert d["hasil"] == "Ibu membeli ikan"
    assert d["arah"] == "dari_banjar" and d["segmen_adalah_hasil"]


def test_banjar_ke_inggris_lewat_perantara(klien, monkeypatch):
    c, main = klien
    panggilan = []

    def palsu(teks, sasaran):
        panggilan.append((teks, sasaran))
        return "Mother buys fish"

    monkeypatch.setattr(main.sumber, "dari_indonesia", palsu)
    d = c.post("/api/terjemah", json={"teks": "Uma manukar iwak", "sumber": "bjn", "sasaran": "en"}).json()
    assert panggilan == [("Ibu membeli ikan", "en")]
    assert d["hasil"] == "Mother buys fish" and d["teks_indonesia"] == "Ibu membeli ikan"
    assert not d["segmen_adalah_hasil"]


def test_salah_satu_harus_banjar(klien):
    c, _ = klien
    assert c.post("/api/terjemah", json={"teks": "hi", "sumber": "en", "sasaran": "id"}).status_code == 400
    assert c.post("/api/terjemah", json={"teks": "hi", "sumber": "bjn", "sasaran": "bjn"}).status_code == 400


def test_kata_banjar_tak_dikenal_dicatat_terpisah(klien):
    c, _ = klien
    d = c.post("/api/terjemah", json={"teks": "aku baisi laptop xyzq", "sumber": "bjn", "sasaran": "id"}).json()
    assert d["tak_dikenal"] == ["xyzq"] and d["dianggap_sama"] == ["laptop"]
    dicatat = {x["kata"] for x in c.get("/api/kata-tak-dikenal", params={"bahasa": "bjn"}).json()}
    assert dicatat == {"laptop", "xyzq"}
    assert c.get("/api/kata-tak-dikenal").json() == []


def test_berkas_pwa_tersedia(klien):
    c, _ = klien
    m = c.get("/manifest.webmanifest")
    assert m.status_code == 200 and m.headers["content-type"].startswith("application/manifest+json")
    data = m.json()
    assert data["display"] == "standalone"
    for ikon in data["icons"]:
        assert c.get("/" + ikon["src"]).status_code == 200
    sw = c.get("/sw.js")
    assert sw.status_code == 200 and "javascript" in sw.headers["content-type"]
