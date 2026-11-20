# Laporan integrasi Mapbox — 17 November 2026

Peta interaktif sudah diganti dari Leaflet/tiles OpenStreetMap ke Mapbox GL JS
(Mapbox Streets). Token publik pengguna disimpan di `.env` lokal yang diabaikan
Git. Tampilan hero, carousel, logo, warna, dan CSS utama sebelum 15 November
dipertahankan. Tidak ada perubahan database atau pengaktifan integrasi MSI.

## Hasil perbandingan langsung

| Pemeriksaan | Hasil |
| --- | --- |
| Token / Styles API Mapbox | HTTP 200, Mapbox Streets |
| Katalog database aplikasi aktif (query read-only aktual) | 7 fasilitas |
| Mapbox kategori hospital, sekitar Lamongan | 25 hasil tempat |
| Mapbox kategori hospital, sekitar Surabaya | 25 hasil tempat |
| Mapbox pencarian nama Soegiri, Lamongan | 10 hasil tempat |
| Mapbox pencarian Puskesmas, Lamongan | 10 hasil tempat |

Hasil Mapbox lebih banyak dibanding **katalog internal yang saat ini dipakai
aplikasi**. Sebelumnya OpenStreetMap menyediakan gambar peta; daftar/marker dan
pencarian SehatWarga tetap berasal dari database internal, bukan pencarian semua
rumah sakit dalam database OpenStreetMap. Karena itu, angka di atas tidak
membuktikan cakupan Mapbox lebih lengkap daripada OpenStreetMap secara global.
Mapbox Streets sendiri menggunakan beberapa sumber termasuk OpenStreetMap.

Angka 25 adalah batas respons kategori, bukan total fasilitas di kota tersebut.
Pencarian nama dibatasi API menjadi 10. Beberapa hasil adalah unit seperti IGD,
laboratorium, dan ruang rawat dalam satu rumah sakit. Ditemukan pula kategori
meragukan, misalnya nama tempat yang tampak bukan rumah sakit. Tidak ada klaim
25 rumah sakit unik atau ketersediaan dokter/layanan/jam buka yang terverifikasi.

## Perubahan yang dapat digunakan

- Beranda dan direktori mempunyai formulir pencarian Mapbox: kota, nama,
  rumah sakit, klinik, puskesmas, dokter gigi, apotek, dan semua layanan kesehatan.
- Pencarian awal dimuat ketika bagian direktori terlihat. Pencarian berikutnya
  melalui tombol Cari atau filter jenis. Lokasi perangkat hanya diminta melalui
  tombol berikon lokasi dengan label Cari fasilitas di dekat saya.
- Daftar ringkas di kiri menampilkan nama dan alamat; memilih kartu menyorot
  lokasi pada peta di kanan. Pada ponsel, peta dan daftar disusun vertikal.
- Marker/popup/zoom memakai Mapbox. Peta katalog internal, detail, dan Asisten
  juga memakai Mapbox; pencarian Asisten masih memakai katalog internal.
- Katalog internal tetap terpisah untuk pengajuan layanan simulasi. Hasil
  Mapbox tidak otomatis menjadi fasilitas terdaftar dan tidak dipakai untuk
  membuat pengajuan layanan atau janji berobat.
- Hasil tidak disimpan ke database/browser storage, respons pencarian no-store.
  Error token, koneksi, waktu tunggu, dan kuota ditampilkan tanpa membocorkan URL
  bertoken. Ada batas 45 pencarian/menit dan 3 request bersamaan per proses.

## Validasi

- `python -m unittest discover -s tests -q`: **234 tes PASS**, termasuk 9 tes baru
  untuk API, validasi koordinat, token rahasia, normalisasi, kuota, dan kegagalan.
- Browser Chromium dengan database preview terisolasi: ukuran 1440 dan 375 px;
  pencarian live mengembalikan 25 kartu di kedua ukuran; peta live selesai dimuat,
  popup bekerja, halaman beranda/detail/Asisten berjalan, error 429 tertangani,
  tanpa JavaScript exception.
- Bukti pemeriksaan di `qa/mapbox-integration/browser-results.json`; screenshot
  beranda/direktori tersedia dalam folder yang sama.
- Pemeriksaan sintaks JavaScript dan `git diff --check`: PASS.
- Database aktual hanya dibaca untuk jumlah fasilitas. Tidak ada seed/migrasi
  atau perubahan data aktual selama pekerjaan ini.

## Batasan dan referensi

Dokumentasi Search Box yang diperiksa masih menyebut dukungan AS, Kanada, dan
Eropa, sedangkan request Indonesia dengan token ini berhasil pada pengujian
langsung. Hasil live bukan jaminan cakupan/dukungan Indonesia untuk masa depan.
Penggunaan peta dan pencarian mengikuti kuota serta penagihan akun Mapbox;
tidak ada janji penggunaan gratis tanpa batas. Hasil POI hanya dipakai sementara.

- [Search Box API, batas hasil, geografi, dan penggunaan sementara](https://docs.mapbox.com/api/search/search-box/)
- [Sumber data Mapbox Streets](https://docs.mapbox.com/data/tilesets/reference/mapbox-streets-v8/)
- [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/)

Untuk memakai konfigurasi baru pada server yang sudah berjalan, restart proses
aplikasi lalu muat ulang halaman. Preview pengujian tidak mengubah database
aktual dan tidak dipertahankan sebagai server permanen.

## Penyesuaian tata letak sesuai referensi

Referensi lokal: `image/refernesimap/map.png`. Formulir ringkas, filter jenis
berupa tombol pilihan, daftar ber-scroll di kiri, dan peta persisten di kanan.
Latar dekorasi peta pada bagian ini disederhanakan agar tidak bersaing dengan
peta interaktif. Keterangan batasan dipindah ke disclosure.
Browser diverifikasi pada 320, 375, 768, 1024, dan 1440 px: tanpa overflow
halaman, kartu/popup/filter berfungsi, error mempertahankan hasil sebelumnya,
empty state dan teks aman. Bukti: `qa/mapbox-layout/results.json`.
10 tes API dan render terkait lulus sesudah perubahan tata letak.
