"""Second factor (RFC 6238) and bounded asynchronous recovery delivery."""
import base64
import hashlib
import hmac
import os
import re
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

_delivery = ThreadPoolExecutor(max_workers=2, thread_name_prefix='recovery')
_slots = BoundedSemaphore(8)

def totp(secret, step=None):
    key=base64.b32decode(secret.upper()+'='*((-len(secret))%8))
    msg=struct.pack('>Q',int(time.time())//30 if step is None else step)
    digest=hmac.new(key,msg,hashlib.sha1).digest()
    offset=digest[-1]&15
    return str((struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1_000_000).zfill(6)

def otp_step(secret, code):
    if not secret or not isinstance(code,str) or not re.fullmatch('[0-9]{6}',code): return None
    now=int(time.time())//30
    for step in (now,now-1,now+1):
        if hmac.compare_digest(totp(secret,step),code): return step
    return None

def recovery_async(app,email):
    # Enqueue the same task for existing and unknown accounts. SMTP never blocks
    # the public response. The bounded queue cannot grow without limit.
    if not _slots.acquire(blocking=False): return
    def deliver():
        try:
            if not os.environ.get('SMTP_HOST'): return
            with app.connect() as db:
                user=db.execute('SELECT id FROM users WHERE email=? AND active=1',(email,)).fetchone()
            if not user: return
            raw=app.token('reset',email,user_id=user['id'])
            app.mail(email,app.origin+'/redefinir.html#'+raw,'reset')
        except Exception:
            # Do not log tokens, addresses or SMTP credentials. Delivery failure
            # remains recoverable through an administrator's manual reset link.
            import logging
            logging.getLogger(__name__).warning('Recovery delivery failed')
        finally: _slots.release()
    try: _delivery.submit(deliver)
    except RuntimeError: _slots.release()
