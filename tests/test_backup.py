import os
from config import BACKUPS_DIR
from path_util import safe_join, sanitize_name

class TestBackupPathSecurity:
    def test_sanitize_name_blocks_traversal_in_backup(self):
        malicious = '../../etc/passwd'
        safe = sanitize_name(malicious)
        assert '..' not in safe
        assert '/' not in safe

    def test_sanitize_name_preserves_valid_names(self):
        name = sanitize_name('my_server_backup_20240520')
        assert name == 'my_server_backup_20240520'

    def test_safe_join_blocks_traversal_in_backup_path(self):
        backup_dir = safe_join(BACKUPS_DIR, '1')
        malicious = '../../etc/passwd'
        safe_name = sanitize_name(malicious)
        try:
            path = safe_join(backup_dir, f'{safe_name}.tar.gz')
            assert os.path.normpath(path).startswith(os.path.normpath(backup_dir))
        except ValueError:
            pass

    def test_safe_join_direct_traversal_raises(self):
        import pytest
        with pytest.raises(ValueError):
            safe_join(BACKUPS_DIR, '../etc')

    def test_create_backup_rejects_traversal_name(self, auth_client):
        r = auth_client.post('/api/servers', json={'name': 'BakSecTest'})
        sid = r.json['id']
        r2 = auth_client.post(f'/api/servers/{sid}/backups', json={'name': '../../../etc/crontab'})
        assert r2.status_code == 201
        r3 = auth_client.get(f'/api/servers/{sid}/backups')
        assert r3.status_code == 200
        assert len(r3.json) == 1
        bp = r3.json[0]['path']
        assert '../../../etc/crontab' not in bp
        assert '../../etc' not in bp
        assert os.path.normpath(bp).startswith(os.path.normpath(BACKUPS_DIR))
