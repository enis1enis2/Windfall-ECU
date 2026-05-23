import os, tempfile, pytest
from path_util import safe_join

class TestPluginDeletePathSecurity:
    def test_safe_join_rejects_traversal_in_delete_plugin(self):
        with pytest.raises(ValueError):
            safe_join('/tmp/servers/test/plugins', '../../../etc/passwd')

    def test_delete_plugin_rejects_traversal(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'PlgSecTest'})
        sid = r.json['id']
        r_del = auth_client.delete(f'/api/servers/{sid}/plugins/../../../etc/passwd')
        assert r_del.status_code == 400
        assert 'Access denied' in r_del.json.get('error', '')

    def test_delete_plugin_rejects_deep_traversal(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'PlgSecTest2'})
        sid = r.json['id']
        r_del = auth_client.delete(f'/api/servers/{sid}/plugins/sub/../../../../etc/shadow')
        assert r_del.status_code == 400

    def test_delete_nonexistent_plugin(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'PlgSecTest3'})
        sid = r.json['id']
        r_del = auth_client.delete(f'/api/servers/{sid}/plugins/nonexistent.jar')
        assert r_del.status_code == 400
        assert 'not found' in r_del.json.get('error', '').lower()

    def test_delete_plugin_normal_file_succeeds(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'PlgSecTest4'})
        sid = r.json['id']
        auth_client.post(f'/api/servers/{sid}/files/write',
                         json={'path': 'plugins/test.jar', 'content': 'fake jar'})
        r_del = auth_client.delete(f'/api/servers/{sid}/plugins/test.jar')
        assert r_del.status_code == 200
