// Dijalankan oleh tests/test_paritas.py: baca data + kalimat (JSON dari stdin), terjemahkan
// dengan mesin JavaScript, tulis segmen hasil (JSON) ke stdout.
import { readFileSync } from "node:fs";
import { bangunMesin } from "../static/mesin.js";

const masuk = JSON.parse(readFileSync(0, "utf-8"));
const { mesin, balik } = bangunMesin(masuk.kamus, masuk.khusus, masuk.kata_id);

const keluar = {
  ke_banjar: masuk.ke_banjar.map(([teks, ragam]) => mesin.terjemah(teks, ragam)),
  dari_banjar: masuk.dari_banjar.map((teks) => balik.terjemah(teks)),
  kenal: masuk.kenal.map((kata) => mesin.kenal(kata)),
};
process.stdout.write(JSON.stringify(keluar));
