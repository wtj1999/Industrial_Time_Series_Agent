"""Durable owner-scoped engineering validation records, separate from expiring plans."""

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from uuid import uuid4

from .errors import NgError


class RcaValidationStore:
    def __init__(self, path):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS rca_analyses (id TEXT PRIMARY KEY, owner TEXT NOT NULL, thread TEXT NOT NULL, body TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS rca_validations (id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, field_id TEXT NOT NULL, body TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS rca_quality_audits (analysis_id TEXT NOT NULL, field_id TEXT NOT NULL, record_ref TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(analysis_id,record_ref))")
            connection.execute("CREATE INDEX IF NOT EXISTS rca_quality_field ON rca_quality_audits(analysis_id,field_id)")
        except Exception:
            connection.close()
            raise
        return connection

    @staticmethod
    def owner(user):
        return hashlib.sha256(user.encode()).hexdigest()

    def run(self, action):
        for attempt in range(4):
            connection = None
            try:
                connection = self.connect()
                with connection:
                    return action(connection)
            except sqlite3.OperationalError as exc:
                if getattr(exc,"sqlite_errorcode",None) != sqlite3.SQLITE_CANTOPEN or attempt == 3:
                    raise NgError("分析及验证档案暂时无法读取或保存，请重试",503) from exc
                time.sleep(.1*(attempt+1))
            finally:
                if connection is not None:
                    connection.close()

    def create(self, analysis_id, user, thread, root, context=None, quality_audit=None):
        body = {"created_at":datetime.now(timezone.utc).isoformat(),
                "fields":{f["field_id"]:{"name":f["name"],"process_name":f["process_name"]} for f in root["factors"]},
                "context":context,"root_cause":root}
        def action(connection):
            connection.execute("INSERT INTO rca_analyses VALUES (?,?,?,?)",[analysis_id,self.owner(user),thread,json.dumps(body,ensure_ascii=False)])
            connection.executemany("INSERT INTO rca_quality_audits VALUES (?,?,?,?)",[
                (analysis_id,row['field_id'],row['record_ref'],json.dumps(row,ensure_ascii=False,allow_nan=False)) for row in quality_audit or []])
        return self.run(action)

    def authorize(self, connection, analysis_id, user, thread):
        row = connection.execute("SELECT body FROM rca_analyses WHERE id=? AND owner=? AND thread=?", [analysis_id,self.owner(user),thread]).fetchone()
        if not row:
            raise NgError("分析记录不存在或不属于当前用户与会话", 404)
        return json.loads(row[0])

    def list(self, analysis_id, user, thread):
        def action(connection):
            self.authorize(connection,analysis_id,user,thread)
            return [json.loads(row[0]) for row in connection.execute("SELECT body FROM rca_validations WHERE analysis_id=? ORDER BY rowid DESC",[analysis_id])]
        return self.run(action)

    def append(self, request, user):
        def action(connection):
            analysis = self.authorize(connection,request.analysis_id,user,request.thread_id)
            if request.field_id not in analysis["fields"]:
                raise NgError("验证因素不属于本次分析",422)
            record = {**request.model_dump(exclude={"factory_id","thread_id"}),"id":str(uuid4()),
                      "recorded_at":datetime.now(timezone.utc).isoformat(),"source":"engineer_record","causal_status":"unconfirmed"}
            if request.before_total and request.after_total:
                before,after = request.before_ng/request.before_total,request.after_ng/request.after_total
                record.update(before_rate=before,after_rate=after,change_percentage_points=(after-before)*100)
            connection.execute("INSERT INTO rca_validations VALUES (?,?,?,?)",[record["id"],request.analysis_id,request.field_id,json.dumps(record,ensure_ascii=False,allow_nan=False)])
            return record
        return self.run(action)

    def quality_audit(self, request, user):
        def action(connection):
            self.authorize(connection,request.analysis_id,user,request.thread_id)
            total=connection.execute("SELECT COUNT(1) FROM rca_quality_audits WHERE analysis_id=? AND field_id=?",[request.analysis_id,request.field_id]).fetchone()[0]
            rows=connection.execute("SELECT body FROM rca_quality_audits WHERE analysis_id=? AND field_id=? ORDER BY record_ref LIMIT ? OFFSET ?",[request.analysis_id,request.field_id,request.limit,request.offset]).fetchall()
            return {"total":total,"offset":request.offset,"records":[json.loads(row[0]) for row in rows]}
        return self.run(action)
