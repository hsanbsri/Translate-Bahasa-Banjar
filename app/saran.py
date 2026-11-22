"""Penyimpanan usulan perbaikan dari pengguna dan catatan kata yang belum ada di kamus.

Keduanya menjadi bahan untuk memperluas kamus secara bertahap.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

LOKASI_DB = Path(os.environ.get(
    "PENERJEMAH_DB", Path(__file__).resolve().parent.parent / "data" / "saran.db"
))


class Penyimpan:
    def __init__(self, lokasi: Path | str = LOKASI_DB):
        self.lokasi = str(lokasi)
        with self._sambung() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS saran (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT NOT NULL,
                    teks_indonesia TEXT NOT NULL,
                    hasil_mesin TEXT NOT NULL,
                    usulan TEXT NOT NULL,
                    catatan TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS kata_tak_dikenal (
                    kata TEXT PRIMARY KEY,
                    jumlah INTEGER NOT NULL DEFAULT 0,
                    terakhir TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kata_tak_dikenal_bjn (
                    kata TEXT PRIMARY KEY,
                    jumlah INTEGER NOT NULL DEFAULT 0,
                    terakhir TEXT NOT NULL
                );
                """
            )
            # migrasi: kolom arah & teks_asal (ditambahkan versi 0.2) untuk usulan dua arah
            kolom = {r[1] for r in db.execute("PRAGMA table_info(saran)")}
            if "arah" not in kolom:
                db.execute("ALTER TABLE saran ADD COLUMN arah TEXT DEFAULT 'ke_banjar'")
            if "teks_asal" not in kolom:
                db.execute("ALTER TABLE saran ADD COLUMN teks_asal TEXT DEFAULT ''")

    def _sambung(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.lokasi)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _sekarang() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def simpan_saran(self, teks_indonesia: str, hasil_mesin: str, usulan: str, catatan: str = "",
                     arah: str = "ke_banjar", teks_asal: str = "") -> int:
        with self._sambung() as db:
            cur = db.execute(
                "INSERT INTO saran (waktu, teks_indonesia, hasil_mesin, usulan, catatan, arah, teks_asal)"
                " VALUES (?,?,?,?,?,?,?)",
                (self._sekarang(), teks_indonesia, hasil_mesin, usulan, catatan, arah, teks_asal),
            )
            return cur.lastrowid

    def daftar_saran(self, batas: int = 100) -> list[dict]:
        with self._sambung() as db:
            rows = db.execute("SELECT * FROM saran ORDER BY id DESC LIMIT ?", (batas,)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _tabel(bahasa: str) -> str:
        return "kata_tak_dikenal_bjn" if bahasa == "bjn" else "kata_tak_dikenal"

    def catat_tak_dikenal(self, kata_kata: list[str], bahasa: str = "id") -> None:
        """Catat kata yang belum ada di kamus; bahasa = "id" (masukan Indonesia) atau "bjn"."""
        if not kata_kata:
            return
        waktu = self._sekarang()
        with self._sambung() as db:
            db.executemany(
                f"""INSERT INTO {self._tabel(bahasa)} (kata, jumlah, terakhir) VALUES (?, 1, ?)
                   ON CONFLICT(kata) DO UPDATE SET jumlah = jumlah + 1, terakhir = excluded.terakhir""",
                [(k.lower(), waktu) for k in kata_kata],
            )

    def daftar_tak_dikenal(self, batas: int = 200, bahasa: str = "id") -> list[dict]:
        with self._sambung() as db:
            rows = db.execute(
                f"SELECT kata, jumlah, terakhir FROM {self._tabel(bahasa)} ORDER BY jumlah DESC, kata LIMIT ?",
                (batas,),
            ).fetchall()
        return [dict(r) for r in rows]
