# SEHATWARGA — STAGE 11
# AUTOMATED BILLING VERIFICATION

Tanggal: 13 November 2026.

**FINAL STATUS: READY FOR STAGE 12 — konfigurasi dan implementasi terverifikasi,
scheduler NOT ACTIVATED.** Tidak ada klaim bahwa eksekusi terjadwal nyata sudah
berjalan. Aktivasi timer dan verifikasi pertama di server tetap keputusan operator.

## A. EXISTING BILLING

| Pemeriksaan | Status | Hasil |
| --- | --- | --- |
| Existing monthly generator | PASS | Runner → CLI existing → contribution_service existing; tidak ada kalkulasi billing kedua. |
| Existing overdue service | PASS | Hanya UNPAID dengan due_date < tanggal acuan; UPDATE bersyarat mempertahankan PAID. |
| CLI compatibility | PASS | `generate-contributions --month YYYY-MM` dan `update-overdue --as-of YYYY-MM-DD` tetap bekerja dengan output manual existing. |
| Unique constraint | PASS | Model/migration unchanged; pasangan participant_id + billing_period diverifikasi pada SQLite dan metadata database terkonfigurasi. |
| Existing billing rules preserved | PASS | Aktif saja, snapshot tarif, jatuh tempo tanggal 10, satu tagihan per peserta/periode. |

Audit source menemukan tarif aktual sesuai konteks: CLASS_1 Rp150.000,
CLASS_2 Rp100.000, CLASS_3 Rp50.000 dari `SIMULATED_RATES`. Tidak disalin ke runner.
Tidak ada perubahan perhitungan nominal/tagihan lama.

Perbaikan terkait keandalan:

- Batch memakai transaksi per peserta melalui single-record service existing.
  Duplicate-key dipulihkan dengan rollback dan konfirmasi record business key pada
  transaksi baru. Tidak mengandalkan savepoint/advisory lock atau mengubah mode TiDB.
  Batch yang gagal karena error lain bisa sudah commit sebagian; rerun idempotent
  melanjutkan peserta yang belum dibuat. Error tersebut tetap nonzero.
- Overdue sebelumnya membaca objek lalu mengubah status ORM; snapshot itu dapat
  tertinggal dari pembayaran. Sekarang kondisi UNPAID/due_date berada di SQL UPDATE,
  sehingga status PAID yang sudah berlaku saat UPDATE dievaluasi tidak tertimpa.
- CLI invalid month/date sebelumnya mencetak error lalu return 0. Sekarang input
  invalid ditolak nonzero; nama command, opsi lama dan output sukses tetap tersedia.

## B. MONTHLY AUTOMATION

| Pemeriksaan | Status |
| --- | --- |
| Monthly runner | PASS — entry point terpisah, real subprocess diuji |
| Active participant filter | PASS — ACTIVE mendapat, INACTIVE tidak mendapat |
| Billing period | PASS — YYYY-MM dari tanggal bisnis WIB, termasuk pergantian tahun |
| Nominal calculation | PASS — tiga kelas dari konstanta existing |
| Due date | PASS — tanggal 10 bulan yang diminta |
| Idempotency | PASS — tiga eksekusi periode sama tidak menambah duplikasi |
| Duplicate protection | PASS — constraint, actual SQLite UNIQUE collision, recovery dan batch lanjut; kode error driver MySQL/TiDB melalui mock |
| Dry-run | PASS — candidate counts, created=0, tanpa add/flush/commit; hash DB file tidak berubah |

Runner: `scripts/jobs/run_monthly_billing.py`. Interpreter child selalu
`<project>/.venv/bin/python`, cwd project root; tidak bergantung cwd pemanggil.
Periode diberikan eksplisit ke CLI. Tidak ada otomatisasi seluruh riwayat.

## C. DAILY OVERDUE AUTOMATION

| Pemeriksaan | Status |
| --- | --- |
| Daily runner | PASS — real subprocess ke CLI existing |
| Due date evaluation | PASS — tanggal 9/10 tidak overdue, tanggal 11 eligible |
| PAID protection | PASS — PAID tidak diubah; guarded-update regression juga lulus |
| Overdue transition | PASS — UNPAID → OVERDUE saja |
| Repeat execution | PASS — update kedua menghasilkan 0 dan timestamp OVERDUE tetap |
| Date and timezone | PASS — ZoneInfo Asia/Jakarta, batas UTC/WIB dan tahun diuji |

Payment PENDING tidak dimutasi. Kebijakan existing tetap: Payment PENDING tidak
menahan Contribution UNPAID dari overdue jika due_date sudah lewat. Tidak dibuat
kebijakan pending hold atau status Contribution baru. Tagihan future, PAID dan
OVERDUE milik peserta lain yang tidak eligible tetap utuh.

## D. SCHEDULER

| Item | Hasil |
| --- | --- |
| Scheduler type | External systemd timer sebagai mekanisme utama contoh; portable CLI runner |
| Scheduler target | Deployment belum diketahui; mesin inspeksi Linux/systemd, tidak dianggap otomatis sebagai server tujuan |
| Monthly schedule | `*-*-01 00:15:00 Asia/Jakarta` |
| Daily schedule | `*-*-* 00:30:00 Asia/Jakarta` |
| Timezone | Asia/Jakarta |
| systemd/calendar validation | PASS — calendar dan empat unit yang dirender ke temporary directory |
| Platform scheduler configuration | NOT APPLICABLE untuk vendor aktual yang belum diketahui; alternatif timezone-native/UTC didokumentasikan dan guard UTC diuji |
| Scheduler auto-start inside Flask | NO — tidak ada scheduler/thread startup pada create_app/import runner |
| Timer installed/enabled | NO — NOT ACTIVATED |

`systemctl list-unit-files 'sehatwarga-*'` dan list-timers read-only menunjukkan
0 unit files dan 0 timers. Tidak menjalankan install unit, daemon-reload,
systemctl enable/start/stop, crontab, atau deployment.

Unit `.service` berisi placeholder PROJECT_ROOT dan SERVICE_USER karena lokasi
deployment belum ditentukan. Validasi menggunakan salinan sementara dengan path
project/user aktual, bukan memasang template ke direktori system-wide.

Monthly WIB = 17:15 UTC **hari terakhir bulan sebelumnya**. Untuk platform UTC
dengan cron lima field, contoh menjalankan runner harian 17:15 UTC dengan
`--only-first-day`; hanya tanggal 1 WIB yang memanggil CLI. Hari lain hanya
mencatat skipped_calendar. Daily WIB = 17:30 UTC hari sebelumnya.
Alternatif ini tidak diaktifkan bersama systemd.

## E. SAFETY

| Pemeriksaan | Status | Batas |
| --- | --- | --- |
| Concurrency protection | PASS | flock nonblocking per job, host/project yang sama; diuji lintas proses |
| Idempotency | PASS | Business key unik, lookup, rollback/recovery dan rerun |
| Failure exit code | PASS | Exit CLI nonzero diteruskan; timeout 124; lock busy 75; tidak ada retry tanpa batas |
| Safe logging | PASS | JSON started/finished, UUID, tanggal/periode, count, durasi, kategori error; raw child stdout/stderr tidak diteruskan |
| Credential protection | PASS | Tidak ada credential di runner/unit; log tests menyertakan sentinel rahasia dan memastikan tidak muncul |
| Database protection | PASS | Automated writes hanya pada SQLite disposable; database aplikasi hanya dibaca untuk audit |

File lock tetap ada agar inode tidak berganti saat proses lain menunggu. Descriptor
diwariskan ke child CLI untuk mempertahankan lock bila parent mati. Lock hanya
berlaku pada filesystem lokal POSIX dengan directory yang sama; bukan distributed
lock. Direct CLI manual tetap kompatibel dan tidak mengambil lock runner.

Counter yang tidak diketahui setelah kegagalan diberi null. Tidak ada log per
peserta, nomor peserta, SQL parameter, isi kesehatan, password atau DATABASE_URL.
Log stdout ditangani journald/platform dengan retensi host; tidak dibuat file log
operasional tanpa rotation. Artifact QA bukan log operasional berkelanjutan.

## F. REGRESSION

| Item | Hasil aktual |
| --- | --- |
| Existing tests before | 197 PASS, 93 subtests PASS, 26.46 detik |
| Existing tests after | Seluruh 197 existing test tetap dijalankan dan PASS di suite akhir |
| New Stage 11 tests | 28 PASS, 25 subtests PASS, 7.32 detik |
| Total tests | 225 |
| Passed | 225 tests + 118 subtests |
| Failed | 0 |
| Errors | 0 |
| Full regression duration | 72.62 detik, berjalan bersamaan dengan browser QA |
| Browser regression Stage 10 | 274 PASS, 0 FAIL, 0 JavaScript exceptions |
| Python compile | PASS |
| pip check | PASS |
| Flask routes | PASS |
| Migration current=head | PASS — 3dfb67eddef4 |
| Git diff check | PASS |

Tidak ada existing test dihapus, dilewati atau diubah assertion-nya. Jumlah
diambil dari hasil discovery/run aktual, bukan angka tetap dari laporan lama.
922 warning pada suite akhir adalah deprecation datetime.utcnow SQLAlchemy dan
typing google-genai existing; tidak ada error regresi.

Tes baru meliputi semua kelas, aktif/nonaktif, due date, periode berbeda,
idempotency, unique constraint, snapshot perubahan rate/kelas, invalid input,
dry-run no writes, duplicate recovery, nonduplicate error, partial batch rerun,
overdue boundary/paid/pending/future, guarded update, WIB boundaries, CLI legacy,
CLI sanitized failure, runner subprocess/interpreter/cwd/exit/log/timeout/lock,
kalender dan rendered units. Real runner test menggunakan SQLite file terpisah,
menjalankan monthly/daily dua kali dan menguji hash sebelum/sesudah dry-run.

## G. DATABASE

| Item | Hasil |
| --- | --- |
| Database engine detected | 8.0.11-TiDB-v8.5.3-serverless; MySQL-compatible |
| Current migration | 3dfb67eddef4 |
| Head migration | 3dfb67eddef4 |
| Database schema changed | NO |
| Data modified during tests | YES, hanya pada database SQLite disposable; NO pada database pengguna/produksi |
| Models/indexes/constraints/migration modified | NO |
| Payment records written by scheduler | NO |

Audit sebelum/sesudah hanya membaca VERSION(), alembic_version dan metadata
unique index. `flask db current`/`heads` juga berhasil; tidak ada upgrade/downgrade.
Hash file memastikan seluruh model, migration, frontend, `.env`, config,
app factory dan requirements yang tercatat sebelum Stage 11 tetap sama.

## H. FILES

Created:

- `scripts/jobs/__init__.py`
- `scripts/jobs/_runner.py`
- `scripts/jobs/run_monthly_billing.py`
- `scripts/jobs/run_daily_overdue.py`
- `deploy/systemd/sehatwarga-monthly-billing.service`
- `deploy/systemd/sehatwarga-monthly-billing.timer`
- `deploy/systemd/sehatwarga-daily-overdue.service`
- `deploy/systemd/sehatwarga-daily-overdue.timer`
- `tests/test_stage11.py`
- `docs/BILLING_AUTOMATION.md`
- `STAGE_11_REPORT.md`
- `qa/stage11/` — baseline, tests, database audit, calendar/unit/project health,
  preserved-file hashes, browser results, scheduler status dan Git snapshots.

Modified khusus Stage 11:

- `backend/app/services/contribution_service.py` — dry-run, duplicate recovery,
  transaksi per peserta dan atomic overdue update.
- `backend/app/cli.py` — opsi tambahan dry-run/JSON, default WIB, exit/error handling.
- `.gitignore` — `.runtime/` untuk file lock.

Unchanged:

- Model, schema, migration, constraint, requirements/dependency, config, `.env`,
  Flask app factory/auth/CSRF, payment service, seluruh frontend dan business rates.
- Seluruh existing tests/source browser test tetap sama. Artefak browser Stage 10
  diregenerasi oleh script existing saat regresi dan hasilnya disalin ke Stage 11.
- Perubahan lokal pengguna yang sudah ada sebelum Stage 11 tetap dipertahankan.

## I. MANUAL VERIFICATION

| Item | Status |
| --- | --- |
| Manual monthly CLI | PASS pada disposable DB: Flask runner + real subprocess; database operasional MANUAL CHECK REQUIRED |
| Manual overdue CLI | PASS pada disposable DB: Flask runner + real subprocess; database operasional MANUAL CHECK REQUIRED |
| Timer activation | NOT ACTIVATED — operator melakukan instalasi/aktivasi setelah review |
| First scheduled execution | MANUAL CHECK REQUIRED — belum ada timer aktif |
| Staging concurrency | MANUAL CHECK REQUIRED — belum ada staging TiDB terpisah yang disetujui |
| Production verification | MANUAL CHECK REQUIRED — tidak menjalankan job mutasi pada data pengguna |

## J. KNOWN LIMITATIONS

- Kesiapan implementasi/configuration dibuktikan; eksekusi terjadwal operasional
  belum dibuktikan karena scheduler belum diaktifkan, sesuai scope.
- Flock tidak mencakup multi-host/container/checkout dengan directory lock berbeda.
  Gunakan satu scheduler instance; unique constraint tetap pertahanan DB.
- SQLite collision, simulated ordering dan mock kode error driver bukan bukti
  concurrency/transaksi TiDB. Write conflict/deadlock/gangguan koneksi di luar
  duplikat terkonfirmasi tetap gagal nonzero dan perlu rerun terkontrol.
- Transaksi per peserta bisa menghasilkan batch parsial jika terjadi kegagalan
  nonduplicate; data yang sudah commit dipertahankan dan rerun melanjutkan.
- Backfill memakai active participant/kelas/tarif **saat dijalankan**, bukan
  rekonstruksi historis. Tidak menyentuh nominal tagihan yang sudah tersimpan.
- Guard UTC platform tidak melakukan catch-up tanggal 2 jika tanggal 1 terlewat;
  gunakan prosedur manual yang didokumentasikan. Persistent systemd catch-up
  hanya bulan berjalan, tidak membuat seluruh periode historis.
- Runtime membutuhkan POSIX/Linux, timezone database Asia/Jakarta, `.venv`,
  environment backend, izin read config/write lock dan konektivitas DB.
- Tidak mengerjakan profile/reset password/notifikasi/backup/payment gateway/AI,
  desain frontend, dashboard scheduler, atau Stage 12–16.

## K. ERRORS

Final automated errors: **0**. Final test failures: **0**.
Final browser failures/JavaScript exceptions: **0**.

Satu kegagalan awal tes runner berasal dari slice assertion baru yang mengambil
lima argumen tetapi expected list hanya berisi empat. Expected full CLI suffix
diperbaiki menjadi `update-overdue --as-of <tanggal> --json --dry-run`; tidak ada
existing business assertion yang diubah. Seluruh tes baru kemudian PASS.

## Dokumentasi dan bukti

Panduan lengkap: [docs/BILLING_AUTOMATION.md](docs/BILLING_AUTOMATION.md), termasuk
manual/dry-run, rendering/install/activation timer, status/journal, retry/backfill,
disable, troubleshooting, UTC platform guard dan batas multi-server.

Bukti utama:

- `qa/stage11/baseline.txt`
- `qa/stage11/stage11-tests.txt`
- `qa/stage11/regression-results.txt`
- `qa/stage11/browser-results.json`
- `qa/stage11/database-before.json` / `database-after.json`
- `qa/stage11/technical-audit.json`
- `qa/stage11/preserved-files-audit.json`
- `qa/stage11/scheduler-status.txt`

Rujukan primer untuk batas database dan timer:
[TiDB constraints](https://docs.pingcap.com/tidb/stable/constraints/),
[systemd.timer](https://www.freedesktop.org/software/systemd/man/250/systemd.timer.html).

**READY FOR STAGE 12 — scheduler NOT ACTIVATED.**
Tidak ada commit, push GitHub, deployment, aktivasi scheduler, atau pekerjaan
Stage 12–16. Pekerjaan berhenti setelah laporan Stage 11 ini.
