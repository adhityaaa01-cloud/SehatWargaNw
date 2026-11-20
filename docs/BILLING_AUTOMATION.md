# Otomatisasi iuran SehatWarga — Stage 11

**Status: konfigurasi siap diuji/diaktifkan operator, NOT ACTIVATED.** Tidak ada
unit yang dipasang, timer diaktifkan, atau tagihan percobaan dibuat pada database
pengguna selama implementasi. Target deployment belum tercatat di repository.
Pilihan utama yang disiapkan adalah **external systemd timer pada Linux**;
alternatif platform/cron di bawah hanya digunakan jika systemd tidak dipilih.

## Pekerjaan dan aturan bisnis

| Job | Jadwal bisnis | Runner | CLI existing yang dipanggil |
| --- | --- | --- | --- |
| Monthly billing | Tanggal 1, 00:15 Asia/Jakarta | `scripts/jobs/run_monthly_billing.py` | `generate-contributions --month YYYY-MM` |
| Daily overdue | Setiap hari, 00:30 Asia/Jakarta | `scripts/jobs/run_daily_overdue.py` | `update-overdue --as-of YYYY-MM-DD` |

Runner memanggil `<project>/.venv/bin/python -m flask --app run.py ... --json`,
dengan working directory project root yang dihitung dari lokasi script.
Tanggal dihitung dengan aware datetime dan `ZoneInfo('Asia/Jakarta')`, terlepas
dari timezone OS. CLI tanpa tanggal eksplisit juga memakai tanggal WIB.
Timestamp database tetap mengikuti konvensi UTC existing.

Aturan yang dipertahankan:

- Hanya Participant dengan `membership_status=ACTIVE` yang mendapat tagihan.
  Ini mengikuti aturan Stage 6; status akun User tidak menjadi filter baru.
- Tarif berasal dari `SIMULATED_RATES` pada contribution_service:
  CLASS_1 Rp150.000, CLASS_2 Rp100.000, CLASS_3 Rp50.000.
- Nominal adalah snapshot ketika tagihan dibuat. Generate ulang tidak menghitung
  ulang nominal atau mengubah tagihan lama, meskipun kelas/tarif telah berubah.
- Periode disimpan sebagai tanggal 1 bulan yang diminta, input CLI `YYYY-MM`.
  Jatuh tempo tetap tanggal 10 bulan itu.
- Overdue hanya memperbarui `Contribution.status=UNPAID AND due_date < as_of`.
  Tanggal 10 belum overdue; tanggal 11 eligible. PAID dan OVERDUE tidak cocok
  dengan kondisi update dan tidak disentuh. Pengulangan tidak memperbarui timestamp
  tagihan yang sudah OVERDUE.
- **Pending payment:** Payment dan Contribution adalah entitas terpisah.
  Aturan existing tidak memberi penundaan overdue karena Payment berstatus PENDING.
  Jika Contribution masih UNPAID dan melewati jatuh tempo, ia menjadi OVERDUE;
  record Payment PENDING sendiri tidak diubah. Tidak ada status/hold baru.
- Tidak ada autodebit, transfer nyata, payment gateway, atau perubahan workflow
  pembayaran simulasi. Scheduler tidak membuat Payment atau menandai PAID.

## Database dan perlindungan duplikasi

Audit read-only mesin pengembangan mendeteksi
`8.0.11-TiDB-v8.5.3-serverless`, kompatibel MySQL. Jangan mengganti dialect atau
mengasumsikan advisory lock MariaDB tersedia. Migrasi tetap
`3dfb67eddef4 (head)`, dan unique index business key peserta+periode terverifikasi.

Service existing dipakai oleh CLI, admin dan runner. Tidak ada implementasi
perhitungan iuran kedua. Unique constraint `uq_participant_billing_period`
tetap menjadi pertahanan database.

Pembuatan batch sekarang memakai transaksi per peserta melalui service existing.
Jika INSERT/COMMIT kalah oleh duplikat, percobaan tersebut di-rollback lalu
record peserta+periode dibaca ulang pada transaksi baru. Hanya duplikat yang
terkonfirmasi dianggap skipped. Error lain tetap gagal dan menghasilkan exit
nonzero. Tidak menggunakan savepoint, advisory lock, atau perubahan konfigurasi DB.
Kode driver 1062, SQLite UNIQUE 2067, serta TiDB deferred-duplicate 8147 dengan
penanda `[kv:1062]` dikenali; cabang MySQL/TiDB diuji memakai mock error driver,
bukan transaksi tulis pada server pengguna.

Jika batch gagal setelah beberapa peserta selesai, tagihan yang sudah commit
tetap ada. Jalankan ulang periode yang sama: yang sudah ada dilewati dan yang
belum ada dibuat. Jangan menghapus tagihan untuk mengulang job. Jumlah created
pada run ulang hanya menghitung INSERT yang berhasil pada run itu.

Overdue memakai satu conditional SQL UPDATE, sehingga tidak menulis status dari
snapshot ORM yang mungkin sudah basi setelah pembayaran. Ini mempertahankan
aturan due-date sambil melindungi tagihan yang sudah PAID saat UPDATE dievaluasi.

## Menjalankan manual dan dry-run

Jalankan dari project root. Gunakan `.venv` project yang sudah berisi requirements
existing; tidak ada dependency scheduler baru.

```sh
# Preview bulan/tanggal WIB sekarang: runner memakai lock yang sama dengan timer.
.venv/bin/python scripts/jobs/run_monthly_billing.py --dry-run
.venv/bin/python scripts/jobs/run_daily_overdue.py --dry-run

# Eksekusi nyata pada database terkonfigurasi — hanya setelah preview ditinjau.
.venv/bin/python scripts/jobs/run_monthly_billing.py
.venv/bin/python scripts/jobs/run_daily_overdue.py

# CLI existing tetap kompatibel; pilih periode/tanggal secara eksplisit.
.venv/bin/python -m flask --app run.py generate-contributions --month 2026-11 --dry-run
.venv/bin/python -m flask --app run.py update-overdue --as-of 2026-11-13 --dry-run
.venv/bin/python -m flask --app run.py generate-contributions --month 2026-11
.venv/bin/python -m flask --app run.py update-overdue --as-of 2026-11-13
```

Tanggal di contoh adalah contoh manual, bukan tanggal hardcoded runner.
Opsi `--json` menampilkan ringkasan mesin tanpa identitas peserta. Output manual
lama tetap digunakan saat `--json` tidak diberikan. Input bulan/tanggal invalid
sekarang menghasilkan exit nonzero; sebelumnya CLI mencetak error lalu return 0.
`--dry-run` hanya membaca/menghitung: tidak add, UPDATE, flush, atau commit.
Preview adalah snapshot sesaat, bukan reservasi jumlah untuk eksekusi berikutnya.

`DATABASE_URL` dan credential tetap berasal dari environment/backend config.
`backend/config.py` memuat `.env` project root melalui python-dotenv. Runner tidak
menyalin credential ke argumen CLI, frontend, unit systemd, atau log.
Pada server operasional jangan set `PYTHON_DOTENV_DISABLED` atau
`SEHATWARGA_TESTING` kecuali memang sengaja memakai environment test.

**Pengujian otomatis** selalu memakai SQLite disposable. Jangan menjalankan
contoh mutasi di atas terhadap database pengguna hanya untuk mencoba scheduler.

## Memasang contoh systemd secara manual

Empat file tersedia pada `deploy/systemd/`. File `.service` adalah template dengan
placeholder `@PROJECT_ROOT@` dan `@SERVICE_USER@`; jangan memasang template mentah.
Tidak ada path deployment yang diasumsikan atau di-hardcode ke laptop pengembang.

Gunakan user OS aplikasi non-root yang dapat membaca project, `.venv`, dan `.env`,
serta menulis direktori lock. User DB membutuhkan izin data aplikasi yang sesuai;
job tidak membutuhkan izin migrasi/schema. Lindungi `.env` agar tidak world-readable.

Contoh rendering pada mesin tujuan (belum menginstal/menjalankan unit):

```sh
cd /lokasi/project/SehatWarga
SW_PROJECT_ROOT="$(pwd -P)"
SW_SERVICE_USER="nama-user-aplikasi"
.venv/bin/python - "$SW_PROJECT_ROOT" "$SW_SERVICE_USER" /tmp/sehatwarga-systemd <<'PY'
from pathlib import Path
import sys
root, user, target = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
assert (root / '.venv/bin/python').is_file()
target.mkdir(parents=True, exist_ok=True)
for source in (root / 'deploy/systemd').glob('sehatwarga-*'):
    rendered = source.read_text().replace('@PROJECT_ROOT@', str(root)).replace('@SERVICE_USER@', user)
    (target / source.name).write_text(rendered)
PY

systemd-analyze verify /tmp/sehatwarga-systemd/*.service /tmp/sehatwarga-systemd/*.timer
systemd-analyze calendar '*-*-01 00:15:00 Asia/Jakarta'
systemd-analyze calendar '*-*-* 00:30:00 Asia/Jakarta'
```

Sesudah operator menyetujui target database, user, preview dan jadwal, instalasi
dan aktivasi **manual** dapat dilakukan pada mesin tujuan:

```sh
sudo install -d -m 0700 -o "$SW_SERVICE_USER" "$SW_PROJECT_ROOT/.runtime/billing"
sudo install -m 0644 /tmp/sehatwarga-systemd/sehatwarga-*.service /etc/systemd/system/
sudo install -m 0644 /tmp/sehatwarga-systemd/sehatwarga-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sehatwarga-monthly-billing.timer sehatwarga-daily-overdue.timer
```

Perintah instalasi/enable/start ini **tidak dijalankan oleh implementasi Stage 11**.
`Type=oneshot`, interpreter `.venv`, working directory, journal logging dan
exit status diatur di unit. `NoNewPrivileges=true`, `UMask=0077`, user non-root;
tidak ada credential di unit. Runner membatasi child CLI hingga 1800 detik dan
unit memberi 31 menit untuk penyelesaian. `Restart=no`: tidak ada retry tanpa batas.

`Persistent=true` dapat menjalankan satu catch-up ketika timer yang melewatkan
jadwal kembali aktif. Monthly tetap menghasilkan **bulan WIB sekarang**, bukan
semua bulan historis. Periksa kebutuhan backfill secara terpisah.

## Status, log, gagal dan rerun

```sh
systemctl list-timers 'sehatwarga-*'
systemctl status sehatwarga-monthly-billing.timer sehatwarga-daily-overdue.timer
systemctl status sehatwarga-monthly-billing.service sehatwarga-daily-overdue.service
journalctl -u sehatwarga-monthly-billing.service --since today
journalctl -u sehatwarga-daily-overdue.service --since today
```

Setiap runner menghasilkan dua event JSON: `started` dan `finished`.
Log berisi nama job, UUID execution_id, started/finished timestamp UTC aware,
tanggal bisnis WIB, periode bulanan, durasi, status, exit_code dan kategori error.
Monthly mencatat eligible_participants, created, skipped_duplicates; daily
mencatat updated_overdue. Dry-run mencatat would_create atau would_update.
Counter yang tidak relevan/tidak diketahui setelah kegagalan bernilai null,
bukan angka sukses palsu. Raw stdout/stderr child, SQL, parameter query,
DATABASE_URL dan data peserta tidak diteruskan ke log runner.

| Exit/status | Arti/tindakan |
| --- | --- |
| 0, success | CLI berhasil dan ringkasan tervalidasi. |
| 0, preview | Dry-run berhasil; tidak ada perubahan. |
| 0, skipped_calendar | Guard platform UTC melewati hari selain tanggal 1 WIB; CLI tidak dijalankan. |
| 75, skipped_locked | Runner dengan lock yang sama masih aktif; tunggu selesai, lalu jalankan ulang jika perlu. |
| 124, failed/cli_timeout | Child melewati 1800 detik; diperhentikan, review DB/jaringan lalu ulangi. |
| Nonzero lain | Exit CLI diteruskan, atau runner gagal sebelum CLI/ringkasan valid. Jangan menganggap sukses. |

Untuk mengulang setelah penyebab gangguan diperbaiki, gunakan runner manual,
atau `sudo systemctl start sehatwarga-monthly-billing.service` / daily service
pada server yang unitnya sudah dipasang oleh operator. Periksa journal dan
ringkasan, jangan mengulang dalam loop tanpa batas. Jika mengatur retry pada
platform, batasi jumlah percobaan dan gunakan jeda; retry bukan bagian runner.

Tidak dibuat file log aplikasi yang tumbuh tanpa batas. Pada systemd gunakan
journald dan kebijakan retensi host (`SystemMaxUse`/`MaxRetentionSec` dikelola
operator). Platform harus menyediakan retention/rotation untuk stdout capture.

Troubleshooting:

- Missing venv/FileNotFoundError: periksa path project dan `.venv/bin/python`.
- PermissionError: periksa user unit, izin baca `.env`, serta direktori lock.
- cli_failure: periksa akses DB, konfigurasi backend, dan hasil preview CLI.
  Pesan CLI billing telah disanitasi; jangan mencetak `.env` untuk debugging.
- cli_timeout: periksa ketersediaan DB/latensi dan jumlah peserta sebelum rerun.
- Invalid summary/ValueError: pastikan runner dan CLI berasal dari versi project
  yang sama, `--json` tersedia, dan wrapper shell tidak mencampur output ke stdout.
- Lock busy: periksa proses aktif. Jangan menghapus lock file saat ada proses;
  menghapusnya bisa membuat inode kedua dan merusak mutual exclusion.

## Lock lokal dan beberapa server

Runner menggunakan `fcntl.flock(LOCK_EX | LOCK_NB)` pada
`<project>/.runtime/billing/<job>.lock` (diabaikan Git). Lock file tidak dihapus
setelah selesai; lock OS lepas ketika descriptor ditutup. Descriptor diwariskan
ke child CLI sehingga parent yang mati tidak melepas lock selama child masih
berjalan. Monthly dan daily mempunyai lock terpisah.

`SEHATWARGA_JOB_LOCK_DIR` dapat menunjuk direktori privat lain. Jika diubah,
semua pemanggilan manual/timer pada host yang sama harus memakai direktori
yang **sama**, dengan izin untuk user aplikasi. Tidak boleh tiap invocation
menggunakan temporary lock directory baru.

Lock ini hanya untuk **host/project yang sama**, pada filesystem lokal POSIX.
Beberapa checkout dengan lock directory berbeda, container tanpa shared lock,
atau beberapa host tidak saling terkunci. Pilih satu instance scheduler pada
platform. Tidak ada distributed/advisory lock baru; unique constraint tetap
menahan duplicate billing. CLI langsung kompatibel tetap tidak mengambil lock
runner; gunakan runner untuk operasi bulan/tanggal sekarang agar lock terpakai.
Backfill CLI langsung tetap dilindungi unique constraint, bukan flock runner.

Write conflict/deadlock/gangguan koneksi TiDB yang bukan duplikat terkonfirmasi
menghasilkan kegagalan nonzero; periksa lalu rerun. Tes SQLite dan mock error
tidak membuktikan perilaku concurrency TiDB. Staging TiDB terpisah diperlukan
untuk pembuktian tersebut sebelum pengoperasian multi-instance.

## Jadwal terlewat dan backfill

Monthly tidak membuat seluruh riwayat otomatis. Identifikasi periode yang benar
dan jalankan preview lalu CLI manual untuk tiap periode yang disetujui:

```sh
.venv/bin/python -m flask --app run.py generate-contributions --month 2026-10 --dry-run
.venv/bin/python -m flask --app run.py generate-contributions --month 2026-10
```

Backfill mengikuti **peserta aktif dan kelas/tarif saat eksekusi** karena sistem
existing tidak menyimpan riwayat eligibility/tarif historis. Nominal tagihan
existing tidak berubah. Jangan menganggap backfill merekonstruksi kondisi masa
lalu secara otomatis.

Overdue yang terlewat beberapa hari cukup dijalankan dengan tanggal WIB sekarang:
semua UNPAID yang sudah lewat jatuh tempo ikut diperbarui, PAID tidak berubah.

## Alternatif platform scheduler / cron

Belum ada platform deployment yang teridentifikasi, sehingga tidak dibuat
konfigurasi vendor atau deployment. Gunakan alternatif ini **sebagai pengganti**
systemd, jangan mengaktifkan keduanya.

Pastikan environment backend, working directory, `.venv`, timezone provider,
satu scheduler instance, batas waktu dan retensi log tersedia. Panggil script
langsung, bukan HTTP endpoint web. Runner hanya menerima opsi tetap, bukan
arbitrary command dari input pengguna/browser.

Jika platform mendukung timezone IANA, set **Asia/Jakarta**:

```text
15 0 1 * *  <project>/.venv/bin/python <project>/scripts/jobs/run_monthly_billing.py
30 0 * * *  <project>/.venv/bin/python <project>/scripts/jobs/run_daily_overdue.py
```

Jika provider hanya mendukung UTC:

- Monthly 1 pukul 00:15 WIB = **hari terakhir bulan sebelumnya pukul 17:15 UTC**.
  Ekspresi `15 17 1 * *` salah: itu sudah tanggal 2 WIB.
- Untuk cron lima field tanpa ekspresi last-day-of-month, jalankan guard setiap
  hari 17:15 UTC. `--only-first-day` hanya menjalankan CLI pada tanggal 1 WIB;
  hari lain menghasilkan skipped_calendar tanpa akses database.
- Daily 00:30 WIB = 17:30 UTC hari sebelumnya; runner tetap mengirim tanggal WIB.

```text
15 17 * * *  <project>/.venv/bin/python <project>/scripts/jobs/run_monthly_billing.py --only-first-day
30 17 * * *  <project>/.venv/bin/python <project>/scripts/jobs/run_daily_overdue.py
```

Pada cron Linux, dukungan `CRON_TZ=Asia/Jakarta` bergantung implementasi; verifikasi
sebelum memakai contoh WIB. Jika tidak didukung, gunakan contoh UTC setelah
memastikan timezone daemon memang UTC. Set path absolut yang benar dan env
backend; jangan menaruh credential dalam crontab. Tidak ada crontab yang dipasang.

Guard platform UTC tidak memberikan catch-up otomatis pada tanggal 2 ketika
tanggal 1 terlewat; operator menjalankan runner tanpa guard/backfill setelah
review. Fitur catch-up/retensi/retry platform harus dikonfigurasi eksplisit.

## Menonaktifkan

Pada deployment systemd yang sudah diaktifkan operator:

```sh
sudo systemctl disable --now sehatwarga-monthly-billing.timer sehatwarga-daily-overdue.timer
```

Menghentikan timer tidak membatalkan service yang sudah berjalan. Jika perlu
menghentikan job aktif, review lalu stop service; batch mungkin sudah commit
sebagian peserta dan dapat dilanjutkan dengan rerun idempotent.
Pada platform/cron, nonaktifkan/hapus jadwal di mekanisme yang dipilih. CLI manual
tetap tersedia. Flask worker tidak pernah memulai scheduler ketika create_app.

## Validasi dan rujukan

```sh
.venv/bin/python -m pytest tests/test_stage11.py -q
.venv/bin/python -m pytest -q
```

Tests meliputi runner subprocess nyata dan database SQLite file disposable,
hash file sebelum/sesudah dry-run, mock clock/driver error, flock lintas proses,
kalender UTC/WIB, dan `systemd-analyze verify` terhadap template yang dirender
ke temporary directory. Tidak memasang unit atau menjalankan systemctl.

Rujukan teknis primer:
[TiDB constraints](https://docs.pingcap.com/tidb/stable/constraints/),
[systemd.timer](https://www.freedesktop.org/software/systemd/man/250/systemd.timer.html).
Pembacaan dokumentasi bukan klaim pengujian tulis/concurrency pada TiDB produksi.
