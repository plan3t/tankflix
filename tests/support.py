"""An isolated local server and representative station data, without external API calls."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import AppConfig, PriceHistory, StationPrice

ROOT = Path(__file__).resolve().parents[1]
UNSAFE_NAME = '</script><img src=x onerror="window.stationXss=true">'


class AppServer:
    def __init__(self):
        self.folder = tempfile.TemporaryDirectory(prefix='tankflix-tests-')
        self.password = secrets.token_urlsafe(32)
        self.database = Path(self.folder.name) / 'app.db'
        self.engine = create_engine(f'sqlite:///{self.database}')
        Base.metadata.create_all(self.engine)
        now = datetime.utcnow()
        self.now = now
        self.records = [
            ('near', 'Alpha Zentrum', 'Alpha', 1.700, 1.0, True, 51.9900, 8.6100, now),
            ('tie', 'Alpha Nord', 'Alpha', 1.700, 2.0, True, 51.9920, 8.6120, now),
            ('closed', 'Beta Express', 'Beta', 1.800, .5, False, 51.9940, 8.6140, now),
            ('old', 'Alpha Fern', 'Alpha', 1.900, 4.6, True, 52.0300, 8.6800, now - timedelta(hours=1)),
            ('unsafe', UNSAFE_NAME, 'ACME <x>', 1.820, 3.1, True, 52.0000, 8.6200, now),
        ]
        with Session(self.engine) as db:
            db.add(AppConfig(id=1, radius_km=5, only_open=False))
            for fuel in ['e5', 'diesel']:
                for identity, name, brand, price, dist, opened, lat, lng, fetched in self.records:
                    actual_price = price if fuel == 'e5' else (1.4 if identity == 'tie' else 1.6)
                    db.add(StationPrice(station_id=identity, fuel_type=fuel, name=name, brand=brand,
                                        street='Teststraße 1', place='Bielefeld', price=actual_price,
                                        distance_km=dist, is_open=opened, lat=lat, lng=lng, fetched_at=fetched))
                    for age, value in [(15, actual_price + .3), (3, actual_price + .25), (.02, actual_price + .2), (0, actual_price)]:
                        db.add(PriceHistory(station_id=identity, fuel_type=fuel, price=value, fetched_at=fetched - timedelta(days=age)))
            db.commit()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}'
        self.log = open(Path(self.folder.name) / 'server.log', 'w+')
        runtime = os.environ.copy()
        runtime.update(DATABASE_URL=f'sqlite:///{self.database}', TANKERKOENIG_API_KEY='',
                       ADMIN_USERNAME='test-admin', ADMIN_PASSWORD=self.password,
                       SECRET_KEY=secrets.token_urlsafe(48), PYTHONDONTWRITEBYTECODE='1')
        self.process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)],
                                        cwd=ROOT, env=runtime, stdout=self.log, stderr=self.log)
        for _ in range(100):
            if self.process.poll() is not None:
                self.log.seek(0)
                raise RuntimeError(self.log.read())
            try:
                if requests.get(self.url, timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(.1)
        else:
            self.close()
            raise RuntimeError('Test server startup timed out')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=15)
        self.log.close()
        self.engine.dispose()
        self.folder.cleanup()
