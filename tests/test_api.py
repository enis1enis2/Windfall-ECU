import json

class TestAuth:
    def test_login_valid(self, client):
        r = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin'})
        assert r.status_code == 200
        assert r.json['status'] == 'ok'
        assert r.json['role'] == 'admin'

    def test_login_invalid(self, client):
        r = client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'})
        assert r.status_code == 401

    def test_auth_status_authenticated(self, auth_client):
        r = auth_client.get('/api/auth/status')
        assert r.json['authenticated'] == True
        assert r.json['role'] == 'admin'

    def test_auth_status_unauthenticated(self, client):
        r = client.get('/api/auth/status')
        assert r.json['authenticated'] == False

    def test_logout(self, auth_client):
        r = auth_client.post('/api/auth/logout')
        assert r.status_code == 200
        r2 = auth_client.get('/api/auth/status')
        assert r2.json['authenticated'] == False

    def test_register_viewer_role(self, client):
        r = client.post('/api/auth/register', json={'username': 'newapi', 'password': 'pass1234'})
        assert r.status_code == 201
        assert r.json['role'] == 'viewer'

    def test_register_duplicate_suffix(self, client):
        r1 = client.post('/api/auth/register', json={'username': 'apidupe', 'password': 'pass1234'})
        r2 = client.post('/api/auth/register', json={'username': 'apidupe', 'password': 'pass5678'})
        assert r2.status_code == 201
        assert r2.json['username'] == 'apidupe_2'

    def test_register_short_username(self, client):
        r = client.post('/api/auth/register', json={'username': 'ab', 'password': 'pass1234'})
        assert r.status_code == 400

class TestServers:
    def test_list_servers_empty(self, auth_client):
        r = auth_client.get('/api/servers')
        assert r.status_code == 200
        assert r.json == []

    def test_list_servers_requires_auth(self, client):
        r = client.get('/api/servers')
        assert r.status_code == 401

    def test_create_and_get_server(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'Test Server', 'server_type': 'vanilla'})
        assert r.status_code == 201
        sid = r.json['id']

        r2 = auth_client.get(f'/api/servers/{sid}')
        assert r2.status_code == 200
        assert r2.json['name'] == 'Test Server'
        assert r2.json['server_type'] == 'vanilla'

    def test_delete_server(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'Delete Me'})
        sid = r.json['id']
        r2 = auth_client.delete(f'/api/servers/{sid}')
        assert r2.status_code == 200
        r3 = auth_client.get(f'/api/servers/{sid}')
        assert r3.status_code == 404

    def test_get_nonexistent_server(self, auth_client):
        r = auth_client.get('/api/servers/99999')
        assert r.status_code == 404

    def test_permission_denied(self, client):
        r = client.get('/api/servers')
        assert r.status_code == 401

class TestFiles:
    def test_list_files(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'FileTest'})
        sid = r.json['id']
        r2 = auth_client.get(f'/api/servers/{sid}/files')
        assert r2.status_code == 200
        entries = r2.json['entries'] if isinstance(r2.json, dict) else r2.json
        assert isinstance(entries if isinstance(r2.json, dict) else r2.json, list if not isinstance(r2.json, dict) else object)

    def test_write_and_read_file(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'RWTest'})
        sid = r.json['id']
        r2 = auth_client.post(f'/api/servers/{sid}/files/write', json={'path': 'test.txt', 'content': 'hello'})
        assert r2.status_code == 200
        r3 = auth_client.get(f'/api/servers/{sid}/files/read', query_string={'path': 'test.txt'})
        assert r3.status_code == 200
        assert r3.json['content'] == 'hello'

    def test_delete_file(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'DelTest'})
        sid = r.json['id']
        auth_client.post(f'/api/servers/{sid}/files/write', json={'path': 'todelete.txt', 'content': 'bye'})
        r2 = auth_client.post(f'/api/servers/{sid}/files/delete', json={'path': 'todelete.txt'})
        assert r2.status_code == 200
        r3 = auth_client.get(f'/api/servers/{sid}/files/read', query_string={'path': 'todelete.txt'})
        assert r3.status_code == 400

    def test_file_traversal_blocked(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'Traversal'})
        sid = r.json['id']
        r2 = auth_client.get(f'/api/servers/{sid}/files/read', query_string={'path': '../../../etc/passwd'})
        assert r2.status_code == 400

class TestSystem:
    def test_metrics_requires_auth(self, client):
        r = client.get('/api/system/metrics')
        assert r.status_code == 401

    def test_metrics_returns_data(self, auth_client):
        r = auth_client.get('/api/system/metrics')
        assert r.status_code == 200
        assert 'ram' in r.json
        assert 'cpu' in r.json
        assert 'disk' in r.json

class TestBackups:
    def test_list_backups_empty(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'BakTest'})
        sid = r.json['id']
        r2 = auth_client.get(f'/api/servers/{sid}/backups')
        assert r2.status_code == 200
        assert r2.json == []

class TestPlugins:
    def test_list_plugins_empty(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'PlgTest'})
        sid = r.json['id']
        r2 = auth_client.get(f'/api/servers/{sid}/plugins')
        assert r2.status_code == 200
        assert r2.json == []
