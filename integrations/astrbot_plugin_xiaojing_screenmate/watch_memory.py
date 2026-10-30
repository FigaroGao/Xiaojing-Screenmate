"""Private companion records and exactly-once write intent journal."""
import sqlite3
import time
import hashlib
from contextlib import contextmanager

class WatchMemory:
    def __init__(self,path):
        self.path=path;path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS notes(episode TEXT,key TEXT,stamp REAL,body TEXT,PRIMARY KEY(episode,key))')
            db.execute('CREATE TABLE IF NOT EXISTS summaries(episode TEXT PRIMARY KEY,body TEXT,state TEXT,memory_id INTEGER)')
        path.chmod(0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    def note(self,episode,key,text):
        if not episode or not text:return
        with self.db() as db:db.execute('INSERT OR IGNORE INTO notes VALUES(?,?,?,?)',(episode,key,time.time(),text[:3000]))
    def material(self,episode):
        with self.db() as db:
            rows=db.execute('SELECT body FROM notes WHERE episode=? ORDER BY stamp',(episode,)).fetchall()
        # Preserve both opening and closing context; full notes remain available locally.
        chosen=rows if len(rows)<=30 else rows[:5]+rows[-25:]
        return '\n'.join(row[0] for row in chosen)[-24000:],len(rows),len(chosen)
    def summary(self,episode):
        with self.db() as db:return db.execute('SELECT body,state,memory_id FROM summaries WHERE episode=?',(episode,)).fetchone()
    def save_draft(self,episode,body):
        with self.db() as db:db.execute('INSERT OR IGNORE INTO summaries VALUES(?,?,?,NULL)',(episode,body,'draft'))
    def state(self,episode,state,memory_id=None):
        with self.db() as db:db.execute('UPDATE summaries SET state=?,memory_id=? WHERE episode=?',(state,memory_id,episode))
