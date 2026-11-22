"""Mesin terjemah berbasis kamus dan aturan imbuhan, dua arah.

- Mesin       : Indonesia -> Banjar
- MesinBalik  : Banjar -> Indonesia (memakai kamus yang sama, dibaca terbalik)

Urutan pencocokan untuk tiap posisi dalam kalimat:
1. frasa terpanjang di kamus (mis. "tidak bisa" <-> "kada kawa")
2. kata utuh di kamus
3. kata ulang ber-tanda-hubung (tiap bagian diterjemahkan)
4. analisis imbuhan (membeli <-> manukar)
5. bila semua gagal: kata dibiarkan dan ditandai "tak_dikenal"
lalu aturan urutan kata ("sangat lelah" <-> "litak banar").
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import morfologi
from .kamus import Kamus

HURUF = r"A-Za-zÀ-ÖØ-öø-ÿ"
POLA_TOKEN = re.compile(rf"[{HURUF}]+(?:-[{HURUF}]+)*|\s+|[^\s{HURUF}]+")
POLA_KATA = re.compile(rf"[{HURUF}]")

# Penguat yang dalam bahasa Indonesia di depan kata sifat, tetapi di belakang dalam Banjar.
PENGUAT_DEPAN = {"sangat"}

DATA = Path(__file__).resolve().parent.parent / "data"
LOKASI_KHUSUS = DATA / "kamus_bjn_khusus.csv"
LOKASI_KATA_ID = DATA / "kata_id_umum.txt"


def muat_khusus(lokasi: Path) -> dict[str, tuple[str, str]]:
    """Kamus khusus Banjar -> Indonesia: {banjar: (indonesia, catatan)}; indonesia kosong = partikel."""
    if not Path(lokasi).exists():
        return {}
    with open(lokasi, encoding="utf-8", newline="") as f:
        baris = (b for b in f if b.strip() and not b.lstrip().startswith("#"))
        return {
            r["banjar"].strip().lower(): ((r.get("indonesia") or "").strip(), (r.get("catatan") or "").strip())
            for r in csv.DictReader(baris) if (r.get("banjar") or "").strip()
        }


def muat_kata(lokasi: Path) -> set[str]:
    if not Path(lokasi).exists():
        return set()
    return {b.strip() for b in Path(lokasi).read_text(encoding="utf-8").splitlines()
            if b.strip() and not b.startswith("#")}


def ejaan_baku_banjar(kata: str) -> str:
    """Ejaan santai -> baku. Bahasa Banjar hanya punya vokal a, i, u; tulisan santai sering
    memakai "e" untuk "a" (semalam -> samalam, bemainan -> bamainan, bedarahan -> badarahan)."""
    return kata.lower().replace("e", "a")


@dataclass
class Segmen:
    asal: str
    hasil: str
    jenis: str            # frasa | kata | imbuhan | ulang | tak_dikenal | lain
    keterangan: str = ""

    def ke_dict(self) -> dict:
        return asdict(self)


def ikuti_huruf_besar(asal: str, hasil: str) -> str:
    if len(asal) > 1 and asal.isupper():
        return hasil.upper()
    if asal[:1].isupper():
        return hasil[:1].upper() + hasil[1:]
    return hasil


def _keterangan(entri) -> str:
    bagian = []
    if entri.varian:
        bagian.append("varian: " + ", ".join(entri.varian))
    if entri.catatan:
        bagian.append(entri.catatan)
    return "; ".join(bagian)


def _spasi(s: Segmen) -> bool:
    return s.jenis == "lain" and s.hasil.isspace()


class Mesin:
    """Indonesia -> Banjar."""

    def __init__(self, kamus: Kamus):
        self.kamus = kamus

    def kenal(self, kata: str) -> bool:
        """True bila kata sudah bisa diterjemahkan (langsung, kata ulang, atau lewat imbuhan)."""
        return self._kata(kata, "biasa").jenis != "tak_dikenal"

    # ---------------------------------------------- bagian khusus arah (ditimpa MesinBalik)
    def _cari(self, teks: str, ragam: str) -> tuple[str, str] | None:
        e = self.kamus.cari(teks)
        return (e.bentuk(ragam), _keterangan(e)) if e else None

    def _panjang_frasa(self) -> int:
        return self.kamus.panjang_frasa_maks

    def _imbuhan(self, kata: str, ragam: str) -> tuple[str, str] | None:
        a = morfologi.analisis(kata, lambda d: d in self.kamus)
        if not a:
            return None
        dasar_bjn = self.kamus.cari(a.dasar).bentuk(ragam)
        if " " in dasar_bjn:
            return None
        return morfologi.bentuk_banjar(a, dasar_bjn), "+".join(x for x in (a.awalan, a.dasar, *a.akhiran) if x)

    def _pasca(self, segmen: list[Segmen]) -> list[Segmen]:
        """Penguat diletakkan di belakang kata sifat: "sangat lelah" -> "litak banar"."""
        i = 0
        while i + 2 < len(segmen):
            a, sela, b = segmen[i], segmen[i + 1], segmen[i + 2]
            if (a.asal.lower() in PENGUAT_DEPAN and a.jenis == "kata" and _spasi(sela)
                    and b.jenis not in ("lain", "tak_dikenal")):
                huruf_awal = a.asal[:1].isupper()
                kata_b = b.hasil[:1].upper() + b.hasil[1:] if huruf_awal else b.hasil
                kata_a = a.hasil if a.asal.isupper() else a.hasil.lower()
                segmen[i:i + 3] = [
                    Segmen(b.asal, kata_b, b.jenis, b.keterangan),
                    sela,
                    Segmen(a.asal, kata_a, a.jenis, "dipindah ke belakang (urutan Banjar)"),
                ]
                i += 3
            else:
                i += 1
        return segmen

    # ---------------------------------------------- bagian bersama
    def _kata(self, kata: str, ragam: str) -> Segmen:
        cocok = self._cari(kata, ragam)
        if cocok:
            return Segmen(kata, ikuti_huruf_besar(kata, cocok[0]), "kata", cocok[1])

        if "-" in kata:
            bagian = [self._kata(b, ragam) for b in kata.split("-")]
            if all(b.jenis != "tak_dikenal" for b in bagian):
                return Segmen(kata, "-".join(b.hasil for b in bagian), "ulang")

        imb = self._imbuhan(kata, ragam)
        if imb:
            return Segmen(kata, ikuti_huruf_besar(kata, imb[0]), "imbuhan", imb[1])

        return Segmen(kata, kata, "tak_dikenal")

    def terjemah(self, teks: str, ragam: str = "biasa") -> list[Segmen]:
        token = POLA_TOKEN.findall(teks)
        segmen: list[Segmen] = []
        i = 0
        while i < len(token):
            t = token[i]
            if not POLA_KATA.search(t):
                segmen.append(Segmen(t, t, "lain"))
                i += 1
                continue

            cocok = self._cocok_frasa(token, i, ragam)
            if cocok:
                seg, i = cocok
                segmen.append(seg)
                continue

            segmen.append(self._kata(t, ragam))
            i += 1
        return self._pasca(segmen)

    def _cocok_frasa(self, token: list[str], i: int, ragam: str):
        """Coba cocokkan frasa terpanjang mulai token ke-i (dipisah spasi saja)."""
        kata_idx = [i]
        j = i + 1
        while len(kata_idx) < self._panjang_frasa() and j + 1 < len(token):
            if not token[j].isspace() or not POLA_KATA.search(token[j + 1]):
                break
            kata_idx.append(j + 1)
            j += 2
        for n in range(len(kata_idx), 1, -1):
            idx = kata_idx[:n]
            frasa = " ".join(token[k].lower() for k in idx)
            cocok = self._cari(frasa, ragam)
            if cocok:
                asal = "".join(token[i: idx[-1] + 1])
                return Segmen(asal, ikuti_huruf_besar(token[i], cocok[0]), "frasa", cocok[1]), idx[-1] + 1
        return None


class MesinBalik(Mesin):
    """Banjar -> Indonesia. Ragam diabaikan (bentuk biasa & halus sama-sama dikenali).

    Urutan pengenalan kata:
    1. kamus khusus Banjar (partikel, bentuk percakapan) lalu kamus utama dibaca terbalik,
       dengan ejaan asli lalu ejaan baku (e -> a)
    2. kata ulang
    3. kata Indonesia yang lazim (mis. "tabrakan") dianggap sama
    4. imbuhan: kata dasar dari kamus; bila tak ada, kata dasar Indonesia lazim dianggap sama
    """

    def __init__(self, kamus: Kamus, lokasi_khusus: Path = LOKASI_KHUSUS, lokasi_kata_id: Path = LOKASI_KATA_ID):
        super().__init__(kamus)
        self.khusus = muat_khusus(lokasi_khusus)
        self.kata_id = muat_kata(lokasi_kata_id)

    def _cari(self, teks: str, ragam: str) -> tuple[str, str] | None:
        t = teks.lower()
        if t in self.khusus:
            indo, catatan = self.khusus[t]
            return indo, catatan or ("partikel, dihilangkan" if not indo else "kamus khusus Banjar")
        calon = self.kamus.cari_balik(t)
        if not calon:
            return None
        ket = ("bisa juga: " + ", ".join(calon[1:4])) if len(calon) > 1 else ""
        return calon[0], ket

    def _panjang_frasa(self) -> int:
        khusus = max((len(k.split()) for k in self.khusus), default=1)
        return max(self.kamus.panjang_frasa_balik_maks, khusus)

    def _dasar_indonesia(self, dasar: str) -> str | None:
        if dasar in self.khusus and self.khusus[dasar][0]:
            return self.khusus[dasar][0]
        calon = self.kamus.cari_balik(dasar)
        return calon[0] if calon else None

    def _imbuhan_balik(self, kata: str, pakai_kata_id: bool) -> tuple[str, str] | None:
        def ada(d: str) -> bool:
            return self._dasar_indonesia(d) is not None or (pakai_kata_id and d in self.kata_id)

        a = morfologi.analisis_banjar(kata, ada)
        if not a:
            return None
        if a.awalan == "ber" and not a.akhiran and a.dasar.endswith("an") and ada(a.dasar[:-2]):
            # utamakan konfiks ba-…-an: bamainan = ba+main+an, bukan ba+mainan
            a = morfologi.Analisis("ber", a.dasar[:-2], ("an",))
        dasar_id = self._dasar_indonesia(a.dasar) or a.dasar
        if " " in dasar_id:
            return None
        ket = [f"{a.awalan or ''}+{a.dasar}+{'+'.join(a.akhiran)}".strip("+")]
        if a.awalan == "ber" and a.akhiran[:1] == ("an",):
            # ba-…-an Banjar: pertahankan ber-…-an bila lazim di Indonesia (bajualan -> berjualan),
            # selain itu jadi ber- saja (badarahan -> berdarah, bamainan -> bermain)
            if morfologi.bentuk_indonesia(a, dasar_id) not in self.kata_id:
                a = morfologi.Analisis(a.awalan, a.dasar, a.akhiran[1:])
                ket.append("ba-…-an → ber-")
        if self._dasar_indonesia(a.dasar) is None:
            ket.append(f"kata dasar '{a.dasar}' dianggap sama dengan Indonesia")
        return morfologi.bentuk_indonesia(a, dasar_id), "; ".join(ket)

    def _kata(self, kata: str, ragam: str) -> Segmen:
        kecil = kata.lower()
        bentuk = [kecil]
        if "-" not in kecil and ejaan_baku_banjar(kecil) != kecil:
            bentuk.append(ejaan_baku_banjar(kecil))

        for b in bentuk:
            cocok = self._cari(b, ragam)
            if cocok:
                ket = "; ".join(x for x in (cocok[1], f"ejaan baku: {b}" if b != kecil else "") if x)
                return Segmen(kata, ikuti_huruf_besar(kata, cocok[0]), "kata", ket)

        if "-" in kata:
            bagian = [self._kata(b, ragam) for b in kata.split("-")]
            if all(b.jenis != "tak_dikenal" for b in bagian):
                return Segmen(kata, "-".join(b.hasil for b in bagian), "ulang")

        # imbuhan dgn kata dasar dari kamus Banjar didahulukan (ditukar -> dibeli, bukan "ditukar")
        for b in reversed(bentuk):              # ejaan baku dulu: imbuhan Banjar ber-vokal a
            imb = self._imbuhan_balik(b, pakai_kata_id=False)
            if imb:
                return Segmen(kata, ikuti_huruf_besar(kata, imb[0]), "imbuhan", imb[1])

        if kecil in self.kata_id:
            return Segmen(kata, kata, "sama", "dianggap sama dengan bahasa Indonesia")

        for b in reversed(bentuk):
            imb = self._imbuhan_balik(b, pakai_kata_id=True)
            if imb:
                return Segmen(kata, ikuti_huruf_besar(kata, imb[0]), "imbuhan", imb[1])

        return Segmen(kata, kata, "tak_dikenal")

    def _pasca(self, segmen: list[Segmen]) -> list[Segmen]:
        # "banar" setelah kata = "sekali" (litak banar -> lelah sekali); berdiri sendiri = "benar"
        for i, s in enumerate(segmen):
            if s.asal.lower() != "banar" or s.jenis != "kata":
                continue
            setelah_kata = i >= 2 and _spasi(segmen[i - 1]) and segmen[i - 2].jenis != "lain"
            s.hasil = ikuti_huruf_besar(s.asal, "sekali" if setelah_kata else "benar")
            s.keterangan = "penguat setelah kata" if setelah_kata else ""

        # Partikel (hasil kosong) dibuang. Di tengah kalimat: spasi sebelumnya ikut dibuang
        # ("berdarah am." -> "berdarah."). Di awal kalimat: koma/spasi sesudahnya dibuang dan
        # huruf besar dipindah ke kata berikutnya ("Am, ulun ..." -> "Saya ...").
        keluar: list[Segmen] = []
        buang_sesudah = besar_berikut = False
        for s in segmen:
            if s.jenis == "kata" and s.hasil == "":
                # di tengah kalimat = didahului spasi yang didahului kata (bukan ". ")
                di_tengah = len(keluar) >= 2 and _spasi(keluar[-1]) and keluar[-2].jenis != "lain"
                if di_tengah:
                    keluar.pop()
                else:
                    buang_sesudah = True
                    besar_berikut = besar_berikut or s.asal[:1].isupper()
                keluar.append(Segmen(s.asal, "", "partikel", s.keterangan))
                continue
            if buang_sesudah and s.jenis == "lain" and re.fullmatch(r"[\s,]*", s.hasil):
                continue
            buang_sesudah = False
            if besar_berikut and s.jenis != "lain":
                s.hasil = s.hasil[:1].upper() + s.hasil[1:]
                besar_berikut = False
            keluar.append(s)
        return keluar


def gabung(segmen: list[Segmen]) -> str:
    return "".join(s.hasil for s in segmen)
