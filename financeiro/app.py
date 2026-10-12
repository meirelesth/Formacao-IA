"""Private, single-owner financial ledger. Money is stored as integer cents."""
import calendar
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent
SCHEMA = '''
CREATE TABLE IF NOT EXISTS owner(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,csrf TEXT NOT NULL,expires INTEGER NOT NULL,last_seen INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(ip TEXT PRIMARY KEY,count INTEGER NOT NULL,until INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS cards(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE,closing_day INTEGER NOT NULL CHECK(closing_day BETWEEN 1 AND 31),due_day INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),limit_cents INTEGER NOT NULL DEFAULT 0,configured INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY,description TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('income','expense','purchase','invoice')),category TEXT NOT NULL,month TEXT NOT NULL,due_date TEXT,amount INTEGER NOT NULL CHECK(amount>0),paid INTEGER NOT NULL DEFAULT 0 CHECK(paid>=0 AND paid<=amount),paid_date TEXT,card_id INTEGER REFERENCES cards(id),invoice_month TEXT,group_id TEXT,part INTEGER DEFAULT 1,parts INTEGER DEFAULT 1,review INTEGER NOT NULL DEFAULT 0,source TEXT UNIQUE,notes TEXT NOT NULL DEFAULT '',version INTEGER NOT NULL DEFAULT 1,deleted INTEGER NOT NULL DEFAULT 0,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,event TEXT NOT NULL,entry_id INTEGER,detail TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invoice_payments(id INTEGER PRIMARY KEY,card_id INTEGER NOT NULL REFERENCES cards(id),month TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),paid_date TEXT NOT NULL,UNIQUE(card_id,month));
CREATE INDEX IF NOT EXISTS entries_month ON entries(month,deleted);
'''

class Problem(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status

class Connection(sqlite3.Connection):
    def __exit__(self,*args):
        try: return super().__exit__(*args)
        finally: self.close()

def cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > Decimal('100000000'): raise ValueError()
        rounded = amount.quantize(Decimal('.01'))
        if amount != rounded: raise ValueError()
        return int(rounded * 100)
    except (ValueError, InvalidOperation, TypeError): raise Problem('Informe um valor positivo com até duas casas decimais.')

def month(value):
    try: datetime.strptime(value, '%Y-%m'); assert len(value) == 7
    except (ValueError, TypeError, AssertionError): raise Problem('Selecione um mês válido.')
    return value

def day(value, optional=False):
    if not value and optional: return None
    try: return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError): raise Problem('Informe uma data válida.')

def shift(value, n):
    y, m = map(int, value.split('-')); y, m = divmod(y*12+m-1+n, 12)
    return f'{y:04}-{m+1:02}'

def dated(value, number):
    y, m = map(int, value.split('-')); return f'{value}-{min(number, calendar.monthrange(y,m)[1]):02}'

def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return f'{salt}:{digest}'

def password_ok(password, encoded):
    salt, digest = encoded.split(':')
    actual = hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return hmac.compare_digest(actual,digest)

class Application:
    def __init__(self, database=None, secure=True, origin=None):
        self.database = database or os.environ.get('FIN_DATABASE','/data/financeiro.sqlite3')
        self.secure = secure
        self.origin = origin or os.environ.get('FIN_ORIGIN','https://luisfernando.online')
        self.alt_origin = os.environ.get('FIN_ALT_ORIGIN','')
        Path(self.database).parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.executescript(SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            if 'configured' not in {r['name'] for r in db.execute('PRAGMA table_info(cards)')}:
                db.execute('ALTER TABLE cards ADD COLUMN configured INTEGER NOT NULL DEFAULT 0')

    def db(self):
        db=sqlite3.connect(self.database,timeout=15,factory=Connection); db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA journal_mode=WAL'); return db

    def audit(self,db,event,entry_id=None,detail=''):
        db.execute('INSERT INTO audit(event,entry_id,detail,created) VALUES(?,?,?,?)',(event,entry_id,detail,int(time.time())))

    def owner(self,name,password):
        if len(password)<12: raise Problem('Use uma senha com pelo menos 12 caracteres.')
        with self.db() as db:
            db.execute('INSERT INTO owner VALUES(1,?,?)',(name,password_hash(password)))

    def __call__(self,env,start):
        headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','same-origin'),('X-Frame-Options','DENY'),('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")]
        try:
            path=env.get('PATH_INFO',''); method=env['REQUEST_METHOD']
            if path in ('/fin','/fin/'):
                data=(ROOT/'public/index.html').read_bytes(); content='text/html; charset=utf-8'; status=200
            elif path in ('/fin/app.js','/fin/style.css','/fin/manifest.json','/fin/icon.svg','/fin/sw.js'):
                file=ROOT/'public'/path.rsplit('/',1)[-1]; data=file.read_bytes()
                content={'.js':'application/javascript','.css':'text/css','.json':'application/manifest+json','.svg':'image/svg+xml'}[file.suffix]; status=200
            elif path=='/fin/healthz':
                data=json.dumps({'ok':True}).encode(); content='application/json'; status=200
            elif path.startswith('/fin/api/'):
                if method not in ('GET','POST'): raise Problem('Método não permitido.',405)
                payload={}
                if method=='POST':
                    allowed={self.origin}
                    if self.alt_origin:allowed.add(self.alt_origin)
                    if env.get('HTTP_ORIGIN') not in allowed: raise Problem('Origem não autorizada.',403)
                    if 'application/json' not in env.get('CONTENT_TYPE',''): raise Problem('Formato inválido.',415)
                    try:
                        length=int(env.get('CONTENT_LENGTH') or 0)
                        if length>32768: raise Problem('Solicitação muito grande.',413)
                        payload=json.loads(env['wsgi.input'].read(length))
                        if not isinstance(payload,dict): raise ValueError()
                    except (ValueError,TypeError): raise Problem('Dados inválidos.')
                with self.db() as db:
                    result,cookie=self.api(db,path,method,payload,env)
                if cookie is not None: headers.append(('Set-Cookie',cookie))
                data=json.dumps(result,ensure_ascii=False).encode(); content='application/json; charset=utf-8'; status=200
            else: raise Problem('Página não encontrada.',404)
        except Problem as e: status=e.status; data=json.dumps({'error':e.message},ensure_ascii=False).encode(); content='application/json; charset=utf-8'
        except Exception:
            status=500; data=b'{"error":"Falha ao processar. Tente novamente."}'; content='application/json'
        headers += [('Content-Type',content),('Content-Length',str(len(data)))]
        start(f'{status} '+{200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',405:'Method Not Allowed',409:'Conflict',413:'Payload Too Large',415:'Unsupported Media Type',429:'Too Many Requests',500:'Internal Server Error',503:'Service Unavailable'}.get(status,'Error'),headers)
        return [data]

    def cookie(self,token,age=28800):
        return f'fin_session={token}; Path=/fin; HttpOnly; SameSite=Strict; Max-Age={age}'+('; Secure' if self.secure else '')

    def api(self,db,path,method,p,env):
        now=int(time.time()); route=path.removeprefix('/fin/api/')
        db.execute('DELETE FROM sessions WHERE expires<? OR last_seen<?',(now,now-1800))
        db.execute('DELETE FROM attempts WHERE until<?',(now-86400,))
        if route=='login' and method=='POST':
            ip=env.get('REMOTE_ADDR','unknown'); attempt=db.execute('SELECT * FROM attempts WHERE ip=?',(ip,)).fetchone()
            if attempt and attempt['count']>=5 and attempt['until']>now: raise Problem('Muitas tentativas. Aguarde 15 minutos.',429)
            password=p.get('password','')
            if not isinstance(password,str) or len(password)>1024: raise Problem('Credenciais inválidas.',401)
            owner=db.execute('SELECT * FROM owner WHERE id=1').fetchone()
            if not owner: raise Problem('A conta privada ainda precisa ser ativada pelo proprietário.',503)
            if not password_ok(password,owner['password']):
                count=attempt['count']+1 if attempt and attempt['until']>now else 1
                db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)',(ip,count,now+900)); db.commit()
                raise Problem('Credenciais inválidas.',401)
            db.execute('DELETE FROM attempts WHERE ip=?',(ip,)); db.execute('DELETE FROM sessions')
            token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),csrf,now+28800,now))
            self.audit(db,'login'); return {'name':owner['name'],'csrf':csrf},self.cookie(token)
        cookie=env.get('HTTP_COOKIE',''); token=''
        for c in cookie.split(';'):
            k,_,v=c.strip().partition('=')
            if k=='fin_session': token=v
        session=db.execute('SELECT * FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if route=='session' and method=='GET':
            return {'authenticated':bool(session),'name':'Luís Fernando' if session else None,'csrf':session['csrf'] if session else None},None
        if not session: raise Problem('Entre para acessar seu financeiro.',401)
        if method=='POST' and not hmac.compare_digest(str(env.get('HTTP_X_CSRF_TOKEN','')),session['csrf']): raise Problem('Atualize a página e tente novamente.',403)
        db.execute('UPDATE sessions SET last_seen=? WHERE token=?',(now,session['token']))
        if route=='logout' and method=='POST':
            db.execute('DELETE FROM sessions WHERE token=?',(session['token'],)); return {'ok':True},self.cookie('',0)
        if route=='data' and method=='GET':
            q=parse_qs(env.get('QUERY_STRING','')); selected=month(q.get('month',[date.today().strftime('%Y-%m')])[0])
            entries=[dict(r) for r in db.execute("SELECT * FROM entries WHERE deleted=0 AND (month=? OR (kind IN ('purchase','invoice') AND invoice_month=?)) ORDER BY COALESCE(due_date,month),id",(selected,selected))]
            cards=[dict(r) for r in db.execute('SELECT * FROM cards ORDER BY name')]
            invoices=[]
            for c in cards:
                rows=list(db.execute("SELECT * FROM entries WHERE deleted=0 AND card_id=? AND invoice_month=? AND kind IN ('purchase','invoice')",(c['id'],selected)))
                total=sum(r['amount'] for r in rows if not r['review'])
                paid=sum(r['paid'] for r in rows if r['kind']=='invoice' and not r['review'])
                pay=db.execute('SELECT * FROM invoice_payments WHERE card_id=? AND month=?',(c['id'],selected)).fetchone()
                paid+=pay['amount'] if pay else 0
                invoices.append({**c,'total':total,'paid':paid,'due_date':dated(selected,c['due_day']) if c['configured'] else None,'review':sum(r['review'] for r in rows)})
            valid=[r for r in entries if not r['review']]
            income=sum(r['amount'] for r in valid if r['kind']=='income')
            expenses=sum(r['amount'] for r in valid if r['kind']=='expense')+sum(i['total'] for i in invoices)
            received=sum(r['paid'] for r in valid if r['kind']=='income')
            paid=sum(r['paid'] for r in valid if r['kind']=='expense')+sum(i['paid'] for i in invoices)
            categories={}
            for r in valid:
                if r['kind']=='expense': categories[r['category']]=categories.get(r['category'],0)+r['amount']
            for i in invoices:
                for r in db.execute("SELECT category,SUM(amount) amount FROM entries WHERE deleted=0 AND review=0 AND card_id=? AND invoice_month=? AND kind IN ('purchase','invoice') GROUP BY category",(i['id'],selected)):
                    categories[r['category']]=categories.get(r['category'],0)+r['amount']
            return {'entries':entries,'cards':cards,'invoices':invoices,'summary':{'income':income,'expenses':expenses,'received':received,'paid':paid,'receivable':income-received,'payable':expenses-paid,'projected':income-expenses,'movement':received-paid,'review':sum(r['review'] for r in entries)},'categories':categories},None
        if route=='cards' and method=='POST':
            name=str(p.get('name','')).strip()[:80]
            if not name: raise Problem('Informe o nome do cartão.')
            try: closing=int(p['closing_day']); due=int(p['due_day']); assert 1<=closing<=31 and 1<=due<=31
            except (KeyError,ValueError,TypeError,AssertionError): raise Problem('Fechamento e vencimento devem ficar entre 1 e 31.')
            limit=cents(p['limit']) if p.get('limit') else 0
            try:
                if p.get('id'):
                    cur=db.execute('UPDATE cards SET name=?,closing_day=?,due_day=?,limit_cents=?,configured=1 WHERE id=?',(name,closing,due,limit,p['id']))
                    if not cur.rowcount:raise Problem('Cartão não encontrado.',404)
                else:db.execute('INSERT INTO cards(name,closing_day,due_day,limit_cents) VALUES(?,?,?,?)',(name,closing,due,limit))
            except sqlite3.IntegrityError: raise Problem('Já existe um cartão com esse nome.',409)
            self.audit(db,'card.create'); return {'ok':True},None
        if route=='entries' and method=='POST':
            description=str(p.get('description','')).strip()[:180]; category=str(p.get('category','')).strip()[:80]
            if not description or not category: raise Problem('Preencha descrição e categoria.')
            kind=p.get('kind'); amount=cents(p.get('amount')); selected=month(p.get('month')); due=day(p.get('due_date'),True)
            if kind not in ('income','expense','purchase'): raise Problem('Selecione o tipo de lançamento.')
            try: parts=int(p.get('parts',1)); assert 1<=parts<=120
            except (ValueError,TypeError,AssertionError): raise Problem('Use de 1 a 120 parcelas ou meses.')
            if due and due[:7]!=selected: raise Problem('A data deve pertencer ao mês selecionado.')
            card=None; invoice=None
            if kind=='purchase':
                card=db.execute('SELECT * FROM cards WHERE id=?',(p.get('card_id'),)).fetchone()
                if not card: raise Problem('Cadastre e selecione um cartão.')
                invoice=month(p.get('invoice_month'))
                # An imported invoice is an opening balance, not a second set of purchases.
                if db.execute("SELECT 1 FROM entries WHERE deleted=0 AND kind='invoice' AND card_id=? AND invoice_month BETWEEN ? AND ?",(card['id'],invoice,shift(invoice,parts-1))).fetchone():
                    raise Problem('Este mês contém uma fatura histórica importada. Revise a fatura antes de adicionar compras.',409)
                if db.execute('SELECT 1 FROM invoice_payments WHERE card_id=? AND month BETWEEN ? AND ?',(card['id'],invoice,shift(invoice,parts-1))).fetchone():
                    raise Problem('Uma dessas faturas já foi paga. Estorne o pagamento antes de incluir compras.',409)
            group=secrets.token_hex(12); ids=[]; base,remainder=divmod(amount,parts) if kind=='purchase' else (amount,0)
            if base<1: raise Problem('O valor é insuficiente para dividir nessas parcelas.')
            for i in range(parts):
                period=shift(selected,i); value=base+(1 if i<remainder else 0)
                cur=db.execute('INSERT INTO entries(description,kind,category,month,due_date,amount,card_id,invoice_month,group_id,part,parts,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(description,kind,category,period,dated(period,int(due[-2:])) if due else None,value,card['id'] if card else None,shift(invoice,i) if invoice else None,group,i+1,parts,now))
                ids.append(cur.lastrowid); self.audit(db,'entry.create',cur.lastrowid)
            return {'ok':True,'ids':ids},None
        if route=='invoice/pay' and method=='POST':
            selected=month(p.get('month')); card_id=p.get('card_id'); paid_date=day(p.get('paid_date'))
            rows=list(db.execute("SELECT * FROM entries WHERE deleted=0 AND review=0 AND card_id=? AND invoice_month=? AND kind IN ('purchase','invoice')",(card_id,selected)))
            if not rows: raise Problem('Não há fatura confirmada neste mês.')
            total=sum(r['amount'] for r in rows); historic=sum(r['paid'] for r in rows if r['kind']=='invoice')
            if db.execute('SELECT 1 FROM invoice_payments WHERE card_id=? AND month=?',(card_id,selected)).fetchone(): raise Problem('A fatura já foi paga.',409)
            remaining=total-historic
            if remaining<=0: raise Problem('A fatura já está quitada.',409)
            db.execute('INSERT INTO invoice_payments(card_id,month,amount,paid_date) VALUES(?,?,?,?)',(card_id,selected,remaining,paid_date)); self.audit(db,'invoice.pay',detail=f'{card_id}:{selected}')
            return {'ok':True},None
        if route in ('settle','review','delete') and method=='POST':
            r=db.execute('SELECT * FROM entries WHERE id=? AND deleted=0',(p.get('id'),)).fetchone()
            if not r: raise Problem('Lançamento não encontrado.',404)
            if p.get('version')!=r['version']: raise Problem('O lançamento foi alterado. Atualize a tela.',409)
            if r['card_id'] and db.execute('SELECT 1 FROM invoice_payments WHERE card_id=? AND month=?',(r['card_id'],r['invoice_month'])).fetchone(): raise Problem('A fatura já foi paga. Estorne o pagamento antes de alterar seus itens.',409)
            if route=='settle':
                if r['review']: raise Problem('Revise o lançamento antes de registrar o pagamento.')
                if r['kind'] in ('purchase','invoice'): raise Problem('Registre o pagamento na aba Cartões.')
                value=cents(p.get('amount')); paid_date=day(p.get('paid_date'))
                if value>r['amount']-r['paid']: raise Problem('O valor supera o saldo pendente.')
                db.execute('UPDATE entries SET paid=paid+?,paid_date=?,version=version+1 WHERE id=?',(value,paid_date,r['id']))
            elif route=='review':
                if p.get('included_invoice'):
                    if not r['review'] or r['kind']!='expense' or r['paid']:raise Problem('Somente despesa importada sem pagamento pode ser marcada como incluída na fatura.')
                    db.execute('UPDATE entries SET deleted=1,review=0,version=version+1,notes=notes||? WHERE id=?',(' Já incluída em fatura, confirmado pelo proprietário.',r['id']))
                    self.audit(db,'entry.included_invoice',r['id']);return {'ok':True},None
                amount=cents(p.get('amount')); due=day(p.get('due_date'),True); category=str(p.get('category','')).strip()[:80]
                if not category: raise Problem('Informe a categoria.')
                if due and due[:7]!=r['month']: raise Problem('A data deve pertencer ao mês do lançamento.')
                paid=r['paid']
                if 'paid_amount' in p and r['kind']!='purchase':paid=0 if str(p['paid_amount']) in ('0','0.00') else cents(p['paid_amount'])
                if amount<paid: raise Problem('O valor não pode ser menor que o pagamento já registrado.')
                db.execute('UPDATE entries SET amount=?,paid=?,due_date=?,category=?,review=0,notes=?,version=version+1 WHERE id=?',(amount,paid,due,category,str(p.get('notes',''))[:500],r['id']))
                self.audit(db,'entry.value_correction',r['id'],json.dumps({'before':{'amount':r['amount'],'paid':r['paid']},'after':{'amount':amount,'paid':paid}}))
            else:
                if r['paid']: raise Problem('Estorne o pagamento antes de excluir.')
                db.execute('UPDATE entries SET deleted=1,version=version+1 WHERE id=?',(r['id'],))
            self.audit(db,'entry.'+route,r['id']); return {'ok':True},None
        if route=='reverse' and method=='POST':
            r=db.execute('SELECT * FROM entries WHERE id=? AND deleted=0',(p.get('id'),)).fetchone()
            if not r: raise Problem('Lançamento não encontrado.',404)
            if p.get('version')!=r['version']: raise Problem('Atualize a tela.',409)
            if r['kind'] in ('purchase','invoice'): raise Problem('Use o estorno da fatura.')
            db.execute('UPDATE entries SET paid=0,paid_date=NULL,version=version+1 WHERE id=?',(r['id'],)); self.audit(db,'entry.reverse',r['id']); return {'ok':True},None
        if route=='invoice/reverse' and method=='POST':
            selected=month(p.get('month'));card_id=p.get('card_id')
            removed=db.execute('DELETE FROM invoice_payments WHERE card_id=? AND month=?',(card_id,selected)).rowcount
            historic=db.execute("UPDATE entries SET paid=0,paid_date=NULL,version=version+1 WHERE kind='invoice' AND deleted=0 AND card_id=? AND invoice_month=? AND paid>0",(card_id,selected)).rowcount
            if not removed and not historic:raise Problem('Não há pagamento para estornar.',409)
            self.audit(db,'invoice.reverse',detail=f'{card_id}:{selected}'); return {'ok':True},None
        if route=='export' and method=='GET':
            return {'entries':[dict(r) for r in db.execute('SELECT * FROM entries WHERE deleted=0')],'cards':[dict(r) for r in db.execute('SELECT * FROM cards')],'invoice_payments':[dict(r) for r in db.execute('SELECT * FROM invoice_payments')]},None
        raise Problem('Operação não encontrada.',404)

application = None

def wsgi(env,start):
    global application
    if application is None: application=Application()
    return application(env,start)
