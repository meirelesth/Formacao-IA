import io
import json
import tempfile
import unittest
from pathlib import Path
from financeiro.app import Application,cents,password_ok,password_hash

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Application(str(Path(self.tmp.name)/'ledger.db'),secure=False,origin='http://localhost');self.app.owner('Test owner','test-only-password-123');self.token='';self.csrf='';self.login()
    def tearDown(self):self.tmp.cleanup()
    def call(self,route,p=None,origin='http://localhost',csrf=None):
        payload=json.dumps(p).encode() if p is not None else b'';path,_,query=route.partition('?');env={'PATH_INFO':'/fin/api/'+path,'QUERY_STRING':query,'REQUEST_METHOD':'POST' if p is not None else 'GET','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(payload)),'wsgi.input':io.BytesIO(payload),'HTTP_ORIGIN':origin,'HTTP_COOKIE':self.token,'HTTP_X_CSRF_TOKEN':self.csrf if csrf is None else csrf,'REMOTE_ADDR':'127.0.0.1'};result={}
        def start(s,h):result['status']=int(s.split()[0]);result['headers']=dict(h)
        body=json.loads(b''.join(self.app(env,start)))
        if 'Set-Cookie'in result['headers']:self.token=result['headers']['Set-Cookie'].split(';')[0]
        return result['status'],body
    def login(self):s,p=self.call('login',{'password':'test-only-password-123'});self.assertEqual(s,200);self.csrf=p['csrf']
    def entry(self,**kw):
        return self.call('entries',dict(description='Conta de teste',kind='expense',category='Moradia',month='2026-10',amount='100.00',**kw))
    def test_auth_origin_csrf(self):
        self.assertEqual(self.call('entries',{},origin='https://evil.example')[0],403)
        self.assertEqual(self.call('entries',{},csrf='invalid')[0],403)
        self.token='';self.assertEqual(self.call('data?month=2026-10')[0],401)
    def test_payment_partial_and_optimistic_version(self):
        status,p=self.entry();self.assertEqual(status,200);eid=p['ids'][0]
        self.assertEqual(self.call('settle',{'id':eid,'version':1,'amount':'40','paid_date':'2026-10-11'})[0],200)
        self.assertEqual(self.call('settle',{'id':eid,'version':1,'amount':'60','paid_date':'2026-10-11'})[0],409)
        self.assertEqual(self.call('settle',{'id':eid,'version':2,'amount':'61','paid_date':'2026-10-11'})[0],400)
        s,d=self.call('data?month=2026-10');self.assertEqual(d['summary']['payable'],6000)
    def test_installments_keep_cents_no_double_count(self):
        self.call('cards',{'name':'Test card','closing_day':25,'due_day':5})
        s,p=self.call('entries',{'description':'Compra','kind':'purchase','category':'Pessoal','month':'2026-10','amount':'100.00','parts':3,'card_id':1,'invoice_month':'2026-11'})
        self.assertEqual(s,200)
        with self.app.db() as db:rows=list(db.execute('SELECT * FROM entries'));self.assertEqual(sum(r['amount'] for r in rows),10000)
        self.assertEqual(self.call('data?month=2026-10')[1]['summary']['expenses'],0)
        d=self.call('data?month=2026-11')[1];self.assertEqual(d['summary']['expenses'],3334)
        self.assertEqual(self.call('invoice/pay',{'card_id':1,'month':'2026-11','paid_date':'2026-11-05'})[0],200)
        d=self.call('data?month=2026-11')[1];self.assertEqual(d['summary']['expenses'],3334);self.assertEqual(d['summary']['payable'],0)
        self.assertEqual(self.call('invoice/pay',{'card_id':1,'month':'2026-11','paid_date':'2026-11-05'})[0],409)
    def test_repeat_and_short_month(self):
        s,p=self.call('entries',{'description':'Aluguel','kind':'expense','category':'Moradia','month':'2026-01','due_date':'2026-01-31','amount':'100','parts':3})
        self.assertEqual(s,200)
        with self.app.db() as db:rows=list(db.execute('SELECT * FROM entries ORDER BY id'));self.assertEqual(rows[1]['due_date'],'2026-02-28');self.assertEqual(sum(r['amount'] for r in rows),30000)
    def test_review_excluded_and_paid_preserved(self):
        self.entry()
        with self.app.db() as db:db.execute('UPDATE entries SET review=1,paid=10000,notes="Importado OK"')
        d=self.call('data?month=2026-10')[1];self.assertEqual(d['summary']['expenses'],0);self.assertEqual(d['summary']['review'],1)
        self.assertEqual(self.call('review',{'id':1,'version':1,'amount':'90','category':'Moradia'})[0],400)
        self.assertEqual(self.call('review',{'id':1,'version':1,'amount':'100','category':'Moradia'})[0],200)
        d=self.call('data?month=2026-10')[1];self.assertEqual(d['summary']['expenses'],10000);self.assertEqual(d['summary']['payable'],0)
    def test_lockout_persisted(self):
        for _ in range(5):self.assertEqual(self.call('login',{'password':'wrong'})[0],401)
        self.assertEqual(self.call('login',{'password':'test-only-password-123'})[0],429)
    def test_money_rejects_nonfinite_and_precision(self):
        for v in ['NaN','Infinity','0','-1','1.234']:
            with self.assertRaises(Exception):cents(v)
        self.assertEqual(cents('0.01'),1)

    def test_paid_invoice_rejects_new_purchase_and_displays_matching_month(self):
        self.call('cards',{'name':'Card','closing_day':20,'due_day':5})
        p={'description':'Compra','kind':'purchase','category':'Pessoal','month':'2026-10','amount':'100','parts':1,'card_id':1,'invoice_month':'2026-11'}
        self.assertEqual(self.call('entries',p)[0],200)
        self.assertEqual(len(self.call('data?month=2026-11')[1]['entries']),1)
        self.call('invoice/pay',{'card_id':1,'month':'2026-11','paid_date':'2026-11-05'})
        self.assertEqual(self.call('entries',p)[0],409)

    def test_imported_card_configuration_and_historical_reversal(self):
        with self.app.db() as db:
            db.execute("INSERT INTO cards(name,closing_day,due_day,configured) VALUES('Imported',1,1,0)")
            db.execute("INSERT INTO entries(description,kind,category,month,amount,paid,card_id,invoice_month,created) VALUES('Historical','invoice','Cartões','2026-10',10000,10000,1,'2026-10',1)")
        d=self.call('data?month=2026-10')[1];self.assertIsNone(d['invoices'][0]['due_date'])
        self.assertEqual(self.call('cards',{'id':1,'name':'Imported','closing_day':25,'due_day':10})[0],200)
        self.assertEqual(self.call('data?month=2026-10')[1]['invoices'][0]['due_date'],'2026-10-10')
        self.assertEqual(self.call('invoice/reverse',{'card_id':1,'month':'2026-10'})[0],200)
        d=self.call('data?month=2026-10')[1];self.assertEqual(d['invoices'][0]['paid'],0)
        self.assertEqual(d['entries'][0]['version'],2)

    def test_explicit_duplicate_review_keeps_trace_excludes_total(self):
        self.entry()
        with self.app.db() as db:db.execute('UPDATE entries SET review=1')
        self.assertEqual(self.call('review',{'id':1,'version':1,'included_invoice':True})[0],200)
        d=self.call('data?month=2026-10')[1];self.assertEqual(d['summary']['expenses'],0)
        with self.app.db() as db:self.assertEqual(db.execute('SELECT deleted FROM entries').fetchone()[0],1)

    def test_edit_after_confirmation_preserves_confirmed_state(self):
        self.entry()
        self.assertEqual(self.call('review',{'id':1,'version':1,'amount':'150','paid_amount':'0','category':'Moradia'})[0],200)
        d=self.call('data?month=2026-10')[1]
        self.assertEqual(d['summary']['expenses'],15000)
        self.assertEqual(d['entries'][0]['review'],0)
        self.assertEqual(self.call('review',{'id':1,'version':2,'amount':'75','paid_amount':'0','category':'Moradia'})[0],200)
        d=self.call('data?month=2026-10')[1];self.assertEqual(d['summary']['expenses'],7500)

    def test_explicit_payment_correction_after_confirmation(self):
        self.entry()
        self.call('settle',{'id':1,'version':1,'amount':'100','paid_date':'2026-10-11'})
        self.assertEqual(self.call('review',{'id':1,'version':2,'amount':'90','paid_amount':'90','category':'Moradia'})[0],200)
        d=self.call('data?month=2026-10')[1];self.assertEqual(d['summary']['expenses'],9000);self.assertEqual(d['summary']['paid'],9000)

if __name__=='__main__':unittest.main()
