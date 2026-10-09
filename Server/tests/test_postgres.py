"""Run against an actual disposable PostgreSQL service in GitHub Actions."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from privsig.server.api import create_app
from privsig.server.hosted import initialize_fictional_school, normalized_postgres_url

@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Disposable PostgreSQL not configured')
def test_actual_postgres_login_and_timetable():
    app = create_app(normalized_postgres_url(os.environ['TEST_POSTGRES_URL']))
    initialize_fictional_school(app, 'IntegrationAdmin!2026', 'IntegrationStudent!2026', 'integration-only-secret-'*3)
    with TestClient(app) as client:
        login = client.post('/auth/login', json={'username':'uczen','password':'IntegrationStudent!2026'})
        assert login.status_code == 200
        headers = {'Authorization':'Bearer ' + login.json()['token']}
        assert client.get('/health').json()['database'] == 'postgresql'
        assert client.get('/records/timetable', headers=headers).json()
        assert client.post('/records/grades', headers=headers, json={'data':{}}).status_code == 403
        with client.websocket_connect('/ws', headers=headers) as ws:
            ws.send_text('ping')
            assert ws.receive_json()['type']=='pong'
