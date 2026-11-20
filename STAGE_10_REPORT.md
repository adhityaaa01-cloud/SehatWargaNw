# SEHATWARGA — STAGE 10 VERIFICATION

Tanggal: 13 November 2026.

**FINAL STATUS: NEEDS ATTENTION**

Seluruh workflow kritis yang **sudah diimplementasikan** berhasil diuji pada
Chromium dan database dummy. Tiga bug diperbaiki dan seluruh regresi lulus.
Namun, skenario perubahan profil yang diminta belum dapat diverifikasi:
aplikasi hanya memiliki profil read-only, tanpa form, service, atau endpoint
edit profil. Stage 10 tidak menambahkan fitur tersebut sesuai larangan fitur baru.
Karena itu laporan ini tidak menyatakan seluruh skenario permintaan sudah PASS.

## Hasil verifikasi

| Item | Status | Bukti/cakupan |
| --- | --- | --- |
| REGISTRATION | PASS | Register browser dua warga dummy; User + Participant tersimpan; nomor peserta, kelas, status; email duplikat ditolak tanpa menambah akun. |
| LOGIN | PASS | Kredensial salah ditolak; warga/admin ke dashboard sesuai role; sesi bertahan; logout menghilangkan akses. |
| PROFILE | FAIL untuk cakupan lengkap permintaan | Pembacaan identitas PASS; POST ditolak 405 dan data tetap. Update profil belum tersedia, sehingga uji ubah/simpan profil tidak dilakukan. Ini keterbatasan existing, bukan regresi. |
| PARTICIPANT CARD | PASS | Nama, nomor peserta, kelas, status cocok dengan akun baru dan database dummy. |
| FAMILY | PASS | Daftar, tambah, edit, persistensi, nonaktifkan; anggota nonaktif hilang dari pilihan pengajuan; ownership GET/POST diuji. |
| FACILITIES | PASS | Pencarian dan filter jenis lewat form; detail; Leaflet asli, marker dan tile OpenStreetMap; koordinat dari fixture DB. Kasus koordinat nol dan null diuji terpisah. |
| SERVICE REQUEST | PASS | Pengajuan diri sendiri dan keluarga melalui form; fasilitas, jenis, tanggal dan kebutuhan; nomor pengajuan dan SUBMITTED terverifikasi. REJECTED dan CANCELLED juga diuji. |
| ADMIN VERIFICATION | PASS | Admin membuka daftar/detail dan memverifikasi kedua pengajuan lewat form browser. |
| SERVICE SCHEDULING | PASS | VERIFIED → SCHEDULED → COMPLETED untuk diri sendiri dan keluarga. |
| SERVICE HISTORY | PASS | Urutan SUBMITTED, VERIFIED, SCHEDULED, COMPLETED; actor warga/admin; indikator riwayat tampil pada halaman warga. Invalid jump tidak mengubah status/riwayat. |
| CONTRIBUTIONS | PASS | Generate periode dummy tahun berikutnya lewat admin; pengulangan tidak menambah tagihan; nominal CLASS_2 Rp100.000, jatuh tempo tanggal 10, status awal. Unique constraint diuji pada DB dummy dan diperiksa read-only pada DB terkonfigurasi. Tarif kelas lain dicakup regresi existing. |
| SIMULATED PAYMENT | PASS | Persetujuan dan metode simulasi, SUCCESS dan PAID; input amount=1 diabaikan; metode invalid/tanpa persetujuan ditolak; pembayaran ulang tidak membuat transaksi kedua. |
| PAYMENT RECEIPT | PASS | Riwayat membuka kuitansi; identitas, nomor, nominal benar; admin melihat transaksi dan tagihan lunas. Detail administratif existing diakses melalui rincian iuran, tanpa membuat route baru. |
| COMPLAINT | PASS | Tiket OPEN; admin mulai IN_PROGRESS, memberi respons lalu RESOLVED atau REJECTED; warga melihat respons/status terbaru. |
| ROLE AUTHORIZATION | PASS | GET halaman admin dan POST endpoint mutasi admin ditolak 403 untuk warga; guest dialihkan ke login; CSRF hilang ditolak 400. |
| OWNERSHIP | PASS | Sesi warga kedua menerima 404 untuk keluarga, pengajuan, iuran, pembayaran, pengaduan warga pertama; mutation probes memakai CSRF sah; data target tetap utuh. Query participant_id tidak mengubah pemilik profil. |
| PRINT CARD | MANUAL CHECK | Layout A4, tombol cetak, data lengkap, navbar/action tersembunyi, nama panjang tidak terpotong: PASS otomatis dan inspeksi visual PDF. Dialog printer dan hasil kertas fisik: MANUAL CHECK REQUIRED. |
| PRINT RECEIPT | MANUAL CHECK | PDF A4 satu halaman, identitas/nominal lengkap, waktu WIB, navbar/action tersembunyi: PASS otomatis dan inspeksi visual. Dialog printer/kertas: MANUAL CHECK REQUIRED. |
| RESPONSIVE | PASS pada Chromium | 375, 768, 1024, 1440px; form, daftar/tabel, detail fasilitas/peta, navbar drawer, chat dan halaman transaksi. Firefox/Safari/perangkat fisik: MANUAL CHECK REQUIRED. |
| EXISTING REGRESSION | PASS | Semua existing test tetap dijalankan; tidak ada assertion existing diubah atau test dihapus/dilewati. |

## Inspection dan keamanan pengujian

- Backend: Flask application factory, SQLAlchemy, Flask-Login, Flask-WTF/CSRF,
  Flask-Migrate/Alembic; role `citizen` dan `admin` melalui `role_required`.
- Frontend: Jinja, CSS/JS existing, font/aset lokal; Leaflet/OpenStreetMap untuk peta.
- Blueprint aktual: `main`, `auth`, `citizen`, `admin`, `facilities`, `assistant`.
  Daftar route lengkap tersimpan pada `qa/stage10/technical-audit.json`.
- Model aktual: User, Participant, FamilyMember, HealthFacility, ServiceRequest,
  ServiceHistory, Contribution, Payment, Complaint. Form dan service terkait
  digunakan melalui route asli; tidak ada API bisnis pengganti dalam pengujian.
- `seed-demo` existing digunakan pada SQLite in-memory khusus proses browser.
  Dua warga tambahan dibuat lewat browser. Admin demo hanya berada di DB dummy itu.
- `scripts/preview.py` / `tests.create_test_app()` menonaktifkan dotenv,
  menetapkan TestingConfig sebelum inisialisasi extension, dan membuat schema
  **hanya pada SQLite disposable**. CSRF tetap aktif. Provider chat fallback.
- Pengujian HTTP memakai empat browser context terpisah untuk warga pertama,
  warga kedua, admin, dan guest. Data hasil UI diperiksa kembali melalui query
  pada database dummy. Tidak menggunakan sesi atau data pengguna nyata.
- Akses DB terkonfigurasi hanya query versi migrasi, versi server dan metadata
  index; koneksi di-rollback. Tidak ada INSERT/UPDATE/DELETE/DDL pada DB itu.
- Tidak ada migrasi, downgrade, reset DB pengguna, email, pembayaran nyata,
  perubahan `.env`, commit, push, deployment, atau pekerjaan Stage 11–16.
- Workspace sudah dirty sebelum Stage 10. Perubahan AI, redesign, scan, aset,
  dan dokumen pengguna dipertahankan. Daftar perubahan di bawah khusus Stage 10.

## Bug dan perbaikan

1. **Waktu UTC dilabeli WIB tanpa konversi.**
   Kuitansi, profil, keluarga dan rincian iuran memformat datetime UTC langsung
   kemudian menambahkan label WIB. Contoh fixture `2026-01-01 20:30 UTC`
   seharusnya tampil `02 January 2026 03:30 WIB`.
   Filter Jinja `wib_datetime` sekarang mengonversi datetime naive UTC maupun
   aware ke Asia/Jakarta. Penyimpanan database tetap UTC; nilai data tidak diubah.
   Regresi memeriksa rollover tanggal/tahun, kuitansi, profil, dan rincian admin.
   Perubahan difokuskan pada timestamp yang sebelumnya secara eksplisit diberi
   label WIB; ini bukan perubahan global penyimpanan atau semua format waktu.

2. **Peta detail hilang untuk koordinat bernilai nol.**
   Kondisi template `latitude and longitude` menganggap nol sebagai koordinat
   kosong. Template memakai `map_facility` dari route existing, yang membedakan
   nol dari null. Tiga kombinasi nol harus merender map container; dua kombinasi
   null tetap menampilkan pesan lokasi belum tersedia.

3. **Nama panjang terpotong pada kartu cetak.**
   Aturan `white-space: nowrap` dan ellipsis untuk layar ikut berlaku saat print.
   Uji nama dummy 93 karakter membuktikan overflow pada media print.
   Aturan khusus print sekarang membungkus nama; tampilan layar tetap sama.
   Browser regression memeriksa scrollWidth/clientWidth dan scrollHeight/clientHeight,
   lalu PDF diperiksa secara visual dan melalui ekstraksi teks.
   Bukti sebelum: `qa/stage10/long-name-card-before-fix.png` dan
   `qa/stage10/browser-before-print-fix.json`.

Tes regresi tambahan sebelum fix mencatat kegagalan timestamp/koordinat pada
`qa/stage10/regressions-before-fix.txt`; sesudah fix seluruhnya lulus pada
`qa/stage10/regressions-after-fix.txt`.

Beberapa kegagalan awal berasal dari harness, bukan aplikasi: port 5060 diblokir
Chromium sehingga diganti 5070; pemeriksaan nama memperhitungkan transformasi
uppercase CSS dan whitespace template; label riwayat disesuaikan dengan label
existing sembari tetap memeriksa status/actor database dan urutan DOM;
stub `window.print` diperbaiki agar tidak dieksekusi otomatis saat dipasang oleh
Playwright; konteks Flask untuk pengujian dua role dipisahkan agar current_user
tidak tercache antar-request. Tidak ada assertion existing yang dilonggarkan.

## Database dan migration

**DATABASE: Unchanged** — database aplikasi terkonfigurasi.

**MIGRATION: 3dfb67eddef4 (head)** — current == head, PASS.

Server aktual melaporkan **8.0.11-TiDB-v8.5.3-serverless**, yaitu TiDB kompatibel
MySQL. Penyebutan MariaDB pada dokumentasi umum tidak sesuai vendor endpoint
lokal saat audit. Metadata database aktual memiliki unique constraint pasangan
`participant_id` + `billing_period`.

Workflow yang mengubah data diuji pada **SQLite in-memory**, bukan MariaDB/TiDB.
Ini membuktikan integrasi browser–Flask–ORM dan business workflow pada database
test, bukan validasi concurrency atau transaksi produksi TiDB/MariaDB.
Skema dan file migration tidak diubah.

Perintah awal di sandbox tidak dapat membuka socket browser/database. Pengujian
lokal dan query read-only diulang dengan izin eksekusi di luar sandbox.
Server DB tidak mendukung `SET TRANSACTION READ ONLY`; audit akhir hanya membaca
versi/metadata dan melakukan rollback, tanpa perintah mutasi.

Bukti: `qa/stage10/database-audit.json`.

## Test summary

| Pengujian | Hasil |
| --- | --- |
| Baseline tests ditemukan aktual | 193 PASS, 88 subtests PASS, 28.77 detik |
| Tes regresi Stage 10 baru | 4 PASS, 5 subtests PASS |
| Tests after fixing | 197 PASS, 93 subtests PASS, 46.44 detik |
| Browser checks | 274 PASS, 0 FAIL |
| Browser JavaScript exceptions | 0 |
| Failed (final automated tests) | 0 |
| Errors (final automated tests) | 0 |
| Existing test skipped/removed | 0 |
| Python compile | PASS |
| pip check | PASS — No broken requirements found |
| Flask routes | PASS |
| Database current/head | PASS |
| Git diff check | PASS |
| Migration diff | Empty |

756 peringatan pada regresi akhir berasal dari deprecation `datetime.utcnow`
SQLAlchemy dan typing google-genai existing. Jumlah pengujian ditemukan dari
run repository aktual, bukan angka tetap dari laporan lama.

Angka automated FAIL=0 tidak berarti skenario edit profil telah dikerjakan:
pengujian secara eksplisit memverifikasi kontrak read-only existing; kesenjangan
dengan permintaan update profil ditulis sebagai PROFILE FAIL di matriks.

## Files modified / added khusus Stage 10

Diubah:

- `backend/app/__init__.py` — tambahan filter timestamp WIB; edit lain yang sudah
  ada sebelum Stage 10 dipertahankan.
- `frontend/templates/citizen/payments/detail.html`
- `frontend/templates/citizen/profile.html`
- `frontend/templates/citizen/family/detail.html`
- `frontend/templates/citizen/contributions/detail.html`
- `frontend/templates/admin/contributions/detail.html`
- `frontend/templates/public/facilities/detail.html`
- `frontend/static/css/main.css` — hanya tambahan wrapping nama pada media print
  dari pekerjaan ini; redesign existing tidak di-reset.

Ditambah:

- `tests/test_stage10.py`
- `scripts/check_stage10_browser.py`
- `scripts/audit_stage10_database.py`
- `STAGE_10_REPORT.md`
- `qa/stage10/` — baseline, log regresi, audit teknis/database, hasil browser,
  screenshot empat ukuran, PDF kartu biasa/nama panjang/kuitansi, bukti sebelum fix.

## Known issues / manual checks

- **Profil read-only:** edit/simpan profil tidak tersedia. Tidak ditambahkan pada
  tahap verification ini. Ini alasan status akhir NEEDS ATTENTION.
- **Printer fisik/dialog:** MANUAL CHECK REQUIRED. Pemanggilan tombol print dan
  layout PDF A4 berhasil diuji, bukan interaksi dengan spooler/printer nyata.
- Firefox, Safari, perangkat fisik dan keyboard virtual: MANUAL CHECK REQUIRED.
- Provider AI nyata tidak diaktifkan atau diperiksa ulang. Browser Stage 10
  menguji fallback lokal; kegagalan koneksi Ollama pada Stage 9.1 belum dapat
  dinyatakan selesai. Existing provider tests tetap menggunakan mock.
- Leaflet/marker dan tile detail nyata berhasil dimuat. Sejumlah request tile
  eksternal gagal/dibatalkan selama navigasi; tidak ada klaim semua tile selalu
  tersedia. Hasil fasilitas tetap tersedia tanpa peta.
- Scan backend dicakup regresi existing. UI scan yang sebelumnya dilepas dari
  chat tidak diaktifkan kembali; kamera fisik bukan cakupan browser Stage 10.
- Tes tidak mencakup beban serentak, multiworker, pembayaran serentak pada
  TiDB/MariaDB atau validasi ulang mutu model AI nyata.

## Reproduce

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_stage10.py -q
.venv/bin/python scripts/check_stage10_browser.py
.venv/bin/python scripts/audit_stage10_database.py
```

Browser otomatis memakai Chromium existing bila tersedia pada lokasi default
mesin audit. Untuk mesin lain, set `BROWSER_EXECUTABLE` ke binary Chromium yang
tersedia. Browser test membuka port lokal 5070, memakai SQLite baru setiap run,
dan mematikan server setelah selesai. Audit database adalah script terpisah
yang membaca konfigurasi backend existing dan tidak mencetak kredensial.

**Berhenti pada Stage 10. Tidak ada fitur baru atau pekerjaan Stage 11–16.**
