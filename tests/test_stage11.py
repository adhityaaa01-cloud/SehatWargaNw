"""Stage 11 billing, CLI and external runner verification on disposable DBs."""
import contextlib
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests import create_test_app
from app.extensions import db
from app.models import Contribution, Participant, Payment, User
from app.services import contribution_service as billing
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError, OperationalError
from scripts.jobs import _runner as jobs

ROOT = Path(__file__).resolve().parents[1]
PERIOD = date(2026, 11, 1)


def participant(index, service_class='CLASS_3', active=True):
    user = User(name=f'Dummy {index}', email=f'billing{index}@example.com',
                password_hash='test-only-unusable', role='citizen', is_active=True)
    db.session.add(user)
    db.session.flush()
    person = Participant(user_id=user.id, participant_number=f'SW-TEST-{index}',
                         full_name=user.name, birth_date=date(1990, 1, 1), gender='MALE',
                         service_class=service_class, membership_status='ACTIVE' if active else 'INACTIVE')
    db.session.add(person)
    db.session.commit()
    return person


def count_bills():
    return db.session.execute(select(func.count()).select_from(Contribution)).scalar_one()


class BillingAutomationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_test_app()
        self.context = self.app.app_context()
        self.context.push()
        self.cli = self.app.test_cli_runner()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_monthly_active_classes_due_period_and_repeat(self):
        active = [participant(i, key) for i, key in enumerate(['CLASS_1', 'CLASS_2', 'CLASS_3'])]
        inactive = participant(99, active=False)
        first = billing.generate_contributions_for_active_participants(PERIOD)
        self.assertEqual((first['created'], first['skipped'], first['total_active']), (3, 0, 3))
        for person in active:
            with self.subTest(service_class=person.service_class):
                bill = db.session.execute(select(Contribution).filter_by(participant_id=person.id)).scalar_one()
                self.assertEqual(bill.amount, billing.SIMULATED_RATES[person.service_class])
                self.assertEqual(bill.billing_period, PERIOD)
                self.assertEqual(bill.due_date, date(2026, 11, 10))
                self.assertEqual(bill.status, 'UNPAID')
        self.assertFalse(db.session.execute(select(Contribution).filter_by(participant_id=inactive.id)).scalars().all())
        for _ in range(2):
            repeated = billing.generate_contributions_for_active_participants(PERIOD)
            self.assertEqual((repeated['created'], repeated['skipped']), (0, 3))
        self.assertEqual(count_bills(), 3)
        self.assertEqual(billing.generate_contributions_for_active_participants(date(2026, 12, 1))['created'], 3)
        self.assertEqual(count_bills(), 6)

    def test_snapshot_survives_rate_and_class_change(self):
        person = participant(1)
        bill, _ = billing.generate_monthly_contribution(person, PERIOD)
        original = bill.amount
        person.service_class = 'CLASS_1'
        db.session.commit()
        with patch.dict(billing.SIMULATED_RATES, {'CLASS_1': Decimal('123456.00')}):
            same, created = billing.generate_monthly_contribution(person, PERIOD)
            future, _ = billing.generate_monthly_contribution(person, date(2026, 12, 1))
            self.assertFalse(created)
            self.assertEqual(same.amount, original)
            self.assertEqual(future.amount, Decimal('123456.00'))

    def test_unique_constraint_still_enforced(self):
        person = participant(1)
        billing.generate_monthly_contribution(person, PERIOD)
        db.session.add(Contribution(participant_id=person.id, billing_period=PERIOD,
                                    amount=1, due_date=date(2026, 11, 10)))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        self.assertEqual(count_bills(), 1)

    def test_duplicate_race_rolls_back_losing_attempt_and_continues_batch(self):
        first = participant(1)
        second = participant(2)
        billing.generate_monthly_contribution(first, PERIOD)
        original = billing.generate_monthly_contribution
        def race(person, period):
            if person.id == first.id:
                real_execute = db.session.execute
                hidden = False
                def stale_lookup(statement, *args, **kwargs):
                    nonlocal hidden
                    if not hidden:
                        hidden = True
                        return MagicMock(scalar_one_or_none=lambda: None)
                    return real_execute(statement, *args, **kwargs)
                # Hide just the pre-insert lookup; the actual INSERT hits the
                # real SQLite unique constraint, as if another worker won.
                with patch.object(db.session, 'execute', side_effect=stale_lookup):
                    return original(person, period)
            return original(person, period)
        with patch.object(billing, 'generate_monthly_contribution', side_effect=race):
            result = billing.generate_contributions_for_active_participants(PERIOD)
        self.assertEqual((result['created'], result['skipped']), (1, 1))
        self.assertEqual(count_bills(), 2)
        self.assertEqual(db.session.execute(select(Contribution).filter_by(participant_id=second.id)).scalar_one().status, 'UNPAID')

    def test_other_integrity_failure_not_misclassified_as_duplicate(self):
        person = participant(1)
        with patch.object(billing, 'get_rate_for_service_class', return_value=None):
            with self.assertRaises(IntegrityError):
                billing.generate_monthly_contribution(person, PERIOD)
        self.assertEqual(count_bills(), 0)
        self.assertTrue(billing.generate_monthly_contribution(person, PERIOD)[1])

    def test_mysql_and_tidb_duplicate_codes_require_confirmed_existing_bill(self):
        person = participant(1)
        billing.generate_monthly_contribution(person, PERIOD)
        for code, message in [(1062, 'Duplicate entry for business key'),
                              (8147, 'transaction aborted [kv:1062]Duplicate entry for business key')]:
            with self.subTest(code=code):
                real_execute = db.session.execute
                calls = 0
                def hide_first(statement, *args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        return MagicMock(scalar_one_or_none=lambda: None)
                    return real_execute(statement, *args, **kwargs)
                error = OperationalError('INSERT', {}, Exception(code, message))
                with patch.object(db.session, 'execute', side_effect=hide_first), \
                     patch.object(db.session, 'commit', side_effect=error):
                    recovered, created = billing.generate_monthly_contribution(person, PERIOD)
                self.assertFalse(created)
                self.assertEqual(recovered.participant_id, person.id)
                self.assertEqual(count_bills(), 1)

    def test_partial_batch_error_is_rerunnable_without_duplicates(self):
        participant(1)
        second = participant(2)
        second.service_class = 'INVALID'
        db.session.commit()
        with self.assertRaises(ValueError):
            billing.generate_contributions_for_active_participants(PERIOD)
        self.assertEqual(count_bills(), 1)
        second.service_class = 'CLASS_3'
        db.session.commit()
        result = billing.generate_contributions_for_active_participants(PERIOD)
        self.assertEqual((result['created'], result['skipped']), (1, 1))

    def test_monthly_dry_run_never_adds_flushes_or_commits(self):
        participant(1)
        with patch.object(db.session, 'commit', side_effect=AssertionError('commit forbidden')), \
             patch.object(db.session, 'add', side_effect=AssertionError('add forbidden')), \
             patch.object(db.session, 'flush', side_effect=AssertionError('flush forbidden')):
            result = self.cli.invoke(args=['generate-contributions', '--month', '2026-11', '--dry-run', '--json'])
        self.assertEqual(result.exit_code, 0, result.output)
        summary = json.loads(result.output)
        self.assertEqual((summary['created'], summary['would_create'], summary['total_active']), (0, 1, 1))
        self.assertEqual(count_bills(), 0)

    def test_invalid_month_is_nonzero_without_writes(self):
        participant(1)
        for value in ['2026-13', '2026-1', '0000-01', 'November', '', '2026-11-01']:
            with self.subTest(month=value):
                result = self.cli.invoke(args=['generate-contributions', '--month', value])
                self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(count_bills(), 0)

    def test_cli_compatibility_and_json_counters(self):
        participant(1)
        result = self.cli.invoke(args=['generate-contributions', '--month', '2026-11'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Tagihan periode', result.output)
        again = self.cli.invoke(args=['generate-contributions', '--month', '2026-11', '--json'])
        self.assertEqual(json.loads(again.output)['skipped'], 1)
        overdue = self.cli.invoke(args=['update-overdue', '--as-of', '2026-11-11'])
        self.assertEqual(overdue.exit_code, 0)
        self.assertIn('Pembaruan status overdue selesai: 1', overdue.output)

    def test_overdue_due_boundary_and_idempotency(self):
        person = participant(1)
        bill, _ = billing.generate_monthly_contribution(person, PERIOD)
        for as_of in [date(2026, 11, 9), date(2026, 11, 10)]:
            with self.subTest(as_of=as_of):
                self.assertEqual(billing.mark_overdue_contributions(as_of_date=as_of), 0)
                self.assertEqual(bill.status, 'UNPAID')
        self.assertEqual(billing.mark_overdue_contributions(as_of_date=date(2026, 11, 11)), 1)
        db.session.refresh(bill)
        timestamp = bill.updated_at
        self.assertEqual(bill.status, 'OVERDUE')
        self.assertEqual(billing.mark_overdue_contributions(as_of_date=date(2026, 11, 11)), 0)
        db.session.refresh(bill)
        self.assertEqual(bill.updated_at, timestamp)

    def test_overdue_paid_pending_and_other_records_policy(self):
        person = participant(1)
        paid, _ = billing.generate_monthly_contribution(person, date(2026, 1, 1))
        paid.status = 'PAID'
        already, _ = billing.generate_monthly_contribution(person, date(2026, 2, 1))
        already.status = 'OVERDUE'
        pending_bill, _ = billing.generate_monthly_contribution(person, date(2026, 3, 1))
        pending = Payment(contribution_id=pending_bill.id, payment_number='PENDING-TEST', amount=pending_bill.amount,
                          payment_method='SIMULATION_TRANSFER', status='PENDING')
        db.session.add(pending)
        other = participant(2)
        future, _ = billing.generate_monthly_contribution(other, date(2027, 1, 1))
        timestamps = {item.id: item.updated_at for item in [paid, already, future]}
        self.assertEqual(billing.mark_overdue_contributions(as_of_date=date(2026, 11, 11)), 1)
        for item, status in [(paid, 'PAID'), (already, 'OVERDUE'), (future, 'UNPAID')]:
            db.session.refresh(item)
            self.assertEqual(item.status, status)
            self.assertEqual(item.updated_at, timestamps[item.id])
        db.session.refresh(pending_bill)
        db.session.refresh(pending)
        self.assertEqual(pending_bill.status, 'OVERDUE')
        self.assertEqual(pending.status, 'PENDING')  # Existing policy: no hold on Contribution.

    def test_atomic_overdue_cannot_overwrite_payment_that_won_first(self):
        person = participant(1)
        bill, _ = billing.generate_monthly_contribution(person, PERIOD)
        real_execute = db.session.execute
        intercepted = False
        def pay_before_update(statement, *args, **kwargs):
            nonlocal intercepted
            if getattr(statement, 'is_update', False) and not intercepted:
                intercepted = True
                real_execute(update(Contribution).where(Contribution.id == bill.id).values(status='PAID'))
            return real_execute(statement, *args, **kwargs)
        with patch.object(db.session, 'execute', side_effect=pay_before_update):
            self.assertEqual(billing.mark_overdue_contributions(as_of_date=date(2026, 11, 11)), 0)
        db.session.refresh(bill)
        self.assertTrue(intercepted)
        self.assertEqual(bill.status, 'PAID')

    def test_overdue_dry_run_no_update_or_commit(self):
        person = participant(1)
        bill, _ = billing.generate_monthly_contribution(person, PERIOD)
        with patch.object(db.session, 'commit', side_effect=AssertionError('commit forbidden')):
            result = self.cli.invoke(args=['update-overdue', '--as-of', '2026-11-11', '--dry-run', '--json'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)['would_update'], 1)
        db.session.refresh(bill)
        self.assertEqual(bill.status, 'UNPAID')

    def test_invalid_as_of_is_nonzero(self):
        for value in ['2026-11-31', '2026-1-1', 'tomorrow', '', '2026-11-11T00:30:00']:
            with self.subTest(as_of=value):
                self.assertNotEqual(self.cli.invoke(args=['update-overdue', '--as-of', value]).exit_code, 0)

    def test_cli_failure_sanitizes_database_error_and_rolls_back(self):
        secret = 'mysql://private-user:private-password@private-host/db SQL bind private-person'
        error = OperationalError('sensitive SQL', {'email': 'private-person'}, Exception(secret))
        for command, function in [('generate-contributions', 'generate_contributions_for_active_participants'),
                                  ('update-overdue', 'mark_overdue_contributions')]:
            with self.subTest(command=command), patch.object(billing, function, side_effect=error):
                result = self.cli.invoke(args=[command, '--json'])
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn('OperationalError', result.output)
                for value in ['private-user', 'private-password', 'private-host', 'private-person', 'sensitive SQL']:
                    self.assertNotIn(value, result.output)
        self.assertEqual(count_bills(), 0)

    def test_cli_default_dates_use_wib_at_utc_month_boundary(self):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 12, 31, 17, 20, tzinfo=timezone.utc).astimezone(tz)
        # The commands import datetime at invocation, so patch the module class.
        with patch('datetime.datetime', Clock):
            monthly = self.cli.invoke(args=['generate-contributions', '--dry-run', '--json'])
            daily = self.cli.invoke(args=['update-overdue', '--dry-run', '--json'])
        self.assertEqual(json.loads(monthly.output)['period'], '2027-01')
        self.assertEqual(json.loads(daily.output)['as_of'], '2027-01-01')


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {'SEHATWARGA_JOB_LOCK_DIR': self.directory.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def invoke(self, job, result=None, now=None, args=None):
        output = io.StringIO()
        instant = now or datetime(2026, 11, 30, 17, 15, tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz)
        with patch.object(jobs, 'datetime', Clock), patch.object(jobs.subprocess, 'run') as child, contextlib.redirect_stdout(output):
            if isinstance(result, Exception):
                child.side_effect = result
            else:
                child.return_value = result or subprocess.CompletedProcess([], 7, 'SECRET stdout', 'SECRET stderr')
            code = jobs.run_job(job, args or [])
        logs = [json.loads(line) for line in output.getvalue().splitlines()]
        return code, logs, child

    def test_wib_boundaries(self):
        for instant, expected in [
            (datetime(2026, 11, 30, 16, 59, tzinfo=timezone.utc), date(2026, 11, 30)),
            (datetime(2026, 11, 30, 17, 0, tzinfo=timezone.utc), date(2026, 12, 1)),
            (datetime(2026, 12, 31, 17, 0, tzinfo=timezone.utc), date(2027, 1, 1))]:
            with self.subTest(instant=instant):
                self.assertEqual(jobs.business_date(instant), expected)
        with self.assertRaises(ValueError):
            jobs.business_date(datetime(2026, 11, 1))

    def test_monthly_cli_interpreter_root_explicit_period_and_safe_metrics(self):
        result = {'success': True, 'dry_run': False, 'period': '2026-12', 'total_active': 3,
                  'created': 2, 'skipped': 1, 'would_create': 0, 'extra_pii': 'PRIVATE'}
        code, logs, child = self.invoke('monthly-billing', subprocess.CompletedProcess([], 0, json.dumps(result), 'PRIVATE'))
        self.assertEqual(code, 0)
        args, kwargs = child.call_args
        self.assertEqual(args[0], [str(ROOT / '.venv/bin/python'), '-m', 'flask', '--app', 'run.py',
                                   'generate-contributions', '--month', '2026-12', '--json'])
        self.assertEqual(kwargs['cwd'], ROOT)
        self.assertEqual(len(kwargs['pass_fds']), 1)
        self.assertNotIn('shell', kwargs)
        self.assertEqual(logs[-1]['created'], 2)
        self.assertEqual(logs[-1]['eligible_participants'], 3)
        self.assertEqual(logs[-1]['skipped_duplicates'], 1)
        self.assertEqual(logs[0]['execution_id'], logs[-1]['execution_id'])
        self.assertNotIn('PRIVATE', json.dumps(logs))

    def test_daily_cli_correct_wib_date_and_dry_run(self):
        result = {'success': True, 'dry_run': True, 'as_of': '2026-12-01', 'updated': 0, 'would_update': 4}
        code, logs, child = self.invoke('daily-overdue', subprocess.CompletedProcess([], 0, json.dumps(result), ''), args=['--dry-run'])
        self.assertEqual(code, 0)
        self.assertEqual(child.call_args.args[0][-5:], ['update-overdue', '--as-of', '2026-12-01', '--json', '--dry-run'])
        self.assertEqual(logs[-1]['status'], 'preview')
        self.assertEqual(logs[-1]['updated_overdue'], 0)
        self.assertEqual(logs[-1]['would_update'], 4)

    def test_utc_only_platform_guard_skips_other_days_without_cli(self):
        code, logs, child = self.invoke('monthly-billing', now=datetime(2026, 11, 29, 17, 15, tzinfo=timezone.utc),
                                       args=['--only-first-day'])
        self.assertEqual(code, 0)
        self.assertEqual(logs[-1]['status'], 'skipped_calendar')
        child.assert_not_called()
        code, _, child = self.invoke('monthly-billing', args=['--only-first-day'])
        self.assertEqual(code, 7)
        child.assert_called_once()

    def test_failure_nonzero_and_no_raw_output_or_environment_secrets(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'SECRET', 'SECRET_KEY': 'SECRET', 'AI_API_KEY': 'SECRET'}):
            code, logs, _ = self.invoke('monthly-billing')
        self.assertEqual(code, 7)
        self.assertEqual(logs[-1]['status'], 'failed')
        self.assertIsNone(logs[-1]['created'])
        self.assertNotIn('SECRET', json.dumps(logs))

    def test_timeout_and_invalid_summary_are_failures(self):
        code, logs, _ = self.invoke('daily-overdue', subprocess.TimeoutExpired(['secret'], 1800, stderr='secret'))
        self.assertEqual(code, 124)
        self.assertEqual(logs[-1]['error_category'], 'cli_timeout')
        for payload in ['not JSON SECRET', json.dumps({'success': True, 'dry_run': False})]:
            with self.subTest(payload=payload):
                code, logs, _ = self.invoke('daily-overdue', subprocess.CompletedProcess([], 0, payload, ''))
                self.assertNotEqual(code, 0)
                self.assertNotIn('SECRET', json.dumps(logs))

    def test_same_host_lock_blocks_parallel_runner_and_releases(self):
        with jobs.job_lock('monthly-billing'):
            code, logs, child = self.invoke('monthly-billing')
            self.assertEqual(code, 75)
            self.assertEqual(logs[-1]['status'], 'skipped_locked')
            child.assert_not_called()
        code, _, child = self.invoke('monthly-billing')
        child.assert_called_once()
        self.assertEqual(code, 7)  # Child now starts; failure is the mock CLI's exit.

    def test_lock_persists_inode_and_is_shared_across_processes(self):
        script = ('import sys;sys.path.insert(0,sys.argv[1]);from scripts.jobs._runner import job_lock;'
                  '\ntry:\n with job_lock("monthly-billing"): pass\nexcept BlockingIOError: sys.exit(75)')
        path = Path(self.directory.name) / 'monthly-billing.lock'
        with jobs.job_lock('monthly-billing'):
            inode = path.stat().st_ino
            child = subprocess.run([sys.executable, '-c', script, str(ROOT)], capture_output=True)
            self.assertEqual(child.returncode, 75, child.stderr)
        child = subprocess.run([sys.executable, '-c', script, str(ROOT)], capture_output=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(path.stat().st_ino, inode)

    def test_import_and_create_app_never_start_scheduler(self):
        with patch.object(jobs.subprocess, 'run') as child, patch('threading.Thread.start') as thread:
            create_test_app()
            import importlib
            import scripts.jobs.run_monthly_billing as monthly
            import scripts.jobs.run_daily_overdue as daily
            importlib.reload(monthly)
            importlib.reload(daily)
            child.assert_not_called()
            thread.assert_not_called()

    def test_systemd_calendars_and_rendered_unit_validation(self):
        self.assertIsNotNone(shutil.which('systemd-analyze'), 'systemd-analyze required for Stage 11 timer validation')
        for name, expression, expected_utc in [
            ('monthly-billing', '*-*-01 00:15:00 Asia/Jakarta', '2026-11-30 17:15:00 UTC'),
            ('daily-overdue', '*-*-* 00:30:00 Asia/Jakarta', '2026-11-30 17:30:00 UTC')]:
            timer = (ROOT / f'deploy/systemd/sehatwarga-{name}.timer').read_text()
            self.assertIn('OnCalendar=' + expression, timer)
            result = subprocess.run(['systemd-analyze', 'calendar', '--base-time=2026-11-30 16:00:00 UTC', expression], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected_utc, result.stdout)
        target = Path(self.directory.name)
        for source in (ROOT / 'deploy/systemd').glob('sehatwarga-*'):
            contents = source.read_text().replace('@PROJECT_ROOT@', str(ROOT)).replace('@SERVICE_USER@', pwd.getpwuid(os.getuid()).pw_name)
            (target / source.name).write_text(contents)
        units = [str(p) for p in target.glob('*.service')] + [str(p) for p in target.glob('*.timer')]
        result = subprocess.run(['systemd-analyze', 'verify', *units], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class RealRunnerIntegrationTests(unittest.TestCase):
    def test_real_subprocess_cli_jobs_and_dry_runs_only_touch_disposable_sqlite(self):
        # File SQLite is shared with real CLI child processes; no provider or
        # production URL is loaded. This does NOT claim TiDB concurrency coverage.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'billing.sqlite'
            url = 'sqlite:///' + str(path)
            from app import create_app
            app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': url, 'AI_PROVIDER': 'fallback'})
            with app.app_context():
                db.create_all()
                person = participant(1, 'CLASS_2')
                past, _ = billing.generate_monthly_contribution(person, date(2001, 1, 1))
                past_id = past.id
            env = {**os.environ, 'DATABASE_URL': url, 'PYTHON_DOTENV_DISABLED': '1', 'SEHATWARGA_TESTING': '1',
                   'AI_PROVIDER': 'fallback', 'SEHATWARGA_JOB_LOCK_DIR': str(Path(directory) / 'locks')}
            def run(name, *args):
                result = subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / f'scripts/jobs/run_{name}.py'), *args],
                                        cwd=directory, env=env, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return json.loads(result.stdout.splitlines()[-1])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(run('monthly_billing', '--dry-run')['created'], 0)
            self.assertEqual(run('daily_overdue', '--dry-run')['would_update'], 1)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
            self.assertEqual(run('monthly_billing')['created'], 1)
            self.assertEqual(run('monthly_billing')['skipped_duplicates'], 1)
            daily = run('daily_overdue')
            self.assertGreaterEqual(daily['updated_overdue'], 1)
            self.assertEqual(run('daily_overdue')['updated_overdue'], 0)
            with app.app_context():
                self.assertEqual(count_bills(), 2)
                self.assertEqual(db.session.get(Contribution, past_id).status, 'OVERDUE')
                self.assertFalse(db.session.execute(select(Payment)).scalars().all())
                db.session.remove()
                db.engine.dispose()
