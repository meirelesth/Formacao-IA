import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from server.app import Application

class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=Application(Path(self.tmp.name)/'test.sqlite3','https://formacao.example')
        self.app.add_user('Aluno A','a@example.com','senha-local-123456')
        self.app.add_user('Aluno B','b@example.com','senha-local-654321')

    def tearDown(self): self.tmp.cleanup()

    def request(self,path,method='GET',data=None,cookie='',origin='https://formacao.example'):
        body=json.dumps(data or {}).encode();result={}
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'HTTP_COOKIE':cookie,'HTTP_ORIGIN':origin,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body),'REMOTE_ADDR':'127.0.0.1'}
        def start(status,headers): result.update(status=int(status[:3]),headers=dict(headers))
        raw=b''.join(self.app(env,start));result['body']=json.loads(raw) if raw and result['headers']['Content-Type'].startswith('application/json') else raw
        return result

    def login(self,email='a@example.com',password='senha-local-123456'):
        r=self.request('/api/login','POST',{'email':email,'password':password})
        self.assertEqual(r['status'],200)
        return r['headers']['Set-Cookie'].split(';')[0],r['body']['csrf']

    def test_login_cookie_and_session(self):
        r=self.request('/api/login','POST',{'email':'a@example.com','password':'senha-local-123456'})
        cookie=r['headers']['Set-Cookie']
        for protection in ['HttpOnly','SameSite=Lax','Secure']: self.assertIn(protection,cookie)
        session=self.request('/api/session',cookie=cookie.split(';')[0])
        self.assertEqual(session['body']['user']['name'],'Aluno A')
        with sqlite3.connect(self.app.database) as db:
            stored=db.execute('SELECT token_hash FROM sessions').fetchone()[0]
            self.assertNotIn(stored,cookie)
            self.assertNotIn('senha-local',db.execute('SELECT password FROM users LIMIT 1').fetchone()[0])

    def test_login_failures_are_generic_and_limited(self):
        for _ in range(5):
            r=self.request('/api/login','POST',{'email':'a@example.com','password':'errada'})
            self.assertEqual(r['status'],401)
        self.assertEqual(self.request('/api/login','POST',{'email':'a@example.com','password':'errada'})['status'],429)
        unknown=self.request('/api/login','POST',{'email':'missing@example.com','password':'errada'})
        self.assertEqual(unknown['body']['error'],'E-mail ou senha inválidos.')

    def test_progress_requires_login(self):
        self.assertEqual(self.request('/api/progress')['status'],401)
        self.assertEqual(self.request('/aluno.html')['status'],303)

    def test_progress_isolated_and_persistent(self):
        a,csrf=self.login()
        r=self.request('/api/progress','PUT',{'lesson':'problema-real','completed':True,'csrf':csrf},a)
        self.assertEqual(r['status'],200)
        self.assertEqual(self.request('/api/progress',cookie=a)['body']['completed'],['problema-real'])
        b,_=self.login('b@example.com','senha-local-654321')
        self.assertEqual(self.request('/api/progress',cookie=b)['body']['completed'],[])
        self.app=Application(self.app.database,'https://formacao.example')
        self.assertEqual(self.request('/api/progress',cookie=a)['body']['completed'],['problema-real'])

    def test_csrf_origin_and_unpublished_lesson(self):
        cookie,csrf=self.login()
        self.assertEqual(self.request('/api/progress','PUT',{'lesson':'problema-real','completed':True},cookie)['status'],403)
        self.assertEqual(self.request('/api/progress','PUT',{'lesson':'problema-real','completed':True,'csrf':csrf},cookie,origin='https://other.example')['status'],403)
        self.assertEqual(self.request('/api/progress','PUT',{'lesson':'apis','completed':True,'csrf':csrf},cookie)['status'],400)

    def test_expired_session_and_logout(self):
        cookie,csrf=self.login()
        self.assertEqual(self.request('/api/logout','POST',{'csrf':csrf},cookie)['status'],200)
        self.assertEqual(self.request('/api/progress',cookie=cookie)['status'],401)
        cookie,_=self.login()
        with self.app.connect() as db: db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.request('/api/progress',cookie=cookie)['status'],401)

    def test_static_paths_and_modes(self):
        self.assertEqual(self.request('/../server/app.py')['status'],404)
        self.assertIn(b'data-preview="true"',self.request('/demo.html')['body'])
        self.assertIn(b'data-preview="false"',self.request('/entrar.html')['body'])
        cookie,_=self.login()
        self.assertIn(b'data-preview="false"',self.request('/aluno.html',cookie=cookie)['body'])

    def test_bad_payloads(self):
        self.assertEqual(self.request('/api/login','POST',{'email':{},'password':[]})['status'],400)
        self.assertEqual(self.request('/api/login','POST',{'email':'x','password':'x'*5000})['status'],413)
        self.assertEqual(self.request('/api/login','POST',{'email':'x','password':'x'},origin='')['status'],403)

if __name__=='__main__': unittest.main()
