# Verifikasi alignment, navbar, dan logo

Quick Services, Direktori Fasilitas, Panduan, Tentang Kami, footer landing, dan navbar publik/warga memakai `.page-container`: lebar maksimum 1680px dan gutter `clamp(20px, 3vw, 48px)`, mengikuti container Direktori yang sudah ada. Hero, formulir, callout bantuan, dan sidebar admin mempertahankan komposisi khususnya.

Quick Services menggunakan Grid 21:79 dengan empat kartu sejajar di desktop, dua kolom pada tablet, dan satu kolom pada mobile. Konten, font, ikon, warna kartu, background mint, gelombang, dan ilustrasi hero dipertahankan.

Navbar sticky yang sudah ada dipertahankan, dengan tinggi konsisten 70px, latar putih, border tipis, chevron SVG, avatar inisial, nama yang dipotong bila panjang, dan indikator teal pada submenu aktif. Layanan tetap merupakan tautan karena belum memiliki submenu. Route, form logout beserta CSRF, autentikasi, backend, dan database aplikasi tidak diubah.

Logo `image/logo.png` disalin utuh ke `frontend/static/images/sehatwarga-logo.png`. PNG RGBA 2172 × 724 tetap transparan dan tidak dipotong atau diubah. Lebar tampilan navbar 210px, 190px pada desktop kecil, dan 180px pada mobile; tinggi mengikuti rasio asli. Navbar dan footer bersama menjangkau login, dashboard, dan Asisten tanpa wordmark/tagline HTML tambahan.

## Perbandingan posisi

Posisi di bawah adalah tepi konten dari kiri viewport, dalam CSS pixel. Nilai Direktori tidak berubah.

| Viewport | Quick Services sebelum | Quick Services sesudah | Direktori dan navbar sesudah |
| --- | ---: | ---: | ---: |
| 1366 × 768 | 52 | 40.98 | 40.98 |
| 1440 × 900 | 52 | 43.20 | 43.20 |
| 1920 × 1080 | 280 | 168 | 168 |

Screenshot landing publik sebelum/sesudah:

| Resolusi | Sebelum | Sesudah |
| --- | --- | --- |
| 1366 × 768 | [Screenshot](before/public-1366.png) | [Screenshot](after/public-1366.png) |
| 1440 × 900 | [Screenshot](before/public-1440.png) | [Screenshot](after/public-1440.png) |
| 1920 × 1080 | [Screenshot](before/public-1920.png) | [Screenshot](after/public-1920.png) |
| 375 × 812 | [Screenshot](before/public-375.png) | [Screenshot](after/public-375.png) |

Ukuran tambahan: 1024 × 768, 768 × 1024, dan 320 × 740. Pengukuran lengkap tersimpan di `before/metrics.json` dan `after/metrics.json`.

## Browser QA

Jalankan dari root proyek:

```sh
BROWSER_EXECUTABLE=/path/to/chromium .venv/bin/python scripts/check_layout_navbar.py
```

Script menggunakan Chromium dan Flask dengan SQLite sementara dari `scripts/preview.py`; `.env` dan database aplikasi tidak digunakan. Cakupan pemeriksaan:

- Container sejajar, tinggi navbar, rasio logo, empat kartu satu baris, dan overflow.
- Tidak ada tabrakan logo, menu, dan profil pada desktop maupun mobile.
- Drawer mobile, focus trap, Escape, dan pemulihan fokus.
- Dropdown Administrasi dan profil, penutupan lewat klik di luar dan Escape.
- Seluruh tujuan link navigasi publik, warga, dan admin menghasilkan HTTP 200.
- Login, dashboard, profil, kartu digital, keluarga, dan Asisten menampilkan logo bersama.
- Form logout warga dan admin tetap bekerja.
- Tidak ada exception JavaScript.

Hasil akhir berada di [checks.json](checks.json). Screenshot navbar, dropdown, drawer, login, dashboard, dan Asisten tersedia di folder ini. CDN peta diblokir selama pengujian navigasi agar pemeriksaan aset lokal tidak bergantung pada jaringan eksternal; fungsi peta bukan bagian dari perubahan ini.
