import pytest

from app import morfologi
from app.kamus import Kamus
from app.mesin import Mesin, gabung


@pytest.fixture(scope="module")
def mesin():
    return Mesin(Kamus.muat())


def tr(mesin, teks, ragam="biasa"):
    return gabung(mesin.terjemah(teks, ragam))


@pytest.mark.parametrize("asal, harap", [
    ("saya mau pergi ke pasar", "aku handak tulak ka pasar"),
    ("Ibu membeli ikan.", "Uma manukar iwak."),
    ("tidak ada uang", "kadada duit"),
    ("Saya tidak bisa tidur", "Aku kada kawa guring"),
    ("Ayah bekerja di sungai", "Abah bagawi di sungai"),
    ("ikan itu dibeli kemarin", "iwak itu ditukar samalam"),
    ("anak-anak senang sekali", "anak-anak himung banar"),
    ("SAYA LELAH", "AKU LITAK"),
    ("rumahnya besar", "rumahnya ganal"),
    ("kemana kamu?", "kamana ikam?"),
    ("Saya sangat lelah", "Aku litak banar"),
    ("Sangat cantik!", "Bungas banar!"),
    ("lelah sekali", "litak banar"),
])
def test_kalimat(mesin, asal, harap):
    assert tr(mesin, asal) == harap


def test_ragam_halus(mesin):
    assert tr(mesin, "saya mau pergi, kamu mau ikut?", "halus").startswith("ulun handak tulak, pian handak")


def test_kata_tak_dikenal_dibiarkan_dan_ditandai(mesin):
    seg = mesin.terjemah("saya punya komputer")
    assert gabung(seg) == "aku baisi komputer"
    assert [s.asal for s in seg if s.jenis == "tak_dikenal"] == ["komputer"]


def test_frasa_tidak_lintas_tanda_baca(mesin):
    # "tidak, ada" bukan frasa "tidak ada"
    assert tr(mesin, "tidak, ada") == "kada, ada"


@pytest.mark.parametrize("dasar, harap", [
    ("tukar", "manukar"), ("bawa", "mambawa"), ("pukul", "mamukul"),
    ("cari", "mancari"), ("sapu", "manyapu"), ("kaji", "mangaji"),
    ("ambil", "mangambil"), ("lihat", "malihat"),
])
def test_nasal_banjar(dasar, harap):
    assert morfologi.nasal_banjar(dasar) == harap


@pytest.mark.parametrize("kata, awalan, dasar, akhiran", [
    ("membeli", "meN", "beli", ()),
    ("memakan", "meN", "makan", ()),
    ("menyapu", "meN", "sapu", ()),
    ("mengambil", "meN", "ambil", ()),
    ("bekerja", "ber", "kerja", ()),
    ("belikannya", "", "beli", ("kan", "nya")),
])
def test_analisis_imbuhan(kata, awalan, dasar, akhiran):
    kamus = {"beli", "makan", "pakan", "sapu", "ambil", "kerja"}
    a = morfologi.analisis(kata, lambda d: d in kamus)
    assert a is not None
    assert (a.awalan, a.dasar, a.akhiran) == (awalan, dasar, akhiran)


# ================================================================ Banjar -> Indonesia
from app.mesin import MesinBalik  # noqa: E402


@pytest.fixture(scope="module")
def balik():
    from pathlib import Path
    return MesinBalik(Kamus.muat(), lokasi_khusus=Path(__file__).parent / "kamus_bjn_khusus_uji.csv")


@pytest.mark.parametrize("asal, harap", [
    ("aku handak tulak ka pasar", "aku mau pergi ke pasar"),
    ("Ulun kada kawa guring", "Saya tidak bisa tidur"),
    ("Uma manukar iwak.", "Ibu membeli ikan."),
    ("Abah bagawi di sungai", "Ayah bekerja di sungai"),
    ("aku litak banar", "aku lelah sekali"),
    ("iwak itu ditukar samalam", "ikan itu dibeli kemarin"),
    ("kadada duit", "tidak ada uang"),
    ("Pian handak ka mana?", "Anda mau ke mana?"),
    ("inya bukah ka rumah", "dia lari ke rumah"),
    ("mambawa iwak", "membawa ikan"),
    ("mancari duit", "mencari uang"),
    ("tukarakan", "belikan"),
    ("banar kah?", "benar kah?"),
])
def test_balik_kalimat(balik, asal, harap):
    assert gabung(balik.terjemah(asal)) == harap


def test_balik_bentuk_halus_dikenali(balik):
    assert gabung(balik.terjemah("sidin")) == "beliau"
    assert gabung(balik.terjemah("inggih")) == "ya"


@pytest.mark.parametrize("dasar, harap", [
    ("beli", "membeli"), ("pukul", "memukul"), ("tulis", "menulis"), ("cari", "mencari"),
    ("sapu", "menyapu"), ("kirim", "mengirim"), ("ambil", "mengambil"), ("lihat", "melihat"),
])
def test_nasal_indonesia(dasar, harap):
    assert morfologi.nasal_indonesia(dasar) == harap


def test_bolak_balik_kalimat_umum(mesin, balik):
    # "saya" sengaja tidak dipakai: saya -> aku (ragam biasa) -> aku, informasi ragam hilang
    for kalimat in ["aku mau pergi ke pasar", "ibu membeli ikan", "ayah bekerja di sungai",
                    "aku tidak bisa tidur", "tidak ada uang", "aku lelah sekali"]:
        assert gabung(balik.terjemah(gabung(mesin.terjemah(kalimat)))).lower() == kalimat


# ---------------------------------------------------------------- Banjar percakapan
@pytest.mark.parametrize("asal, harap", [
    # ejaan santai (e untuk a), ba-…-an, partikel
    ("ulun semalam bemainan di jalan", "saya kemarin bermain di jalan"),
    ("ada urang tabrakan neh bedarahan am", "ada orang tabrakan berdarah"),
    ("abah bajualan iwak", "ayah berjualan ikan"),          # ber-…-an lazim: -an dipertahankan
    ("Am, ulun litak banar pang.", "Saya lelah sekali."),    # partikel di awal & akhir
    ("Inya garing. Ai, kayapa ikam?", "Dia sakit. Bagaimana kamu?"),
    ("nyaman pang, tagal larang.", "nyaman, tetapi mahal."),
])
def test_balik_percakapan(balik, asal, harap):
    assert gabung(balik.terjemah(asal)) == harap


# ---------------------------------------------------------------- ragam kasar
def test_ragam_kasar(mesin):
    assert tr(mesin, "saya mau pergi, kamu mau ke mana?", "kasar") == "unda handak tulak, nyawa handak ka mana?"
    # kata tanpa bentuk kasar memakai bentuk biasa
    assert tr(mesin, "dia lelah", "kasar") == "inya litak"


def test_balik_ragam_kasar(balik):
    assert gabung(balik.terjemah("Unda handak tulak, nyawa handak ka mana?")) == "Saya mau pergi, kamu mau ke mana?"
