// Antarmuka Penerjemah Banjar. Terjemahan berjalan di browser (mesin.js); bahasa lain
// lewat MyMemory (sumber.js). Fitur pengelolaan (Tinjau Kamus, usulan, catatan kata tak
// dikenal) hanya aktif bila dijalankan lewat server lokal (data/info.json: mode "server").
import { bangunMesin, gabung } from "./mesin.js";
import { BATAS_KARAKTER, terjemahLuar } from "./sumber.js";

const $ = (id) => document.getElementById(id);
let terakhir = null;      // hasil terjemahan terakhir
let namaBahasa = {};      // kode -> nama, diisi dari data/info.json
let modeServer = false;   // true = server lokal (pengelolaan aktif); false = hosting statis
let data = null;          // { kamus, mesin, balik }
let kamusBerubah = false; // kamus diubah lewat Tinjau Kamus -> muat ulang sebelum dipakai

async function muatData() {
  const ambil = async (nama) => {
    const r = await fetch(`data/${nama}`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`Gagal memuat ${nama}`);
    return r.json();
  };
  const [kamus, khusus, kataId] = await Promise.all(
    [ambil("kamus.json"), ambil("khusus.json"), ambil("kata_id_umum.json")]
  );
  data = bangunMesin(kamus, khusus, kataId);
  kamusBerubah = false;
  $("versi").textContent = `Versi ${namaBahasa.__versi || ""} · ${data.kamus.ukuran} entri kamus`;
}

const LABEL_JENIS = {
  kata: "dari kamus",
  frasa: "frasa dari kamus",
  imbuhan: "dibentuk dari imbuhan",
  ulang: "kata ulang",
  tak_dikenal: "belum ada di kamus",
  sama: "tidak ada di kamus; dianggap sama dengan bahasa Indonesia",
};

async function api(path, opsi = {}) {
  let r;
  try {
    r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opsi });
  } catch {
    throw new Error("Tidak tersambung ke server. Periksa koneksi internet, lalu coba lagi.");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Galat ${r.status}`);
  return data;
}

// ------------------------------------------------------------------ tab
document.querySelectorAll(".tab button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab button").forEach((b) => b.setAttribute("aria-selected", b === btn));
    document.querySelectorAll(".panel").forEach((p) => (p.hidden = p.id !== btn.dataset.panel));
    if (btn.dataset.panel === "panel-kamus") muatKamus();
    if (btn.dataset.panel === "panel-tinjau") mulaiTinjau();
  });
});

// ------------------------------------------------------------------ arah bahasa
const BJN = "bjn";

function isiPilihanBahasa(bahasa) {
  const sumber = $("sumber"), sasaran = $("sasaran");
  sumber.append(new Option("Banjar", BJN));
  sasaran.append(new Option("Banjar", BJN, true, true));
  for (const [kode, nama] of Object.entries(bahasa)) {
    sumber.append(new Option(nama, kode, kode === "id", kode === "id"));
    if (kode !== "auto") sasaran.append(new Option(nama, kode));
  }
  aturArah();
}

// Salah satu sisi harus Banjar: bila sisi yang diubah bukan Banjar, sisi lainnya jadi Banjar.
function aturArah(diubah) {
  const sumber = $("sumber"), sasaran = $("sasaran");
  if (diubah === sumber) {
    if (sumber.value === BJN && sasaran.value === BJN) sasaran.value = "id";
    else if (sumber.value !== BJN) sasaran.value = BJN;
  } else if (diubah === sasaran) {
    if (sasaran.value === BJN && sumber.value === BJN) sumber.value = "id";
    else if (sasaran.value !== BJN) sumber.value = BJN;
  }
  $("ragam").hidden = sasaran.value !== BJN;
  $("masukan").placeholder = sumber.value === BJN
    ? "Ketik teks Banjar… contoh: Ulun handak tulak ka pasar manukar iwak."
    : "Ketik teks di sini… contoh: Saya mau pergi ke pasar membeli ikan.";
}

$("sumber").addEventListener("change", (e) => aturArah(e.target));
$("sasaran").addEventListener("change", (e) => aturArah(e.target));
$("tombol-tukar").addEventListener("click", () => {
  const sumber = $("sumber"), sasaran = $("sasaran");
  let lama = sumber.value === "auto" ? (terakhir?.sumber_terdeteksi || "id") : sumber.value;
  if (lama !== BJN && (!namaBahasa[lama] || lama === "auto")) lama = "id"; // bahasa terdeteksi di luar daftar
  sumber.value = sasaran.value;
  sasaran.value = lama;
  if (terakhir?.hasil) $("masukan").value = terakhir.hasil;
  aturArah();
  if ($("masukan").value.trim()) terjemahkan();
});

// ------------------------------------------------------------------ terjemah
function tampilSegmen(wadah, segmen, labelAsal) {
  for (const s of segmen) {
    if (s.jenis === "partikel") continue; // partikel Banjar yang dihilangkan
    if (s.jenis === "lain") {
      wadah.append(s.hasil);
      continue;
    }
    const span = document.createElement("span");
    span.className = `seg seg-${s.jenis}`;
    span.textContent = s.hasil;
    const ket = [s.asal !== s.hasil ? `${labelAsal}: ${s.asal}` : "", LABEL_JENIS[s.jenis] || "", s.keterangan]
      .filter(Boolean)
      .join(" · ");
    if (ket) span.title = ket;
    wadah.append(span);
  }
}

function tampilkanHasil(data) {
  const kotak = $("hasil");
  const perantara = $("perantara");
  kotak.replaceChildren();
  perantara.replaceChildren();
  const labelAsal = data.arah === "dari_banjar" ? "Banjar" : "Indonesia";

  if (data.segmen_adalah_hasil) {
    tampilSegmen(kotak, data.segmen, labelAsal);
  } else {
    kotak.textContent = data.hasil; // hasil layanan luar (mis. Inggris/Arab)
  }

  // Baris perantara: hanya bila ada tahap lewat bahasa Indonesia
  perantara.hidden = true;
  if (data.arah === "ke_banjar" && data.sumber_terdeteksi !== "id") {
    const nama = namaBahasa[data.sumber_terdeteksi] || data.sumber_terdeteksi;
    perantara.append(`Terdeteksi: ${nama} · Perantara (Indonesia): ${data.teks_indonesia}`);
    perantara.hidden = false;
  } else if (data.arah === "dari_banjar" && !data.segmen_adalah_hasil) {
    perantara.append("Perantara (Indonesia): ");
    tampilSegmen(perantara, data.segmen, labelAsal);
    perantara.hidden = false;
  }
  $("tombol-salin").disabled = !data.hasil;
  $("tombol-usul").disabled = !data.hasil;
}

const unik = (xs) => [...new Set(xs)].sort();

async function jalankanTerjemah(teks, sumber, sasaran, ragam) {
  if ((sumber === BJN) === (sasaran === BJN)) throw new Error("Salah satu bahasa (asal atau tujuan) harus Banjar.");
  if (teks.length > BATAS_KARAKTER) throw new Error(`Teks terlalu panjang (maks ${BATAS_KARAKTER} karakter).`);
  if (!data || kamusBerubah) await muatData();

  let teksId, terdeteksi, segmen, hasil;
  const arah = sasaran === BJN ? "ke_banjar" : "dari_banjar";
  if (arah === "ke_banjar") {
    // bahasa apa pun -> Indonesia -> Banjar
    if (sumber === "id") [teksId, terdeteksi] = [teks, "id"];
    else ({ hasil: teksId, terdeteksi } = await terjemahLuar(teks, sumber, "id"));
    segmen = data.mesin.terjemah(teksId, ragam);
    hasil = gabung(segmen);
  } else {
    // Banjar -> Indonesia -> bahasa tujuan
    terdeteksi = BJN;
    segmen = data.balik.terjemah(teks);
    teksId = gabung(segmen);
    hasil = sasaran === "id" ? teksId : (await terjemahLuar(teksId, "id", sasaran)).hasil;
  }
  const takDikenal = unik(segmen.filter((s) => s.jenis === "tak_dikenal").map((s) => s.asal.toLowerCase()));
  const dianggapSama = unik(segmen.filter((s) => s.jenis === "sama").map((s) => s.asal.toLowerCase()));

  if (modeServer) {
    // catat kata yang belum dikenal sebagai bahan perluasan kamus (tidak menghambat tampilan)
    const kata = arah === "ke_banjar" ? takDikenal : [...takDikenal, ...dianggapSama];
    if (kata.length) {
      api("/api/kata-tak-dikenal", {
        method: "POST", body: JSON.stringify({ kata, bahasa: arah === "ke_banjar" ? "id" : BJN }),
      }).catch(() => {});
    }
  }
  return {
    arah, sumber, sasaran, sumber_terdeteksi: terdeteksi, teks_indonesia: teksId, hasil, segmen,
    segmen_adalah_hasil: sasaran === BJN || sasaran === "id",
    tak_dikenal: takDikenal, dianggap_sama: dianggapSama, teks_asal: teks,
  };
}

async function terjemahkan() {
  const teks = $("masukan").value;
  if (!teks.trim()) return;
  const tombol = $("tombol-terjemah");
  tombol.disabled = true;
  tombol.textContent = "Menerjemahkan…";
  $("galat").hidden = true;
  try {
    const ragam = document.querySelector('input[name="ragam"]:checked').value;
    terakhir = await jalankanTerjemah(teks, $("sumber").value, $("sasaran").value, ragam);
    tampilkanHasil(terakhir);
  } catch (e) {
    $("galat").textContent = e.message;
    $("galat").hidden = false;
  } finally {
    tombol.disabled = false;
    tombol.textContent = "Terjemahkan";
  }
}

$("tombol-terjemah").addEventListener("click", terjemahkan);
$("masukan").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) terjemahkan();
});
$("masukan").addEventListener("input", (e) => {
  $("hitung").textContent = `${e.target.value.length} / 4500`;
});
document.querySelectorAll('input[name="ragam"]').forEach((r) =>
  r.addEventListener("change", () => terakhir && terjemahkan())
);

$("tombol-salin").addEventListener("click", async () => {
  if (!terakhir) return;
  try {
    await navigator.clipboard.writeText(terakhir.hasil);
    $("tombol-salin").textContent = "Tersalin";
    setTimeout(() => ($("tombol-salin").textContent = "Salin"), 1500);
  } catch {
    /* clipboard tidak tersedia (mis. bukan https) */
  }
});

// ------------------------------------------------------------------ usulan
$("tombol-usul").addEventListener("click", () => {
  if (!terakhir) return;
  $("usul-mesin").value = terakhir.hasil;
  $("usul-benar").value = terakhir.hasil;
  $("usul-catatan").value = "";
  $("dialog-usul").showModal();
});

$("dialog-usul").addEventListener("close", async () => {
  if ($("dialog-usul").returnValue !== "kirim" || !terakhir) return;
  try {
    await api("/api/saran", {
      method: "POST",
      body: JSON.stringify({
        teks_indonesia: terakhir.teks_indonesia,
        hasil_mesin: terakhir.hasil,
        usulan: $("usul-benar").value,
        catatan: $("usul-catatan").value,
        arah: terakhir.arah,
        teks_asal: terakhir.teks_asal || "",
      }),
    });
  } catch (e) {
    $("galat").textContent = `Usulan gagal dikirim: ${e.message}`;
    $("galat").hidden = false;
  }
});

// ------------------------------------------------------------------ kamus
let jedaCari = null;
async function muatKamus() {
  if (!data || kamusBerubah) await muatData();
  const baris = data.kamus.telusur($("cari-kamus").value, 200);
  const tbody = $("isi-kamus");
  tbody.replaceChildren(
    ...baris.map((e) => {
      const tr = document.createElement("tr");
      const banjar = [e.banjar, ...e.varian].join(" / ");
      for (const isi of [e.indonesia, banjar, e.banjarHalus, e.banjarKasar, e.catatan]) {
        const td = document.createElement("td");
        td.textContent = isi;
        tr.append(td);
      }
      return tr;
    })
  );
  $("info-kamus").textContent = baris.length ? `${baris.length} entri ditampilkan` : "Tidak ditemukan.";
}
$("cari-kamus").addEventListener("input", () => {
  clearTimeout(jedaCari);
  jedaCari = setTimeout(muatKamus, 200);
});

// ------------------------------------------------------------------ tinjau kamus
const tinjau = { antrean: [], kini: null, lewati: new Set(), sibuk: false };

function tandai(el, kalimat, kata) {
  // tampilkan kalimat dengan kata yang dicari disorot (tanpa innerHTML)
  el.replaceChildren();
  if (!kata) return el.append(kalimat);
  const pola = new RegExp(`(^|[^\\p{L}])(${kata.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})(?=[^\\p{L}]|$)`, "giu");
  let akhir = 0;
  for (const m of kalimat.matchAll(pola)) {
    const awal = m.index + m[1].length;
    el.append(kalimat.slice(akhir, awal));
    const mark = document.createElement("mark");
    mark.textContent = m[2];
    el.append(mark);
    akhir = awal + m[2].length;
  }
  el.append(kalimat.slice(akhir));
}

function tampilStatistik(s) {
  const persen = s.ditinjau + s.sisa ? (s.ditinjau / (s.ditinjau + s.sisa)) * 100 : 0;
  $("batang-isi").style.width = `${persen.toFixed(1)}%`;
  $("info-tinjau").textContent =
    `${s.ditinjau} ditinjau · ${s.sisa} tersisa · kamus ${s.entri_kamus} entri`;
  $("versi").textContent = $("versi").textContent.replace(/\d+ entri kamus/, `${s.entri_kamus} entri kamus`);
}

function pilihUsulan(teks, fokus = false) {
  $("t-banjar").value = teks;
  document.querySelectorAll("#t-usulan button").forEach((b) =>
    b.classList.toggle("dipilih", b.dataset.nilai === teks)
  );
  if (fokus) $("t-banjar").focus();
  else document.activeElement?.blur();
}

function tampilItem() {
  const it = tinjau.antrean.shift();
  tinjau.kini = it || null;
  $("kartu-tinjau").hidden = !it;
  if (!it) {
    $("t-kosong").textContent = tinjau.lewati.size
      ? "Antrean sesi ini habis. Kata yang dilewati akan muncul lagi setelah halaman dimuat ulang."
      : "Semua kandidat sudah ditinjau.";
    $("t-kosong").hidden = false;
    return;
  }
  $("t-kosong").hidden = true;
  $("t-kata").textContent = it.indonesia;

  const lencana = $("t-lencana");
  lencana.replaceChildren();
  for (const s of it.sumber.split("+").filter(Boolean)) {
    const span = document.createElement("span");
    span.textContent = s === "nusax" ? "korpus NusaX" : "model NLLB";
    lencana.append(span);
  }
  if (it.sepakat) {
    const span = document.createElement("span");
    span.className = "sepakat";
    span.textContent = `kedua sumber sepakat: ${it.sepakat}`;
    lencana.append(span);
  }

  const wadah = $("t-usulan");
  wadah.replaceChildren(
    ...it.usulan.map((u, i) => {
      const b = document.createElement("button");
      b.dataset.nilai = u;
      const k = document.createElement("kbd");
      k.textContent = `${i + 1}`;
      b.append(k, u);
      b.addEventListener("click", () => pilihUsulan(u));
      return b;
    })
  );

  $("t-halus").value = "";
  $("t-kasar").value = "";
  $("t-contoh").hidden = !it.contoh_id;
  if (it.contoh_id) {
    tandai($("t-contoh-id"), it.contoh_id, it.indonesia);
    tandai($("t-contoh-bjn"), it.contoh_bjn, it.usulan[0]);
  }
  pilihUsulan(it.sepakat || it.usulan[0] || "");
}

async function isiAntrean() {
  const kecuali = [...tinjau.lewati, ...tinjau.antrean.map((x) => x.indonesia)].join(",");
  const d = await api(`/api/tinjau/antrian?n=20&kecuali=${encodeURIComponent(kecuali)}`);
  tinjau.antrean.push(...d.item);
  tampilStatistik(d.statistik);
}

async function mulaiTinjau() {
  if (tinjau.kini) return;
  try {
    await isiAntrean();
    if (!tinjau.antrean.length && !tinjau.lewati.size) {
      $("t-kosong").textContent =
        "Belum ada kandidat. Jalankan alat pembuat kandidat terlebih dulu (lihat README).";
      $("t-kosong").hidden = false;
      return;
    }
    tampilItem();
  } catch (e) {
    galatTinjau(e.message);
  }
}

function galatTinjau(pesan) {
  $("t-galat").textContent = pesan;
  $("t-galat").hidden = !pesan;
}

async function lanjut() {
  if (tinjau.antrean.length < 5) await isiAntrean();
  tampilItem();
}

async function putuskan(keputusan) {
  const it = tinjau.kini;
  if (!it || tinjau.sibuk) return;
  galatTinjau("");
  if (keputusan === "lewati") {
    tinjau.lewati.add(it.indonesia);
    return lanjut();
  }
  const banjar = $("t-banjar").value.trim();
  if (keputusan === "simpan" && !banjar) return galatTinjau("Isi terjemahan Banjar dulu.");
  tinjau.sibuk = true;
  try {
    const d = await api("/api/tinjau", {
      method: "POST",
      body: JSON.stringify({
        indonesia: it.indonesia, keputusan, banjar,
        banjar_halus: $("t-halus").value, banjar_kasar: $("t-kasar").value,
      }),
    });
    tampilStatistik(d.statistik);
    kamusBerubah = true;
    // kata turunan bisa jadi sudah terjemahkan oleh entri baru: buang dari antrean lokal
    tinjau.antrean = [];
    await lanjut();
  } catch (e) {
    galatTinjau(e.message);
  } finally {
    tinjau.sibuk = false;
  }
}

async function batalkanTerakhir() {
  if (tinjau.sibuk) return;
  tinjau.sibuk = true;
  try {
    const d = await api("/api/tinjau/batal", { method: "POST" });
    tampilStatistik(d.statistik);
    kamusBerubah = true;
    tinjau.antrean = [];
    if (tinjau.kini) tinjau.lewati.delete(tinjau.kini.indonesia);
    await isiAntrean();
    // tampilkan kembali kata yang dibatalkan paling depan
    const i = tinjau.antrean.findIndex((x) => x.indonesia === d.dibatalkan.indonesia);
    if (i > 0) tinjau.antrean.unshift(...tinjau.antrean.splice(i, 1));
    tampilItem();
    galatTinjau("");
  } catch (e) {
    galatTinjau(e.message);
  } finally {
    tinjau.sibuk = false;
  }
}

$("t-simpan").addEventListener("click", () => putuskan("simpan"));
$("t-sama").addEventListener("click", () => putuskan("sama"));
$("t-lewati").addEventListener("click", () => putuskan("lewati"));
$("t-buang").addEventListener("click", () => putuskan("buang"));
$("t-batal").addEventListener("click", batalkanTerakhir);

// Pintasan papan ketik. Saat kursor di kolom isian, hanya Enter (simpan) dan Esc (keluar)
// yang aktif sehingga mengetik tidak terganggu; di luar isian, tombol tunggal aktif.
document.addEventListener("keydown", (e) => {
  if ($("panel-tinjau").hidden || $("dialog-usul").open || !tinjau.kini) return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  const diIsian = document.activeElement?.tagName === "INPUT" &&
    document.activeElement.closest(".kartu-tinjau");

  if (diIsian) {
    if (e.key === "Enter") { e.preventDefault(); putuskan("simpan"); }
    else if (e.key === "Escape") { e.preventDefault(); document.activeElement.blur(); }
    return;
  }
  if (document.activeElement?.closest("input, textarea, select")) return;

  const kunci = e.key.toLowerCase();
  const aksi = {
    enter: () => putuskan("simpan"),
    s: () => putuskan("sama"),
    l: () => putuskan("lewati"),
    b: () => putuskan("buang"),
    z: () => batalkanTerakhir(),
    e: () => { const i = $("t-banjar"); i.focus(); i.select(); },
  }[kunci];
  if (aksi) {
    e.preventDefault();
    aksi();
  } else if (/^[1-5]$/.test(e.key) && tinjau.kini.usulan[+e.key - 1]) {
    e.preventDefault();
    pilihUsulan(tinjau.kini.usulan[+e.key - 1], false);
  }
});

// ------------------------------------------------------------------ awal
(async function mulai() {
  try {
    const r = await fetch("data/info.json", { cache: "no-cache" });
    const info = await r.json();
    modeServer = info.mode === "server";
    namaBahasa = { ...info.bahasa, [BJN]: "Banjar", __versi: info.versi };
    isiPilihanBahasa(info.bahasa);
    // hosting statis: sembunyikan fitur pengelolaan yang butuh server
    document.querySelector('.tab button[data-panel="panel-tinjau"]').hidden = !modeServer;
    $("tombol-usul").hidden = !modeServer;
    await muatData();
  } catch (e) {
    $("galat").textContent = "Data aplikasi gagal dimuat. Periksa koneksi lalu muat ulang halaman.";
    $("galat").hidden = false;
    return;
  }
  // tautan berbagi: ?dari=bjn&ke=en&teks=...&ragam=halus -> isi otomatis lalu terjemahkan
  const q = new URLSearchParams(location.search);
  if (q.get("teks")) {
    for (const [param, id] of [["dari", "sumber"], ["ke", "sasaran"]]) {
      const nilai = q.get(param);
      if (nilai && [...$(id).options].some((o) => o.value === nilai)) { $(id).value = nilai; aturArah($(id)); }
    }
    const ragam = document.querySelector(`input[name="ragam"][value="${q.get("ragam")}"]`);
    if (ragam) ragam.checked = true;
    $("masukan").value = q.get("teks").slice(0, BATAS_KARAKTER);
    $("hitung").textContent = `${$("masukan").value.length} / ${BATAS_KARAKTER}`;
    terjemahkan();
  }
  // buka tab langsung lewat alamat, mis. http://127.0.0.1:8000/#tinjau
  const tabAwal = { "#kamus": "panel-kamus", "#tinjau": "panel-tinjau" }[location.hash];
  const tombol = tabAwal && document.querySelector(`.tab button[data-panel="${tabAwal}"]`);
  if (tombol && !tombol.hidden) tombol.click();
})();

// ------------------------------------------------------------------ PWA (pasang sebagai aplikasi)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}

let ajakanPasang = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();          // tampilkan tombol sendiri, bukan banner bawaan
  ajakanPasang = e;
  $("tombol-pasang").hidden = false;
});
$("tombol-pasang").addEventListener("click", async () => {
  if (!ajakanPasang) return;
  ajakanPasang.prompt();
  await ajakanPasang.userChoice;
  ajakanPasang = null;
  $("tombol-pasang").hidden = true;
});
window.addEventListener("appinstalled", () => ($("tombol-pasang").hidden = true));
