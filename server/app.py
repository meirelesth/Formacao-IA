"""Aplicação WSGI de autenticação e progresso. Executar atrás de HTTPS em produção."""
import argparse
import getpass
import hashlib
import hmac
import json
import mimetypes
import os
import posixpath
import secrets
import sqlite3
import time
from contextlib import contextmanager
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import unquote, urlsplit
from server.access import Access

SITE = Path(os.environ.get('SITE_ROOT', str(Path(__file__).resolve().parent.parent))).resolve()
SESSION_SECONDS = 8 * 3600
ITERATIONS = 600_000

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f'{salt}:{digest}'

def password_matches(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)

class Application(Access):
    def __init__(self, database=None, origin=None, site=None):
        self.site = Path(site or SITE).resolve()
        self.database = Path(database or os.environ.get('DATABASE_PATH', 'data/formacao.sqlite3')).resolve()
        self.origin = (origin or os.environ.get('APP_ORIGIN', 'http://127.0.0.1:8080')).rstrip('/')
        parsed = urlsplit(self.origin)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path:
            raise ValueError('APP_ORIGIN deve ser uma origem HTTP(S), sem caminho.')
        self.secure = parsed.scheme == 'https'
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, csrf TEXT NOT NULL, expires INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE TABLE IF NOT EXISTS progress(user_id INTEGER NOT NULL, lesson_id TEXT NOT NULL, completed INTEGER NOT NULL, updated INTEGER NOT NULL, PRIMARY KEY(user_id,lesson_id), FOREIGN KEY(user_id) REFERENCES users(id));
                CREATE TABLE IF NOT EXISTS attempts(key TEXT NOT NULL, created INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS attempts_key ON attempts(key,created);
            ''')
        self.migrate()
        os.chmod(self.database, 0o600)
        self.dummy_hash = password_hash(secrets.token_urlsafe(24))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_user(self, name, email, password):
        if len(password) < 12 or len(password) > 256:
            raise ValueError('A senha deve ter de 12 a 256 caracteres.')
        if not name.strip() or '@' not in email or len(email) > 254:
            raise ValueError('Nome e e-mail válidos são obrigatórios.')
        with self.connect() as db:
            db.execute('INSERT INTO users(name,email,password) VALUES(?,?,?)', (name.strip(), email.strip().lower(), password_hash(password)))

    def session(self, environ):
        cookie = SimpleCookie()
        try:
            cookie.load(environ.get('HTTP_COOKIE',''))
            token = cookie['lf_session'].value
        except (KeyError, CookieError):
            return None
        if len(token) > 128:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:
            return db.execute('SELECT s.*,u.name,u.email,u.role,u.active,u.courses FROM sessions s JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires>? AND u.active=1', (token_hash,int(time.time()))).fetchone()

    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD','GET')
        path = posixpath.normpath('/'+unquote(environ.get('PATH_INFO','/')).lstrip('/'))
        headers = [('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' https://cdn.jsdelivr.net; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")]
        if self.secure: headers.append(('Strict-Transport-Security','max-age=31536000'))
        def respond(status, payload, extra=None, content_type='application/json; charset=utf-8'):
            body = json.dumps(payload,ensure_ascii=False).encode() if content_type.startswith('application/json') else payload
            start_response(status, headers + [('Content-Type',content_type),('Content-Length',str(len(body))),('Cache-Control','no-store')] + (extra or []))
            return [body]
        if path=='/healthz' and method=='GET':
            with self.connect() as db: db.execute('SELECT 1').fetchone()
            return respond('200 OK',{'ok':True})
        if method not in ('GET','POST','PUT'):
            return respond('405 Method Not Allowed',{'error':'Método não permitido.'})
        if method in ('POST','PUT'):
            if environ.get('HTTP_ORIGIN') != self.origin:
                return respond('403 Forbidden',{'error':'Origem da requisição não permitida.'})
            if environ.get('CONTENT_TYPE','').split(';')[0] != 'application/json':
                return respond('415 Unsupported Media Type',{'error':'Envie JSON.'})
            try:
                size=int(environ.get('CONTENT_LENGTH') or 0)
                if size < 1 or size > 4096:
                    return respond('413 Payload Too Large',{'error':'Requisição inválida.'})
                data=json.loads(environ['wsgi.input'].read(size))
                if not isinstance(data,dict): raise ValueError()
            except (ValueError,KeyError,UnicodeError):
                return respond('400 Bad Request',{'error':'JSON inválido.'})
        else:
            data={}
        session=self.session(environ)
        access=self.access_route(path,method,data,session,environ,respond)
        if access is not None: return access
        if path == '/api/session' and method == 'GET':
            return respond('200 OK',{'authenticated': bool(session), **({'user':{'name':session['name'],'email':session['email'],'role':session['role']},'csrf':session['csrf']} if session else {})})
        if path == '/api/login' and method == 'POST':
            email=data.get('email',''); password=data.get('password','')
            if not isinstance(email,str) or not isinstance(password,str) or len(email)>254 or len(password)>256:
                return respond('400 Bad Request',{'error':'Dados de acesso inválidos.'})
            email=email.strip().lower(); now=int(time.time())
            if self.limited('login-ip:'+environ.get('REMOTE_ADDR',''),20) or self.limited('login-email:'+hashlib.sha256(email.encode()).hexdigest(),5):
                return respond('429 Too Many Requests',{'error':'Muitas tentativas. Aguarde 15 minutos.'})
            # Sem confiar em X-Forwarded-For: o proxy deve passar o endereço validado.
            key=hashlib.sha256((environ.get('REMOTE_ADDR','')+'|'+email).encode()).hexdigest()
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM attempts WHERE created<?',(now-900,))
                db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
                count=db.execute('SELECT COUNT(*) FROM attempts WHERE key=?',(key,)).fetchone()[0]
                if count>=5:
                    return respond('429 Too Many Requests',{'error':'Muitas tentativas. Aguarde 15 minutos.'},[('Retry-After','900')])
                db.execute('INSERT INTO attempts(key,created) VALUES(?,?)',(key,now))
                user=db.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                valid=password_matches(password,user['password'] if user else self.dummy_hash)
                if not user or not valid or not user['active']:
                    return respond('401 Unauthorized',{'error':'E-mail ou senha inválidos.'})
                token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                if session: db.execute('DELETE FROM sessions WHERE token_hash=?',(session['token_hash'],))
                db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,now+SESSION_SECONDS))
            cookie=f'lf_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_SECONDS}' + ('; Secure' if self.secure else '')
            return respond('200 OK',{'user':{'name':user['name'],'email':user['email'],'role':user['role']},'csrf':csrf},[('Set-Cookie',cookie)])
        if path.startswith('/api/'):
            if not session:
                return respond('401 Unauthorized',{'error':'Entre para acessar sua formação.'})
            if method != 'GET' and not hmac.compare_digest(str(data.get('csrf','')),session['csrf']):
                return respond('403 Forbidden',{'error':'Sessão inválida. Recarregue a página.'})
            if path == '/api/logout' and method == 'POST':
                with self.connect() as db: db.execute('DELETE FROM sessions WHERE token_hash=?',(session['token_hash'],))
                return respond('200 OK',{'ok':True},[('Set-Cookie','lf_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'+('; Secure' if self.secure else ''))])
            if path == '/api/progress' and method == 'GET':
                with self.connect() as db: rows=db.execute('SELECT lesson_id,completed FROM progress WHERE user_id=?',(session['user_id'],)).fetchall()
                return respond('200 OK',{'completed':[r['lesson_id'] for r in rows if r['completed']]})
            if path == '/api/progress' and method == 'PUT':
                catalog=self.catalog_for(session)
                valid={l['id'] for c in catalog['courses'] for m in c['modules'] for l in m['lessons'] if l.get('available')}
                lesson=data.get('lesson'); done=data.get('completed')
                if not isinstance(lesson,str) or lesson not in valid or not isinstance(done,bool):
                    return respond('400 Bad Request',{'error':'Aula ou progresso inválido.'})
                with self.connect() as db: db.execute('INSERT INTO progress VALUES(?,?,?,?) ON CONFLICT(user_id,lesson_id) DO UPDATE SET completed=excluded.completed,updated=excluded.updated',(session['user_id'],lesson,int(done),int(time.time())))
                return respond('200 OK',{'ok':True})
            return respond('404 Not Found',{'error':'Recurso não encontrado.'})
        if method != 'GET':
            return respond('405 Method Not Allowed',{'error':'Método não permitido.'})
        if path == '/': path='/index.html'
        if path == '/aluno.html' and not session:
            return respond('303 See Other',b'',[('Location','entrar.html')],content_type='text/plain')
        preview=False
        if path == '/admin.html' and (not session or session['role']!='admin'):
            return respond('303 See Other',b'',[('Location','entrar.html')],content_type='text/plain')
        if path == '/catalogo.json':
            if not session: return respond('401 Unauthorized',{'error':'Entre para acessar sua formação.'})
            return respond('200 OK',self.catalog_for(session))
        if path.startswith('/materiais/') and path!='/materiais/Portfolio_Formacao_IA_VIP.pdf':
            if not session: return respond('401 Unauthorized',{'error':'Entre para acessar o material.'})
            if not self.allowed_material(session,path.lstrip('/')): return respond('403 Forbidden',{'error':'Material não incluído na sua matrícula.'})
        target=(self.site/path.lstrip('/')).resolve()
        public_names={'index.html','styles.css','app.js','aluno.html','aluno.css','aluno.js','entrar.html','entrar.js','catalogo.json','login.css','ativar.html','redefinir.html','acesso.js','admin.html','admin.js','planos.html','planos.css','portfolio.css','favicon.ico'}
        relative=path.lstrip('/')
        public=relative in public_names or relative.startswith(('assets/','materiais/'))
        if not public or not target.is_relative_to(self.site) or not target.is_file() or target.suffix not in {'.html','.css','.js','.json','.jpg','.png','.svg','.md','.ico','.pdf'}:
            return respond('404 Not Found',{'error':'Página não encontrada.'})
        content=target.read_bytes()
        if target.suffix=='.html':
            content=content.replace(b'data-preview="true"',b'data-preview="'+(b'true' if preview else b'false')+b'"')
        return respond('200 OK',content,content_type=mimetypes.guess_type(target.name)[0] or 'application/octet-stream')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=['serve','create-user','create-admin','backup']); parser.add_argument('--name');parser.add_argument('--email');parser.add_argument('--output');parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args(); app=Application()
    if args.action in ('create-user','create-admin'):
        if not args.name or not args.email: parser.error('--name e --email são obrigatórios')
        password=getpass.getpass('Senha (mínimo 12 caracteres): ')
        if password != getpass.getpass('Confirme a senha: '): raise ValueError('As senhas são diferentes.')
        app.add_user(args.name,args.email,password)
        if args.action=='create-admin':
            with app.connect() as db: db.execute("UPDATE users SET role='admin' WHERE email=?",(args.email.strip().lower(),))
        print('Conta criada.')
    elif args.action=='backup':
        if not args.output: parser.error('--output é obrigatório')
        with app.connect() as db, sqlite3.connect(args.output) as dest: db.backup(dest)
        os.chmod(args.output,0o600)
        print('Backup concluído.')
    else:
        from wsgiref.simple_server import make_server
        print(f'Desenvolvimento local: http://127.0.0.1:{args.port}')
        with make_server('127.0.0.1',args.port,app) as httpd: httpd.serve_forever()

if __name__=='__main__': main()

