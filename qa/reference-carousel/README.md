# Redesign carousel berdasarkan referensi

Acuan visual adalah keempat gambar di `image/sehatwarga-carousel-individual/`, yang telah dikonfirmasi pengguna. Gambar referensi tidak dipakai sebagai background atau screenshot UI di website.

Banner dibangun ulang dengan HTML/Jinja, CSS gradient teal–cyan, dan tiga bentuk gelombang diagonal SVG. Nomor, ikon kategori, judul putih, deskripsi, dan CTA putih tetap merupakan elemen HTML yang dapat diakses. Ilustrasi 3D ditampilkan sebagai empat PNG transparan terpisah, tanpa tulisan yang dipanggang ke gambar.

Tinggi desktop berada di 270–300px, dengan teks memakai sekitar 55% ruang isi dan elemen ilustrasi sekitar 43% sisi kanan. `object-fit: contain` dan ruang tepi menjaga gambar tetap utuh. Pada mobile, panel 500px menempatkan ilustrasi di bawah teks, dan gelombang hanya melewati area bawah agar teks tetap terbaca.

Empat varian menggunakan palet teal/cyan yang berdekatan dengan aksen gelombang berbeda serta konsep ilustrasi masing-masing:

| Layanan | Aset runtime | Screenshot desktop | Screenshot mobile |
| --- | --- | --- | --- |
| Kepesertaan & keluarga | [PNG](../../frontend/static/images/services-3d/01-kepesertaan-keluarga.png) | [1440px](slide-01-1440.png) | [375px](slide-01-375.png) |
| Pengajuan layanan | [PNG](../../frontend/static/images/services-3d/02-pengajuan-layanan.png) | [1440px](slide-02-1440.png) | [375px](slide-02-375.png) |
| Iuran & pembayaran | [PNG](../../frontend/static/images/services-3d/03-iuran-pembayaran.png) | [1440px](slide-03-1440.png) | [375px](slide-03-375.png) |
| Pengaduan | [PNG](../../frontend/static/images/services-3d/04-pengaduan.png) | [1440px](slide-04-1440.png) | [375px](slide-04-375.png) |

Aset dibuat menggunakan built-in **image_gen**, satu generasi per konsep, dengan transparansi. Semua PNG berukuran 1536 × 1024 dan disimpan di `frontend/static/images/services-3d/`. [Prompt lengkap](prompts.md).

Dibandingkan dengan referensi: gradasi gelap di kiri, gelombang diagonal berlapis, kartu nomor putih, ikon kategori, CTA putih, dan kumpulan objek 3D di kanan dipertahankan sebagai karakter utama. Teks referensi dibangun sebagai HTML; kontrol navigasi tetap di luar banner agar ilustrasi tidak tertutup. Material keramik putih, tepi teal/biru, detail dokumen, dan bayangan alami digunakan secara konsisten pada aset baru.

## Verifikasi

**137 pemeriksaan browser lulus, 0 gagal.** [Hasil lengkap](checks.json).

Ukuran yang diperiksa: 1366 × 768, 1440 × 900, 1920 × 1080, 768 × 1024, 375 × 812, dan 320 × 740. Keempat slide pada setiap ukuran diperiksa dan diambil screenshot-nya. Hasil akhir juga diperiksa secara visual terhadap keempat referensi.

Cakupan: ilustrasi termuat dan transparan, mapping kategori, gambar utuh dalam panel, CTA berada di dalam banner, tinggi panel stabil, alignment container, tidak ada horizontal overflow, urutan 01→02→03→04→01, durasi diam empat detik, transisi kanan ke kiri, previous/next, pause/play, hover, fokus keyboard, offscreen, visibility, reduced motion, klik berulang, route layanan asli, dan fallback tanpa JavaScript. Tidak ada exception JavaScript.

Timer dan state machine di `service-showcase.js` tidak diubah: durasi transisi tetap 480ms dan dwell tetap 4000ms. Hero dibandingkan langsung dengan snapshot template sebelum perubahan dan isinya identik. Navbar, backend Flask, database aplikasi, routing, dan autentikasi tidak disentuh.

QA memakai Chromium dan Flask preview dengan SQLite sementara, bukan database aplikasi. CDN peta diblokir selama QA navigasi; tab tersembunyi diuji melalui simulasi property/event visibility, sedangkan offscreen diuji melalui scroll browser.

Jalankan ulang:

```sh
BROWSER_EXECUTABLE=/path/to/chromium .venv/bin/python scripts/check_service_showcase.py
```
