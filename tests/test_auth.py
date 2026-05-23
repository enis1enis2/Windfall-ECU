import pytest
from auth import register_user, verify_user, create_user, delete_user, change_password, change_username, change_role, get_users, get_user_by_id, ROLES

class TestRegisterUser:
    def test_register_valid(self):
        ok, msg, db_user = register_user('testuser1', 'password123')
        assert ok
        assert db_user == 'testuser1'

    def test_register_short_username(self):
        ok, msg, db_user = register_user('ab', 'password123')
        assert not ok
        assert db_user is None

    def test_register_short_password(self):
        ok, msg, db_user = register_user('testuser2', 'abc')
        assert not ok
        assert db_user is None

    def test_register_duplicate_gets_suffix(self):
        register_user('dupuser', 'pass1234')
        ok, msg, db_user = register_user('dupuser', 'pass5678')
        assert ok
        assert db_user == 'dupuser_2'

    def test_register_duplicate_gets_next_suffix(self):
        register_user('triple', 'pass1234')
        register_user('triple', 'pass5678')
        ok, msg, db_user = register_user('triple', 'pass9012')
        assert ok
        assert db_user == 'triple_3'

    def test_register_viewer_role(self):
        register_user('viewertest', 'pass1234')
        uid, role = verify_user('viewertest', 'pass1234')
        assert role == 'viewer'

class TestVerifyUser:
    def test_verify_correct(self):
        register_user('verifyuser', 'mypassword')
        uid, role = verify_user('verifyuser', 'mypassword')
        assert uid is not None

    def test_verify_wrong_password(self):
        register_user('verifyuser2', 'correctpass')
        uid, role = verify_user('verifyuser2', 'wrongpass')
        assert uid is None

    def test_verify_nonexistent(self):
        uid, role = verify_user('nobody', 'password')
        assert uid is None

    def test_verify_with_suffixed_name(self):
        register_user('suffixuser', 'pass1234')
        register_user('suffixuser', 'pass5678')
        uid, role = verify_user('suffixuser_2', 'pass5678')
        assert uid is not None

class TestCreateUser:
    def test_create_viewer(self):
        ok, msg = create_user('created1', 'pass1234', 'viewer')
        assert ok
        uid, role = verify_user('created1', 'pass1234')
        assert role == 'viewer'

    def test_create_operator(self):
        ok, msg = create_user('created2', 'pass1234', 'operator')
        assert ok
        uid, role = verify_user('created2', 'pass1234')
        assert role == 'operator'

    def test_create_admin(self):
        ok, msg = create_user('created3', 'pass1234', 'admin')
        assert ok
        uid, role = verify_user('created3', 'pass1234')
        assert role == 'admin'

    def test_create_invalid_role(self):
        ok, msg = create_user('created4', 'pass1234', 'superadmin')
        assert not ok

class TestChangePassword:
    def test_change_password(self):
        register_user('changepw', 'oldpass')
        uid, _ = verify_user('changepw', 'oldpass')
        ok, msg = change_password(uid, 'newpass')
        assert ok
        uid2, _ = verify_user('changepw', 'newpass')
        assert uid2 == uid

    def test_change_password_short(self):
        register_user('changepw2', 'oldpass')
        uid, _ = verify_user('changepw2', 'oldpass')
        ok, msg = change_password(uid, 'ab')
        assert not ok

class TestChangeUsername:
    def test_change_username(self):
        register_user('oldname', 'pass1234')
        uid, _ = verify_user('oldname', 'pass1234')
        ok, msg = change_username(uid, 'newname')
        assert ok
        uid2, _ = verify_user('newname', 'pass1234')
        assert uid2 == uid

    def test_change_username_short(self):
        register_user('oldname2', 'pass1234')
        uid, _ = verify_user('oldname2', 'pass1234')
        ok, msg = change_username(uid, 'ab')
        assert not ok

class TestChangeRole:
    def test_change_role(self):
        register_user('roleuser', 'pass1234')
        uid, role = verify_user('roleuser', 'pass1234')
        assert role == 'viewer'
        ok, msg = change_role(uid, 'admin')
        assert ok
        _, role = verify_user('roleuser', 'pass1234')
        assert role == 'admin'

    def test_change_role_invalid(self):
        register_user('roleuser2', 'pass1234')
        uid, _ = verify_user('roleuser2', 'pass1234')
        ok, msg = change_role(uid, 'god')
        assert not ok

class TestGetUsers:
    def test_get_users_returns_list(self):
        users = get_users()
        assert isinstance(users, list)
        assert any(u['username'] == 'admin' for u in users)

    def test_get_user_by_id(self):
        register_user('getuser', 'pass1234')
        uid, _ = verify_user('getuser', 'pass1234')
        u = get_user_by_id(uid)
        assert u is not None
        assert u['username'] == 'getuser'

    def test_get_user_by_id_nonexistent(self):
        assert get_user_by_id(99999) is None

class TestDeleteUser:
    def test_delete_user(self):
        register_user('deluser', 'pass1234')
        users_before = len(get_users())
        uid, _ = verify_user('deluser', 'pass1234')
        ok, msg = delete_user(uid)
        assert ok
        assert len(get_users()) == users_before - 1
