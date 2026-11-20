import unittest
from unittest.mock import patch

from tests import create_test_app
from app.extensions import db
from sqlalchemy.exc import OperationalError


class DatabaseAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.app = create_test_app()
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_login_recovers_after_database_outage(self):
        credentials = {'email': 'warga.demo@sehatwarga.test', 'password': 'invalid-password'}
        error = OperationalError('SELECT private', {}, OSError('private database hostname'))
        with patch.object(db.session, 'execute', side_effect=error):
            response = self.client.post('/login', data=credentials)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Retry-After'], '30')
        self.assertIn('Koneksi Database Sedang Terganggu', response.text)
        self.assertNotIn('private', response.text)
        self.assertEqual(self.client.post('/login', data=credentials).status_code, 401)

    def test_outage_during_session_user_loading_does_not_break_error_page(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '123'
            session['_fresh'] = True
        error = OperationalError('SELECT', {}, OSError('DNS unavailable'))
        with patch.object(db.session, 'get', side_effect=error) as lookup:
            response = self.client.get('/citizen/dashboard')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(lookup.call_count, 1)
        with self.client.session_transaction() as session:
            self.assertEqual(session['_user_id'], '123')
