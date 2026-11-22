# Penerjemah Banjar

Aplikasi web untuk menerjemahkan teks **dari berbagai bahasa ke bahasa Banjar** dan
**dari bahasa Banjar ke berbagai bahasa**, dengan pilihan ragam **biasa** (aku/ikam),
**halus** (ulun/pian), dan **kasar** (unda/nyawa).

Hak Cipta © 2026 **Hasan**. Seluruh hak dilindungi; lihat [LICENSE](LICENSE).

## Cara kerja

```
Teks (bahasa apa pun)
   │  Tahap 1: terjemah ke bahasa Indonesia (layanan luar, butuh internet)
   ▼          dilewati bila sumber = Indonesia → tetap jalan luring
Teks Indonesia
   │  Tahap 2: mesin Indonesia → Banjar (inti aplikasi ini)
   │    1. frasa terpanjang di kamus      "tidak bisa"  → "kada kawa"
   │    2. kata utuh di kamus             "tidur"       → "guring"
   │    3. kata ulang                     "anak-anak"   → "anak-anak"
   │    4. analisis imbuhan + peluluhan   "membeli"     → "manukar"
   │                                      "bekerja"     → "bagawi"
   │    5. aturan urutan kata             "sangat lelah"→ "litak banar"
   │    6. kata yang belum dikenal dibiarkan, ditandai, dan dicatat
   ▼
Teks Banjar (setiap kata diberi warna sesuai asal terjemahannya)
```

Arah sebaliknya memakai kamus yang sama, dibaca terbalik:

```
Teks Banjar
   │  mesin Banjar → Indonesia: frasa/kata dari indeks balik kamus, imbuhan Banjar
   │  dilepas lalu imbuhan Indonesia dipasang dgn peluluhan ("manukar" → "membeli",
   │  "bagawi" → "bekerja"), "X banar" → "X sekali"; bentuk halus (ulun, pian, sidin) ikut dikenali
   ▼
Teks Indonesia ──(layanan luar, bila tujuan bukan Indonesia)──► Inggris / Arab / Jepang / …
```

Teks Banjar percakapan juga ditangani:

- **ejaan santai** "e" untuk "a" dicoba ke ejaan baku (*semalam → samalam → kemarin*, *bedarahan → badarahan*)
- **partikel** di `data/kamus_bjn_khusus.csv` dihilangkan (*am, ai, pang, neh*)
- **ba-…-an** menjadi ber- (*badarahan → berdarah*), kecuali bentuk ber-…-an memang lazim (*bajualan → berjualan*)
- **kata dasar yang sama dengan Indonesia** (*main, darah*) dikenali lewat `data/kata_id_umum.txt` dan ditandai
  garis putus-putus; kata seperti ini ikut dicatat di `/api/kata-tak-dikenal?bahasa=bjn` untuk diverifikasi

Bila satu bentuk Banjar berasal dari beberapa kata Indonesia (mis. *banar* ← sangat/sekali/benar),
dipilih: kata yang sama persis, lalu entri yang bentuk utamanya cocok, lalu varian, lalu bentuk
halus; sisanya ditampilkan sebagai "bisa juga" saat kursor diarahkan ke kata.

## Dua cara berjalan

| | Web publik (statis) | Server lokal (pengelola) |
|---|---|---|
| Terjemahan | di browser (`static/mesin.js`) | sama, di browser |
| Bahasa lain | browser → MyMemory langsung | sama |
| Banjar ↔ Indonesia tanpa internet | ya (setelah dibuka/dipasang sekali) | ya |
| Tinjau Kamus, usulan, catatan kata tak dikenal | disembunyikan | aktif |
| Hosting | Cloudflare Pages (gratis) | komputer sendiri |

`static/mesin.js` adalah salinan setia mesin Python (`app/`). `tests/test_paritas.py`
menjalankan ±60 ribu kata & kalimat di kedua versi dan mewajibkan hasilnya identik, jadi
setiap perubahan aturan harus dilakukan di keduanya.

## Menjalankan

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn app.main:app --reload
```

Buka http://127.0.0.1:8000

Menjalankan tes: `./venv/bin/python -m pytest -q`

## Hosting gratis di Cloudflare Pages

Cloudflare Pages → *Create* → *Connect to Git* → pilih repo ini, lalu isi:

| Pengaturan | Nilai |
|---|---|
| Framework preset | None |
| Build command | `python3 alat/bangun_web.py` |
| Build output directory | `web` |

Setiap `git push` ke `main` otomatis membangun ulang situs (termasuk kamus terbaru).
Membangun secara lokal: `python3 alat/bangun_web.py` → folder `web/` (hanya butuh Python
standar, tanpa pustaka tambahan). Tautan berbagi didukung, mis.
`/?dari=bjn&ke=en&teks=Ulun+handak+tulak` atau `/?dari=id&ke=bjn&ragam=halus&teks=...`.

Lewat alur **Workers** (Create app → Continue with GitHub), isi:
- Project name: `penerjemah-banjar` (harus sama dengan `name` di `wrangler.jsonc`)
- Build command: `python3 alat/bangun_web.py`
- Deploy command: `npx wrangler deploy`
- Preview command: `npx wrangler versions upload`

## Pasang di HP (PWA, tanpa Play Store)

Aplikasi ini adalah *Progressive Web App*: buka di Chrome Android → menu ⋮ → **Instal aplikasi**
(atau tombol **Pasang aplikasi** di pojok kanan atas). Ikon muncul di layar utama dan aplikasi
terbuka layar penuh.

Syarat browser: halaman harus dibuka lewat **HTTPS** (atau `localhost`). Jadi agar bisa dipasang
dari HP, server perlu di-hosting dengan alamat HTTPS. Berkas terkait: `static/manifest.webmanifest`,
`static/sw.js` (service worker, jaringan-dulu; `/api/` tidak pernah di-cache), `static/ikon/`
(dibuat ulang dengan `python3 alat/buat_ikon.py`).

## Struktur

| Berkas | Isi |
|---|---|
| `data/kamus_id_bjn.csv` | Kamus Indonesia–Banjar (bisa diedit di Excel/LibreOffice) |
| `data/kamus_bjn_khusus.csv` | Khusus arah Banjar → Indonesia: partikel (am, ai, pang…), bentuk percakapan |
| `data/kata_id_umum.txt` | ±35 ribu kata Indonesia lazim; kata dasar Banjar yang tak ada di kamus tapi ada di sini dianggap sama |
| `app/kamus.py` | Pemuat & pencari kamus |
| `app/morfologi.py` | Analisis & pembentukan imbuhan, dua arah (Indonesia ↔ Banjar) |
| `app/mesin.py` | Mesin terjemah: `Mesin` (Indonesia → Banjar) & `MesinBalik` (Banjar → Indonesia) |
| `static/mesin.js` | Mesin yang sama dalam JavaScript (dipakai antarmuka) |
| `static/sumber.js` | Bahasa lain ↔ Indonesia dari browser (MyMemory) |
| `app/data_web.py` | Ekspor kamus ke JSON (`/data/*.json`) |
| `alat/bangun_web.py` | Bangun versi statis ke `web/` |
| `app/sumber.py` | Bahasa lain ↔ Indonesia lewat layanan luar (MyMemory, cadangan Google) |
| `app/saran.py` | Penyimpanan usulan perbaikan & kata yang belum dikenal (SQLite) |
| `app/tinjau.py` | Antrean Tinjau Kamus |
| `alat/` | Pembuat kandidat kamus (NusaX, NLLB) |
| `app/main.py` | Server API (FastAPI) |
| `static/` | Antarmuka web (HTML/CSS/JS tanpa framework, tanpa pustaka luar) |
| `tests/` | Pengujian otomatis |

## API

| Metode | Alamat | Fungsi |
|---|---|---|
| POST | `/api/terjemah` | `{teks, sumber, sasaran, ragam}` → hasil + rincian per kata; salah satu dari `sumber`/`sasaran` harus `bjn` |
| GET | `/api/kamus?q=` | Cari kamus |
| POST | `/api/saran` | Kirim usulan perbaikan |
| GET | `/api/saran` | Lihat usulan |
| GET | `/api/kata-tak-dikenal?bahasa=id\|bjn` | Kata yang paling sering belum dikenal (masukan Indonesia / Banjar) |
| GET/POST | `/api/tinjau/...` | Antrean, keputusan, dan pembatalan Tinjau Kamus |
| GET | `/api/info` | Versi, jumlah entri kamus, daftar bahasa |

API yang sama nanti dipakai oleh aplikasi Android.

## Menambah kamus

1. Buka `data/kamus_id_bjn.csv`.
2. Tambah baris `indonesia,banjar,banjar_halus,catatan,banjar_kasar`. Varian dipisah `|` (mis. `wan|lawan`);
   kolom halus/kasar boleh kosong (memakai bentuk biasa).
3. Cukup isi **kata dasar**; bentuk berimbuhan (me-, ber-, di-, ter-, ke-, se-, -kan, -an, -i, -nya)
   dibentuk otomatis.
4. Hapus tulisan `perlu cek` di kolom catatan setelah entri diverifikasi.
5. Mulai ulang server.

Lihat `/api/kata-tak-dikenal` untuk mengetahui kata apa yang paling dibutuhkan.

## Tinjau Kamus (memperluas kamus dengan cepat)

Tab **Tinjau Kamus** menampilkan kandidat padanan satu per satu, diurutkan dari kata yang
paling sering dipakai. Pengguna cukup memeriksa: kata yang disetujui langsung masuk ke
`data/kamus_id_bjn.csv`, dan setiap keputusan dicatat di `data/tinjauan.csv`.
Bentuk turunan (mis. *tempatnya*) otomatis hilang dari antrean setelah kata dasarnya
(*tempat*) disimpan.

| Tombol | Fungsi |
|---|---|
| `1`–`5` | pilih usulan |
| `Enter` | simpan isian |
| `S` | sama dengan bahasa Indonesia |
| `L` | lewati (muncul lagi di sesi berikutnya) |
| `B` | buang (nama, singkatan, salah ketik) |
| `Z` | batalkan keputusan terakhir |
| `E` / `Esc` | masuk / keluar kolom isian |

### Membuat ulang kandidat

Kandidat disiapkan sekali dengan alat di folder `alat/` (lingkungan `venv-alat` terpisah,
berisi PyTorch CPU, transformers, sentencepiece, PySastrawi):

```bash
# 1. sejajarkan kata pada korpus paralel NusaX (±10 detik)
./venv/bin/python -I alat/kandidat_nusax.py sumber_data/nusax sumber_data/kandidat_nusax.csv
# 2. usulan NLLB untuk ±2.500 kata dasar tersering (CPU, beberapa menit)
./venv-alat/bin/python alat/kandidat_nllb.py --jumlah 2500 --tambahan sumber_data/kandidat_nusax.csv
# 3. gabungkan menjadi antrean tinjauan
./venv/bin/python -I alat/gabung_kandidat.py sumber_data/kandidat_nusax.csv \
    sumber_data/kandidat_nllb.csv sumber_data/frekuensi/id_50k.txt data/kandidat.csv
```

Kandidat hanyalah draf: setiap entri kamus diputuskan oleh peninjau manusia.

## Sumber data & lisensi

| Sumber | Dipakai untuk | Lisensi |
|---|---|---|
| NusaX-MT (Winata dkk., 2022, arXiv:2205.15960) | korpus paralel Indonesia–Banjar untuk menarik kandidat kata | CC-BY-SA 4.0 |
| FrequencyWords, hermitdave (OpenSubtitles 2018) | urutan prioritas kata Indonesia; `data/kata_id_umum.txt` | CC-BY-SA 4.0 |
| PySastrawi | pemotongan imbuhan & daftar kata dasar Indonesia (hanya di `alat/`; kamus kata dasarnya dari Kateglo, CC-BY-NC-SA 3.0, **tidak** disertakan dalam aplikasi) | MIT |
| NLLB-200 distilled 600M (Meta) | draf usulan padanan; **tidak** disertakan dalam aplikasi | CC-BY-NC 4.0 |
| MyMemory API | tahap 1, bahasa lain → Indonesia | layanan pihak ketiga |

## Konfigurasi (variabel lingkungan)

| Nama | Default | Arti |
|---|---|---|
| `PENERJEMAH_PENYEDIA` | `mymemory,google` | Urutan penyedia tahap 1 |
| `MYMEMORY_EMAIL` | (kosong) | Email Anda sendiri untuk menaikkan kuota harian MyMemory |
| `PENERJEMAH_DB` | `data/saran.db` | Lokasi basis data usulan |

## Batasan yang diketahui

- Kualitas sangat bergantung pada kelengkapan kamus; kamus awal baru ±150 entri.
- Tahap 1 bergantung pada layanan luar (kuota harian MyMemory ±5.000 karakter per IP tanpa email).
- Kata yang bermakna ganda (mis. Indonesia "lagi", Banjar "pulang" = lagi/kembali) belum dibedakan menurut konteks.
- Arah Banjar → Indonesia kehilangan informasi ragam (ulun → saya, aku → aku).
- Acuan dialek: Banjar Kuala.

## Rencana

- [ ] Perluas kamus (target awal 1.000–2.000 kata dasar) dan verifikasi entri `perlu cek`
- [ ] Pilihan dialek Banjar Hulu
- [x] Arah sebaliknya: Banjar → Indonesia / bahasa lain
- [x] Bisa dipasang di Android sebagai PWA (tanpa Play Store)
- [x] Versi statis untuk hosting gratis (Cloudflare Pages)
- [ ] Mode luring penuh untuk tahap 1 (model terjemah lokal)

## Hak cipta

Hak Cipta © 2026 Hasan. Seluruh hak dilindungi.
Kode sumber, tampilan, ikon, dan kamus Indonesia–Banjar adalah ciptaan Hasan.
Penggunaan ulang, perubahan, atau penggunaan komersial memerlukan izin tertulis;
komponen pihak ketiga tetap mengikuti lisensinya masing-masing (lihat [LICENSE](LICENSE)).
