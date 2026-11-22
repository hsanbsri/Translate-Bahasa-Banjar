"""Buat ikon aplikasi (PWA) bertema "Sungai": latar teal, pita gigi haruan kuning, tulisan "Bj".

Pemakaian (butuh Pillow):  python3 alat/buat_ikon.py
Keluaran: static/ikon/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AKAR = Path(__file__).resolve().parent.parent
KELUAR = AKAR / "static" / "ikon"
TEAL, KUNING, PUTIH = "#0e7480", "#e0a526", "#ffffff"
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
SKALA = 4  # gambar besar lalu diperkecil agar tepi halus


def gambar(ukuran: int, maskable: bool) -> Image.Image:
    n = ukuran * SKALA
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if maskable:
        d.rectangle([0, 0, n, n], fill=TEAL)          # Android memotong sendiri bentuknya
        isi = 0.72                                     # isi di dalam zona aman
    else:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=int(n * 0.22), fill=TEAL)
        isi = 1.0

    # pita gigi haruan: segitiga kuning menghadap ke bawah di tepi atas
    lebar_gigi = n * 0.125 * isi
    tinggi_gigi = n * 0.085 * isi
    atas = n * 0.06 if maskable else 0.0  # maskable: Android memotong tepi, pita sedikit diturunkan
    if not maskable:
        # potong ke bentuk kotak membulat
        topeng = Image.new("L", (n, n), 0)
        ImageDraw.Draw(topeng).rounded_rectangle([0, 0, n - 1, n - 1], radius=int(n * 0.22), fill=255)
    pita = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    dp = ImageDraw.Draw(pita)
    tebal = n * 0.035 * isi
    dp.rectangle([0, 0, n, atas + tebal], fill=KUNING)
    x = -lebar_gigi / 2
    while x < n:
        dp.polygon([(x, atas + tebal), (x + lebar_gigi, atas + tebal),
                    (x + lebar_gigi / 2, atas + tebal + tinggi_gigi)], fill=KUNING)
        x += lebar_gigi
    if not maskable:
        pita.putalpha(Image.composite(pita.getchannel("A"), Image.new("L", (n, n), 0), topeng))
    img = Image.alpha_composite(img, pita)

    # tulisan "Bj"
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(n * 0.46 * isi))
    teks = "Bj"
    kotak = d.textbbox((0, 0), teks, font=font)
    w, h = kotak[2] - kotak[0], kotak[3] - kotak[1]
    pusat_y = n * 0.56
    d.text(((n - w) / 2 - kotak[0], pusat_y - h / 2 - kotak[1]), teks, font=font, fill=PUTIH)

    return img.resize((ukuran, ukuran), Image.LANCZOS)


def main() -> None:
    KELUAR.mkdir(parents=True, exist_ok=True)
    for ukuran, nama, maskable in [
        (192, "ikon-192.png", False),
        (512, "ikon-512.png", False),
        (512, "ikon-maskable-512.png", True),
        (180, "apple-touch-icon.png", True),   # iOS: kotak penuh, sudut dibulatkan sistem
        (32, "favicon-32.png", False),
    ]:
        gambar(ukuran, maskable).save(KELUAR / nama, optimize=True)
        print("->", KELUAR / nama)


if __name__ == "__main__":
    main()
