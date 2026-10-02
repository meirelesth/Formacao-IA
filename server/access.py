"""Convites, recuperação e administração de matrículas; sem cadastro público."""
import hashlib
import json
import re
import secrets
import smtplib
import os
import ssl
import time
from email.message import EmailMessage
from urllib.parse import quote

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

class Access:
    def migrate(self):
        with self.connect() as db:
            columns={r['name'] for r in db.execute('PRAGMA table_info(users)')}
            for name, definition in [('role', "TEXT NOT NULL DEFAULT 'student'"), ('active','INTEGER NOT NULL DEFAULT 1'),('courses',"TEXT NOT NULL DEFAULT '[\"basica\",\"avancada\"]'")]:
                if name not in columns: db.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
            db.executescript('''CREATE TABLE IF NOT EXISTS access_tokens(token_hash TEXT PRIMARY KEY,purpose TEXT NOT NULL,email TEXT NOT NULL,name TEXT NOT NULL,courses TEXT NOT NULL,user_id INTEGER,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor INTEGER,event TEXT NOT NULL,target TEXT,created INTEGER NOT NULL);''')

    def catalog_for(self, session):
        catalog=json.loads((self.site/'catalogo.json').read_text())
        if session['role']=='admin': return catalog
        allowed=json.loads(session['courses'])
        catalog['courses']=[c for c in catalog['courses'] if c['id'] in allowed]
        lesson_paths={l.get('material') for c in catalog['courses'] for m in c['modules'] for l in m['lessons']}
        all_lesson_paths={l.get('material') for c in json.loads((self.site/'catalogo.json').read_text())['courses'] for m in c['modules'] for l in m['lessons']}
        catalog['materials']=[m for m in catalog['materials'] if m['path'] not in all_lesson_paths or m['path'] in lesson_paths]
        return catalog

    def allowed_material(self, session, path):
        catalog=self.catalog_for(session)
        paths={m['path'] for m in catalog['materials']}
        paths.update(l.get('material') for c in catalog['courses'] for m in c['modules'] for l in m['lessons'])
        return path in paths

    def token(self,purpose,email,name='',courses=None,user_id=None):
        raw=secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('DELETE FROM access_tokens WHERE expires<?',(int(time.time())-86400,))
            db.execute('UPDATE access_tokens SET used=1 WHERE email=? AND purpose=?',(email,purpose))
            db.execute('INSERT INTO access_tokens VALUES(?,?,?,?,?,?,?,0)',(digest(raw),purpose,email,name,json.dumps(courses or []),user_id,int(time.time())+(48*3600 if purpose=='invite' else 1800)))
        return raw

    def limited(self,key,maximum=5):
        now=int(time.time())
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM attempts WHERE created<?',(now-900,))
            if db.execute('SELECT COUNT(*) FROM attempts WHERE key=?',(key,)).fetchone()[0]>=maximum: return True
            db.execute('INSERT INTO attempts VALUES(?,?)',(key,now))
        return False

    def mail(self,email,link,purpose):
        host=os.environ.get('SMTP_HOST')
        if not host: return False
        msg=EmailMessage();msg['From']=os.environ['SMTP_FROM'];msg['To']=email
        msg['Subject']='Seu acesso à Formação IA Luís Fernando' if purpose=='invite' else 'Redefina sua senha — Formação IA Luís Fernando'
        msg.set_content('Use o link para '+('ativar seu acesso (válido por 48 horas)' if purpose=='invite' else 'redefinir sua senha (válido por 30 minutos)')+':\n\n'+link+'\n\nSe não reconhece esta solicitação, ignore esta mensagem.')
        with smtplib.SMTP(host,int(os.environ.get('SMTP_PORT','587')),timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.environ.get('SMTP_USER'): smtp.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
            smtp.send_message(msg)
        return True

    def access_route(self,path,method,data,session,environ,respond):
        from server.app import password_hash
        if path in ('/api/activate','/api/reset-password') and method=='POST':
            if self.limited('token:'+environ.get('REMOTE_ADDR',''),20): return respond('429 Too Many Requests',{'error':'Muitas tentativas. Aguarde 15 minutos.'})
            raw=data.get('token');password=data.get('password')
            if not isinstance(raw,str) or len(raw)>128 or not isinstance(password,str) or not 12<=len(password)<=256:
                return respond('400 Bad Request',{'error':'Informe o link de acesso e uma senha com pelo menos 12 caracteres.'})
            purpose='invite' if path=='/api/activate' else 'reset'
            hashed=password_hash(password)
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                token=db.execute('SELECT * FROM access_tokens WHERE token_hash=? AND purpose=? AND used=0 AND expires>?',(digest(raw),purpose,int(time.time()))).fetchone()
                if not token: return respond('400 Bad Request',{'error':'Link inválido ou expirado. Solicite um novo link.'})
                if purpose=='invite':
                    if db.execute('SELECT id FROM users WHERE email=?',(token['email'],)).fetchone(): return respond('409 Conflict',{'error':'A conta já existe. Entre ou recupere sua senha.'})
                    db.execute('INSERT INTO users(name,email,password,courses) VALUES(?,?,?,?)',(token['name'],token['email'],hashed,token['courses']))
                else:
                    user=db.execute('SELECT id FROM users WHERE id=? AND active=1',(token['user_id'],)).fetchone()
                    if not user: return respond('400 Bad Request',{'error':'Link inválido ou expirado. Solicite um novo link.'})
                    db.execute('UPDATE users SET password=? WHERE id=?',(hashed,user['id']))
                    db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
                db.execute('UPDATE access_tokens SET used=1 WHERE token_hash=?',(digest(raw),))
                db.execute('INSERT INTO audit(actor,event,target,created) VALUES(NULL,?,?,?)',(purpose,token['email'],int(time.time())))
            return respond('200 OK',{'ok':True})
        if path=='/api/forgot-password' and method=='POST':
            email=data.get('email','')
            if not isinstance(email,str) or len(email)>254: return respond('400 Bad Request',{'error':'Informe um e-mail válido.'})
            if self.limited('reset-ip:'+environ.get('REMOTE_ADDR',''),10) or self.limited('reset-email:'+digest(email.strip().lower())):
                return respond('429 Too Many Requests',{'error':'Muitas solicitações. Aguarde 15 minutos.'})
            with self.connect() as db: user=db.execute('SELECT id FROM users WHERE email=? AND active=1',(email.strip().lower(),)).fetchone()
            if user and os.environ.get('SMTP_HOST'):
                raw=self.token('reset',email.strip().lower(),user_id=user['id'])
                try: self.mail(email.strip().lower(),self.origin+'/redefinir.html#'+raw,'reset')
                except (OSError,smtplib.SMTPException): pass
            return respond('200 OK',{'ok':True,'message':'Se o e-mail estiver autorizado, enviaremos as instruções. Caso não receba, solicite ajuda ao professor.'})
        if not path.startswith('/api/admin/'): return None
        if not session: return respond('401 Unauthorized',{'error':'Entre para continuar.'})
        if session['role']!='admin': return respond('403 Forbidden',{'error':'Acesso exclusivo da administração.'})
        if method!='GET' and not secrets.compare_digest(str(data.get('csrf','')),session['csrf']): return respond('403 Forbidden',{'error':'Sessão inválida.'})
        if path=='/api/admin/students' and method=='GET':
            with self.connect() as db:
                users=[dict(r) for r in db.execute("SELECT id,name,email,active,courses FROM users WHERE role='student' ORDER BY name")]
                invites=[dict(r) for r in db.execute("SELECT name,email,courses,expires FROM access_tokens WHERE purpose='invite' AND used=0 AND expires>?",(int(time.time()),))]
            return respond('200 OK',{'students':users,'invitations':invites})
        if path=='/api/admin/invite' and method=='POST':
            name=data.get('name');email=data.get('email');courses=data.get('courses')
            if not isinstance(name,str) or not 1<=len(name.strip())<=120 or not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or not isinstance(courses,list) or not courses or any(c not in ('basica','avancada') for c in courses):
                return respond('400 Bad Request',{'error':'Informe nome, e-mail e pelo menos um plano válido.'})
            email=email.strip().lower()
            with self.connect() as db:
                if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone(): return respond('409 Conflict',{'error':'Este e-mail já possui uma conta.'})
            raw=self.token('invite',email,name.strip(),courses);link=self.origin+'/ativar.html#'+quote(raw)
            sent=False
            try: sent=self.mail(email,link,'invite')
            except (OSError,smtplib.SMTPException): pass
            with self.connect() as db: db.execute('INSERT INTO audit(actor,event,target,created) VALUES(?,?,?,?)',(session['user_id'],'invited',email,int(time.time())))
            return respond('201 Created',{'link':link,'sent':sent,'expires_hours':48})
        if path=='/api/admin/student' and method=='PUT':
            user_id=data.get('id');active=data.get('active');courses=data.get('courses')
            if type(user_id)!=int or not isinstance(active,bool) or not isinstance(courses,list) or (active and not courses) or any(c not in ('basica','avancada') for c in courses): return respond('400 Bad Request',{'error':'Dados inválidos.'})
            with self.connect() as db:
                row=db.execute("SELECT id FROM users WHERE id=? AND role='student'",(user_id,)).fetchone()
                if not row:return respond('404 Not Found',{'error':'Aluno não encontrado.'})
                db.execute('UPDATE users SET active=?,courses=? WHERE id=?',(int(active),json.dumps(courses),user_id))
                db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
                db.execute('INSERT INTO audit(actor,event,target,created) VALUES(?,?,?,?)',(session['user_id'],'enrollment_updated',str(user_id),int(time.time())))
            return respond('200 OK',{'ok':True})
        if path=='/api/admin/reset-link' and method=='POST':
            user_id=data.get('id')
            if type(user_id)!=int:return respond('400 Bad Request',{'error':'Aluno inválido.'})
            with self.connect() as db: user=db.execute("SELECT * FROM users WHERE id=? AND active=1 AND role='student'",(user_id,)).fetchone()
            if not user:return respond('404 Not Found',{'error':'Aluno não encontrado.'})
            raw=self.token('reset',user['email'],user_id=user_id)
            return respond('200 OK',{'link':self.origin+'/redefinir.html#'+raw})
        return respond('404 Not Found',{'error':'Recurso não encontrado.'})
