"""Analisis imbuhan bahasa Indonesia dan pembentukan ulang dalam bahasa Banjar.

Dipakai hanya bila sebuah kata tidak ditemukan utuh di kamus. Kata dipecah menjadi
awalan + kata dasar + akhiran; kata dasar diterjemahkan lewat kamus, lalu imbuhan
padanan Banjar dipasang kembali, misalnya:

    membeli -> meN- + beli  -> maN- + tukar   -> manukar
    bekerja -> ber- + kerja -> ba-  + gawi    -> bagawi
    dibawakan -> di- + bawa + -kan -> di- + bawa + -akan -> dibawaakan
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

VOKAL = set("aiueo")

# Akhiran luar (partikel/posesif) dan akhiran dalam (pembentuk kata), dengan padanan Banjar.
AKHIRAN_LUAR = {"lah": "lah", "kah": "kah", "pun": "pun", "nya": "nya", "ku": "ku", "mu": "mu"}
AKHIRAN_DALAM = {"kan": "akan", "an": "an", "i": "i"}

PANJANG_DASAR_MIN = 3


@dataclass(frozen=True)
class Analisis:
    awalan: str            # "", "ber", "meN", "di", "ter", "ke", "se"
    dasar: str             # kata dasar Indonesia
    akhiran: tuple[str, ...]  # urut dari dalam ke luar, mis. ("kan", "nya")

    @property
    def jumlah_imbuhan(self) -> int:
        return (1 if self.awalan else 0) + len(self.akhiran)


# ---------------------------------------------------------------- pelepasan imbuhan

def _lepas_akhiran(kata: str) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Hasilkan (sisa, akhiran) untuk 0, 1, atau 2 akhiran."""
    yield kata, ()
    luar_opsi = [("", kata)] + [(a, kata[: -len(a)]) for a in AKHIRAN_LUAR if kata.endswith(a)]
    for luar, sisa in luar_opsi:
        if luar and len(sisa) >= PANJANG_DASAR_MIN:
            yield sisa, (luar,)
        for dalam in AKHIRAN_DALAM:
            if sisa.endswith(dalam) and len(sisa) - len(dalam) >= PANJANG_DASAR_MIN:
                inti = sisa[: -len(dalam)]
                yield inti, (dalam, luar) if luar else (dalam,)


def _kandidat_meN(sisa: str) -> list[str]:
    """Kembalikan kemungkinan kata dasar dari bentuk meN- (tanpa 'me' di depan)."""
    if sisa.startswith("ng"):
        r = sisa[2:]
        return [r, "k" + r] if r[:1] in VOKAL else [r]      # mengikat -> ikat, mengirim -> kirim
    if sisa.startswith("ny"):
        r = sisa[2:]
        return ["s" + r] if r[:1] in VOKAL else []
    if sisa.startswith("m"):
        r = sisa[1:]
        if r[:1] in VOKAL:
            return ["m" + r, "p" + r]      # memakan -> makan, memukul -> pukul
        return [r] if r[:1] in ("b", "f", "v") else ["m" + r] if r[:1] else []
    if sisa.startswith("n"):
        r = sisa[1:]
        if r[:1] in VOKAL:
            return ["n" + r, "t" + r]      # menanti -> nanti, menulis -> tulis
        return [r] if r[:1] in ("d", "c", "j", "t") else ["n" + r] if r[:1] else []
    return [sisa] if sisa[:1] in ("l", "r", "w", "y") else []


def _lepas_awalan(kata: str) -> Iterator[tuple[str, str]]:
    """Hasilkan (awalan, kandidat_dasar)."""
    yield "", kata
    if kata.startswith("me"):
        for d in _kandidat_meN(kata[2:]):
            yield "meN", d
    if kata.startswith("ber"):
        yield "ber", kata[3:]
    if kata.startswith("bel"):
        yield "ber", kata[3:]               # belajar -> ajar
    if kata.startswith("be"):
        yield "ber", kata[2:]               # bekerja -> kerja
    for aw in ("di", "ter", "ke", "se"):
        if kata.startswith(aw):
            yield aw, kata[len(aw):]


def analisis(kata: str, ada: Callable[[str], bool]) -> Analisis | None:
    """Cari pemecahan imbuhan terbaik yang kata dasarnya ada di kamus.

    Prioritas: imbuhan paling sedikit, lalu kata dasar paling panjang. Bila masih seri
    (mis. memakan: makan/pakan), dipilih kata dasar yang sama dengan bentuk permukaannya.
    """
    kata = kata.lower()
    terbaik: Analisis | None = None
    for sisa, akhiran in _lepas_akhiran(kata):
        for awalan, dasar in _lepas_awalan(sisa):
            if not awalan and not akhiran:
                continue
            if len(dasar) < PANJANG_DASAR_MIN or not ada(dasar):
                continue
            calon = Analisis(awalan, dasar, akhiran)
            if terbaik is None or (calon.jumlah_imbuhan, -len(calon.dasar)) < (
                terbaik.jumlah_imbuhan, -len(terbaik.dasar)
            ):
                terbaik = calon
    return terbaik


# ---------------------------------------------------------------- pembentukan Banjar

def nasal_banjar(dasar: str) -> str:
    """Pasang awalan maN- Banjar dengan peluluhan bunyi."""
    h = dasar[:1]
    if h == "p":
        return "mam" + dasar[1:]
    if h == "b":
        return "mam" + dasar
    if h == "t":
        return "man" + dasar[1:]
    if h in ("d", "c", "j"):
        return "man" + dasar
    if h == "s":
        return "many" + dasar[1:]
    if h == "k":
        return "mang" + dasar[1:]
    if h in ("g", "h") or h in VOKAL:
        return "mang" + dasar
    return "ma" + dasar


AWALAN_BANJAR: dict[str, Callable[[str], str]] = {
    "": lambda d: d,
    "meN": nasal_banjar,
    "ber": lambda d: "ba" + d,
    "di": lambda d: "di" + d,
    "ter": lambda d: "ta" + d,
    "ke": lambda d: "ka" + d,
    "se": lambda d: "sa" + d,
}


def bentuk_banjar(a: Analisis, dasar_banjar: str) -> str:
    kata = AWALAN_BANJAR[a.awalan](dasar_banjar.lower())
    for ak in a.akhiran:
        kata += AKHIRAN_DALAM.get(ak) or AKHIRAN_LUAR[ak]
    return kata


# ================================================================ arah Banjar -> Indonesia

AKHIRAN_LUAR_BJN = {"lah": "lah", "kah": "kah", "pun": "pun", "nya": "nya", "ku": "ku", "mu": "mu"}
AKHIRAN_DALAM_BJN = {"akan": "kan", "an": "an", "i": "i"}   # "akan" dicek sebelum "an"


def _lepas_akhiran_bjn(kata: str) -> Iterator[tuple[str, tuple[str, ...]]]:
    yield kata, ()
    luar_opsi = [("", kata)] + [(a, kata[: -len(a)]) for a in AKHIRAN_LUAR_BJN if kata.endswith(a)]
    for luar, sisa in luar_opsi:
        if luar and len(sisa) >= PANJANG_DASAR_MIN:
            yield sisa, (luar,)
        for dalam in AKHIRAN_DALAM_BJN:
            if sisa.endswith(dalam) and len(sisa) - len(dalam) >= PANJANG_DASAR_MIN:
                inti = sisa[: -len(dalam)]
                yield inti, (dalam, luar) if luar else (dalam,)


def _kandidat_maN(sisa: str) -> list[str]:
    """Kemungkinan kata dasar Banjar dari bentuk maN- (tanpa 'ma' di depan)."""
    if sisa.startswith("ng"):
        r = sisa[2:]
        return [r, "k" + r] if r[:1] in VOKAL else [r] if r[:1] in ("g", "h") else []
    if sisa.startswith("ny"):
        r = sisa[2:]
        return ["s" + r] if r[:1] in VOKAL else []
    if sisa.startswith("m"):
        r = sisa[1:]
        if r[:1] in VOKAL:
            return ["m" + r, "p" + r]       # mamukul -> pukul
        return [r] if r[:1] in ("b", "f", "v") else []
    if sisa.startswith("n"):
        r = sisa[1:]
        if r[:1] in VOKAL:
            return ["n" + r, "t" + r]       # manukar -> tukar
        return [r] if r[:1] in ("d", "c", "j") else []
    return [sisa] if sisa[:1] in ("l", "r", "w", "y") else []


def _lepas_awalan_bjn(kata: str) -> Iterator[tuple[str, str]]:
    yield "", kata
    if kata.startswith("ma"):
        for d in _kandidat_maN(kata[2:]):
            yield "meN", d
    if kata.startswith("ba"):
        yield "ber", kata[2:]
    for aw_bjn, aw_id in (("di", "di"), ("ta", "ter"), ("ka", "ke"), ("sa", "se")):
        if kata.startswith(aw_bjn):
            yield aw_id, kata[len(aw_bjn):]


def analisis_banjar(kata: str, ada: Callable[[str], bool]) -> Analisis | None:
    """Pecah kata Banjar berimbuhan; awalan & akhiran dikembalikan dalam label Indonesia."""
    kata = kata.lower()
    terbaik: Analisis | None = None
    for sisa, akhiran in _lepas_akhiran_bjn(kata):
        for awalan, dasar in _lepas_awalan_bjn(sisa):
            if not awalan and not akhiran:
                continue
            if len(dasar) < PANJANG_DASAR_MIN or not ada(dasar):
                continue
            calon = Analisis(awalan, dasar, tuple(AKHIRAN_DALAM_BJN.get(a) or AKHIRAN_LUAR_BJN[a] for a in akhiran))
            if terbaik is None or (calon.jumlah_imbuhan, -len(calon.dasar)) < (
                terbaik.jumlah_imbuhan, -len(terbaik.dasar)
            ):
                terbaik = calon
    return terbaik


def nasal_indonesia(dasar: str) -> str:
    """Pasang awalan meN- bahasa Indonesia dengan peluluhan bunyi."""
    h = dasar[:1]
    if h == "p":
        return "mem" + dasar[1:]
    if h in ("b", "f", "v"):
        return "mem" + dasar
    if h == "t":
        return "men" + dasar[1:]
    if h in ("d", "c", "j", "z"):
        return "men" + dasar
    if h == "s":
        return "meny" + dasar[1:]
    if h == "k":
        return "meng" + dasar[1:]
    if h in ("g", "h") or h in VOKAL:
        return "meng" + dasar
    return "me" + dasar


BER_KHUSUS = {"ajar": "belajar", "kerja": "bekerja", "ternak": "beternak"}


def ber_indonesia(dasar: str) -> str:
    if dasar in BER_KHUSUS:
        return BER_KHUSUS[dasar]
    return ("be" if dasar.startswith("r") else "ber") + dasar


AWALAN_INDONESIA: dict[str, Callable[[str], str]] = {
    "": lambda d: d,
    "meN": nasal_indonesia,
    "ber": ber_indonesia,
    "di": lambda d: "di" + d,
    "ter": lambda d: "ter" + d,
    "ke": lambda d: "ke" + d,
    "se": lambda d: "se" + d,
}


def bentuk_indonesia(a: Analisis, dasar_id: str) -> str:
    kata = AWALAN_INDONESIA[a.awalan](dasar_id.lower())
    for ak in a.akhiran:
        kata += ak
    return kata
