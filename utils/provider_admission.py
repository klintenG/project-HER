"""Account-scoped, cancellation-safe prediction pacing on one worker host."""
import asyncio
import fcntl
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time


class ProviderAdmission:
    def __init__(self, credential, interval=1, root=None):
        key=hashlib.sha256(credential.encode()).hexdigest()[:20]
        self.path=Path(root or tempfile.gettempdir())/('her-image-admission-'+key+'.json')
        self.interval=max(0,float(interval))

    def _update(self,cooldown=None):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('a+') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX)
            try:
                stream.seek(0)
                try:stored=json.load(stream)
                except (ValueError,TypeError):stored={}
                if not isinstance(stored,dict) or stored.get('version')!=3:stored={}
                try:value=float(stored.get('next',0));cooldown_until=float(stored.get('cooldown_until',0))
                except (ValueError,TypeError):value=0;cooldown_until=0
                # Python 3.9 on macOS does not guarantee a common monotonic
                # origin across processes. Persist epoch time for host-wide
                # coordination; monotonic clocks remain local trace timers.
                now=time.time()
                if not math.isfinite(value) or value>now+300:value=now
                if not math.isfinite(cooldown_until) or cooldown_until>now+300:cooldown_until=now
                if cooldown is not None:cooldown_until=max(cooldown_until,now+cooldown)
                delay=max(0,value-now,cooldown_until-now)
                # Commit only an admission that can happen NOW. Waiting tasks
                # never reserve future slots that survive their cancellation.
                following=now+self.interval if cooldown is None and delay<=0 else value
                stream.seek(0);stream.truncate()
                json.dump({'version':3,'next':following,'cooldown_until':cooldown_until},stream);stream.flush()
                return delay
            finally:fcntl.flock(stream,fcntl.LOCK_UN)

    async def wait(self):
        waited=0
        while True:
            delay=self._update()
            if delay<=0:return waited
            await asyncio.sleep(delay);waited+=delay

    def wait_sync(self,waiter):
        waited=0
        while True:
            delay=self._update()
            if delay<=0:return waited
            waiter(delay);waited+=delay

    def throttled(self,seconds):
        self._update(cooldown=max(1,min(60,float(seconds))))
