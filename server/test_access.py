import json
import time
import unittest
from unittest.mock import patch
from server import test_app

class EnrollmentTests(unittest.TestCase):
    tearDown=test_app.AuthenticationTests.tearDown
    request=test_app.AuthenticationTests.request
    login=test_app.AuthenticationTests.login
    def setUp(self):
        test_app.AuthenticationTests.setUp(self)
        self.app.add_user('Professor','teacher@example.com','teacher-pass-123456')
        with self.app.connect() as db: db.execute("UPDATE users SET role='admin' WHERE email='teacher@example.com'")
        self.app.admin_totp_secret='JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'
        self.admin,self.csrf=self.login('teacher@example.com','teacher-pass-123456')

    def invite(self):
        r=self.request('/api/admin/invite','POST',{'name':'Novo Aluno','email':'new@example.com','courses':['basica'],'csrf':self.csrf},self.admin)
        self.assertEqual(r['status'],201)
        return r['body']['link'].split('#')[1]

    def activate(self,token):
        return self.request('/api/activate','POST',{'token':token,'password':'new-password-123456'})

    def test_invite_activation_and_single_use(self):
        token=self.invite();self.assertEqual(self.activate(token)['status'],200)
        self.assertEqual(self.activate(token)['status'],400)
        cookie,_=self.login('new@example.com','new-password-123456')
        r=self.request('/catalogo.json',cookie=cookie)
        self.assertEqual([c['id'] for c in r['body']['courses']],['basica'])
        with self.app.connect() as db:
            self.assertNotEqual(db.execute('SELECT token_hash FROM access_tokens').fetchone()[0],token)

    def test_expired_and_replaced_invites(self):
        old=self.invite();new=self.invite()
        self.assertEqual(self.activate(old)['status'],400)
        with self.app.connect() as db: db.execute('UPDATE access_tokens SET expires=0')
        self.assertEqual(self.activate(new)['status'],400)

    def test_no_public_registration_and_no_student_admin(self):
        self.assertEqual(self.request('/api/register','POST',{'email':'any@example.com'})['status'],401)
        cookie,csrf=self.login()
        self.assertEqual(self.request('/api/admin/students',cookie=cookie)['status'],403)
        self.assertEqual(self.request('/api/admin/invite','POST',{'csrf':csrf},cookie)['status'],403)
        self.assertEqual(self.request('/api/admin/invite','POST',{},self.admin)['status'],403)

    def test_private_materials_and_course_authorization(self):
        token=self.invite();self.activate(token);cookie,csrf=self.login('new@example.com','new-password-123456')
        r=self.request('/catalogo.json',cookie=self.admin)['body']
        lesson=r['courses'][1]['modules'][0]['lessons'][0]
        material='/'+lesson['material']
        self.assertEqual(self.request(material)['status'],401)
        self.assertEqual(self.request(material,cookie=cookie)['status'],403)
        self.assertEqual(self.request('/catalogo.json')['status'],401)
        self.assertEqual(self.request('/api/progress','PUT',{'lesson':lesson['id'],'completed':True,'csrf':csrf},cookie)['status'],400)

    def test_suspend_invalidates_live_session(self):
        cookie,_=self.login()
        with self.app.connect() as db: user=db.execute("SELECT id FROM users WHERE email='a@example.com'").fetchone()[0]
        r=self.request('/api/admin/student','PUT',{'id':user,'active':False,'courses':['basica'],'csrf':self.csrf},self.admin)
        self.assertEqual(r['status'],200)
        self.assertEqual(self.request('/api/progress',cookie=cookie)['status'],401)
        self.assertEqual(self.request('/api/login','POST',{'email':'a@example.com','password':'senha-local-123456'})['status'],401)

    def test_reset_single_use_and_invalidates_session(self):
        cookie,_=self.login()
        with self.app.connect() as db: user=db.execute("SELECT id FROM users WHERE email='a@example.com'").fetchone()[0]
        r=self.request('/api/admin/reset-link','POST',{'id':user,'csrf':self.csrf},self.admin)
        token=r['body']['link'].split('#')[1]
        payload={'token':token,'password':'changed-password-123456'}
        self.assertEqual(self.request('/api/reset-password','POST',payload)['status'],200)
        self.assertEqual(self.request('/api/reset-password','POST',payload)['status'],400)
        self.assertEqual(self.request('/api/progress',cookie=cookie)['status'],401)
        self.assertEqual(self.request('/api/login','POST',{'email':'a@example.com','password':'senha-local-123456'})['status'],401)
        self.assertEqual(self.request('/api/login','POST',{'email':'a@example.com','password':'changed-password-123456'})['status'],200)

    def test_recovery_does_not_expose_account_existence(self):
        a=self.request('/api/forgot-password','POST',{'email':'a@example.com'})
        b=self.request('/api/forgot-password','POST',{'email':'unknown@example.com'})
        self.assertEqual(a['body'],b['body'])
        self.assertNotIn('token',a['body'])

    def test_invite_validation_and_origin(self):
        for courses in ([],['not-a-course'],None):
            r=self.request('/api/admin/invite','POST',{'name':'A','email':'n@example.com','courses':courses,'csrf':self.csrf},self.admin)
            self.assertEqual(r['status'],400)
        token=self.invite()
        self.assertEqual(self.request('/api/activate','POST',{'token':token,'password':'good-password-12345'},origin='https://other.example')['status'],403)

    def test_private_source_paths_and_admin_page(self):
        for path in ('/server/app.py','/.env','/data/formacao.sqlite3','/docs/IMPLANTACAO.md','/demo.html'):
            self.assertEqual(self.request(path)['status'],404)
        self.assertEqual(self.request('/admin.html')['status'],303)
        self.assertEqual(self.request('/admin.html',cookie=self.admin)['status'],200)

    def test_normalized_paths_cannot_bypass_auth(self):
        self.assertEqual(self.request('/assets/../catalogo.json')['status'],401)
        self.assertEqual(self.request('/assets/%2e%2e/admin.html')['status'],303)
        self.assertEqual(self.request('/assets/../materiais/aulas/ia-generativa-vip.md')['status'],401)

    def test_smtp_invitation_and_recovery(self):
        with patch.dict('os.environ',{'SMTP_HOST':'smtp.example'}), patch.object(self.app,'mail',return_value=True) as sender:
            token=self.invite()
            self.assertEqual(sender.call_args.args[0],'new@example.com')
            self.assertIn('#'+token,sender.call_args.args[1])
            with patch('server.access.recovery_async') as queue:
                self.request('/api/forgot-password','POST',{'email':'a@example.com'})
                queue.assert_called_once_with(self.app,'a@example.com')

    def test_backup_restore_keeps_accounts_and_progress(self):
        import sqlite3
        target=self.app.database.parent/'backup.sqlite3'
        with self.app.connect() as db, sqlite3.connect(target) as copy: db.backup(copy)
        restored=test_app.Application(target,'https://formacao.example')
        with restored.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],1)

    def test_administrator_requires_second_factor_and_rejects_replay(self):
        from server.security import totp
        payload={'email':'teacher@example.com','password':'teacher-pass-123456'}
        self.assertEqual(self.request('/api/login','POST',payload)['status'],401)
        payload['otp']=totp(self.app.admin_totp_secret)
        self.assertEqual(self.request('/api/login','POST',payload)['status'],401)
        with self.app.connect() as db: db.execute('DELETE FROM otp_used')
        self.assertEqual(self.request('/api/login','POST',payload)['status'],200)
        self.assertEqual(self.request('/api/login','POST',payload)['status'],401)

    def test_administrator_login_closed_without_configured_factor(self):
        self.app.admin_totp_secret=''
        self.assertEqual(self.request('/api/login','POST',{'email':'teacher@example.com','password':'teacher-pass-123456','otp':'123456'})['status'],401)

    def test_idle_sessions_are_invalidated_server_side(self):
        cookie,_=self.login()
        with self.app.connect() as db: db.execute('UPDATE sessions SET last_seen=?',(int(time.time())-1801,))
        self.assertEqual(self.request('/api/progress',cookie=cookie)['status'],401)
        self.assertEqual(self.request('/api/admin/students',cookie=self.admin)['status'],401)

    def test_student_cannot_change_own_role(self):
        cookie,csrf=self.login()
        self.assertEqual(self.request('/api/admin/student','PUT',{'id':1,'active':True,'courses':['basica'],'role':'admin','csrf':csrf},cookie)['status'],403)
        with self.app.connect() as db: self.assertEqual(db.execute('SELECT role FROM users WHERE id=1').fetchone()[0],'student')

    def test_recovery_schedules_unknown_and_known_accounts_identically(self):
        with patch('server.access.recovery_async') as queue:
            a=self.request('/api/forgot-password','POST',{'email':'a@example.com'})
            b=self.request('/api/forgot-password','POST',{'email':'unknown@example.com'})
            self.assertEqual(a['body'],b['body'])
            self.assertEqual(queue.call_count,2)
            self.assertEqual([c.args[1] for c in queue.call_args_list],['a@example.com','unknown@example.com'])

    def test_malformed_unicode_csrf_and_null_paths_fail_closed(self):
        cookie,_=self.login()
        self.assertEqual(self.request('/api/logout','POST',{'csrf':'á'},cookie)['status'],403)
        self.assertEqual(self.request('/api/admin/invite','POST',{'csrf':'á'},self.admin)['status'],403)
        self.assertEqual(self.request('/assets/a\x00.png')['status'],400)

    def test_xss_name_is_returned_as_json_not_executed_markup(self):
        with self.app.connect() as db: db.execute("UPDATE users SET name=? WHERE id=1",('<img src=x onerror=alert(1)>',))
        cookie,_=self.login()
        r=self.request('/api/session',cookie=cookie)
        self.assertTrue(r['headers']['Content-Type'].startswith('application/json'))
        self.assertIn("script-src 'self'",r['headers']['Content-Security-Policy'])
        self.assertEqual(r['headers']['Cache-Control'],'no-store')

    def test_totp_rfc6238_vector(self):
        import base64
        from server.security import totp
        secret=base64.b32encode(b'12345678901234567890').decode()
        self.assertEqual(totp(secret,1),'287082')
