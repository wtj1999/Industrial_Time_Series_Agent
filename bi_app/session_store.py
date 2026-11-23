"""Owner-scoped BI transcripts. Never opens or imports an agent_app database."""

import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
APP_NAMES = {
    'manufacturing-bi-analysis': '制造BI分析智能体', 'quality-bi-analysis': '品质BI分析智能体',
    'cost-bi-analysis': '成本BI分析智能体', 'equipment-bi-analysis': '设备BI分析智能体',
    'ng-defect-analysis': '不良品类型分析智能体', 'control-plan-analysis': 'Control Plan 工艺参数查询',
}
FACTORY_NAMES = {'jinzhai-phase-2': '金寨二期', 'jinzhai-phase-3': '金寨三期', 'wuhu-phase-1': '芜湖一期'}
TENANT_NAMES = {'11200001': '金寨二期', '11300001': '金寨三期', '14100001': '芜湖一期'}


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    from fastapi.encoders import jsonable_encoder
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, allow_nan=False)


def message(content, role='assistant'):
    return {'kind': 'message', 'message': {'role': role, 'content': content, 'timestamp': now()}}


def scope(app_id, *, factory_id=None, tenant_id=None):
    if app_id not in APP_NAMES:
        raise ValueError('Unsupported BI application')
    return {'app_id': app_id, 'app_name': APP_NAMES[app_id], 'factory_id': factory_id,
            'tenant_id': tenant_id, 'factory_name': FACTORY_NAMES.get(factory_id) or TENANT_NAMES.get(tenant_id)}


class BiSessionStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        if self.path.is_relative_to(ROOT.parent / 'agent_app'):
            raise ValueError('BI conversation storage must be separate from agent_app')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS bi_sessions (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, thread TEXT NOT NULL, scope TEXT NOT NULL,
                    metadata TEXT NOT NULL, title TEXT NOT NULL, last_query TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(owner,thread,scope)
                );
                CREATE INDEX IF NOT EXISTS bi_sessions_owner ON bi_sessions(owner,updated_at DESC);
                CREATE TABLE IF NOT EXISTS bi_messages (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL REFERENCES bi_sessions(id) ON DELETE CASCADE,
                    artifact TEXT, body TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS bi_messages_session ON bi_messages(session_id,sequence);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def owner(user):
        return hashlib.sha256(user.encode()).hexdigest()

    def _authorize(self, db, user, session_id):
        row = db.execute('SELECT * FROM bi_sessions WHERE id=? AND owner=?', (session_id, self.owner(user))).fetchone()
        if row is None:
            raise HTTPException(404, 'BI历史对话不存在或不属于当前用户')
        return row

    @staticmethod
    def _append(db, session_id, body, artifact=None):
        entry_id = str(uuid4())
        body = {**body, 'id': entry_id}
        db.execute('INSERT INTO bi_messages(id,session_id,artifact,body,created) VALUES (?,?,?,?,?)',
                   (entry_id, session_id, artifact, encode(body), time.time()))
        return entry_id

    @staticmethod
    def _replace(db, entry_id, body, artifact=None):
        db.execute('UPDATE bi_messages SET body=?,artifact=? WHERE id=?', (encode({**body, 'id': entry_id}), artifact, entry_id))

    def begin(self, user, thread, metadata, *, query='', kind='query', confirmation=None, selection=None):
        fingerprint = encode({key: metadata.get(key) for key in ('app_id', 'factory_id', 'tenant_id')})
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = db.execute('SELECT * FROM bi_sessions WHERE owner=? AND thread=? AND scope=?',
                                (self.owner(user), thread, fingerprint)).fetchone()
            if record is None:
                session_id, created = str(uuid4()), now()
                title = ' '.join(query.split())[:40] or '新对话'
                db.execute('INSERT INTO bi_sessions VALUES (?,?,?,?,?,?,?,?,?)',
                           (session_id, self.owner(user), thread, fingerprint, encode(metadata), title, '', created, created))
                last_query = ''
            else:
                session_id, last_query = record['id'], record['last_query']
            if kind == 'query' and query:
                last_query = query
                for entry in db.execute('SELECT id,body FROM bi_messages WHERE session_id=?', (session_id,)).fetchall():
                    body = json.loads(entry['body'])
                    if body['kind'] == 'confirm' and not body.get('submitted'):
                        body['expired'] = True
                        self._replace(db, entry['id'], body)
            if query:
                self._append(db, session_id, message(query, 'user'))
            if kind == 'deep_analyze':
                progress = {'stage': 'preparing', 'message': '准备读取已确认字段', 'sequence': 0, 'elapsed_seconds': 0}
                pending = {'kind': 'deep_progress', 'progress': progress, 'history': [progress]}
            else:
                pending = message('请求已提交，结果尚未保存。请稍后刷新历史或重新发起查询。')
            entry_id = self._append(db, session_id, pending)
            db.execute('UPDATE bi_sessions SET last_query=?,updated_at=? WHERE id=?', (last_query, now(), session_id))
        return {'session_id': session_id, 'entry_id': entry_id, 'kind': kind, 'thread_id': thread,
                'analysis_query': last_query, 'confirmation': confirmation, 'selection': selection}

    def _submitted(self, db, operation):
        key, selection = operation.get('confirmation'), operation.get('selection')
        if selection is None:
            return
        for entry in db.execute('SELECT id,artifact,body FROM bi_messages WHERE session_id=? ORDER BY sequence DESC', (operation['session_id'],)).fetchall():
            body = json.loads(entry['body'])
            if body['kind'] not in {'confirm', 'deep_confirm'} or body.get('submitted') or body.get('expired'):
                continue
            if key and entry['artifact'] != key:
                continue
            body['submitted'] = True
            if body['kind'] == 'deep_confirm':
                body['plan']['target_id'] = selection['target_id']
                body['plan']['feature_ids'] = selection['feature_ids']
            elif 'response' in body:
                body['response']['confirm']['preselect'] = selection.get('option_ids', [])
            else:
                for field in body['confirm'].get('need_confirm', []):
                    field['selected_values'] = selection.get(field['cls'], [])
            self._replace(db, entry['id'], body, entry['artifact'])
            break

    def finish(self, operation, result, *, control_plan=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM bi_sessions WHERE id=?', (operation['session_id'],)).fetchone():
                return  # Deleting an in-flight conversation must never resurrect it.
            self._submitted(db, operation)
            kind = operation['kind']
            if kind == 'deep_analyze':
                self._finish_progress(db, operation, 'completed', '取数与分析完成')
                self._append(db, operation['session_id'], {'kind': 'deep_result', 'result': result})
            elif kind == 'deep_recommend':
                self._replace(db, operation['entry_id'], {'kind': 'deep_confirm', 'plan': result, 'submitted': False}, result['plan_id'])
            elif result.get('status') == 'need_confirm':
                body = ({'kind': 'confirm', 'response': result, 'submitted': False, 'expired': False} if control_plan else
                        {'kind': 'confirm', 'confirm': result['confirm'], 'threadId': operation['thread_id'],
                         'submitted': False, 'analysisQuery': operation['analysis_query']})
                self._replace(db, operation['entry_id'], body, result.get('confirm', {}).get('confirmation_id'))
            else:
                self._replace(db, operation['entry_id'], {'kind': 'result', 'response' if control_plan else 'result': result})
            db.execute('UPDATE bi_sessions SET updated_at=? WHERE id=?', (now(), operation['session_id']))

    def update_progress(self, operation, progress):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            entry = db.execute('SELECT body FROM bi_messages WHERE id=?', (operation['entry_id'],)).fetchone()
            if entry is None:
                return
            body = json.loads(entry['body'])
            if body['kind'] != 'deep_progress' or body['progress']['stage'] in {'completed', 'failed', 'cancelled'}:
                return
            body['progress'] = progress
            body['history'] = [*body['history'], progress][-160:]
            self._replace(db, operation['entry_id'], body)

    def _finish_progress(self, db, operation, stage, text):
        entry = db.execute('SELECT body FROM bi_messages WHERE id=?', (operation['entry_id'],)).fetchone()
        if entry is None:
            return
        body = json.loads(entry['body'])
        progress = {**body.get('progress', {}), 'stage': stage, 'message': text}
        progress['sequence'] = progress.get('sequence', 0) + 1
        body.update(progress=progress, history=[*body.get('history', []), progress][-160:])
        self._replace(db, operation['entry_id'], body)

    def fail(self, operation, text, *, cancelled=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if operation['kind'] == 'deep_analyze':
                self._finish_progress(db, operation, 'cancelled' if cancelled else 'failed', text)
            else:
                self._replace(db, operation['entry_id'], message(text))
            db.execute('UPDATE bi_sessions SET updated_at=? WHERE id=?', (now(), operation['session_id']))

    @staticmethod
    def _summary(row):
        return {'session_id': row['id'], 'thread_id': row['thread'], 'title': row['title'],
                'created_at': row['created_at'], 'updated_at': row['updated_at'],
                'message_count': row['message_count'], 'source': 'bi', **json.loads(row['metadata'])}

    def list(self, user, limit=100):
        with self.connect() as db:
            rows = db.execute('''SELECT s.*, (SELECT COUNT(*) FROM bi_messages m WHERE m.session_id=s.id) AS message_count
                                 FROM bi_sessions s WHERE owner=? ORDER BY updated_at DESC,id LIMIT ?''', (self.owner(user), limit)).fetchall()
            return [{**self._summary(row), 'user_id': user} for row in rows]

    def get(self, user, session_id):
        try:
            confirmation_ttl = max(1, int(os.getenv('BI_NG_CONFIRMATION_TTL_SECONDS', '86400')))
        except ValueError:
            confirmation_ttl = 86400
        with self.connect() as db:
            record = self._authorize(db, user, session_id)
            entries = db.execute('SELECT body,created FROM bi_messages WHERE session_id=? ORDER BY sequence', (session_id,)).fetchall()
            summary = self._summary({**dict(record), 'message_count': len(entries)})
            turns = []
            for entry in entries:
                body = json.loads(entry['body'])
                ttl = confirmation_ttl if summary['app_id'] == 'ng-defect-analysis' else 86400
                if body['kind'] in {'confirm', 'deep_confirm'} and not body.get('submitted') and time.time()-entry['created'] > ttl:
                    body['expired'] = True
                if body['kind'] == 'deep_progress' and body['progress']['stage'] not in {'completed', 'failed', 'cancelled'}:
                    body = {**message('这次深度分析尚无已保存结果，请稍后刷新历史或重新发起分析。'), 'id': body['id']}
                turns.append(body)
            return {**summary, 'user_id': user, 'turns': turns, 'version': 1}

    def delete(self, user, session_id):
        with self.connect() as db:
            record = self._authorize(db, user, session_id)
            db.execute('DELETE FROM bi_sessions WHERE id=? AND owner=?', (session_id, self.owner(user)))
            return {**json.loads(record['metadata']), 'thread_id': record['thread']}


@lru_cache
def get_bi_sessions():
    load_dotenv(ROOT / '.env', override=False)
    return BiSessionStore(os.getenv('BI_SESSIONS_DB_PATH', str(ROOT / '.state' / 'bi_sessions.sqlite3')))
