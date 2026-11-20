"""Standard-library runner. No Flask import, scheduler thread or DB connection.

Runs only the existing, fixed Flask billing commands with explicit WIB arguments.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIB = ZoneInfo('Asia/Jakarta')
JOBS = {'monthly-billing': ('generate-contributions', '--month'),
        'daily-overdue': ('update-overdue', '--as-of')}


def business_date(now=None):
    now = now if now is not None else datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Aware clock required')
    return now.astimezone(WIB).date()


@contextmanager
def job_lock(job):
    # Same project/host lock for scheduled, manual and dry-run runner executions.
    # Never unlink: a second inode would allow parallel holders of "the same" lock.
    import fcntl
    directory = Path(os.environ.get('SEHATWARGA_JOB_LOCK_DIR', PROJECT_ROOT / '.runtime/billing'))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / (job + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        os.close(fd)


def emit(**fields):
    print(json.dumps(fields, sort_keys=True), flush=True)


def run_job(job, argv=None):
    if job not in JOBS:
        raise ValueError('Unknown job')
    parser = argparse.ArgumentParser(description=job + ' through the existing Flask CLI')
    parser.add_argument('--dry-run', action='store_true', help='Read-only preview through the billing service')
    if job == 'monthly-billing':
        parser.add_argument('--only-first-day', action='store_true',
                            help='UTC-only platform guard: skip unless the WIB business day is 1')
    options = parser.parse_args(argv)
    execution_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    started_clock = time.monotonic()
    today = business_date(started_at)
    period = today.strftime('%Y-%m') if job == 'monthly-billing' else None
    base = {'job': job, 'execution_id': execution_id, 'started_at': started_at.isoformat(),
            'business_date': today.isoformat(), 'billing_period': period,
            'timezone': 'Asia/Jakarta', 'dry_run': options.dry_run}
    emit(**base, event='started')
    metrics = {'eligible_participants': None, 'created': None, 'skipped_duplicates': None,
               'updated_overdue': None, 'would_create': None, 'would_update': None}
    code, status, category = 1, 'failed', None
    try:
        if job == 'monthly-billing' and options.only_first_day and today.day != 1:
            emit(**base, **metrics, event='finished', finished_at=datetime.now(timezone.utc).isoformat(),
                 duration_seconds=round(time.monotonic() - started_clock, 3), status='skipped_calendar',
                 exit_code=0, error_category=None)
            return 0
        with job_lock(job) as fd:
            python = PROJECT_ROOT / '.venv/bin/python'
            if not python.is_file():
                raise FileNotFoundError('Project virtual environment missing')
            command, argument = JOBS[job]
            value = period if period is not None else today.isoformat()
            args = [str(python), '-m', 'flask', '--app', 'run.py', command, argument, value, '--json']
            if options.dry_run:
                args.append('--dry-run')
            # Keep the lock in the child too: if the parent is killed, another
            # runner must not overlap the still-running CLI. Never shell=True.
            result = subprocess.run(args, cwd=PROJECT_ROOT, capture_output=True, text=True,
                                    timeout=1800, pass_fds=(fd,))
            code = result.returncode if result.returncode >= 0 else 128 - result.returncode
            # Raw stdout/stderr may contain DB exceptions; never forward them.
            if code:
                category = 'cli_failure'
            else:
                summary = json.loads(result.stdout)
                if summary.get('success') is not True or summary.get('dry_run') != options.dry_run:
                    raise ValueError('Invalid CLI summary')
                keys = ['total_active', 'created', 'skipped', 'would_create'] if period else ['updated', 'would_update']
                if any(type(summary.get(key)) is not int or summary[key] < 0 for key in keys):
                    raise ValueError('Invalid CLI counters')
                if period and summary.get('period') != period:
                    raise ValueError('Wrong CLI billing period')
                if period is None and summary.get('as_of') != today.isoformat():
                    raise ValueError('Wrong CLI business date')
                if period:
                    metrics.update(eligible_participants=summary['total_active'], created=summary['created'],
                                   skipped_duplicates=summary['skipped'], would_create=summary['would_create'])
                else:
                    metrics.update(updated_overdue=summary['updated'], would_update=summary['would_update'])
                status = 'preview' if options.dry_run else 'success'
    except BlockingIOError:
        code, status, category = 75, 'skipped_locked', 'lock_busy'
    except subprocess.TimeoutExpired:
        code, category = 124, 'cli_timeout'
    except Exception as error:
        code, category = 1, type(error).__name__
    emit(**base, **metrics, event='finished', finished_at=datetime.now(timezone.utc).isoformat(),
         duration_seconds=round(time.monotonic() - started_clock, 3), status=status,
         exit_code=code, error_category=category)
    return code
