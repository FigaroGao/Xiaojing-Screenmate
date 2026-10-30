"""Durable timing and final summary cache; no screenshots or raw transcripts."""
import sqlite3
import time
import secrets
from contextlib import contextmanager


class Sessions:
    def __init__(self, path):
        self.path=path
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,started REAL,ended REAL,last_seen REAL,reason TEXT,ack TEXT)')
            if 'summary' not in {r[1] for r in db.execute('PRAGMA table_info(sessions)')}:
                db.execute('ALTER TABLE sessions ADD COLUMN summary TEXT')
            db.execute("UPDATE sessions SET ended=last_seen,reason='interrupted' WHERE ended IS NULL")
        path.chmod(0o600)
        self.current=None
        self.started=None

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()

    def start(self):
        if self.current:return self.current
        ident=secrets.token_hex(12);now=time.time()
        with self.db() as db:db.execute('INSERT INTO sessions(id,started,last_seen) VALUES(?,?,?)',(ident,now,now))
        self.current=ident
        self.started=now
        return ident

    def touch(self):
        if self.current:
            with self.db() as db:db.execute('UPDATE sessions SET last_seen=? WHERE id=?',(time.time(),self.current))

    def end(self,reason='paused'):
        if self.current:
            now=time.time()
            with self.db() as db:db.execute('UPDATE sessions SET ended=?,last_seen=?,reason=? WHERE id=?',(now,now,reason,self.current))
            self.current=None
            self.started=None

    def pending(self):
        with self.db() as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM sessions WHERE ended IS NOT NULL AND ack IS NULL ORDER BY started LIMIT 20')]

    def recent(self):
        with self.db() as db:
            db.row_factory=sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM sessions ORDER BY started DESC LIMIT 20')]

    def missing_summaries(self):
        return [r['id'] for r in self.recent() if r['ack'] and str(r['ack']).isdigit() and not r['summary']]

    def acknowledge(self,ident,memory_id,summary=None):
        if not isinstance(memory_id,int) or memory_id<1:raise ValueError('invalid memory receipt')
        if summary is not None and (not isinstance(summary,str) or len(summary)>4000):raise ValueError('invalid summary')
        with self.db() as db:db.execute('UPDATE sessions SET ack=?,summary=COALESCE(?,summary) WHERE id=? AND ended IS NOT NULL',(str(memory_id),summary,ident))
