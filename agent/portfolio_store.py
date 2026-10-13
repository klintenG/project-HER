"""Durable portfolio job/quota records and private media, isolated from the UI.

SQLite is for a single local development process. Cloud Run requires Firestore
and a private Cloud Storage bucket; no in-memory production fallback exists.
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager


class SQLiteStore:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=20)
        try:yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def get(self,key):
        with self.connection() as db:
            row=db.execute('SELECT value FROM records WHERE key=?',(key,)).fetchone()
            return json.loads(row[0]) if row else None
    def set(self,key,value):
        return self.atomic(lambda tx:tx.set(key,value))
    def atomic(self,operation):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            class Transaction:
                def get(self,key):
                    row=db.execute('SELECT value FROM records WHERE key=?',(key,)).fetchone()
                    return json.loads(row[0]) if row else None
                def set(self,key,value):
                    db.execute('INSERT OR REPLACE INTO records VALUES (?,?)',(key,json.dumps(value)))
            return operation(Transaction())


class FirestoreStore:
    def __init__(self,project,namespace='her_portfolio'):
        from google.cloud import firestore
        self.api=firestore;self.client=firestore.Client(project=project)
        self.records=self.client.collection(namespace)
    def get(self,key):
        data=self.records.document(key).get(timeout=15).to_dict()
        if data:data.pop('delete_after',None)
        return data
    def encode(self,value):
        return {**value,**({'delete_after':datetime.fromtimestamp(value['expires_at'],timezone.utc)} if 'expires_at' in value else {})}
    def set(self,key,value):
        self.records.document(key).set(self.encode(value),timeout=15)
    def atomic(self,operation):
        outer=self
        @self.api.transactional
        def execute(transaction):
            class Transaction:
                def get(self,key):
                    data=outer.records.document(key).get(transaction=transaction).to_dict()
                    if data:data.pop('delete_after',None)
                    return data
                def set(self,key,value):transaction.set(outer.records.document(key),outer.encode(value))
            return operation(Transaction())
        return execute(self.client.transaction(max_attempts=5))


class LocalMedia:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def upload(self,source,key,content_type):
        import shutil
        dest=self.root/key;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        return {'key':key,'size':dest.stat().st_size,'content_type':content_type}
    def chunks(self,asset,start,end):
        with (self.root/asset['key']).open('rb') as stream:
            stream.seek(start);remaining=end-start+1
            while remaining>0:
                data=stream.read(min(65536,remaining))
                if not data:break
                remaining-=len(data);yield data
    def exists(self,asset):return (self.root/asset['key']).is_file()


class GCSMedia:
    def __init__(self,bucket,project):
        from google.cloud import storage
        self.bucket=storage.Client(project=project).bucket(bucket)
    def upload(self,source,key,content_type):
        blob=self.bucket.blob(key)
        blob.upload_from_filename(str(source),content_type=content_type,if_generation_match=0,timeout=180)
        return {'key':key,'size':Path(source).stat().st_size,'content_type':content_type,'generation':int(blob.generation)}
    def chunks(self,asset,start,end):
        blob=self.bucket.blob(asset['key'],generation=asset.get('generation'))
        with blob.open('rb',chunk_size=256*1024) as stream:
            stream.seek(start);remaining=end-start+1
            while remaining>0:
                data=stream.read(min(65536,remaining))
                if not data:break
                remaining-=len(data);yield data
    def exists(self,asset):return self.bucket.blob(asset['key'],generation=asset.get('generation')).exists(timeout=15)
