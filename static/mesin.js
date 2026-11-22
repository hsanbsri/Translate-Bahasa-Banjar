// Mesin terjemah Indonesia <-> Banjar untuk browser (dan Node, untuk uji kesamaan).
//
// Salinan setia dari app/kamus.py, app/morfologi.py, dan app/mesin.py. Versi Python tetap
// menjadi acuan: tests/test_paritas.py menjalankan ribuan kalimat di kedua versi dan
// mewajibkan hasilnya identik. Bila mengubah aturan di sini, ubah juga versi Python-nya.

// ================================================================ kamus

export class Kamus {
  constructor() {
    this.entri = new Map();          // indonesia -> entri
    this.balik = new Map();          // bentuk Banjar -> [[prioritas, urutan, indonesia]]
    this.panjangFrasaMaks = 1;
    this.panjangFrasaBalikMaks = 1;
    this._urutan = 0;
  }

  /** baris: [indonesia, banjar ("a|b"), halus, catatan, kasar] dalam urutan kamus. */
  static dariBaris(baris) {
    const k = new Kamus();
    for (const [indonesia, banjar, halus = "", catatan = "", kasar = ""] of baris) {
      const varian = banjar.split("|").map((v) => v.trim()).filter(Boolean);
      k.tambah({
        indonesia, banjar: varian[0], varian: varian.slice(1),
        banjarHalus: halus, catatan, banjarKasar: kasar,
      });
    }
    return k;
  }

  tambah(e) {
    if (this.entri.has(e.indonesia)) this.hapus(e.indonesia);
    this.entri.set(e.indonesia, e);
    this.panjangFrasaMaks = Math.max(this.panjangFrasaMaks, jumlahKata(e.indonesia));
    this._urutan += 1;
    const bentuk = [[0, e.banjar], ...e.varian.map((v) => [1, v])];
    if (e.banjarHalus) bentuk.push([2, e.banjarHalus]);
    if (e.banjarKasar) bentuk.push([3, e.banjarKasar]);
    for (const [prioritas, b0] of bentuk) {
      const b = b0.toLowerCase();
      if (!this.balik.has(b)) this.balik.set(b, []);
      const daftar = this.balik.get(b);
      if (daftar.every((x) => x[2] !== e.indonesia)) daftar.push([prioritas, this._urutan, e.indonesia]);
      this.panjangFrasaBalikMaks = Math.max(this.panjangFrasaBalikMaks, jumlahKata(b));
    }
  }

  hapus(indonesia) {
    if (!this.entri.delete(indonesia)) return;
    for (const [b, daftar] of [...this.balik]) {
      const sisa = daftar.filter((x) => x[2] !== indonesia);
      if (sisa.length) this.balik.set(b, sisa);
      else this.balik.delete(b);
    }
  }

  cari(kata) { return this.entri.get(kata.toLowerCase()) || null; }
  ada(kata) { return this.entri.has(kata.toLowerCase()); }
  get ukuran() { return this.entri.size; }

  cariBalik(bentuk) {
    const b = bentuk.toLowerCase();
    const daftar = [...(this.balik.get(b) || [])];
    daftar.sort((x, y) => (Number(x[2] !== b) - Number(y[2] !== b)) || (x[0] - y[0]) || (x[1] - y[1]));
    return daftar.map((x) => x[2]);
  }

  adaBalik(bentuk) { return this.balik.has(bentuk.toLowerCase()); }

  /** Cari entri yang memuat q di kolom Indonesia atau Banjar (untuk tab Kamus). */
  telusur(q, batas = 50) {
    q = q.trim().toLowerCase();
    const semua = [...this.entri.values()];
    const urutId = (a, b) => (a.indonesia < b.indonesia ? -1 : a.indonesia > b.indonesia ? 1 : 0);
    if (!q) return semua.sort(urutId).slice(0, batas);
    const persis = [], awalan = [], memuat = [];
    for (const e of semua) {
      const ladang = [e.indonesia, e.banjar.toLowerCase(), e.banjarHalus.toLowerCase(),
        e.banjarKasar.toLowerCase(), ...e.varian.map((v) => v.toLowerCase())];
      if (ladang.includes(q)) persis.push(e);
      else if (ladang.some((x) => x.startsWith(q))) awalan.push(e);
      else if (ladang.some((x) => x.includes(q))) memuat.push(e);
    }
    return [...persis, ...awalan.sort(urutId), ...memuat.sort(urutId)].slice(0, batas);
  }
}

export function bentukRagam(e, ragam = "biasa") {
  if (ragam === "halus" && e.banjarHalus) return e.banjarHalus;
  if (ragam === "kasar" && e.banjarKasar) return e.banjarKasar;
  return e.banjar;
}

function jumlahKata(s) {
  const t = s.trim();
  return t ? t.split(/\s+/).length : 0;
}

// ================================================================ morfologi

const VOKAL = new Set("aiueo");
const PANJANG_DASAR_MIN = 3;
const AKHIRAN_LUAR = { lah: "lah", kah: "kah", pun: "pun", nya: "nya", ku: "ku", mu: "mu" };
const AKHIRAN_DALAM = { kan: "akan", an: "an", i: "i" };
const AKHIRAN_LUAR_BJN = { lah: "lah", kah: "kah", pun: "pun", nya: "nya", ku: "ku", mu: "mu" };
const AKHIRAN_DALAM_BJN = { akan: "kan", an: "an", i: "i" };

const awal = (s) => s.slice(0, 1);
const vokal = (s) => VOKAL.has(awal(s));

function* lepasAkhiran(kata, luarPeta, dalamPeta) {
  yield [kata, []];
  const luarOpsi = [["", kata]];
  for (const a of Object.keys(luarPeta)) if (kata.endsWith(a)) luarOpsi.push([a, kata.slice(0, -a.length)]);
  for (const [luar, sisa] of luarOpsi) {
    if (luar && sisa.length >= PANJANG_DASAR_MIN) yield [sisa, [luar]];
    for (const dalam of Object.keys(dalamPeta)) {
      if (sisa.endsWith(dalam) && sisa.length - dalam.length >= PANJANG_DASAR_MIN) {
        yield [sisa.slice(0, -dalam.length), luar ? [dalam, luar] : [dalam]];
      }
    }
  }
}

function kandidatMeN(sisa) {
  if (sisa.startsWith("ng")) { const r = sisa.slice(2); return vokal(r) ? [r, "k" + r] : [r]; }
  if (sisa.startsWith("ny")) { const r = sisa.slice(2); return vokal(r) ? ["s" + r] : []; }
  if (sisa.startsWith("m")) {
    const r = sisa.slice(1);
    if (vokal(r)) return ["m" + r, "p" + r];
    return ["b", "f", "v"].includes(awal(r)) ? [r] : awal(r) ? ["m" + r] : [];
  }
  if (sisa.startsWith("n")) {
    const r = sisa.slice(1);
    if (vokal(r)) return ["n" + r, "t" + r];
    return ["d", "c", "j", "t"].includes(awal(r)) ? [r] : awal(r) ? ["n" + r] : [];
  }
  return ["l", "r", "w", "y"].includes(awal(sisa)) ? [sisa] : [];
}

function* lepasAwalan(kata) {
  yield ["", kata];
  if (kata.startsWith("me")) for (const d of kandidatMeN(kata.slice(2))) yield ["meN", d];
  if (kata.startsWith("ber")) yield ["ber", kata.slice(3)];
  if (kata.startsWith("bel")) yield ["ber", kata.slice(3)];
  if (kata.startsWith("be")) yield ["ber", kata.slice(2)];
  for (const aw of ["di", "ter", "ke", "se"]) if (kata.startsWith(aw)) yield [aw, kata.slice(aw.length)];
}

function kandidatMaN(sisa) {
  if (sisa.startsWith("ng")) {
    const r = sisa.slice(2);
    return vokal(r) ? [r, "k" + r] : ["g", "h"].includes(awal(r)) ? [r] : [];
  }
  if (sisa.startsWith("ny")) { const r = sisa.slice(2); return vokal(r) ? ["s" + r] : []; }
  if (sisa.startsWith("m")) {
    const r = sisa.slice(1);
    if (vokal(r)) return ["m" + r, "p" + r];
    return ["b", "f", "v"].includes(awal(r)) ? [r] : [];
  }
  if (sisa.startsWith("n")) {
    const r = sisa.slice(1);
    if (vokal(r)) return ["n" + r, "t" + r];
    return ["d", "c", "j"].includes(awal(r)) ? [r] : [];
  }
  return ["l", "r", "w", "y"].includes(awal(sisa)) ? [sisa] : [];
}

function* lepasAwalanBjn(kata) {
  yield ["", kata];
  if (kata.startsWith("ma")) for (const d of kandidatMaN(kata.slice(2))) yield ["meN", d];
  if (kata.startsWith("ba")) yield ["ber", kata.slice(2)];
  for (const [bjn, id] of [["di", "di"], ["ta", "ter"], ["ka", "ke"], ["sa", "se"]]) {
    if (kata.startsWith(bjn)) yield [id, kata.slice(bjn.length)];
  }
}

const jumlahImbuhan = (a) => (a.awalan ? 1 : 0) + a.akhiran.length;
const lebihBaik = (c, t) => {
  const [ci, ti] = [jumlahImbuhan(c), jumlahImbuhan(t)];
  return ci < ti || (ci === ti && -c.dasar.length < -t.dasar.length);
};

function cariAnalisis(kata, ada, akhiranGen, awalanGen, petaAkhiran) {
  kata = kata.toLowerCase();
  let terbaik = null;
  for (const [sisa, akhiran] of akhiranGen(kata)) {
    for (const [awalan, dasar] of awalanGen(sisa)) {
      if (!awalan && !akhiran.length) continue;
      if (dasar.length < PANJANG_DASAR_MIN || !ada(dasar)) continue;
      const calon = { awalan, dasar, akhiran: petaAkhiran(akhiran) };
      if (terbaik === null || lebihBaik(calon, terbaik)) terbaik = calon;
    }
  }
  return terbaik;
}

export function analisis(kata, ada) {
  return cariAnalisis(kata, ada, (k) => lepasAkhiran(k, AKHIRAN_LUAR, AKHIRAN_DALAM), lepasAwalan, (a) => a);
}

export function analisisBanjar(kata, ada) {
  return cariAnalisis(kata, ada, (k) => lepasAkhiran(k, AKHIRAN_LUAR_BJN, AKHIRAN_DALAM_BJN), lepasAwalanBjn,
    (a) => a.map((x) => AKHIRAN_DALAM_BJN[x] || AKHIRAN_LUAR_BJN[x]));
}

export function nasalBanjar(d) {
  const h = awal(d);
  if (h === "p") return "mam" + d.slice(1);
  if (h === "b") return "mam" + d;
  if (h === "t") return "man" + d.slice(1);
  if (["d", "c", "j"].includes(h)) return "man" + d;
  if (h === "s") return "many" + d.slice(1);
  if (h === "k") return "mang" + d.slice(1);
  if (["g", "h"].includes(h) || VOKAL.has(h)) return "mang" + d;
  return "ma" + d;
}

export function nasalIndonesia(d) {
  const h = awal(d);
  if (h === "p") return "mem" + d.slice(1);
  if (["b", "f", "v"].includes(h)) return "mem" + d;
  if (h === "t") return "men" + d.slice(1);
  if (["d", "c", "j", "z"].includes(h)) return "men" + d;
  if (h === "s") return "meny" + d.slice(1);
  if (h === "k") return "meng" + d.slice(1);
  if (["g", "h"].includes(h) || VOKAL.has(h)) return "meng" + d;
  return "me" + d;
}

const BER_KHUSUS = { ajar: "belajar", kerja: "bekerja", ternak: "beternak" };
const berIndonesia = (d) => BER_KHUSUS[d] || (d.startsWith("r") ? "be" : "ber") + d;

const AWALAN_BANJAR = {
  "": (d) => d, meN: nasalBanjar, ber: (d) => "ba" + d, di: (d) => "di" + d,
  ter: (d) => "ta" + d, ke: (d) => "ka" + d, se: (d) => "sa" + d,
};
const AWALAN_INDONESIA = {
  "": (d) => d, meN: nasalIndonesia, ber: berIndonesia, di: (d) => "di" + d,
  ter: (d) => "ter" + d, ke: (d) => "ke" + d, se: (d) => "se" + d,
};

export function bentukBanjar(a, dasarBanjar) {
  let kata = AWALAN_BANJAR[a.awalan](dasarBanjar.toLowerCase());
  for (const ak of a.akhiran) kata += AKHIRAN_DALAM[ak] || AKHIRAN_LUAR[ak];
  return kata;
}

export function bentukIndonesia(a, dasarId) {
  let kata = AWALAN_INDONESIA[a.awalan](dasarId.toLowerCase());
  for (const ak of a.akhiran) kata += ak;
  return kata;
}

// ================================================================ mesin

const HURUF = "A-Za-zÀ-ÖØ-öø-ÿ";
const POLA_TOKEN = new RegExp(`[${HURUF}]+(?:-[${HURUF}]+)*|\\s+|[^\\s${HURUF}]+`, "g");
const POLA_KATA = new RegExp(`[${HURUF}]`);
const PENGUAT_DEPAN = new Set(["sangat"]);

const besar = (s) => s !== s.toLowerCase() && s === s.toUpperCase();   // = str.isupper() Python
const spasiSaja = (s) => /^\s+$/.test(s);                               // = str.isspace() Python
const seg = (asal, hasil, jenis, keterangan = "") => ({ asal, hasil, jenis, keterangan });
const spasi = (s) => s.jenis === "lain" && spasiSaja(s.hasil);

export function ikutiHurufBesar(asal, hasil) {
  if (asal.length > 1 && besar(asal)) return hasil.toUpperCase();
  if (besar(asal.slice(0, 1))) return hasil.slice(0, 1).toUpperCase() + hasil.slice(1);
  return hasil;
}

export const gabung = (segmen) => segmen.map((s) => s.hasil).join("");

function keteranganEntri(e) {
  const bagian = [];
  if (e.varian.length) bagian.push("varian: " + e.varian.join(", "));
  if (e.catatan) bagian.push(e.catatan);
  return bagian.join("; ");
}

/** Indonesia -> Banjar. */
export class Mesin {
  constructor(kamus) { this.kamus = kamus; }

  kenal(kata) { return this._kata(kata, "biasa").jenis !== "tak_dikenal"; }

  _cari(teks, ragam) {
    const e = this.kamus.cari(teks);
    return e ? [bentukRagam(e, ragam), keteranganEntri(e)] : null;
  }

  _panjangFrasa() { return this.kamus.panjangFrasaMaks; }

  _imbuhan(kata, ragam) {
    const a = analisis(kata, (d) => this.kamus.ada(d));
    if (!a) return null;
    const dasarBjn = bentukRagam(this.kamus.cari(a.dasar), ragam);
    if (dasarBjn.includes(" ")) return null;
    return [bentukBanjar(a, dasarBjn), [a.awalan, a.dasar, ...a.akhiran].filter(Boolean).join("+")];
  }

  _pasca(segmen) {
    let i = 0;
    while (i + 2 < segmen.length) {
      const [a, sela, b] = [segmen[i], segmen[i + 1], segmen[i + 2]];
      if (PENGUAT_DEPAN.has(a.asal.toLowerCase()) && a.jenis === "kata" && spasi(sela)
          && b.jenis !== "lain" && b.jenis !== "tak_dikenal") {
        const hurufAwal = besar(a.asal.slice(0, 1));
        const kataB = hurufAwal ? b.hasil.slice(0, 1).toUpperCase() + b.hasil.slice(1) : b.hasil;
        const kataA = besar(a.asal) ? a.hasil : a.hasil.toLowerCase();
        segmen.splice(i, 3,
          seg(b.asal, kataB, b.jenis, b.keterangan),
          sela,
          seg(a.asal, kataA, a.jenis, "dipindah ke belakang (urutan Banjar)"));
        i += 3;
      } else {
        i += 1;
      }
    }
    return segmen;
  }

  _kata(kata, ragam) {
    const cocok = this._cari(kata, ragam);
    if (cocok) return seg(kata, ikutiHurufBesar(kata, cocok[0]), "kata", cocok[1]);
    if (kata.includes("-")) {
      const bagian = kata.split("-").map((b) => this._kata(b, ragam));
      if (bagian.every((b) => b.jenis !== "tak_dikenal")) {
        return seg(kata, bagian.map((b) => b.hasil).join("-"), "ulang");
      }
    }
    const imb = this._imbuhan(kata, ragam);
    if (imb) return seg(kata, ikutiHurufBesar(kata, imb[0]), "imbuhan", imb[1]);
    return seg(kata, kata, "tak_dikenal");
  }

  terjemah(teks, ragam = "biasa") {
    const token = teks.match(POLA_TOKEN) || [];
    const segmen = [];
    let i = 0;
    while (i < token.length) {
      const t = token[i];
      if (!POLA_KATA.test(t)) { segmen.push(seg(t, t, "lain")); i += 1; continue; }
      const cocok = this._cocokFrasa(token, i, ragam);
      if (cocok) { segmen.push(cocok[0]); i = cocok[1]; continue; }
      segmen.push(this._kata(t, ragam));
      i += 1;
    }
    return this._pasca(segmen);
  }

  _cocokFrasa(token, i, ragam) {
    const kataIdx = [i];
    let j = i + 1;
    while (kataIdx.length < this._panjangFrasa() && j + 1 < token.length) {
      if (!spasiSaja(token[j]) || !POLA_KATA.test(token[j + 1])) break;
      kataIdx.push(j + 1);
      j += 2;
    }
    for (let n = kataIdx.length; n > 1; n--) {
      const idx = kataIdx.slice(0, n);
      const frasa = idx.map((k) => token[k].toLowerCase()).join(" ");
      const cocok = this._cari(frasa, ragam);
      if (cocok) {
        const akhir = idx[idx.length - 1];
        const asal = token.slice(i, akhir + 1).join("");
        return [seg(asal, ikutiHurufBesar(token[i], cocok[0]), "frasa", cocok[1]), akhir + 1];
      }
    }
    return null;
  }
}

/** Ejaan santai -> baku (vokal Banjar hanya a, i, u): semalam -> samalam. */
export const ejaanBakuBanjar = (kata) => kata.toLowerCase().replaceAll("e", "a");

/** Banjar -> Indonesia. khusus: Map banjar -> [indonesia, catatan]; kataId: Set kata Indonesia lazim. */
export class MesinBalik extends Mesin {
  constructor(kamus, khusus = new Map(), kataId = new Set()) {
    super(kamus);
    this.khusus = khusus;
    this.kataId = kataId;
  }

  _cari(teks) {
    const t = teks.toLowerCase();
    if (this.khusus.has(t)) {
      const [indo, catatan] = this.khusus.get(t);
      return [indo, catatan || (!indo ? "partikel, dihilangkan" : "kamus khusus Banjar")];
    }
    const calon = this.kamus.cariBalik(t);
    if (!calon.length) return null;
    return [calon[0], calon.length > 1 ? "bisa juga: " + calon.slice(1, 4).join(", ") : ""];
  }

  _panjangFrasa() {
    let khusus = 1;
    for (const k of this.khusus.keys()) khusus = Math.max(khusus, jumlahKata(k));
    return Math.max(this.kamus.panjangFrasaBalikMaks, khusus);
  }

  _dasarIndonesia(dasar) {
    if (this.khusus.has(dasar) && this.khusus.get(dasar)[0]) return this.khusus.get(dasar)[0];
    const calon = this.kamus.cariBalik(dasar);
    return calon.length ? calon[0] : null;
  }

  _imbuhanBalik(kata, pakaiKataId) {
    const ada = (d) => this._dasarIndonesia(d) !== null || (pakaiKataId && this.kataId.has(d));
    let a = analisisBanjar(kata, ada);
    if (!a) return null;
    if (a.awalan === "ber" && !a.akhiran.length && a.dasar.endsWith("an") && ada(a.dasar.slice(0, -2))) {
      a = { awalan: "ber", dasar: a.dasar.slice(0, -2), akhiran: ["an"] };   // ba+main+an, bukan ba+mainan
    }
    const dasarId = this._dasarIndonesia(a.dasar) || a.dasar;
    if (dasarId.includes(" ")) return null;
    const ket = [`${a.awalan || ""}+${a.dasar}+${a.akhiran.join("+")}`.replace(/^\++|\++$/g, "")];
    if (a.awalan === "ber" && a.akhiran[0] === "an") {
      if (!this.kataId.has(bentukIndonesia(a, dasarId))) {
        a = { awalan: a.awalan, dasar: a.dasar, akhiran: a.akhiran.slice(1) };
        ket.push("ba-…-an → ber-");
      }
    }
    if (this._dasarIndonesia(a.dasar) === null) ket.push(`kata dasar '${a.dasar}' dianggap sama dengan Indonesia`);
    return [bentukIndonesia(a, dasarId), ket.join("; ")];
  }

  _kata(kata, ragam) {
    const kecil = kata.toLowerCase();
    const bentuk = [kecil];
    if (!kecil.includes("-") && ejaanBakuBanjar(kecil) !== kecil) bentuk.push(ejaanBakuBanjar(kecil));

    for (const b of bentuk) {
      const cocok = this._cari(b, ragam);
      if (cocok) {
        const ket = [cocok[1], b !== kecil ? `ejaan baku: ${b}` : ""].filter(Boolean).join("; ");
        return seg(kata, ikutiHurufBesar(kata, cocok[0]), "kata", ket);
      }
    }
    if (kata.includes("-")) {
      const bagian = kata.split("-").map((b) => this._kata(b, ragam));
      if (bagian.every((b) => b.jenis !== "tak_dikenal")) {
        return seg(kata, bagian.map((b) => b.hasil).join("-"), "ulang");
      }
    }
    for (const b of [...bentuk].reverse()) {
      const imb = this._imbuhanBalik(b, false);
      if (imb) return seg(kata, ikutiHurufBesar(kata, imb[0]), "imbuhan", imb[1]);
    }
    if (this.kataId.has(kecil)) return seg(kata, kata, "sama", "dianggap sama dengan bahasa Indonesia");
    for (const b of [...bentuk].reverse()) {
      const imb = this._imbuhanBalik(b, true);
      if (imb) return seg(kata, ikutiHurufBesar(kata, imb[0]), "imbuhan", imb[1]);
    }
    return seg(kata, kata, "tak_dikenal");
  }

  _pasca(segmen) {
    segmen.forEach((s, i) => {
      if (s.asal.toLowerCase() !== "banar" || s.jenis !== "kata") return;
      const setelahKata = i >= 2 && spasi(segmen[i - 1]) && segmen[i - 2].jenis !== "lain";
      s.hasil = ikutiHurufBesar(s.asal, setelahKata ? "sekali" : "benar");
      s.keterangan = setelahKata ? "penguat setelah kata" : "";
    });

    const keluar = [];
    let buangSesudah = false, besarBerikut = false;
    for (const s of segmen) {
      if (s.jenis === "kata" && s.hasil === "") {
        const diTengah = keluar.length >= 2 && spasi(keluar[keluar.length - 1])
          && keluar[keluar.length - 2].jenis !== "lain";
        if (diTengah) keluar.pop();
        else { buangSesudah = true; besarBerikut = besarBerikut || besar(s.asal.slice(0, 1)); }
        keluar.push(seg(s.asal, "", "partikel", s.keterangan));
        continue;
      }
      if (buangSesudah && s.jenis === "lain" && /^[\s,]*$/.test(s.hasil)) continue;
      buangSesudah = false;
      if (besarBerikut && s.jenis !== "lain") {
        s.hasil = s.hasil.slice(0, 1).toUpperCase() + s.hasil.slice(1);
        besarBerikut = false;
      }
      keluar.push(s);
    }
    return keluar;
  }
}

/** Bangun kedua mesin dari data JSON (data/kamus.json, data/khusus.json, data/kata_id_umum.json). */
export function bangunMesin(barisKamus, khususObj = {}, kataId = []) {
  const kamus = Kamus.dariBaris(barisKamus);
  const khusus = new Map(Object.entries(khususObj));
  return { kamus, mesin: new Mesin(kamus), balik: new MesinBalik(kamus, khusus, new Set(kataId)) };
}
