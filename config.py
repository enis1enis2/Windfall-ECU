import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'instances.db')
SERVERS_DIR = os.path.join(BASE_DIR, 'servers')
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups')
HOST = '0.0.0.0'
PORT = 8080
JAVA_BIN = 'java'
SECRET_KEY = 'greatpanel-secret-change-me'
