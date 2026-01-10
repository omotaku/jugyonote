#!/usr/bin/env python3
"""Simple migration script: copy users and notes from a backup sqlite file into current DB.
Usage: python3 scripts/migrate_from_backup.py /path/to/backup.db /path/to/target.db
This will copy users and notes, mapping old notes fields to new schema (tags/period/region left empty).
"""
import sqlite3
import sys
import shutil
from datetime import datetime

def migrate(src, dst):
    # ensure dst exists
    conn_src = sqlite3.connect(src)
    conn_dst = sqlite3.connect(dst)
    conn_src.row_factory = sqlite3.Row
    cur_src = conn_src.cursor()
    cur_dst = conn_dst.cursor()

    # copy users (avoid duplicates by username)
    cur_src.execute('SELECT * FROM users')
    users = cur_src.fetchall()
    for u in users:
        cur_dst.execute('SELECT id FROM users WHERE username = ?', (u['username'],))
        if cur_dst.fetchone():
            continue
        cur_dst.execute('INSERT INTO users (username, password) VALUES (?, ?)', (u['username'], u['password']))
    conn_dst.commit()

    # build mapping old_user_id -> new_user_id
    cur_dst.execute('SELECT id, username FROM users')
    mapping = {r['username']: r['id'] for r in cur_dst.fetchall()}

    # copy notes
    cur_src.execute('SELECT * FROM notes')
    notes = cur_src.fetchall()
    for n in notes:
        # try finding username by joining users table in src
        user_id = n['user_id']
        cur_src.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user_row = cur_src.fetchone()
        if not user_row:
            continue
        username = user_row['username']
        new_user_id = mapping.get(username)
        if not new_user_id:
            continue
        created = n['created_at'] or datetime.utcnow().isoformat()
        updated = n.get('updated_at') or created
        cur_dst.execute('INSERT INTO notes (user_id, title, content, tags, period, region, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (new_user_id, n['title'], n['content'], '', '', '', created, updated))
    conn_dst.commit()
    conn_src.close()
    conn_dst.close()
    print('Migration complete.')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: migrate_from_backup.py /path/to/backup.db /path/to/target.db')
        sys.exit(1)
    migrate(sys.argv[1], sys.argv[2])
