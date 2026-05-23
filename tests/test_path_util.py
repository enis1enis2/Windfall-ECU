import os, tempfile, pytest
from path_util import safe_join, sanitize_name, safe_path, safe_write

class TestSafeJoin:
    def test_normal_path(self):
        assert safe_join('/base', 'sub', 'file.txt') == os.path.normpath('/base/sub/file.txt')

    def test_single_part(self):
        assert safe_join('/base', 'file.txt') == os.path.normpath('/base/file.txt')

    def test_rejects_traversal(self):
        with pytest.raises(ValueError):
            safe_join('/base', '../etc/passwd')

    def test_rejects_deep_traversal(self):
        with pytest.raises(ValueError):
            safe_join('/base', 'sub', '..', '..', 'etc')

    def test_rejects_absolute_inside(self):
        with pytest.raises(ValueError):
            safe_join('/base', '/etc/passwd')

    def test_empty_parts(self):
        assert safe_join('/base') == os.path.normpath('/base')

    def test_trailing_slash_base(self):
        assert safe_join('/base/', 'file.txt') == os.path.normpath('/base/file.txt')

    def test_dot_paths(self):
        assert safe_join('/base', '.', 'file.txt') == os.path.normpath('/base/file.txt')
        assert safe_join('/base', 'sub', '.', 'file.txt') == os.path.normpath('/base/sub/file.txt')

    def test_double_dot_same_dir(self):
        with pytest.raises(ValueError):
            safe_join('/base', 'sub', '..')

class TestSanitizeName:
    def test_keeps_alphanumeric(self):
        assert sanitize_name('hello123') == 'hello123'

    def test_strips_path_separators(self):
        assert sanitize_name('../etc/passwd') == '.._etc_passwd'

    def test_keeps_allowed_special(self):
        assert sanitize_name('my-server_backup.1') == 'my-server_backup.1'

    def test_replaces_invalid_chars(self):
        assert sanitize_name('a<b>c:d|e?f*g') == 'a_b_c_d_e_f_g'

    def test_empty_string(self):
        assert sanitize_name('') == ''

    def test_only_invalid(self):
        assert sanitize_name('<>:') == '___'

    def test_unicode(self):
        assert sanitize_name('héllo') == 'h_llo'

    def test_spaces(self):
        assert sanitize_name('my backup') == 'my backup'

class TestSafePath:
    def test_safe_path_combines(self):
        result = safe_path('/base', 'valid_name')
        assert result == os.path.normpath('/base/valid_name')

    def test_safe_path_sanitizes_name(self):
        result = safe_path('/base', '../hack')
        assert result == os.path.normpath('/base/.._hack')

    def test_safe_path_sanitizes_traversal(self):
        result = safe_path('/base', '../../etc')
        assert '/' not in result  # slashes replaced

class TestSafeWrite:
    def test_writes_file_content(self):
        tmp = tempfile.mkdtemp()
        try:
            fp = os.path.join(tmp, 'test.txt')
            safe_write(fp, 'hello world')
            with open(fp) as f:
                assert f.read() == 'hello world'
        finally:
            os.remove(fp)
            os.rmdir(tmp)

    def test_creates_parent_dirs(self):
        tmp = tempfile.mkdtemp()
        try:
            fp = os.path.join(tmp, 'sub', 'nested', 'test.txt')
            safe_write(fp, 'nested')
            with open(fp) as f:
                assert f.read() == 'nested'
        finally:
            import shutil
            shutil.rmtree(tmp)
