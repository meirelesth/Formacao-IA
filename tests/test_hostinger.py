"""Integration/security checks against Apache + PHP + real MySQL (disposable CI)."""
import base64, hashlib, hmac, json, re, struct, subprocess, time, unittest
from urllib import request, error, parse
BASE='http://127.0.0.1:8080'
class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None
OPENER=request.build_opener(NoRedirect())
def otp(secret,step=None):
    s=int(time.time())//30 if step is None else step
    h=hmac.new(base64.b32decode(secret),struct.pack('>Q',s),hashlib.sha1).digest();i=h[-1]&15
    return str((struct.unpack('>I',h[i:i+4])[0]&0x7fffffff)%1000000).zfill(6)
def call(path,method='GET',data=None,cookie='',origin=BASE,form=False,raw=None,ctype=None):
    body=raw if raw is not None else (parse.urlencode(data).encode() if form else json.dumps(data or {}).encode()) if method!='GET' else None
    headers={'Origin':origin,'Cookie':cookie,'Content-Type':ctype or ('application/x-www-form-urlencoded' if form else 'application/json')}
    req=request.Request(BASE+path,data=body,headers=headers,method=method)
    try:r=OPENER.open(req)
    except error.HTTPError as e:r=e
    content=r.read();return r.code,dict(r.headers),json.loads(content) if r.headers.get('Content-Type','').startswith('application/json') else content.decode(errors='replace')
def fixture(action):
    return subprocess.check_output(['docker','exec','lf-hostinger','php','/tmp/hostinger-fixture.php',action],text=True)
class HostingerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initial setup is tested through the actual protected browser form.
        key='fixture-setup-key-32-characters-abcdef'
        status,_,html=call('/instalar');assert status==200
        assert call('/login.css')[0]==200 # CSS must work before schema installation.
        assert call('/instalar','POST',{'setup_key':'wrong'},form=True)[0]==200
        status,_,html=call('/instalar','POST',{'setup_key':key},form=True);assert status==200
        cls.secret=re.search(r'<strong>([A-Z2-7]{32})</strong>',html)[1]
        status,_,html=call('/instalar','POST',{'phase':'create','setup_key':key,'name':'Professor','email':'teacher@example.com','password':'teacher-pass-123456','confirm':'teacher-pass-123456','otp':otp(cls.secret)},form=True)
        assert status==200 and 'Instalação concluída' in html
        assert call('/instalar')[0]==404
    def setUp(self):fixture('reset')
    def login(self,email='a@example.com',password='senha-local-123456'):
        payload={'email':email,'password':password}
        if email=='teacher@example.com':payload['otp']=otp(self.secret)
        status,headers,body=call('/api/login','POST',payload);self.assertEqual(status,200,(status,body))
        return headers['Set-Cookie'].split(';')[0],body['csrf']
    def admin(self):return self.login('teacher@example.com','teacher-pass-123456')
    def invite(self,email='new@example.com',courses=None):
        cookie,csrf=self.admin();status,_,b=call('/api/admin/invite','POST',{'name':'Novo Aluno','email':email,'courses':courses or ['basica'],'csrf':csrf},cookie)
        self.assertEqual(status,201);return b['link'].split('#')[1]
    def test_01_setup_closed_and_public_assets(self):
        self.assertEqual(call('/instalar')[0],404)
        for path in ['/','/entrar.html','/ativar.html','/login.css','/certificado.js','/assets/certificado-modelo.png']:
            self.assertEqual(call(path)[0],200,path)
    def test_02_no_public_registration(self):
        self.assertEqual(call('/api/register','POST',{'email':'x@example.com'})[0],401)
    def test_03_cookie_and_private_hashes(self):
        cookie,_=self.login();s,h,b=call('/api/session',cookie=cookie)
        self.assertTrue(b['authenticated']);self.assertEqual(b['user']['email'],'a@example.com')
        _,headers,_=call('/api/login','POST',{'email':'b@example.com','password':'senha-local-654321'})
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Lax',headers['Set-Cookie'])
        stored=json.loads(fixture('inspect'));self.assertNotIn(cookie.split('=',1)[1],[x['token_hash'] for x in stored['sessions']]);self.assertTrue(all('senha-local' not in x['password'] for x in stored['users']))
    def test_04_origin_and_csrf(self):
        c,t=self.login()
        self.assertEqual(call('/api/logout','POST',{},c)[0],403)
        self.assertEqual(call('/api/logout','POST',{'csrf':'á'},c)[0],403)
        self.assertEqual(call('/api/logout','POST',{'csrf':t},c,origin='https://other.example')[0],403)
    def test_05_progress_isolation(self):
        a,t=self.login();self.assertEqual(call('/api/progress','PUT',{'lesson':'ia-generativa','completed':True,'csrf':t},a)[0],200)
        self.assertIn('ia-generativa',call('/api/progress',cookie=a)[2]['completed'])
        b,_=self.login('b@example.com','senha-local-654321');self.assertEqual(call('/api/progress',cookie=b)[2]['completed'],[])
    def test_06_plan_authorization(self):
        a,t=self.login();catalog=call('/catalogo.json',cookie=a)[2];self.assertEqual([x['id'] for x in catalog['courses']],['basica'])
        b,_=self.login('b@example.com','senha-local-654321');other=call('/catalogo.json',cookie=b)[2];self.assertEqual([x['id'] for x in other['courses']],['avancada'])
        lesson=other['courses'][0]['modules'][0]['lessons'][0]
        self.assertEqual(call('/'+lesson['material'],cookie=a)[0],403)
        self.assertEqual(call('/api/progress','PUT',{'lesson':lesson['id'],'completed':True,'csrf':t},a)[0],400)
    def test_07_private_files_without_login(self):
        self.assertEqual(call('/catalogo.json')[0],401)
        self.assertEqual(call('/materiais/aulas/ia-generativa.md')[0],401)
        for path in ['/aluno.html','/admin.html']:self.assertEqual(call(path)[0],303)
        for path in ['/formacao-private/config.php','/hostinger/schema.sql','/.env','/server/app.py','/backup.zip']:
            self.assertIn(call(path)[0],[403,404],path)
    def test_08_traversal_and_encoded_paths(self):
        for path in ['/assets/../catalogo.json','/assets/%2e%2e/catalogo.json','/assets/%2e%2e/materiais/aulas/ia-generativa.md']:
            self.assertEqual(call(path)[0],401,path)
        self.assertIn(call('/assets/../../formacao-private/config.php')[0],[400,403,404])
    def test_09_student_cannot_administer(self):
        c,t=self.login();self.assertEqual(call('/api/admin/students',cookie=c)[0],403)
        self.assertEqual(call('/api/admin/invite','POST',{'name':'A','email':'a@example.com','courses':['basica'],'csrf':t},c)[0],403)
    def test_10_admin_totp_and_replay(self):
        data={'email':'teacher@example.com','password':'teacher-pass-123456'}
        self.assertEqual(call('/api/login','POST',data)[0],401)
        data['otp']=otp(self.secret);self.assertEqual(call('/api/login','POST',data)[0],200)
        self.assertEqual(call('/api/login','POST',data)[0],401)
    def test_11_invitation_and_single_use(self):
        raw=self.invite();self.assertEqual(call('/api/activate','POST',{'token':raw,'password':'12345'})[0],400)
        p={'token':raw,'password':'Ab1!xy'}
        self.assertEqual(call('/api/activate','POST',p)[0],200);self.assertEqual(call('/api/activate','POST',p)[0],400)
        c,_=self.login('new@example.com','Ab1!xy');self.assertEqual([x['id'] for x in call('/catalogo.json',cookie=c)[2]['courses']],['basica'])
        self.assertNotIn(raw,[x['token_hash'] for x in json.loads(fixture('inspect'))['tokens']])
    def test_12_expired_invitation(self):
        raw=self.invite();fixture('expire-token');self.assertEqual(call('/api/activate','POST',{'token':raw,'password':'new-password-123456'})[0],400)
    def test_13_reset_revokes_existing_sessions(self):
        student,_=self.login();a,t=self.admin();rows=call('/api/admin/students',cookie=a)[2]['students'];uid=next(x['id'] for x in rows if x['email']=='a@example.com')
        raw=call('/api/admin/reset-link','POST',{'id':uid,'csrf':t},a)[2]['link'].split('#')[1];data={'token':raw,'password':'Cd2!yz'}
        self.assertEqual(call('/api/reset-password','POST',data)[0],200);self.assertEqual(call('/api/reset-password','POST',data)[0],400)
        self.assertEqual(call('/api/progress',cookie=student)[0],401)
        self.assertEqual(call('/api/login','POST',{'email':'a@example.com','password':'senha-local-123456'})[0],401)
        self.login('a@example.com','Cd2!yz')
    def test_14_suspension_revokes_sessions(self):
        student,_=self.login();a,t=self.admin();uid=next(x['id'] for x in call('/api/admin/students',cookie=a)[2]['students'] if x['email']=='a@example.com')
        self.assertEqual(call('/api/admin/student','PUT',{'id':uid,'active':False,'courses':['basica'],'csrf':t},a)[0],200)
        self.assertEqual(call('/api/progress',cookie=student)[0],401)
        self.assertEqual(call('/api/login','POST',{'email':'a@example.com','password':'senha-local-123456'})[0],401)
    def test_15_recovery_generic_and_durable(self):
        a=call('/api/forgot-password','POST',{'email':'a@example.com'});b=call('/api/forgot-password','POST',{'email':'unknown@example.com'})
        self.assertEqual(a[2],b[2]);self.assertEqual(len(json.loads(fixture('inspect'))['jobs']),2)
        fixture('run-cron');self.assertEqual(json.loads(fixture('inspect'))['jobs'],[])
    def test_16_expiry_and_idle_timeout(self):
        c,_=self.login();fixture('expire-session');self.assertEqual(call('/api/progress',cookie=c)[0],401)
        c,_=self.login();fixture('idle-session');self.assertEqual(call('/api/progress',cookie=c)[0],401)
    def test_17_logout(self):
        c,t=self.login();self.assertEqual(call('/api/logout','POST',{'csrf':t},c)[0],200);self.assertEqual(call('/api/progress',cookie=c)[0],401)
    def test_18_rate_limit_and_generic_login(self):
        for _ in range(5):self.assertEqual(call('/api/login','POST',{'email':'a@example.com','password':'wrong'})[0],401)
        self.assertEqual(call('/api/login','POST',{'email':'a@example.com','password':'wrong'})[0],429)
        self.assertEqual(call('/api/login','POST',{'email':'missing@example.com','password':'wrong'})[2]['error'],'E-mail ou senha inválidos.')
    def test_19_malformed_json_and_sql_injection(self):
        self.assertEqual(call('/api/login','POST',raw=b'[]')[0],400)
        self.assertEqual(call('/api/login','POST',{'email':{},'password':[]})[0],400)
        self.assertEqual(call('/api/login','POST',raw=b'{bad')[0],400)
        self.assertEqual(call('/api/login','POST',raw=b'x'*4097)[0],413)
        self.assertEqual(call('/api/login','POST',{'email':"' OR 1=1 --",'password':'wrong'})[0],401)
    def test_20_content_type_and_headers(self):
        self.assertEqual(call('/api/login','POST',{'email':'a'},ctype='text/plain')[0],415)
        _,headers,_=call('/entrar.html');self.assertEqual(headers['X-Content-Type-Options'],'nosniff');self.assertEqual(headers['X-Frame-Options'],'DENY');self.assertEqual(headers['Cache-Control'],'no-store')
    def test_21_admin_csrf_and_bad_plan_types(self):
        a,t=self.admin()
        self.assertEqual(call('/api/admin/invite','POST',{},a)[0],403)
        for courses in [[],['fake'],[{}],['basica','basica']]:
            self.assertEqual(call('/api/admin/invite','POST',{'name':'A','email':'n@example.com','courses':courses,'csrf':t},a)[0],400)
    def test_22_admin_projection_has_no_hash_or_token(self):
        a,_=self.admin();_,_,data=call('/api/admin/students',cookie=a)
        self.assertTrue(all('password' not in u and 'token' not in u for u in data['students']))
    def test_23_reset_wrong_token_and_weak_password(self):
        self.assertEqual(call('/api/reset-password','POST',{'token':'bad','password':'strong-password-123'})[0],400)
        self.assertEqual(call('/api/activate','POST',{'token':'bad','password':'short'})[0],400)
    def test_24_health_and_unrecognized_method(self):
        self.assertTrue(call('/healthz')[2]['ok']);self.assertEqual(call('/api/session','DELETE')[0],405)
    def test_25_full_recovery_queue_has_generic_response_and_stays_bounded(self):
        fixture('fill-queue');a=call('/api/forgot-password','POST',{'email':'a@example.com'});b=call('/api/forgot-password','POST',{'email':'unknown@example.com'})
        self.assertEqual(a[0],200);self.assertEqual(a[2],b[2]);self.assertEqual(len(json.loads(fixture('inspect'))['jobs']),1000)
    def test_skills_publication_and_access(self):
        self.assertEqual(call('/api/skills')[0],401)
        a,t=self.login()
        self.assertEqual(call('/api/admin/skills',cookie=a)[0],403)
        c,csrf=self.admin()
        payload=dict(title='Skill de teste',category='Dados',description='Pacote de teste',version='1.0',platform='claude',download_url='https://example.com/skill.zip',source_url='https://example.com/docs',install_command='',published=False,csrf=csrf)
        self.assertEqual(call('/api/admin/skills','POST',{**payload,'csrf':'wrong'},c)[0],403)
        status,_,data=call('/api/admin/skills','POST',payload,c)
        self.assertEqual(status,201)
        id=data['id']
        self.assertNotIn(id,[s['id'] for s in call('/api/skills',cookie=a)[2]['skills']])
        update={**payload,'id':id,'published':True}
        self.assertEqual(call('/api/admin/skills','PUT',update,c)[0],200)
        self.assertIn(id,[s['id'] for s in call('/api/skills',cookie=a)[2]['skills']])
        self.assertEqual(call('/api/admin/skills','PUT',{**update,'download_url':'javascript:alert(1)'},c)[0],400)
        self.assertEqual(call('/api/admin/skills','PUT',{**update,'download_url':''},c)[0],400)
        self.assertEqual(call('/api/admin/skills','PUT',{**update,'published':False},c)[0],200)
        self.assertNotIn(id,[s['id'] for s in call('/api/skills',cookie=a)[2]['skills']])
        accented={**update,'published':False,'description':'Á'*500}
        self.assertEqual(call('/api/admin/skills','PUT',accented,c)[0],200)
        self.assertEqual(call('/api/admin/skills','PUT',{**accented,'description':'Á'*501},c)[0],400)

    def test_central_company_withdrawal_existing_database(self):
        a,_=self.login()
        call('/api/skills',cookie=a)
        excluded=json.loads(fixture('seed-retired-skills'))
        c,_=self.admin()
        skills=call('/api/admin/skills',cookie=c)[2]['skills']
        self.assertFalse(set(excluded)&{s['id'] for s in skills})
        for id in excluded:
            self.assertEqual(call('/api/skills/'+str(id)+'/download',cookie=a)[0],404)

    def test_central_git_deployment_import(self):
        fixture('git-skills-layout')
        try:
            a,_=self.login()
            status,_,body=call('/api/skills',cookie=a)
            self.assertEqual(status,200)
            self.assertEqual(len(body['skills']),1303)
            self.assertEqual(sum(bool(s['download_url']) for s in body['skills']),131)
            target=next(s for s in body['skills'] if s['title']=='Documentos do Word (DOCX)')
            self.assertEqual(call(target['download_url'])[0],401)
            self.assertTrue(call(target['download_url'],cookie=a)[2].startswith('PK'))
            self.assertEqual(len(call('/api/skills',cookie=a)[2]['skills']),1303)
            for name in ['skills-catalog.json','skills-packages.json']:
                self.assertIn(call('/server/'+name)[0],[403,404])
            c,_=self.admin()
            self.assertEqual(len(call('/api/admin/skills',cookie=c)[2]['skills']),1303)
            self.assertEqual(call('/api/skills/bundle/download',cookie=c)[0],200)
        finally:
            fixture('restore-skills-layout')

    def test_central_import_and_packages(self):
        a,t=self.login()
        skills=call('/api/skills',cookie=a)[2]['skills']
        self.assertEqual(sum(s['platform']=='catalog' for s in skills),1172)
        self.assertEqual(sum(s['download_url'].startswith('/api/skills/') for s in skills),131)
        target=next(s for s in skills if s['title']=='Documentos do Word (DOCX)')
        self.assertEqual(call(target['download_url'])[0],401)
        download=call(target['download_url'],cookie=a)
        self.assertEqual(download[0],200)
        self.assertTrue(download[2].startswith('PK'))
        self.assertEqual(call('/api/skills/bundle/download',cookie=a)[0],403)
        c,csrf=self.admin()
        self.assertEqual(call('/api/admin/skills','PUT',{**target,'csrf':csrf,'published':False},c)[0],200)
        self.assertEqual(call(target['download_url'],cookie=a)[0],404)
        self.assertFalse(any(s['id']==target['id'] for s in call('/api/skills',cookie=a)[2]['skills']))
        self.assertEqual(call('/api/skills/bundle/download',cookie=c)[0],200)

    def test_central_additions_preserve_admin_edits(self):
        a,_=self.login()
        call('/api/skills',cookie=a)
        original=json.loads(fixture('seed-legacy-localization'))
        c,csrf=self.admin()
        rows=call('/api/admin/skills',cookie=c)[2]['skills']
        migrated=next(s for s in rows if s['id']==original['id'])
        self.assertEqual(migrated['title'],'Minha skill n8n')
        self.assertEqual(migrated['description'],'Minha descrição personalizada.')
        self.assertFalse(migrated['published'])
        changed={**migrated,'title':'Minha edição em português','csrf':csrf}
        self.assertEqual(call('/api/admin/skills','PUT',changed,c)[0],200)
        rows=call('/api/admin/skills',cookie=c)[2]['skills']
        self.assertEqual(next(s for s in rows if s['id']==original['id'])['title'],changed['title'])
        self.assertEqual(call('/api/admin/skills','PUT',{**original,'csrf':csrf},c)[0],200)

    def test_featured_skills_authenticated_downloads(self):
        a,_=self.login()
        rows={s['id']:s for s in call('/api/skills',cookie=a)[2]['skills']}
        for id in range(3000000,3000005):
            row=rows[id]
            self.assertTrue(row['source_url'].startswith('https://github.com/'))
            self.assertEqual(call(row['download_url'])[0],401)
            status,headers,body=call(row['download_url'],cookie=a)
            self.assertEqual(status,200)
            self.assertTrue(body.startswith('PK'))
            self.assertIn('-ptbr.zip',headers['Content-Disposition'])

    def test_30_payment_access_and_duplicate_notifications(self):
        fixture('seed-payments')
        def status(digit):
            return call('/api/payments/status','POST',{'reference':digit*32,'key':digit*64})
        self.assertEqual(call('/api/payments/config')[2]['enabled'],False)
        self.assertEqual(call('/api/payments/create','POST',{})[0],503)
        self.assertEqual(status('4')[2]['state'],'WAITING')
        self.assertIsNone(status('4')[2]['access_url'])
        self.assertIsNone(status('3')[2]['access_url'])
        self.assertIsNone(status('6')[2]['access_url'])
        self.assertTrue(status('6')[2]['admin_test'])
        self.assertEqual(status('6')[2]['amount'],100)
        basic=status('1');self.assertEqual(basic[0],200);link=basic[2]['access_url']
        self.assertTrue(link.startswith('/ativar.html#'))
        self.assertEqual(status('1')[2]['access_url'],link)
        self.assertTrue(status('2')[2]['access_url'].startswith('/ativar.html#'))
        info=json.loads(fixture('inspect-payments'))
        self.assertEqual(len(info['invites']),2)
        for invite in info['invites']:
            self.assertEqual(set(json.loads(invite['courses'])),{'basica','avancada'})
        self.assertEqual(info['orders'][2]['fulfilled'],0)
        self.assertEqual(info['orders'][3]['fulfilled'],0)
        bad=call('/api/payments/status','POST',{'reference':'1'*32,'key':'f'*64})
        self.assertEqual(bad[0],404)
        self.assertEqual(call('/api/payments/status','POST',{'reference':'1'*32,'key':'1'*64},origin='https://evil.example')[0],403)
        self.assertEqual(call('/api/activate','POST',{'token':link.split('#')[1],'password':'123456'})[0],200)
        cookie,_=self.login('newpay@example.com','123456')
        catalog=call('/catalogo.json',cookie=cookie)[2]
        self.assertEqual({c['id'] for c in catalog['courses']},{'basica','avancada'})
        self.assertEqual(status('1')[2]['access_url'],'/entrar.html')
        self.assertEqual(status('5')[2]['access_url'],'/entrar.html')
        c,_=self.login()
        self.assertEqual({course['id'] for course in call('/catalogo.json',cookie=c)[2]['courses']},{'basica','avancada'})

    def test_31_payment_administration_protected(self):
        self.assertEqual(call('/api/admin/payments/test')[0],401)
        self.assertEqual(call('/api/admin/payments/test','POST',{})[0],401)
        self.assertEqual(call('/api/admin/payments/settings')[0],401)
        c,t=self.login()
        self.assertEqual(call('/api/admin/payments/settings',cookie=c)[0],403)
        self.assertEqual(call('/api/admin/payments/test',cookie=c)[0],403)
        c,t=self.admin()
        self.assertEqual(call('/api/admin/payments/settings',cookie=c)[2]['configured'],False)
        self.assertEqual(call('/api/admin/payments/test',cookie=c)[2]['products']['admin_test']['amount'],100)
        self.assertEqual(call('/api/admin/payments/test','POST',{'csrf':'wrong'},c)[0],403)
        self.assertEqual(call('/api/admin/payments/settings','PUT',{'environment':'production','token':'','enabled':True,'csrf':t},c)[0],400)
        self.assertEqual(call('/api/admin/payments/settings','PUT',{'environment':'production','token':'fixture-only-token','enabled':False,'csrf':'wrong'},c)[0],403)

if __name__=='__main__':unittest.main(verbosity=2)
