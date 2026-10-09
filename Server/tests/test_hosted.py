import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from privsig.server.api import create_app
from privsig.server.hosted import initialize_fictional_school, normalized_postgres_url

ADMIN = 'TestAdminPassword!2026'
STUDENT = 'TestStudentPassword!2026'

def test_database_url_requires_postgres():
    assert normalized_postgres_url('postgres://x') == 'postgresql+psycopg://x'
    assert normalized_postgres_url('postgresql://x') == 'postgresql+psycopg://x'
    with pytest.raises(ValueError): normalized_postgres_url('sqlite:///local.db')

def test_missing_credentials_fail_before_public_accounts_created(tmp_path):
    app = create_app('sqlite:///' + str(tmp_path/'test.db'))
    with pytest.raises(ValueError): initialize_fictional_school(app, '', '', '')
    with TestClient(app) as c:
        assert c.post('/auth/login', json={'username':'admin','password':'PrivsigDemo!2026'}).status_code == 401

def test_seed_credentials_scope_and_restart_persistence(tmp_path):
    url = 'sqlite:///' + str(tmp_path/'test.db')
    app = create_app(url)
    assert initialize_fictional_school(app, ADMIN, STUDENT, 'x'*40)
    with TestClient(app) as c:
        for username in ['admin','uczen','nauczyciel','rodzic']:
            assert c.post('/auth/login', json={'username':username,'password':'PrivsigDemo!2026'}).status_code == 401
        reply = c.post('/auth/login', json={'username':'uczen','password':STUDENT})
        assert reply.status_code == 200
        headers = {'Authorization':'Bearer ' + reply.json()['token']}
        assert c.get('/records/timetable', headers=headers).json()
        assert c.post('/records/grades', headers=headers, json={'data':{}}).status_code == 403
        assert c.post('/auth/login', json={'username':'admin','password':ADMIN}).status_code == 200
    next_app = create_app(url)
    assert not initialize_fictional_school(next_app, 'another-password-123', 'different-password-123', 'y'*40)
    with TestClient(next_app) as c:
        assert c.post('/auth/login', json={'username':'admin','password':ADMIN}).status_code == 200
