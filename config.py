import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'instances.db')
SERVERS_DIR = os.path.join(BASE_DIR, 'servers')
HOST = os.environ.get('GREATPANEL_HOST', '0.0.0.0')
PORT = int(os.environ.get('GREATPANEL_PORT', '8080'))
JAVA_BIN = os.environ.get('GREATPANEL_JAVA', 'java')
SECRET_KEY = os.environ.get('GREATPANEL_SECRET', 'windfall-ecu-secret-change-me')
