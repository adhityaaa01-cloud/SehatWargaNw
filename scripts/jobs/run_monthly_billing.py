"""Monthly billing entry point; invoked externally, never by a Flask worker."""
if __package__:
    from ._runner import run_job
else:
    from _runner import run_job

if __name__ == '__main__':
    raise SystemExit(run_job('monthly-billing'))
