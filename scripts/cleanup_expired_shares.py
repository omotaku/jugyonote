#!/usr/bin/env python3
"""Disable (revoke) public_links whose expires_at < now or already expired.
Usage: python3 scripts/cleanup_expired_shares.py [--db path/to/notes.db]
"""
import sqlite3
import sys
import os
from datetime import datetime

DB = os.environ.get('NOTES_DB') or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'notes.db')
if len(sys.argv) > 1:
    DB = sys.argv[1]

def cleanup(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    # find expired and not yet revoked
    cur.execute("SELECT id, token, expires_at FROM public_links WHERE revoked = 0 AND expires_at IS NOT NULL")
    rows = cur.fetchall()
    to_revoke = []
    for r in rows:
        try:
            if r['expires_at'] and datetime.fromisoformat(r['expires_at']) < datetime.utcnow():
                to_revoke.append(r['id'])
        except Exception:
            continue
    if to_revoke:
        cur.execute('BEGIN')
        for lid in to_revoke:
            cur.execute('UPDATE public_links SET revoked = 1 WHERE id = ?', (lid,))
        conn.commit()
    conn.close()
    return to_revoke

if __name__ == '__main__':
    revoked = cleanup(DB)
    if revoked:
        print('Revoked links:', revoked)
    else:
        print('No expired links found')
