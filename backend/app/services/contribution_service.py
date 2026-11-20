from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from app.extensions import db
from app.models.contribution import Contribution
from app.models.participant import Participant

# Centralized source of truth for simulation rates
# PENTING: Tarif ini adalah simulasi akademik SehatWarga, bukan tarif BPJS atau regulasi pemerintah resmi.
SIMULATED_RATES = {
    "CLASS_1": Decimal("150000.00"),
    "CLASS_2": Decimal("100000.00"),
    "CLASS_3": Decimal("50000.00"),
}

RATE_DESCRIPTION = "Tarif simulasi SehatWarga"

CONTRIBUTION_STATUS_LABELS = {
    "UNPAID": "Belum Dibayar",
    "PAID": "Lunas",
    "OVERDUE": "Terlambat",
}


def get_rate_for_service_class(service_class: str) -> Decimal:
    """
    Returns the simulated contribution rate for a specific service class.
    Label: Tarif simulasi SehatWarga (Bukan tarif resmi BPJS).
    """
    if service_class not in SIMULATED_RATES:
        raise ValueError(f"Kelas layanan '{service_class}' tidak memiliki tarif simulasi yang valid.")
    return SIMULATED_RATES[service_class]


def get_billing_period_start(target_date: date = None) -> date:
    """
    Normalizes any date to the first day of its month.
    Example: 2026-09-15 -> 2026-09-01
    """
    if target_date is None:
        target_date = date.today()
    return date(target_date.year, target_date.month, 1)


def get_simulated_due_date(billing_period: date) -> date:
    """
    Returns the simulated due date for a billing period (day 10 of that month).
    Example: 2026-09-01 -> 2026-09-10
    """
    period_start = get_billing_period_start(billing_period)
    return date(period_start.year, period_start.month, 10)


def generate_monthly_contribution(
    participant: Participant, billing_period: date = None, commit: bool = True
) -> tuple[Contribution, bool]:
    """
    Generates a single monthly contribution for an active participant.
    Idempotent: If contribution already exists for this participant and billing period,
    returns (existing_contribution, False).
    Only ACTIVE participants are eligible for new billing generation.
    """
    if participant.membership_status != "ACTIVE":
        raise ValueError("Peserta tidak aktif sehingga tidak dapat dibuatkan tagihan iuran baru.")

    period_start = get_billing_period_start(billing_period)

    # Check existing contribution for idempotency
    existing = db.session.execute(
        select(Contribution).filter_by(
            participant_id=participant.id, billing_period=period_start
        )
    ).scalar_one_or_none()

    if existing:
        return existing, False

    participant_id = participant.id
    # Snapshot rate based on participant's current service_class
    amount = get_rate_for_service_class(participant.service_class)
    due_date = get_simulated_due_date(period_start)

    contribution = Contribution(
        participant_id=participant.id,
        billing_period=period_start,
        amount=amount,
        status="UNPAID",
        due_date=due_date,
    )
    db.session.add(contribution)

    if commit:
        try:
            db.session.commit()
        except DBAPIError as error:
            db.session.rollback()
            # Recover only a duplicate confirmed by the unique business key in
            # a new transaction. No savepoints/advisory locks assumed on TiDB.
            code = getattr(error.orig, "sqlite_errorcode", None)
            args = getattr(error.orig, "args", ())
            duplicate = code == 2067 or (bool(args) and (
                args[0] == 1062 or (args[0] == 8147 and "[kv:1062]" in str(error.orig))
            ))
            if duplicate:
                existing = db.session.execute(select(Contribution).filter_by(
                    participant_id=participant_id, billing_period=period_start
                )).scalar_one_or_none()
                if existing is not None:
                    return existing, False
            raise
        except Exception:
            db.session.rollback()
            raise

    return contribution, True


def generate_contributions_for_active_participants(target_period: date = None, *, dry_run: bool = False) -> dict:
    """
    Generates monthly contributions for all ACTIVE participants for a given billing month.
    Idempotent: skips participants who already have a bill for this month.
    Returns summary dict.
    """
    period_start = get_billing_period_start(target_period)

    created_count = 0
    skipped_count = 0
    would_create = 0

    try:
        with db.session.no_autoflush:
            active_participants = db.session.execute(
                select(Participant).filter_by(membership_status="ACTIVE").order_by(Participant.id)
            ).scalars().all()
            for participant in active_participants:
                if dry_run:
                    exists = db.session.execute(select(Contribution.id).filter_by(
                        participant_id=participant.id, billing_period=period_start
                    )).scalar_one_or_none()
                    if exists is not None:
                        skipped_count += 1
                    else:
                        get_rate_for_service_class(participant.service_class)
                        would_create += 1
                else:
                    # Commit each contribution through the same single-record
                    # service. A losing duplicate rolls back only this attempt;
                    # previous records survive and rerunning completes the batch.
                    _, created = generate_monthly_contribution(participant, period_start)
                    created_count += int(created)
                    skipped_count += int(not created)
    except Exception:
        db.session.rollback()
        raise

    return {
        "period": period_start,
        "created": created_count,
        "skipped": skipped_count,
        "total_active": len(active_participants),
        "would_create": would_create,
        "dry_run": dry_run,
    }


def mark_overdue_contributions(reference_date: date = None, as_of_date: date = None, *, dry_run: bool = False) -> int:
    """
    Scans for UNPAID contributions past their due date and transitions them to OVERDUE.
    PAID contributions are strictly untouched.
    Returns the number of updated records.
    """
    target_date = as_of_date if as_of_date is not None else reference_date
    if target_date is None:
        target_date = date.today()

    eligible = (Contribution.status == "UNPAID", Contribution.due_date < target_date)
    try:
        if dry_run:
            from sqlalchemy import func
            with db.session.no_autoflush:
                return db.session.execute(select(func.count()).select_from(Contribution).where(*eligible)).scalar_one()
        # Evaluate status in the UPDATE itself, not from a stale ORM snapshot.
        # A contribution already paid by a concurrent transaction cannot match.
        result = db.session.execute(update(Contribution).where(*eligible).values(
            status="OVERDUE", updated_at=datetime.now(timezone.utc)
        ))
        db.session.commit()
        return result.rowcount
    except Exception:
        db.session.rollback()
        raise


def validate_contribution_ownership(contribution: Contribution, participant_id: int) -> bool:
    """
    Validates whether a contribution belongs to the specified participant.
    """
    return contribution.participant_id == participant_id
