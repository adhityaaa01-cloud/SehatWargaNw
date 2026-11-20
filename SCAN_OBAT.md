# Scan Obat dalam Asisten SehatWarga

Fitur lokal untuk membaca kemasan, membandingkan kandidat, mengoreksi bacaan di
server, mengonfirmasi identitas, dan menampilkan fakta rujukan. Tidak memberi dosis
pribadi. Perlindungan chat medis yang sudah ada tetap berlaku.

## Lingkungan dan menjalankan

Dari root repository, gunakan interpreter proyek:

```sh
.venv/bin/python scripts/preview.py
# http://127.0.0.1:5055/assistant — SQLite in-memory, tidak membaca .env
.venv/bin/python -m unittest tests.test_medicine_scan -v
.venv/bin/python -m unittest discover tests -v
node --check frontend/static/js/assistant.js
```

Aplikasi dengan konfigurasi development Anda: `.venv/bin/python run.py`.
Tidak diperlukan migrasi. `.env` tidak diubah oleh fitur ini.

Paket Python dicatat di `backend/requirements.txt` (root `requirements.txt`
merujuk manifest tersebut): `pytesseract==0.3.13`, `Pillow==13.0.0`.
Keduanya **sudah tersedia** di `.venv` saat audit; tidak diinstal ulang.
Engine dan data bahasa adalah paket **sistem Arch**, terpisah dari pip:
`tesseract`, `tesseract-data-ind`, `tesseract-data-eng`.
Jika belum tersedia di mesin lain: `sudo pacman -S tesseract tesseract-data-ind tesseract-data-eng`.
Verifikasi: `.venv/bin/python -c 'import pytesseract; print(pytesseract.get_languages())'`.

Konfigurasi yang relevan: `OMP_THREAD_LIMIT` (opsional; nilai `1` dapat mengurangi beban thread Tesseract),
`MAX_CONTENT_LENGTH` (sudah ada, batas global;
scan juga membatasi file 5 MiB), `MEDICINE_CATALOG_PATH` (opsional dalam
konfigurasi Flask untuk menunjuk JSON lain, dipakai fixture test). Tidak ada
API key baru. `AI_PROVIDER` tidak diperlukan oleh scan.

## Demo

1. Buka Asisten → tombol **+** / “Tambah lampiran”.
2. Pilih **Unggah Gambar** atau **Ambil Foto**. Kamera belakang diminta lewat
   pemilih kamera perangkat; jika tidak tersedia/izin ditolak, gunakan galeri.
3. Periksa pratinjau. **Ganti** dan **Batal** belum mengunggah apa pun.
4. **Kirim gambar**, tunggu OCR, baca teks dan bandingkan kandidat.
5. Koreksi berdasarkan tulisan yang benar-benar terlihat pada kemasan; klik
   **Cocokkan ulang**. Untuk identitas lemah, tambahkan NIE atau kekuatan yang
   bisa diperiksa. Jangan menyalin NIE contoh untuk mengesahkan produk berbeda.
6. **Konfirmasi produk ini** hanya tersedia setelah pemeriksaan server cukup.
   Kartu membedakan hasil OCR dari rujukan; sumber dan tanggal ada di kartu.

Untuk PANADOL Regular, gunakan foto yang memperlihatkan nama PANADOL, kaplet,
Paracetamol 500 mg atau NIE DBL9624502804A1. Varian Extra/Anak/Flu tidak sama.
Untuk `image/oskadon.png`, praproses sungguhan membaca **Orkadon**, Paracetamol,
Caffeine, dan **4 Tablet**. Nama file yang diganti tidak dipakai dalam pencarian.
Kandidat OSKADON muncul, **belum boleh dikonfirmasi**: kadar/NIE belum terbaca.
Ambil foto sisi NIE atau koreksi dengan NIE yang benar-benar ada pada kemasan.
Kartu OSKADON menyatakan kekuatan dan peringatan belum tersedia dalam sumber.
Jumlah kemasan 4 tablet tidak diperlakukan sebagai 4 mg.

## Sumber dan cakupan yang benar-benar diverifikasi

Diperiksa 5 November 2026. **2 identitas produk** tersimpan, dengan
**1 kartu berisi kekuatan, indikasi dan peringatan resmi (PANADOL)** dan
**1 kartu parsial (OSKADON)**. Belum 20–30 produk; entri tidak ditambah hanya
untuk memenuhi kuota. Tidak ada fixture sintetis di katalog aplikasi.

- OSKADON tablet: [Cek BPOM](https://cekbpom.pom.go.id/produk-obat), cari
  `DBL8730700110A1` atau `OSKADON`. Pemeriksaan halaman publik beserta permintaan
  DataTables yang ditemukan di HTML resmi mengembalikan nama, bentuk TABLET,
  caffeine/paracetamol, pendaftar/produsen SUPRA FERBINDO FARMA dan kemasan
  1 strip 4 tablet. Detail `EREG100014VR12600023`, aplikasi `05`, menunjukkan
  e-labelling masyarakat/nakes kosong. Jangan menganggap detail URL permanen.
  [Halaman resmi Tempo Scan](https://www.temposcangroup.com/id/produk-layanan/otc/oskadon)
  membedakan OSKADON dari EXTRA, SP, SP NEURO; bagian OSKADON mendukung kegunaan
  sakit kepala. **Kadar, basis kekuatan dan peringatan lengkap belum terverifikasi**;
  nilai disimpan kosong, bukan diisi angka dari penjual atau ingatan.
- PANADOL kaplet 500 mg (Regular): [identitas BPOM](https://registrasiobat.pom.go.id/en/daftar-produk/assesment-report/DBL9624502804A1)
  mendukung NIE, bentuk, kekuatan dan pendaftar. [Label resmi](https://registrasiobat.pom.go.id/files/assesment-reports/01783924613.pdf)
  ditautkan dari riwayat registrasi, disetujui 15 Januari 2026,
  `EREG10027312500056 / EREG10027312500057`, NPA010259. Halaman 1 (foil) diperiksa
  secara visual setelah rasterisasi PDF dan OCR; halaman 3 mendukung kandungan
  per kaplet, indikasi dan produsen. Peringatan diringkas tanpa mengubah batas
  angka; bahan tambahan dipisahkan dari paracetamol.
- [Dokumentasi API KFA](https://satusehat.kemkes.go.id/platform/docs/id/master-data/kfa/rest-api-kfa/)
  mensyaratkan OAuth client_credentials dan persetujuan Kemenkes. Portal publik
  KFA dapat dibuka, tetapi bukan pemberian akses API. Aplikasi ini **tidak**
  memanggil API KFA atau endpoint BPOM saat scan. Tidak ada klaim izin akses API.

Mode yang bekerja adalah **pencarian katalog JSON lokal** dari fakta yang diperiksa,
bukan pencarian internet langsung. Sumber publik dapat dibaca, tetapi lisensi
redistribusi massal/API belum diverifikasi; tidak ada bulk scraping, salinan PDF,
atau klaim izin penggunaan ulang tanpa batas. Record menyimpan ringkasan fakta
terbatas dan tautan sumber, bukan menggandakan leaflet. Untuk perluasan publik,
periksa ketentuan/izin penggunaan data sebelum menambah katalog massal.

Jika tidak cocok: **“Produk belum ditemukan dalam katalog”**, tawarkan NIE/foto
sisi lain. Konflik NIE, nama, varian, bentuk atau satuan menahan konfirmasi.
OSKADON berkadar tertentu pada foto juga ditahan karena kadar rujukannya belum
tersedia. Untuk melengkapi kartu itu dibutuhkan leaflet/label resmi varian
OSKADON tablet NIE DBL8730700110A1 yang memuat kadar per tablet dan peringatan.

## Batas dan penyimpanan

OCR: Pillow memvalidasi JPEG/PNG/WebP aktual, EXIF, maksimal 20 juta piksel,
resize sisi terpanjang 1800 px (pembesaran maksimal 3× hanya untuk gambar kecil),
grayscale/autocontrast/sharpen, Tesseract `ind+eng --psm 11`, timeout 12 detik.
Foto diproses di memori; temporary files internal pytesseract memakai context
cleanup termasuk timeout. Tidak ditaruh di static. Nama file diabaikan.

Scan tersimpan **di memori proses** dengan token acak, pemilik sesi, snapshot
katalog, teks OCR terpisah dari koreksi, dan TTL 15 menit. Cookie hanya menyimpan
token pemilik; maksimal 128 scan dan 2 OCR bersamaan per proses. Entri kedaluwarsa
dihapus saat akses berikutnya. Restart menghapus semua scan. Preview satu proses
didukung; deployment multiworker memerlukan shared store/affinity (belum dibuat).
Foto sisi lain membuat scan lanjutan dengan gabungan bacaan sebelumnya dan foto baru; percakapan lama tetap terlihat. Bukti yang bertentangan tetap menahan konfirmasi. Koreksi memicu
pencarian server, dan browser tidak mengirim fakta kartu. Konfirmasi berulang
idempoten; koreksi setelah konfirmasi ditolak. Tidak ada persentase keyakinan.

Kartu selalu template deterministik. Provider chat yang ada belum menyediakan
kontrak ringkasan fakta yang dapat menjamin semua angka dan peringatan tetap utuh;
karena itu scan tidak mengirim gambar/OCR/fakta ke provider. Provider mati atau
timeout tidak menghalangi kartu. Diagnosis dan pertanyaan dosis pribadi tetap
melewati safety chat lama. Tautan kartu berasal dari katalog aplikasi; teks OCR
hanya dirender dengan textContent/value.

## Catatan pengujian

Baseline sebelum perubahan: `.venv/bin/python -m unittest discover tests`,
**160 tes lulus** dalam 27,244 detik, SQLite in-memory lewat TestingConfig;
peringatan ResourceWarning dan exception route 500 yang sengaja diuji muncul.
Log baseline lokal `/tmp/scan-baseline.log`. Tidak ada dependensi proyek diganti.

Tes endpoint baru memakai CSRF sungguhan dan SQLite terisolasi. Fixture sintetis
UJIADON hanya dibuat dalam temporary directory test. OCR dimock untuk kasus
negatif terkontrol: dua varian, NIE/nama/kadar/bentuk/sumber berlawanan, angka
kemasan, koma desimal, mg/mL/per 5 mL, timeout, engine hilang; juga memeriksa
file rusak/besar/format/piksel, manipulasi ID, sesi lain, kedaluwarsa, snapshot,
konfirmasi berulang dan tidak memanggil provider.

`test_real_oskadon_photo_via_endpoint` memakai Tesseract sungguhan dan foto lokal.
Koreksi NIE pada tes itu adalah **input test**, bukan bukti NIE terbaca dari foto.
Kebenaran fakta kartu dibandingkan record yang sumbernya diperiksa terpisah.
Satu foto tidak membuktikan akurasi umum OCR.

Uji browser opsional memakai Playwright dan Chromium yang sudah tersedia.
Tooling Playwright diunduh ke `/tmp/sehatwarga-browser-tools`, tidak ke `.venv`.
Jalankan (sesuaikan executable Chromium mesin Anda):

```sh
PYTHONPATH=/tmp/sehatwarga-browser-tools \
BROWSER_EXECUTABLE=/home/adhitya/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome \
.venv/bin/python scripts/check_medicine_scan.py
```

Script membuka server SQLite terisolasi di port 5056, menguji UI desktop dan
375 px, pratinjau tanpa upload, batal/ganti, OCR, koreksi, konfirmasi, sumber,
chat biasa, escaping dan overflow. Chart PANADOL dihasilkan khusus untuk uji OCR,
**bukan foto kemasan nyata**; foto OSKADON digunakan terpisah. Kamera fisik dan
izin kamera perangkat tidak dapat dibuktikan oleh browser headless ini.


Hasil pemeriksaan tambahan selama pengerjaan: akses DNS sandbox ke BPOM gagal,
kemudian pembacaan publik berhasil dengan izin jaringan. Browser perlu izin socket
lokal di luar sandbox. Percobaan browser awal menemukan font sistem tidak tersedia
(diganti font bawaan Pillow pada chart), sinkronisasi locator test dengan hasil
koreksi (diperbaiki), dan satu OCR chart melewati 12 detik ketika proses bersaing.
Script browser kini membatasi thread OCR dengan `OMP_THREAD_LIMIT=1`; aplikasi tetap
mengembalikan pesan timeout aman dan tombol coba lagi. Engine/language/timeout
negatif diuji dengan mock; jaringan sumber diperiksa sungguhan saat audit, bukan
saat scan. Tidak ada foto PANADOL nyata dalam checkout; alur PANADOL diuji memakai
chart dan label resmi sebagai pemeriksaan fakta, sehingga uji foto kemasan PANADOL
nyata masih perlu dilakukan oleh pemilik kemasan.

Hasil akhir:

- Regresi: `OMP_THREAD_LIMIT=1 .venv/bin/python -m unittest discover tests` —
  **176 tes lulus**, 28,461 detik (160 baseline + 16 tes scan).
- Tes scan terfokus: 16 tes lulus, mencakup penggabungan foto dan penolakan pemilik
  berbeda; payload `verified`/kartu palsu diabaikan. Context temporary file asli
  pytesseract diuji saat kegagalan engine dan tidak meninggalkan `tess_*`.
- Browser Chromium nyata: **1440 px dan 375 px lulus**, masing-masing 10 request
  scan/koreksi/konfirmasi termasuk foto tambahan, tanpa error JavaScript.
  Tesseract sungguhan, tanpa mock OCR atau respons endpoint pada uji browser.
  Screenshot `/tmp/scan-candidates-{1440,375}.png` dan
  `/tmp/scan-card-{1440,375}.png`; log `/tmp/scan-browser.log`.
- `node --check`, compileall berkas fitur, dan `git diff --check` lulus.
- Perangkat kamera nyata/izin ditolak belum diuji; jalur galeri dan atribut
  `capture=environment` diperiksa di browser. PANADOL memakai chart OCR,
  OSKADON memakai foto nyata lokal. Tidak ada klaim akurasi umum.

Berkas fitur yang ditambah/diubah:
`backend/app/__init__.py`, `backend/app/routes/assistant.py`,
`backend/app/services/medicine_scan.py`, `backend/app/data/medicines.json`,
`backend/requirements.txt`, `frontend/templates/assistant/chat.html`,
`frontend/static/js/assistant.js`, `frontend/static/css/assistant.css`,
`tests/test_medicine_scan.py`, `scripts/check_medicine_scan.py`, `SCAN_OBAT.md`.
Perubahan lokal AI/config/aset utama dan berkas pengguna lainnya dipertahankan;
tidak ada reset, commit, push, deploy, atau penimpaan `.env`.
