# SEHATWARGA — STAGE 9.1
# AI ASSISTANT IMPROVEMENT REPORT

Tanggal pengujian: 9 November 2026. Implementasi Flask/Jinja2 Stage 9 digunakan kembali.

## A. ROOT CAUSE ANALYSIS

**Penyebab timeout berdasarkan bukti:**

1. Provider aktif dari konfigurasi root `.env` adalah **Ollama**, model **llama3.1:latest**.
   Nilai `OLLAMA_TIMEOUT_SECONDS=15000` berunit detik; kode sebelumnya membatasinya
   menjadi **180 detik**. `AI_TIMEOUT_MS=15000` merupakan konfigurasi lain, bukan timeout
   adapter Ollama. Frontend membatalkan fetch setelah **20 detik**, sehingga jawaban
   fallback backend dapat tiba setelah browser berhenti menunggu.
2. Satu real request sederhana di luar sandbox gagal terhubung: **URLError, errno 110**,
   durasi **135,28 detik**, tanpa respons model. Percobaan pertama di sandbox ditolak
   dengan errno 1 dan tidak digunakan sebagai bukti gangguan provider.
3. Kode sebelumnya menelan exception provider dengan peringatan generik; tidak ada
   klasifikasi/telemetri yang membantu membedakan masalah konfigurasi dan jaringan.
4. Frontend hanya mengirim message. Adapter Ollama mengabaikan history. Header hanya
   membaca nama provider dari config, tanpa observasi keberhasilan. Ini menjelaskan
   masalah konteks/status, bukan penyebab koneksi jaringan gagal.

**Konfigurasi:** endpoint diset, model diset. Credential provider lain ditemukan sebagai
SET, tanpa dicetak. Ollama lokal tidak bergantung pada key Gemini/Groq tersebut.
Root `.env` dimuat melalui dotenv; pengujian menonaktifkannya dengan sengaja.
Tidak ada bukti bahwa API key menjadi penyebab kegagalan ini. Ketersediaan model di server
belum dapat diperiksa karena koneksi tidak berhasil.

**Solusi:** adapter tetap Ollama; koneksi/header dibatasi 10 detik, body read default
35 detik dan maksimum 45 detik. Nilai lama 15000 dibatasi 45. Browser 125 detik mencakup
budget dua attempt dan fallback. Retry maksimum satu hanya untuk koneksi/rate limit/5xx;
read timeout, key/model/request/config invalid tidak diulang. SDK retries dinonaktifkan.
Error diklasifikasi, log disanitasi, fallback menjawab intent yang dikenal.
Dokumentasi environment menjelaskan perbedaan detik/milidetik.
Format POST /api/chat, messages, stream=false, message.content sesuai
[dokumentasi resmi Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md).

Kegagalan koneksi eksternal belum diperbaiki: bukti saat ini tidak dapat membedakan
server tidak berjalan, firewall, routing, atau keterjangkauan jaringan tujuan.

## B. AI PROVIDER

| Pemeriksaan | Hasil |
| --- | --- |
| Configuration | PASS — Ollama terpilih, endpoint/model tersedia; timeout lama salah satuan |
| Provider initialization | PASS |
| Connection | FAIL — real request timeout, bukan dugaan API key |
| Response parsing | PASS — mocked; respons nyata belum diterima |
| Timeout handling | PASS — mocked, fallback; koneksi/header dibatasi |
| Retry handling | PASS — maksimum satu retry; nonretryable tidak diulang |

`GET /assistant/status` tanpa call generasi. Cache 60 detik per proses/provider/model.
AI AKTIF hanya setelah respons nyata pada proses tersebut; tidak diklaim berdasarkan config.
Status tanpa bukti ditulis MEMERIKSA — belum ada respons terverifikasi. Status gagal
AI TIDAK TERSEDIA; konfigurasi/adapter tidak tersedia memakai MODE BANTUAN DASAR.

## C. AI INTELLIGENCE

| Pemeriksaan | Hasil |
| --- | --- |
| Natural language understanding | PASS — variasi deterministik dan payload provider mocked; kualitas LLM nyata belum dinilai |
| Conversation context | PASS — maksimal 10 pesan, 2000 karakter/pesan, total 10000 |
| Follow-up questions | PASS — keluarga dan kelanjutan workflow; tipe fasilitas terdekat |
| SehatWarga knowledge | PASS — dibandingkan form, route, service, model/status aktual |
| Service guide | PASS — 9 langkah; submit belum konfirmasi janji |
| Contribution guide | PASS — konstanta tarif/status simulasi existing |
| Payment guide | PASS — termasuk “membayar iuran”, Iuran > rincian > Bayar |
| Complaint guide | PASS — form/status/tanggapan existing |

Intent existing dipertahankan, termasuk nama kompatibilitas ACCOUNT_GUIDE,
MEMBERSHIP_SUMMARY, EMERGENCY, MEDICAL_INQUIRY, SECURITY_INQUIRY. GENERAL_HELP,
MEMBERSHIP_GUIDE dan FACILITY_DETAIL tersedia pada vocabulary; detail fasilitas diakses
melalui kartu hasil database. Pertanyaan natural informasional dapat dipahami provider
pada satu request jawaban; tidak ada request LLM klasifikasi tambahan per pesan.

## D. FALLBACK

Greeting, general help, service guide, facility search, contribution guide,
payment guide, complaint guide, family/membership guide, medical safety,
dan fallback after provider failure: **PASS**.

UNKNOWN meminta penjelasan ulang. Jawaban AI dan panduan dasar mempunyai label berbeda.
Fallback keluarga/kelanjutan layanan tidak mengulang seluruh panduan awal.

## E. LOCATION

| Pemeriksaan | Hasil |
| --- | --- |
| Location consent | PASS — klik eksplisit sebelum navigator.geolocation |
| GPS handling | PASS — browser geolocation emulation; perangkat fisik MANUAL CHECK REQUIRED |
| Facility filtering | PASS — active-only/type/city existing dan follow-up rumah sakit |
| Haversine | PASS — existing tests dipertahankan |
| Nearest ordering | PASS — existing tests dipertahankan |
| Coordinate integrity | PASS — data database; null tidak diberi marker |
| Location privacy | PASS — tidak ada write database/GPS ke LLM |

Koordinat berizin hanya di memori halaman, digunakan untuk follow-up maksimal 5 menit.
Tanpa koordinat valid diminta izin lagi. City search tidak meminta GPS. Penolakan izin,
position unavailable, dan timeout diuji dengan stub browser. Hasil jarak dilabeli
perkiraan garis lurus; telepon/koordinat/link detail tersedia pada kartu.

## F. MAP

Leaflet: **PASS**. OpenStreetMap tiles: **PASS**.
User marker: **PASS** (GPS emulation). Facility markers: **PASS**.
Popup: **PASS** (kartu DOM aman). fitBounds: **MANUAL CHECK REQUIRED** untuk penilaian
cakupan geografis visual yang rinci; pemanggilan existing tetap dipertahankan.
CDN dan tiles berhasil pada pengujian Chromium. Kartu tetap tersedia jika peta gagal.

## G. FRONTEND

Loading, retry, double submit prevention, input preservation, conversation context,
provider status, sidebar relevance, Enter/Shift+Enter: **PASS**.
Loading/double submit diuji dengan respons yang sengaja ditahan, retry dengan HTTP 503
simulasi lalu request ulang berhasil. Tidak ada auto resend berkali-kali.
Mobile layout: **PASS** pada Chromium 375, 768, 1024, 1440px; screenshot keempat ukuran
juga diperiksa. Pengujian Safari/Firefox dan perangkat fisik: **MANUAL CHECK REQUIRED**.
36 pemeriksaan browser lulus, nol JavaScript exception.

Sidebar berisi lima quick prompt yang mengirim chat. Akses upload/scan dan teks kemasan
obat dihapus dari halaman/chat JS. Backend scan yang sudah ada sebelum task tidak
diperluas dan tidak menjadi bagian Stage 9.1. Desain keseluruhan tidak diubah.

## H. SECURITY

CSRF: **PASS**. XSS: **PASS** (input script tampil sebagai teks).
Prompt injection protection: **PASS** untuk deterministic guard dan role validation.
Secret protection: **PASS** untuk pengujian log/payload/response lokal yang tersedia.
Location privacy: **PASS**. Conversation isolation: **PASS** — memori per halaman,
backend stateless, tidak ada history milik user lain yang diambil/disimpan.
No raw HTML rendering: **PASS** — textContent dan elemen DOM, termasuk popup fasilitas.

System role frontend ditolak. History melebihi limit ditolak; data sensitif disaring.
Data ringkasan kepesertaan tetap lewat current_user/role/active checks existing dan tidak
masuk history provider dari frontend. LLM tidak mempunyai tool SQL/shell/business action.
Rate protection sederhana 30 request per menit per sesi; CSRF tidak dinonaktifkan.
Ini bukan bukti bahwa semua serangan prompt injection terhadap LLM dapat dicegah;
evaluasi adversarial model nyata masih diperlukan setelah koneksi tersedia.

## I. MEDICAL SAFETY

No diagnosis: **PASS**. Emergency-safe response: **PASS**.
Facility suggestion: **PASS**. Tidak ada resep/dosis atau nomor darurat yang dikarang.
Skenario “Saya sakit dada, penyakit apa?” menolak diagnosis dan mengarahkan ke tenaga
kesehatan; indikator darurat eksplisit memakai respons pertolongan medis segera.

## J. TEST SUMMARY

| Item | Hasil |
| --- | --- |
| Existing tests menurut laporan sebelumnya | 112 |
| Existing tests ditemukan sebelum perubahan | 176 |
| Baseline aktual | 174 PASS, 2 FAIL, 85 subtests PASS |
| Existing tests setelah perubahan | 176 PASS, termasuk 112 Stage 3–9 existing |
| New Stage 9.1 tests | 17 PASS |
| Total tests | 193 |
| Passed | 193, ditambah 88 subtests PASS |
| Failed | 0 |
| Errors | 0 |
| Mocked provider test | PASS — Gemini/Groq/Ollama dan reliability |
| Real API test | FAIL — Ollama connection timeout; bukan NOT CONFIGURED |
| Browser QA | 36 PASS, 0 FAIL |

Dua kegagalan baseline berasal dari perubahan disclaimer homepage/assistant yang sudah
ada pada workspace. Teks diperbaiki tanpa mengubah assertion atau menghapus test existing.
692 warning berasal dari deprecation SQLAlchemy datetime.utcnow dan google-genai typing.
`compileall`: PASS. `pip check`: PASS. Flask routes: PASS.
`git diff --check`: PASS. Tidak ada dependency baru.

## K. DATABASE

Current migration: **3dfb67eddef4**.
Head migration: **3dfb67eddef4**.
Current == head: **PASS**, pemeriksaan read-only alembic_version pada database terkonfigurasi.
Percobaan CLI pertama gagal DNS di sandbox; pemeriksaan read-only di luar sandbox berhasil.
Database changed: **NO** (database aplikasi). Migration required: **NO**.
Test/preview memakai database SQLite disposable tersendiri. Tidak ada reset/downgrade,
penghapusan data pengguna, perubahan model/schema/migration, atau perubahan workflow bisnis.

## L. FILE CHANGES

Dibuat untuk Stage 9.1:

- backend/app/services/assistant_runtime.py
- tests/test_stage91.py
- scripts/check_stage91_browser.py
- docs/ASSISTANT.md
- STAGE_9_1_REPORT.md
- qa/stage91/: test-results.txt, browser-results.json, provider-result.json,
  demo.json, assistant-375/768/1024/1440.png, conversation.png

Diubah pada task ini:

- backend/config.py — default timeout Ollama dalam detik
- backend/app/services/ai_service.py — routing/fallback, context payload, timeout/parsing
- backend/app/services/assistant_service.py — history validation, redaction, orchestration
- backend/app/services/assistant_safety.py — token “obat” tidak menangkap “berobat”, redaksi GPS
- backend/app/services/assistant_knowledge.py — verified guide dan system prompt
- backend/app/routes/assistant.py — cached status endpoint dan basic rate protection
- frontend/static/js/assistant.js — history, retry, loading, lokasi follow-up, kartu; scan UI dilepas
- frontend/templates/assistant/chat.html — status, disclaimer, quick prompt/sidebar relevan
- frontend/templates/public/home.html — satu teks disclaimer baseline test
- .env.example — contoh konfigurasi Ollama tanpa credential

Workspace sudah mempunyai banyak perubahan pengguna sebelum task. Daftar ini khusus
pekerjaan Stage 9.1; perubahan lain tidak di-reset atau dianggap sebagai hasil task ini.
Tidak ada commit atau push.

## M. KNOWN LIMITATIONS

- Server Ollama terkonfigurasi belum dapat dihubungi; real model/semantic quality belum
  dapat divalidasi. Periksa keterjangkauan endpoint dari mesin Flask dan layanan Ollama
  di mesin tujuan sebelum menyatakan AI aktif. Jangan mengganti key/provider tanpa bukti.
- `.env` lokal tetap menyimpan nilai timeout lama; adapter membatasi nilainya dengan aman.
  Panduan menyarankan OLLAMA_TIMEOUT_SECONDS=35 saat konfigurasi deployment diperbarui.
- Status/cache dan rate limit per proses/sesi adalah proteksi MVP, bukan distributed limiter.
- URL gateway Ollama dengan autentikasi khusus belum didukung adapter existing.
- History tidak bertahan setelah reload; redaksi heuristik bukan detektor PII sempurna.
- Peta memerlukan CDN/tile network; GPS fisik, browser lain, dan penilaian fitBounds rinci
  tetap MANUAL CHECK REQUIRED. Penyedia tile menerima area peta; GPS tidak dikirim ke LLM.
- Fallback memahami intent umum dan follow-up yang diuji, bukan semua kemungkinan bahasa.

## N. ERRORS

Application/regression errors tersisa: **0**.
Real provider connection error tersisa: **URLError errno 110**, tidak ada respons AI nyata.
Peringatan deprecation existing tetap dicatat, tanpa mengubah model atau service bisnis.

# FINAL STATUS

**NEEDS ATTENTION**

Implementasi, fallback, konteks, keamanan, peta, browser QA, dan regresi sudah terverifikasi.
Koneksi Ollama nyata masih gagal; AI aktif dan kualitas model nyata belum dapat diklaim.
Seluruh pekerjaan dan laporan berhenti di sini; tidak ada fitur tambahan, commit, atau push.
