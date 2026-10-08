import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import Base
from app.models import AlertLog, AppConfig, FetchStatus, PriceHistory, StationPrice
from app.services.overview import overview_data
from app.services.poller import PricePoller
from tests.support import AppServer, UNSAFE_NAME


class PollingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            db.add(AppConfig(id=1, only_open=False))
            db.commit()
        self.session_patch = patch('app.services.poller.SessionLocal', self.sessions)
        self.session_patch.start()
        self.key_patch = patch.object(settings, 'tankerkoenig_api_key', 'test-key')
        self.key_patch.start()
        self.poller = PricePoller()
        self.station = dict(id='station', name='Test', price=1.7, lat=51.9, lng=8.6, isOpen=True, dist=1)
        self.response = Mock()
        self.response.json.return_value = {'ok': True, 'stations': [self.station]}

    def tearDown(self):
        self.session_patch.stop()
        self.key_patch.stop()
        self.engine.dispose()

    def count(self, model):
        with self.sessions() as db:
            return db.scalar(select(func.count()).select_from(model))

    def test_cached_poll_does_not_duplicate_history_or_refresh_sample_time(self):
        with patch('app.services.tankerkoenig.requests.get', return_value=self.response) as get:
            self.poller.poll_once()
            with self.sessions() as db:
                first = db.scalar(select(StationPrice.fetched_at))
            self.poller.poll_once()
        self.assertEqual(get.call_count, 2)
        self.assertEqual(self.count(PriceHistory), 2)
        with self.sessions() as db:
            self.assertEqual(first, db.scalar(select(StationPrice.fetched_at)))
            self.assertEqual(db.get(FetchStatus, 'e5').state, 'ok')

    def test_failed_fetch_keeps_prices_and_original_timestamps(self):
        with patch('app.services.tankerkoenig.requests.get', return_value=self.response):
            self.poller.poll_once()
        with self.sessions() as db:
            old = db.get(FetchStatus, 'e5').last_success_at
        with patch('app.services.tankerkoenig.time.time', return_value=old.replace(tzinfo=timezone.utc).timestamp() + 1000), \
             patch('app.services.tankerkoenig.time.sleep'), \
             patch('app.services.tankerkoenig.requests.get', side_effect=requests.Timeout()):
            self.poller.poll_once()
        self.assertEqual(self.count(PriceHistory), 2)
        self.assertEqual(self.count(StationPrice), 2)
        with self.sessions() as db:
            self.assertEqual(db.get(FetchStatus, 'e5').state, 'error')
            self.assertEqual(db.get(FetchStatus, 'e5').last_success_at, old)

    def test_successful_empty_fetch_clears_previous_snapshot(self):
        with patch('app.services.tankerkoenig.requests.get', return_value=self.response):
            self.poller.poll_once()
            self.poller.client._cache.clear()
            self.response.json.return_value = {'ok': True, 'stations': []}
            self.poller.poll_once()
        self.assertEqual(self.count(StationPrice), 0)
        self.assertEqual(self.count(PriceHistory), 2)
        with self.sessions() as db:
            self.assertEqual(db.get(FetchStatus, 'e5').state, 'empty')

    def test_missing_key_preserves_existing_data(self):
        with patch('app.services.tankerkoenig.requests.get', return_value=self.response):
            self.poller.poll_once()
        with patch.object(settings, 'tankerkoenig_api_key', ''), patch('app.services.tankerkoenig.requests.get') as get:
            self.poller.poll_once()
        get.assert_not_called()
        self.assertEqual(self.count(StationPrice), 2)
        with self.sessions() as db:
            self.assertEqual(db.get(FetchStatus, 'e5').state, 'missing_key')

    def test_malformed_response_is_a_failure_not_empty_success(self):
        self.response.json.return_value = {'ok': True, 'stations': {'bad': 'response'}}
        with patch('app.services.tankerkoenig.requests.get', return_value=self.response), patch('app.services.tankerkoenig.time.sleep'):
            self.poller.poll_once()
        with self.sessions() as db:
            self.assertEqual(db.get(FetchStatus, 'e5').state, 'error')
            self.assertIsNone(db.get(FetchStatus, 'e5').last_success_at)

    def test_latest_previous_sample_drives_alarm_and_stale_status(self):
        now = datetime.utcnow() - timedelta(hours=1)
        with self.sessions() as db:
            db.add(StationPrice(station_id='s', fuel_type='e5', name='S', price=1.7, fetched_at=now))
            db.add_all([PriceHistory(station_id='s', fuel_type='e5', price=2, fetched_at=now - timedelta(days=2)),
                        PriceHistory(station_id='s', fuel_type='e5', price=1.8, fetched_at=now - timedelta(hours=1))])
            db.add(FetchStatus(fuel_type='e5', state='error', last_success_at=now))
            db.commit()
            result = overview_data(db, db.get(AppConfig, 1), 'e5')
        self.assertEqual(result['station_meta']['s']['delta_cents'], -10)
        self.assertTrue(result['station_meta']['s']['strong_drop'])
        self.assertTrue(result['station_meta']['s']['stale'])
        self.assertEqual(result['fetch_health']['state'], 'error')
        self.assertTrue(result['fetch_health']['stale'])


    def test_successful_empty_missing_and_pending_states_are_distinct(self):
        with self.sessions() as db:
            cfg = db.get(AppConfig, 1)
            self.assertEqual(overview_data(db, cfg, 'e5')['fetch_health']['state'], 'pending')
            status = FetchStatus(fuel_type='e5', state='empty', last_success_at=datetime.utcnow())
            db.add(status)
            db.commit()
            self.assertEqual(overview_data(db, cfg, 'e5')['fetch_health']['state'], 'empty')
            with patch.object(settings, 'tankerkoenig_api_key', ''):
                self.assertEqual(overview_data(db, cfg, 'e5')['fetch_health']['state'], 'missing_key')

    def test_existing_database_keeps_data_when_fetch_status_table_is_added(self):
        with self.sessions() as db:
            db.add(StationPrice(station_id='old', fuel_type='e5', name='Old', price=1.7))
            db.commit()
        FetchStatus.__table__.drop(self.engine)
        Base.metadata.create_all(self.engine)
        self.assertEqual(self.count(StationPrice), 1)
        with self.sessions() as db:
            db.add(FetchStatus(fuel_type='e5', state='missing_key'))
            db.commit()
            data = overview_data(db, db.get(AppConfig, 1), 'e5')
            self.assertIsNotNone(data['fetch_health']['last_success_at'])

    def test_alert_deduplication_and_delivery_metadata_are_preserved(self):
        with self.sessions() as db:
            cfg = db.get(AppConfig, 1)
            cfg.teams_enabled = True
            cfg.teams_webhook_url = 'https://example.invalid/test-only'
            db.commit()
        with patch('app.services.tankerkoenig.requests.get', return_value=self.response), \
             patch('app.services.alerts.send_teams_message', return_value=True) as send:
            self.poller.poll_once()
            self.poller.client._cache.clear()
            self.poller.poll_once()
        self.assertEqual(send.call_count, 2)
        self.assertEqual(self.count(AlertLog), 2)
        with self.sessions() as db:
            meta = overview_data(db, db.get(AppConfig, 1), 'e5')['station_meta']['station']
            self.assertIsNotNone(meta['last_alert_at'])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = AppServer()

    @classmethod
    def tearDownClass(cls):
        cls.server.close()

    def test_overview_json_is_safe_and_fuel_specific(self):
        response = requests.get(self.server.url, timeout=5)
        self.assertEqual(response.status_code, 200)
        match = re.search(r'<script id="overview-data" type="application/json">(.*?)</script>', response.text, re.S)
        payload = json.loads(match[1])
        self.assertEqual(len(payload['stations']), 5)
        self.assertEqual(next(s['name'] for s in payload['stations'] if s['id'] == 'unsafe'), UNSAFE_NAME)
        self.assertNotIn('</script><img', match[1])
        self.assertIn('Kein API-Key', response.text)
        response = requests.get(self.server.url + '/?fuel=diesel', timeout=5)
        payload = json.loads(re.search(r'<script id="overview-data" type="application/json">(.*?)</script>', response.text, re.S)[1])
        self.assertEqual(next(s['price'] for s in payload['stations'] if s['id'] == 'tie'), 1.4)

    def test_history_periods_validation_and_fuel_isolation(self):
        sizes = []
        for days in [1, 7, 30]:
            response = requests.get(self.server.url + f'/api/stations/near/history?days={days}', timeout=5)
            self.assertEqual(response.status_code, 200)
            points = response.json()['points']
            self.assertEqual(points, sorted(points, key=lambda point: point['at']))
            sizes.append(len(points))
        self.assertEqual(sizes, [2, 3, 4])
        response = requests.get(self.server.url + '/api/stations/tie/history?fuel=diesel', timeout=5)
        self.assertAlmostEqual(response.json()['points'][-1]['price'], 1.4)
        for query in ['days=2', 'fuel=e10']:
            self.assertEqual(requests.get(self.server.url + '/api/stations/near/history?' + query, timeout=5).status_code, 422)
        self.assertEqual(requests.get(self.server.url + '/api/stations/missing/history', timeout=5).status_code, 404)

    def test_admin_login_csrf_save_and_logout_regression(self):
        client = requests.Session()
        self.assertEqual(client.get(self.server.url + '/admin', allow_redirects=False, timeout=5).status_code, 302)
        page = client.get(self.server.url + '/admin/login', timeout=5)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
        data = dict(username='test-admin', password=self.server.password, csrf_token='bad')
        self.assertEqual(client.post(self.server.url + '/admin/login', data=data, timeout=5).status_code, 400)
        data['csrf_token'] = token
        self.assertEqual(client.post(self.server.url + '/admin/login', data=data, allow_redirects=False, timeout=5).status_code, 302)
        page = client.get(self.server.url + '/admin', timeout=5)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text)[1]
        values = dict(origin_address='Testort', origin_lat=51.99, origin_lng=8.61, radius_km=5,
                      threshold_e5=1.8, threshold_diesel=1.7, strong_change_cents=5,
                      poll_interval_seconds=10, csrf_token=token)
        self.assertEqual(client.post(self.server.url + '/admin', data=values, timeout=5).status_code, 200)
        with Session(self.server.engine) as db:
            self.assertEqual(db.get(AppConfig, 1).poll_interval_seconds, 300)
        client.post(self.server.url + '/admin/logout', timeout=5)
        self.assertEqual(client.get(self.server.url + '/admin', allow_redirects=False, timeout=5).status_code, 302)
