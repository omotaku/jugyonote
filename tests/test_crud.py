import pytest
from app import app
from datetime import datetime
import tempfile
import os

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # use a temporary file DB so connections share the same file
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, 'test_notes.db')
    app.config['DATABASE'] = db_path
    with app.app_context():
        from app import init_db
        init_db()
    with app.test_client() as client:
        yield client

def register(client, username='testuser', password='pass'):
    return client.post('/register', data={'username': username, 'password': password}, follow_redirects=True)

def login(client, username='testuser', password='pass'):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

def test_register_login_create_edit_delete(client):
    rv = register(client)
    text = rv.get_data(as_text=True)
    assert '登録しました' in text or '登録' in text
    rv = login(client)
    text = rv.get_data(as_text=True)
    assert 'ダッシュボード' in text or rv.status_code in (200,302)

    # create note
    rv = client.post('/notes/new', data={'title':'史料','content':'内容'}, follow_redirects=True)
    assert rv.status_code == 200
    text = rv.get_data(as_text=True)
    assert '史料' in text or '内容' in text

    # get note id by listing
    rv = client.get('/dashboard')
    text = rv.get_data(as_text=True)
    assert '史料' in text

    # edit first note (find edit link)
    # crud operations via database check
    from app import query_db
    with app.app_context():
        notes = query_db('SELECT * FROM notes')
        assert len(notes) == 1
        nid = notes[0]['id']

    rv = client.post(f'/notes/{nid}/edit', data={'title':'史料改','content':'更新'}, follow_redirects=True)
    assert rv.status_code == 200
    with app.app_context():
        notes = query_db('SELECT * FROM notes WHERE id = ?', (nid,))
        assert notes[0]['title'] == '史料改'

    # delete
    rv = client.post(f'/notes/{nid}/delete', follow_redirects=True)
    assert rv.status_code == 200
    with app.app_context():
        notes = query_db('SELECT * FROM notes')
        assert len(notes) == 0
