-- users and notes schema
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS notes;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

CREATE TABLE notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT,
    content TEXT,
    tags TEXT,
    period TEXT,
    region TEXT,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE public_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT,
    expires_at TEXT,
    revoked INTEGER DEFAULT 0,
    FOREIGN KEY(note_id) REFERENCES notes(id)
);
