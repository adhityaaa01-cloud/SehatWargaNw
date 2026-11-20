# Asisten SehatWarga

Flask/Jinja2 Stage 9 dipertahankan. Assistant hanya membaca: tidak mempunyai tool SQL,
shell, atau tindakan bisnis. Fasilitas menggunakan facility_service dan HealthFacility;
ringkasan kepesertaan existing tetap diperiksa melalui current_user dan role warga aktif.
Pengajuan, pembayaran, dan pengaduan harus dilakukan lewat halaman akun yang berotorisasi.

## Konfigurasi

Root `.env` dimuat oleh backend/config.py, kecuali mode testing atau dotenv dinonaktifkan.
Restart aplikasi setelah mengganti konfigurasi. Jangan menaruh credential pada frontend.

```dotenv
AI_PROVIDER=fallback
AI_API_KEY=
AI_MODEL=
AI_TIMEOUT_MS=15000
# Untuk provider Ollama yang sudah digunakan proyek:
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest
OLLAMA_TIMEOUT_SECONDS=35
```

`AI_PROVIDER`: fallback, ollama, groq, atau gemini. Jangan mengganti provider hanya karena
koneksi gagal. Ollama memakai URL/model existing; AI_MODEL dapat digunakan jika
OLLAMA_MODEL kosong. API key tidak diperlukan untuk Ollama lokal tanpa autentikasi.
Adapter Ollama existing tidak mendukung gateway yang mewajibkan autentikasi.
Groq mempertahankan GROQ_API_KEY/GROQ_MODEL dengan AI_API_KEY/AI_MODEL sebagai alternatif
jika variabel khusus tidak tersedia. Gemini memakai AI_API_KEY/AI_MODEL.
Tidak ada credential contoh nyata di dokumen ini.

OLLAMA_TIMEOUT_SECONDS berunit **detik**, bukan milidetik. Nilai 15000 tidak berarti 15
 detik. Adapter membatasi body read ke maksimum 45 detik; koneksi/header maksimal 10 detik.
AI_TIMEOUT_MS milik adapter SDK berunit milidetik, dengan batas existing maksimum 30 detik.
Browser menyediakan 125 detik untuk seluruh budget backend dan pengembalian fallback.
Read timeout adalah timeout I/O, bukan deadline wall-clock keras untuk setiap byte.

## Routing, konteks, dan fallback

Safety, data akun, pencarian fasilitas, Haversine, dan rekomendasi GPS tetap lokal.
Pertanyaan informasional diteruskan ke provider terpilih dengan system prompt backend
serta knowledge dari konstanta service aktif. Tidak ada call klasifikasi tambahan untuk
setiap pesan; provider dapat memahami kalimat natural pada satu request jawaban.

Fallback menangani sapaan, bantuan, akun/kepesertaan, keluarga, layanan, iuran,
pembayaran simulasi, pengaduan, fasilitas, dan keselamatan. Pertanyaan yang tidak dikenal
meminta penjelasan ulang. Jawaban diberi label AI atau Panduan dasar SehatWarga.

Riwayat hanya berada dalam memori halaman browser, hilang saat reload/navigasi. Maksimal
10 pesan, role user/assistant, tiap pesan 2000 karakter, total 10000 karakter.
Backend memvalidasi history dan menyaring identifier, email, URL, koordinat desimal,
dan pesan sensitif sebelum meneruskan konteks. System prompt tidak diambil dari frontend.
Riwayat adalah data tidak tepercaya, bukan instruksi yang mengalahkan aturan backend.
Tidak ada tabel chat baru, localStorage, atau koordinat dalam cookie sesi.

Error diklasifikasi: CONFIGURATION_ERROR, AUTHENTICATION_ERROR, MODEL_NOT_FOUND,
RATE_LIMIT, CONNECTION_ERROR, PROVIDER_TIMEOUT, INVALID_RESPONSE, UNKNOWN_PROVIDER_ERROR.
Satu retry dengan exponential-backoff awal 250 ms untuk koneksi, HTTP 5xx, atau rate limit.
Timeout lambat, autentikasi, model, request invalid, dan konfigurasi tidak diulang.
SDK retry dinonaktifkan agar tidak berlipat. Fallback dikembalikan setelah gagal.
Log mencatat ID, kategori, provider, durasi, dan attempt; tidak mencatat exception mentah,
credential, isi chat, atau GPS. Proteksi dasar: 30 request chat/lokasi per menit per sesi.

## Status

`GET /assistant/status` hanya membaca konfigurasi/cache, tanpa request generasi berbayar.
TTL hasil request 60 detik per proses/provider/model:

- AI AKTIF: respons provider telah berhasil.
- MODE BANTUAN DASAR: adapter tidak terkonfigurasi/tersedia; fallback ada.
- AI TIDAK TERSEDIA: percobaan provider terakhir gagal.
- MEMERIKSA — belum ada respons terverifikasi: belum ada bukti, atau cache kedaluwarsa.

Label awal MEMERIKSA berubah setelah endpoint status selesai. Status unknown tidak
menjamin probe sedang berjalan. Cache process-local bukan monitoring seluruh cluster.
Kegagalan inisialisasi tersedia di log kategori konfigurasi; halaman tidak mengklaim aktif.

## Lokasi dan peta

Ketik `Puskesmas terdekat dari saya`, lalu klik **Gunakan Lokasi Saya** dan berikan izin
browser. GPS tidak diakses saat halaman dibuka. Koordinat hanya dikirim ke backend lokal
untuk validasi dan Haversine; tidak disimpan ke database dan tidak diteruskan ke LLM.
Memori browser dapat memakai lokasi berizin selama 5 menit untuk `Kalau rumah sakit?`.
Tanpa koordinat valid, izin diminta kembali. `Cari klinik di Surabaya` tidak meminta GPS.
Hasil hanya fasilitas aktif dari database. Jarak adalah perkiraan garis lurus.
Koordinat null tidak diberi marker. Peta Leaflet memakai tile OpenStreetMap; jika CDN atau
tile gagal, kartu informasi tetap tersedia. Penyedia tile menerima permintaan area peta
sesuai fungsi peta existing, sehingga klaim “tidak diteruskan ke provider” khusus LLM.

## Pengujian

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_stage91.py -q
.venv/bin/python -m compileall backend tests run.py
.venv/bin/python -m pip check
.venv/bin/flask --app run.py routes
.venv/bin/flask --app run.py db current
.venv/bin/flask --app run.py db heads
.venv/bin/python scripts/check_stage91_browser.py
```

Browser QA memakai preview SQLite disposable, bukan database aplikasi terkonfigurasi.
Jika versi Chromium Playwright default belum terpasang, set BROWSER_EXECUTABLE ke binary
Chromium existing. Artefak: qa/stage91/browser-results.json, demo.json, screenshot 4 ukuran.
Uji provider otomatis memakai mock, tidak membuktikan koneksi API nyata. Untuk real test,
pakai satu pertanyaan publik sederhana dengan izin jaringan; jangan cetak config rahasia.

## Batasan

Prototype akademik independen, bukan layanan resmi BPJS. Pembayaran hanya simulasi.
Assistant bukan dokter dan tidak memberi diagnosis, resep, atau dosis. Untuk kondisi
mengancam keselamatan, cari pertolongan medis/UGD atau layanan darurat setempat.
Tidak ada nomor darurat yang dikarang. Jadwal dokter, jam buka, dan kapasitas yang tidak
tersedia di database tidak boleh ditebak. Kualitas LLM tetap perlu evaluasi manusia setelah
provider dapat diakses. Rate limiter/cache in-memory adalah proteksi MVP per worker;
rotasi cookie/sesi atau banyak worker memerlukan proteksi deployment tambahan.
