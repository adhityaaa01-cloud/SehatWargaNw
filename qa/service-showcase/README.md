# Service showcase SehatWarga

Quick Services kini menampilkan satu panel layanan selebar container, dengan teks dan CTA di kiri serta ilustrasi kategori di kanan. Header layanan, mint background, dan alignment dengan Direktori dipertahankan. Panel desktop dikembalikan ke tinggi ringkas 220px; pada mobile panel setinggi 460px dengan teks di atas dan ilustrasi di bawah. Kontrol pause/play kini hanya menampilkan ikon, dengan label aksesibel tetap tersedia.

Setiap slide diam selama **4000ms**, kemudian bergeser dari kanan ke kiri selama **480ms** menggunakan `translateX`, opacity, dan `cubic-bezier(0.22, 1, 0.36, 1)`. Timer baru dimulai setelah transisi selesai. Urutan berulang 01 → 02 → 03 → 04 → 01.

| Slide | File PNG asli | Route layanan |
| --- | --- | --- |
| Kepesertaan & keluarga | `01-kepesertaan-keluarga.png` | `/citizen/family` |
| Pengajuan layanan | `02-pengajuan-layanan.png` | `/citizen/services` |
| Iuran & pembayaran | `03-iuran-pembayaran.png` | `/citizen/contributions` |
| Pengaduan | `04-pengaduan.png` | `/citizen/complaints` |

PNG disalin dari `image/sehatwarga_slide_backgrounds/` ke `frontend/static/images/services/` tanpa perubahan byte. Background dikembalikan ke `background-size: cover` dan `background-position: center`, mengikuti komposisi panel ringkas sebelumnya. Area ilustrasi mobile setinggi 160px. Preload keempat background dan tinggi viewport tetap mencegah perubahan ukuran panel saat gambar dimuat atau slide berganti.

Kontrol meliputi previous, next, pause/play, nomor posisi, dan empat segmen progress. Autoplay berhenti saat showcase tidak terlihat, tab tidak aktif, pointer berada di atas showcase, atau fokus keyboard berada di dalamnya. Setiap perubahan manual membatalkan timer lama. Transisi dikunci agar klik berulang tidak memulai transisi bersamaan.

Reduced motion menonaktifkan autoplay saat awal dan menghilangkan gerakan transisi; pengguna tetap dapat memilih layanan secara manual atau mengaktifkan autoplay sendiri. Slide tidak aktif memakai `hidden`, `inert`, dan `aria-hidden`, sehingga CTA tersembunyi tidak masuk urutan Tab. Pergantian otomatis tidak memindahkan fokus atau membacakan pengumuman berulang. Tanpa JavaScript, empat panel dan link layanan tetap tersedia sebagai daftar statis.

Tidak ada perubahan backend, database aplikasi, routing, autentikasi, hero, navbar, atau section lain. Animasi masuk empat kartu lama dihapus dari `main.js` karena digantikan oleh showcase.

## Hasil browser

Panel besar 8:3 telah dibatalkan sesuai permintaan; kontrol pause/play tetap berupa ikon. Hasil pengujian interaksi carousel awal (220px): 137 lulus, [checks.json](checks.json). Artefak `uncropped-*` dan `refinement-checks.json` merekam versi panel besar sebelum dibatalkan.

Diuji melalui Chromium dengan Flask preview dan SQLite sementara. Pengujian tidak membaca `.env` atau menggunakan database aplikasi. CDN peta diblokir agar uji showcase tidak bergantung pada jaringan eksternal. Kondisi tab tersembunyi disimulasikan melalui properti dan event visibility; kondisi offscreen diuji dengan scroll browser.

Cakupan: durasi diam empat detik, urutan autoplay dan loop, arah dan opacity saat transisi, pause/play, hover, fokus CTA, visibility, offscreen, klik berulang, previous/next, pemetaan background, keutuhan PNG, ukuran panel, alignment, horizontal overflow, reduced motion, fallback tanpa JavaScript, serta pembukaan route asli melalui keyboard.

Screenshot setiap slide tersedia untuk 1366 × 768, 1440 × 900, 1920 × 1080, 768 × 1024, 375 × 812, dan 320 × 740.

| Slide | Desktop 1440px | Mobile 375px |
| --- | --- | --- |
| 01 | [Screenshot](slide-01-1440.png) | [Screenshot](slide-01-375.png) |
| 02 | [Screenshot](slide-02-1440.png) | [Screenshot](slide-02-375.png) |
| 03 | [Screenshot](slide-03-1440.png) | [Screenshot](slide-03-375.png) |
| 04 | [Screenshot](slide-04-1440.png) | [Screenshot](slide-04-375.png) |

[Transisi sedang berlangsung](transition.png). Screenshot dengan konteks halaman tersedia di `page-slide-01.png` sampai `page-slide-04.png`.

Jalankan ulang dari root proyek:

```sh
BROWSER_EXECUTABLE=/path/to/chromium .venv/bin/python scripts/check_service_showcase.py
```

Implementasi ada di `frontend/templates/public/home.html`, bagian Quick Services pada `frontend/static/css/main.css`, dan `frontend/static/js/service-showcase.js`. Browser QA layout sebelumnya juga diperbarui agar memeriksa satu panel dari empat layanan.
