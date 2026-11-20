# Redesign SehatWarga — 6 November 2026

Implementasi: beranda berorientasi layanan dan pencarian; shell navy/teal dengan font lokal; lapisan dekorasi global, tilt, partikel dan orbit dihapus; chat lebih tenang dan scroll respons biasa mempertahankan posisi pembaca. Drawer, sidebar admin, tabel mobile, form, status, print, otorisasi dan kontrak scan yang sudah tersedia dipertahankan. Tidak ada perubahan database/backend, .env, commit atau deployment.

Halaman yang menerima gaya bersama: publik (beranda, direktori/detail fasilitas), autentikasi, dashboard/profil/kartu/keluarga/layanan/iuran/pembayaran/pengaduan warga, seluruh halaman admin, asisten, halaman error. Template beranda dan shell diubah langsung; halaman lain memakai komponen bersama yang sudah ada. Ini belum merupakan audit interaksi lengkap setiap halaman.

Komponen: token warna/ukuran/container/fokus; tombol 44px; kartu, badge, tabel responsif, form, summary panel, disclosure, drawer dengan fokus, footer. Tidak memasang framework frontend.

Berkas yang diubah dalam pekerjaan ini:
- frontend/templates/base.html
- frontend/templates/public/home.html
- frontend/static/css/main.css
- frontend/static/css/assistant.css
- frontend/static/js/main.js
- frontend/static/js/assistant.js
- scripts/check_browser.py
- qa/REDESIGN_CURRENT.md

Perubahan lokal lain sudah ada sebelum pekerjaan dan tidak dibuat oleh redesign ini. Penyesuaian stylesheet/JS dilakukan di atas perubahan lokal, termasuk mempertahankan pemuatan peta dan fitur scan.

Referensi dibaca langsung sebagai konten web: https://www.onemedical.com/, https://www.zocdoc.com/, https://www.nhs.uk/, https://service-manual.nhs.uk/design-system, https://satusehat.kemkes.go.id/mobile/. Interaksi/visual referensi tidak diperiksa dengan browser.

Menjalankan preview terisolasi:
```
.venv/bin/python scripts/preview.py
# http://127.0.0.1:5055
```
Gunakan akun demo yang didokumentasikan README. Untuk konfigurasi lokal yang sudah ada: `.venv/bin/python run.py`.

Pengujian aktual:
- `.venv/bin/python -m unittest discover tests`: baseline 176 lulus (28,518 detik), sesudah perubahan 176 lulus (27,296 detik).
- `.venv/bin/python -m unittest tests.test_render_routes tests.test_medicine_scan`: 17 lulus (4,163 detik), setelah penyesuaian akhir.
- `git diff --check`: lulus.
- Browser QA awal gagal karena Playwright belum tersedia. Playwright kemudian dipasang; Chromium memerlukan unduhan besar yang belum selesai. Tidak ada screenshot baru yang tervalidasi. Screenshot lama dalam qa tidak menjadi bukti pekerjaan ini.

Pemeriksaan tertunda: visual aktual 360/375/768/1024/1440; login/logout browser; keyboard/drawer; error formulir; filter; upload/foto/pratinjau dan hasil chat; cetak kartu/kuitansi; data panjang dan empty state. Tes render bukan bukti layout. Skrip browser diperluas untuk 360px serta screenshot fasilitas, tetapi belum berhasil dijalankan sampai akhir. Jangan menyatakan target redesign menyeluruh sudah tervalidasi.
