"""Separate viewer password and revocable, persistent browser sessions."""
from __future__ import annotations
import argparse
import hashlib
import fcntl
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
import time


class LoginLimited(RuntimeError):
    pass


def lock_store(path):
    path.parent.mkdir(parents=True,exist_ok=True);path.parent.chmod(0o700)
    descriptor=os.open(path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR,0o600)
    lock=os.fdopen(descriptor,'a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close();raise RuntimeError('Stop the viewer before changing its password or starting another viewer')
    return lock


class ViewerAuth:
    SESSION_SECONDS=8*60*60
    IDLE_SECONDS=30*60
    LOGIN_WINDOW=5*60
    def __init__(self,path:Path,clock=time.time,service=False):
        self.path=path;self.clock=clock;self.lock=threading.RLock()
        self.hash_slots=threading.BoundedSemaphore(2)
        self.attempts={};self.global_attempts=[];self.last_save=0
        self._service_lock=lock_store(path) if service else None
        try:
            self.data=json.loads(path.read_text()) if path.exists() else {'version':1,'password':None,'sessions':{}}
            if self.data.get('version')!=1 or not isinstance(self.data.get('sessions'),dict):
                raise ValueError('Invalid viewer authentication store')
        except Exception:self.close();raise
    def close(self):
        if self._service_lock:self._service_lock.close();self._service_lock=None
    @staticmethod
    def _hash(password,salt):
        return hashlib.scrypt(password.encode('utf-8'),salt=bytes.fromhex(salt),n=2**17,r=8,p=1,maxmem=256*1024*1024).hex()
    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.path.parent.chmod(0o700)
        fd,name=tempfile.mkstemp(prefix='.viewer-auth-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(self.data,f);f.flush();os.fsync(f.fileno())
            os.chmod(name,0o600);os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)
        self.last_save=self.clock()
    def set_password(self,password):
        if not 12<=len(password)<=256:raise ValueError('Use a viewer password between 12 and 256 characters')
        salt=secrets.token_hex(16)
        digest=self._hash(password,salt)
        with self.lock:
            self.data={'version':1,'password':{'salt':salt,'scrypt':digest},'sessions':{}}
            self._save()
    def login(self,password,address):
        if not isinstance(password,str) or len(password)>256:return None
        now=self.clock()
        with self.lock:
            self.attempts={a:[t for t in ts if t>now-self.LOGIN_WINDOW] for a,ts in self.attempts.items() if any(t>now-self.LOGIN_WINDOW for t in ts)}
            self.global_attempts=[t for t in self.global_attempts if t>now-self.LOGIN_WINDOW]
            if len(self.attempts.get(address,[]))>=5 or len(self.global_attempts)>=30:raise LoginLimited()
            if not self.data['password']:return None
            self.attempts.setdefault(address,[]).append(now);self.global_attempts.append(now)
            stored=dict(self.data['password'])
        if not self.hash_slots.acquire(blocking=False):raise LoginLimited()
        try:valid=hmac.compare_digest(self._hash(password,stored['salt']),stored['scrypt'])
        finally:self.hash_slots.release()
        if not valid:return None
        with self.lock:
            # A concurrent password change must invalidate an in-flight login.
            if self.data['password']!=stored:return None
            self.attempts.pop(address,None)
            sessions=self.data['sessions']
            sessions={k:v for k,v in sessions.items() if v['expires']>now and v['seen']>now-self.IDLE_SECONDS}
            while len(sessions)>=8:sessions.pop(min(sessions,key=lambda k:sessions[k]['seen']))
            token=secrets.token_hex(32)
            sessions[hashlib.sha256(token.encode()).hexdigest()]={'expires':now+self.SESSION_SECONDS,'seen':now}
            self.data['sessions']=sessions;self._save();return token
    def valid(self,token,touch=True):
        if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):return False
        key=hashlib.sha256(token.encode()).hexdigest();now=self.clock()
        with self.lock:
            session=self.data['sessions'].get(key)
            if not session:return False
            if session['expires']<=now or session['seen']<=now-self.IDLE_SECONDS:
                self.data['sessions'].pop(key);self._save();return False
            if touch:
                session['seen']=now
                if now-self.last_save>=60:self._save()
            return True
    def logout(self,token):
        if not isinstance(token,str):return
        with self.lock:
            self.data['sessions'].pop(hashlib.sha256(token.encode()).hexdigest(),None);self._save()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Set a separate viewer password; restart the viewer afterwards')
    parser.add_argument('--store',type=Path,default=Path('/data/viewer/auth.json'))
    args=parser.parse_args()
    try:
        with lock_store(args.store):
            password=sys.stdin.readline(4096).rstrip('\r\n')
            ViewerAuth(args.store).set_password(password)
        print('Viewer password hash stored; existing sessions revoked. Start the viewer to apply.')
    except (RuntimeError,ValueError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(1)
