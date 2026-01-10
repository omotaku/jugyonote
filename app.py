import sqlite3
from flask import Flask, g, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from datetime import datetime, timedelta
import uuid
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'notes.db')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')
app.config['DATABASE'] = DB_PATH

# Flask-Login setup
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Predefined world-history templates
NOTE_TEMPLATES = {
    '年表テンプレート': "# 年表\n\n- 年: 主要出来事\n",
    '出来事カード': "# 出来事名\n\n**日時:** \n\n**場所:** \n\n**詳細:** \n\n**影響:** \n",
    '主要人物': "# 人物名\n\n**生没年:** \n\n**役割:** \n\n**業績／説明:** \n",
}


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.executescript(f.read())
    db.commit()


def ensure_public_links_columns():
    db = get_db()
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='public_links'")
    if not cur.fetchone():
        # create table if missing
        db.execute('''CREATE TABLE public_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TEXT,
            expires_at TEXT,
            revoked INTEGER DEFAULT 0,
            FOREIGN KEY(note_id) REFERENCES notes(id)
        )''')
        db.commit()
        return
    cur = db.execute("PRAGMA table_info(public_links)")
    cols = [r[1] for r in cur.fetchall()]
    if 'expires_at' not in cols:
        db.execute("ALTER TABLE public_links ADD COLUMN expires_at TEXT")
    if 'revoked' not in cols:
        db.execute("ALTER TABLE public_links ADD COLUMN revoked INTEGER DEFAULT 0")
    db.commit()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if user:
        return User(user['id'], user['username'])
    return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('ユーザー名とパスワードを入力してください')
            return redirect(url_for('register'))
        db = get_db()
        try:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                       (username, generate_password_hash(password)))
            db.commit()
            flash('登録しました。ログインしてください。')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('そのユーザー名は既に使われています')
            return redirect(url_for('register'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user and check_password_hash(user['password'], password):
            user_obj = User(user['id'], user['username'])
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        flash('認証に失敗しました')
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


# note: using flask_login.login_required decorator instead of custom one


@app.route('/dashboard')
@login_required
def dashboard():
    user_id = int(current_user.get_id())
    q = request.args.get('q','').strip()
    period = request.args.get('period','').strip()
    region = request.args.get('region','').strip()
    tags = request.args.get('tags','').strip()
    sql = 'SELECT * FROM notes WHERE user_id = ?'
    params = [user_id]
    if q:
        sql += ' AND (title LIKE ? OR content LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%'])
    if period:
        sql += ' AND period = ?'
        params.append(period)
    if region:
        sql += ' AND region LIKE ?'
        params.append(f'%{region}%')
    if tags:
        # support comma-separated tags (OR match any)
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        if tag_list:
            tag_clauses = []
            for t in tag_list:
                tag_clauses.append('tags LIKE ?')
                params.append(f'%{t}%')
            sql += ' AND (' + ' OR '.join(tag_clauses) + ')'
    # pagination
    page = int(request.args.get('page', 1))
    per_page = 10
    # count total
    count_sql = 'SELECT COUNT(*) as cnt FROM (' + sql + ')'
    total_row = query_db(count_sql, tuple(params), one=True)
    total = total_row['cnt'] if total_row else 0
    total_pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    sql += ' LIMIT ? OFFSET ?'
    params.extend([per_page, offset])
    notes = query_db(sql, tuple(params))
    # fetch public link tokens for displayed notes
    note_ids = [n['id'] for n in notes]
    public_map = {}
    if note_ids:
        qmarks = ','.join(['?']*len(note_ids))
        rows = query_db(f'SELECT note_id, token FROM public_links WHERE note_id IN ({qmarks})', tuple(note_ids))
        for r in rows:
            public_map[r['note_id']] = r['token']
    return render_template('dashboard.html', notes=notes, q=q, period=period, region=region, tags=tags, page=page, total_pages=total_pages, public_map=public_map)


@app.route('/notes/new', methods=['GET', 'POST'])
@login_required
def note_new():
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content']
        tags = request.form.get('tags','').strip()
        period = request.form.get('period','').strip()
        region = request.form.get('region','').strip()
        db = get_db()
        cur = db.execute('INSERT INTO notes (user_id, title, content, tags, period, region, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (int(current_user.get_id()), title, content, tags, period, region, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        db.commit()
        note_id = cur.lastrowid
        if request.headers.get('X-Auto-Save'):
            return jsonify({'status':'ok','id': note_id})
        return redirect(url_for('dashboard'))
    # default world-history template for new notes
    default_content = "# 年表\n\n- 年: 主要出来事\n\n# 重要人物\n\n- 名前 — 役割／説明\n\n# 出来事の詳細\n\n説明をここに書いてください。\n\n# 参考文献\n\n- 出典1\n"
    return render_template('note_edit.html', note=None, default_content=default_content, templates=NOTE_TEMPLATES)


@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def note_edit(note_id):
    note = query_db('SELECT * FROM notes WHERE id = ? AND user_id = ?', (note_id, int(current_user.get_id())), one=True)
    if not note:
        flash('ノートが見つかりません')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content']
        tags = request.form.get('tags','').strip()
        period = request.form.get('period','').strip()
        region = request.form.get('region','').strip()
        db = get_db()
        db.execute('UPDATE notes SET title = ?, content = ?, tags = ?, period = ?, region = ?, updated_at = ? WHERE id = ? AND user_id = ?',
                   (title, content, tags, period, region, datetime.utcnow().isoformat(), note_id, int(current_user.get_id())))
        db.commit()
        if request.headers.get('X-Auto-Save'):
            return jsonify({'status':'ok'})
        return redirect(url_for('dashboard'))
    return render_template('note_edit.html', note=note, templates=NOTE_TEMPLATES)


@app.route('/notes/<int:note_id>/delete', methods=['POST'])
@login_required
def note_delete(note_id):
    db = get_db()
    db.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, int(current_user.get_id())))
    db.commit()
    return redirect(url_for('dashboard'))


@app.route('/notes/<int:note_id>/export')
@login_required
def note_export(note_id):
    note = query_db('SELECT * FROM notes WHERE id = ? AND user_id = ?', (note_id, int(current_user.get_id())), one=True)
    if not note:
        flash('ノートが見つかりません')
        return redirect(url_for('dashboard'))
    title = note['title'] or f'note-{note_id}'
    md = f"# {title}\n\n" \
         + (f"<!-- period:{note['period'] or ''} region:{note['region'] or ''} tags:{note['tags'] or ''} -->\n\n") \
         + (note['content'] or '')
    resp = make_response(md)
    resp.headers.set('Content-Type', 'text/markdown; charset=utf-8')
    resp.headers.set('Content-Disposition', f'attachment; filename={title.replace(" ","_")}-{note_id}.md')
    return resp


@app.route('/notes/<int:note_id>/share', methods=['POST'])
@login_required
def note_share(note_id):
    # create or return existing public token for note
    note = query_db('SELECT * FROM notes WHERE id = ? AND user_id = ?', (note_id, int(current_user.get_id())), one=True)
    if not note:
        flash('ノートが見つかりません')
        return redirect(url_for('dashboard'))
    ttl = request.form.get('ttl_days')
    expires_at = None
    if ttl:
        try:
            days = int(ttl)
            expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
        except Exception:
            expires_at = None
    existing = query_db('SELECT * FROM public_links WHERE note_id = ?', (note_id,), one=True)
    if existing:
        token = existing['token']
        # update expiration if provided
        if expires_at:
            db = get_db()
            db.execute('UPDATE public_links SET expires_at = ?, revoked = 0 WHERE note_id = ?', (expires_at, note_id))
            db.commit()
    else:
        token = uuid.uuid4().hex
        db = get_db()
        db.execute('INSERT INTO public_links (note_id, token, created_at, expires_at, revoked) VALUES (?, ?, ?, ?, 0)', (note_id, token, datetime.utcnow().isoformat(), expires_at))
        db.commit()
    link = url_for('public_note_view', token=token, _external=True)
    flash(f'公開リンクを生成しました: {link}')
    return redirect(url_for('dashboard'))


@app.route('/s/<token>')
def public_note_view(token):
    row = query_db('SELECT n.*, p.expires_at as expires_at, p.revoked as revoked FROM notes n JOIN public_links p ON p.note_id = n.id WHERE p.token = ?', (token,), one=True)
    if not row:
        return render_template('public_not_found.html'), 404
    # check revoked/expired
    if row['revoked']:
        return render_template('public_not_found.html'), 404
    if row['expires_at']:
        try:
            exp = datetime.fromisoformat(row['expires_at'])
            if datetime.utcnow() > exp:
                return render_template('public_not_found.html'), 404
        except Exception:
            pass
    # render a minimal read-only view
    return render_template('public_note.html', note=row)


@app.route('/shares')
@login_required
def shares_list():
    user_id = int(current_user.get_id())
    rows = query_db('SELECT p.id, p.token, p.expires_at, p.revoked, n.id as note_id, n.title FROM public_links p JOIN notes n ON p.note_id = n.id WHERE n.user_id = ? ORDER BY p.created_at DESC', (user_id,))
    return render_template('shares.html', shares=rows)


@app.route('/shares/<int:link_id>/revoke', methods=['POST'])
@login_required
def shares_revoke(link_id):
    # ensure link belongs to user
    row = query_db('SELECT p.* FROM public_links p JOIN notes n ON p.note_id = n.id WHERE p.id = ?', (link_id,), one=True)
    if not row:
        flash('リンクが見つかりません')
        return redirect(url_for('shares_list'))
    # check owner
    note = query_db('SELECT * FROM notes WHERE id = ?', (row['note_id'],), one=True)
    if note['user_id'] != int(current_user.get_id()):
        flash('権限がありません')
        return redirect(url_for('shares_list'))
    db = get_db()
    db.execute('UPDATE public_links SET revoked = 1 WHERE id = ?', (link_id,))
    db.commit()
    flash('共有リンクを取り消しました')
    return redirect(url_for('shares_list'))


@app.route('/notes/export_all')
@login_required
def export_all_notes():
    user_id = int(current_user.get_id())
    notes = query_db('SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    import csv
    from io import StringIO
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['id','title','tags','period','region','created_at','updated_at','content'])
    for n in notes:
        writer.writerow([n['id'], n['title'] or '', n['tags'] or '', n['period'] or '', n['region'] or '', n['created_at'] or '', n['updated_at'] or '', n['content'] or ''])
    output = si.getvalue()
    resp = make_response(output)
    resp.headers.set('Content-Type', 'text/csv; charset=utf-8')
    resp.headers.set('Content-Disposition', f'attachment; filename=notes_all_user_{user_id}.csv')
    return resp


@app.route('/notes/import', methods=['GET', 'POST'])
@login_required
def note_import():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f:
            flash('ファイルが選択されていません')
            return redirect(url_for('note_import'))
        data = f.read().decode('utf-8')
        title = ''
        lines = data.splitlines()
        if lines and lines[0].startswith('#'):
            title = lines[0].lstrip('#').strip()
        content = data
        db = get_db()
        cur = db.execute('INSERT INTO notes (user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
                   (int(current_user.get_id()), title, content, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        db.commit()
        flash('インポートしました')
        return redirect(url_for('dashboard'))
    return render_template('import.html')


if __name__ == '__main__':
    # Ensure database exists: backup existing and initialize schema
    if not os.path.exists(app.config['DATABASE']):
        print('Database not found, initializing...')
        with app.app_context():
            init_db()
    else:
        # create a timestamped backup before re-initializing
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        bak_path = app.config['DATABASE'] + f'.bak.{ts}'
        try:
            import shutil
            shutil.copyfile(app.config['DATABASE'], bak_path)
            print(f'Backed up existing database to {bak_path}')
        except Exception as e:
            print('Backup failed:', e)
        # initialize (will DROP and CREATE according to schema.sql)
        try:
            with app.app_context():
                init_db()
            print('Database initialized from schema.sql')
        except Exception as e:
            print('Database initialization failed:', e)
    app.run(port=5001, debug=True)
