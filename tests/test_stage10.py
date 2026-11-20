"""Regressions found during Stage 10 workflow/document verification."""
import unittest
from datetime import datetime, timezone
from sqlalchemy import select
from tests import create_test_app
from app.extensions import db
from app.models import HealthFacility, User, Payment


class Stage10RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_test_app()
        result = cls.app.test_cli_runner().invoke(args=[
            'seed-demo', '--admin-password=AdminDemo123!', '--citizen-password=WargaDemo123!'])
        if result.exit_code:
            raise RuntimeError('Unable to seed isolated Stage 10 database')

    def test_zero_coordinates_render_detail_map(self):
        with self.app.app_context():
            for index, (latitude, longitude) in enumerate([(0, 106), (-6, 0), (0, 0)]):
                facility = HealthFacility(facility_code=f'S10-ZERO-{index}', name='Zero coordinate fixture',
                                          facility_type='CLINIC', latitude=latitude, longitude=longitude, is_active=True)
                db.session.add(facility)
                db.session.commit()
                with self.subTest(latitude=latitude, longitude=longitude):
                    response = self.app.test_client().get(f'/facilities/{facility.id}')
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(b'id="facility-detail-map"', response.data)
                    self.assertNotIn(b'Lokasi peta belum tersedia', response.data)

    def test_missing_coordinates_still_hide_map(self):
        with self.app.app_context():
            for index, (latitude, longitude) in enumerate([(None, 106), (-6, None)]):
                facility = HealthFacility(facility_code=f'S10-NONE-{index}', name='Missing coordinate fixture',
                                          facility_type='CLINIC', latitude=latitude, longitude=longitude, is_active=True)
                db.session.add(facility)
                db.session.commit()
                with self.subTest(latitude=latitude, longitude=longitude):
                    response = self.app.test_client().get(f'/facilities/{facility.id}')
                    self.assertNotIn(b'id="facility-detail-map"', response.data)
                    self.assertIn(b'Lokasi peta belum tersedia', response.data)

    def test_document_timestamps_convert_utc_to_wib_across_day_boundary(self):
        with self.app.app_context():
            admin = db.session.execute(select(User).filter_by(email='admin.demo@sehatwarga.test')).scalar_one()
            payment = db.session.execute(select(Payment)).scalars().first()
            # Persisted SQLAlchemy UTC datetimes are naive when loaded from SQLite/MySQL.
            instant = datetime(2026, 1, 1, 20, 30)
            payment.created_at = instant
            payment.paid_at = instant
            payment.contribution.participant.registered_at = instant
            db.session.commit()
            citizen_id = payment.contribution.participant.user_id
            admin_id, payment_id, contribution_id = admin.id, payment.id, payment.contribution_id
        # Requests need their own Flask contexts so current_user is not cached
        # across different sessions by an enclosing application context.
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(citizen_id)
            session['_fresh'] = True
        receipt = client.get(f'/citizen/payments/{payment_id}')
        self.assertEqual(receipt.status_code, 200)
        self.assertIn(b'02 January 2026, 03:30:00 WIB', receipt.data)
        profile = client.get('/citizen/profile')
        self.assertIn(b'02 January 2026 03:30 WIB', profile.data)
        with client.session_transaction() as session:
            session['_user_id'] = str(admin_id)
        detail = client.get(f'/admin/contributions/{contribution_id}')
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'02 January 2026 03:30 WIB', detail.data)

    def test_aware_timestamp_keeps_instant(self):
        # Also handle aware values returned by services before a DB reload.
        with self.app.app_context():
            rendered = self.app.jinja_env.from_string('{{ value|wib_datetime("%Y-%m-%d %H:%M WIB") }}').render(
                value=datetime(2026, 12, 31, 20, 30, tzinfo=timezone.utc))
            self.assertEqual(rendered, '2027-01-01 03:30 WIB')
