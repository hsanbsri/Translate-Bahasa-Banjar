// Terjemahan bahasa lain <-> Indonesia (bahasa perantara) lewat API publik MyMemory,
// dipanggil langsung dari browser (MyMemory mengizinkan CORS). Batas 500 byte per
// permintaan, jadi teks dipecah per kalimat. Padanan app/sumber.py.

export const BATAS_KARAKTER = 4500;
const BATAS_BYTE = 450;
const KODE_MYMEMORY = { auto: "Autodetect", jw: "jv" };
const ukuranByte = (s) => new TextEncoder().encode(s).length;

/** Pecah teks per kalimat menjadi potongan <= batas byte (spasi ikut terbawa). */
export function potong(teks, batas = BATAS_BYTE) {
  const kalimat = teks.match(/[^.!?。！？\n]*[.!?。！？\n]+\s*|[^.!?。！？\n]+\s*$/g) || [teks];
  const hasil = [];
  let kini = "";
  for (let k of kalimat) {
    while (ukuranByte(k) > batas) {                 // kalimat tunggal terlalu panjang
      let bagian = "";
      for (const huruf of k) {
        if (ukuranByte(bagian + huruf) > batas) break;
        bagian += huruf;
      }
      const sela = bagian.lastIndexOf(" ");
      if (sela > 0) bagian = bagian.slice(0, sela + 1);
      if (kini) { hasil.push(kini); kini = ""; }
      hasil.push(bagian);
      k = k.slice(bagian.length);
    }
    if (ukuranByte(kini + k) > batas) { hasil.push(kini); kini = k; }
    else kini += k;
  }
  if (kini) hasil.push(kini);
  return hasil.filter((p) => p.trim());
}

/** Kembalikan { hasil, terdeteksi }. Lempar Error berpesan jelas bila gagal. */
export async function terjemahLuar(teks, sumber, sasaran) {
  if (teks.length > BATAS_KARAKTER) throw new Error(`Teks terlalu panjang (maks ${BATAS_KARAKTER} karakter).`);
  if (sumber === sasaran || !teks.trim()) return { hasil: teks, terdeteksi: sumber };
  const dari = KODE_MYMEMORY[sumber] || sumber;
  const ke = KODE_MYMEMORY[sasaran] || sasaran;
  const potongan = [];
  let terdeteksi = null;
  for (const p of potong(teks)) {
    const url = "https://api.mymemory.translated.net/get?" +
      new URLSearchParams({ q: p.trim(), langpair: `${dari}|${ke}` });
    let d;
    try {
      const r = await fetch(url);
      d = await r.json();
    } catch {
      throw new Error("Gagal menghubungi layanan terjemahan. Periksa koneksi internet; " +
        "terjemahan Banjar ↔ Indonesia tetap bisa tanpa internet.");
    }
    if (Number(d.responseStatus) !== 200) {
      throw new Error(`Layanan terjemahan menolak permintaan: ${d.responseDetails || d.responseStatus}. ` +
        "Kuota harian mungkin habis; coba lagi besok. Banjar ↔ Indonesia tetap bisa dipakai.");
    }
    terdeteksi = terdeteksi || d.responseData.detectedLanguage;
    potongan.push(d.responseData.translatedText + p.slice(p.trimEnd().length));
  }
  if (sumber !== "auto") terdeteksi = sumber;
  return { hasil: potongan.join(""), terdeteksi: (terdeteksi || sumber).split("-")[0].toLowerCase() };
}
