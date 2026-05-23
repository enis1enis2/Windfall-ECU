import os, sys, tempfile, pytest, shutil

_test_dir = tempfile.mkdtemp(prefix='windfall_test_')

os.environ['GREATPANEL_SECRET'] = 'test-secret-key'

import config
config.DATABASE = os.path.join(_test_dir, 'test.db')
config.SERVERS_DIR = os.path.join(_test_dir, 'servers')
config.BACKUPS_DIR = os.path.join(_test_dir, 'backups')
config.SECRET_KEY = 'test-secret-key'
config.PORT = 0

import app
import auth, models
from path_util import safe_join, sanitize_name, safe_path


@pytest.fixture
def client():
    app.app.config['TESTING'] = True
    app.app.config['SERVER_NAME'] = 'localhost'
    with app.app.test_client() as c:
        with app.app.app_context():
            yield c


@pytest.fixture
def auth_client(client):
    client.post('/api/auth/login', json={
        'username': 'admin', 'password': 'admin'
    })
    return client


@pytest.fixture
def db():
    yield
    models._execute('DELETE FROM servers')
    models._execute('DELETE FROM backups')


def pytest_unconfigure():
    shutil.rmtree(_test_dir, ignore_errors=True)
