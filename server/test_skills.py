import unittest, time
from server import test_app as testing
class SkillsTests(unittest.TestCase):
    setUp=testing.AuthenticationTests.setUp
    tearDown=testing.AuthenticationTests.tearDown
    request=testing.AuthenticationTests.request
    login=testing.AuthenticationTests.login
    def test_skills_lifecycle_authorization(self):
        self.assertEqual(self.request('/api/skills')['status'],401)
        student,token=self.login()
        self.assertEqual(self.request('/api/admin/skills',cookie=student)['status'],403)
        self.assertEqual(self.request('/api/admin/skills','POST',{'csrf':token},student)['status'],403)
        with self.app.connect() as db: db.execute("UPDATE users SET role='admin' WHERE email='a@example.com'")
        payload=dict(title='Skill de teste',category='Dados',description='Pacote de teste',version='1.0',platform='claude',download_url='https://example.com/skill.zip',source_url='https://example.com/docs',install_command='',published=False,csrf=token)
        missing={**payload,'csrf':'wrong'}
        self.assertEqual(self.request('/api/admin/skills','POST',missing,student)['status'],403)
        created=self.request('/api/admin/skills','POST',payload,student)
        self.assertEqual(created['status'],201)
        id=created['body']['id']
        self.assertEqual(self.request('/api/skills',cookie=student)['body']['skills'],[])
        self.assertEqual(len(self.request('/api/admin/skills',cookie=student)['body']['skills']),1)
        update={**payload,'id':id,'published':True}
        self.assertEqual(self.request('/api/admin/skills','PUT',update,student)['status'],200)
        other,_=self.login('b@example.com','senha-local-654321')
        self.assertEqual(self.request('/api/skills',cookie=other)['body']['skills'][0]['id'],id)
        self.assertEqual(self.request('/api/skills','PUT',update,other)['status'],403)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'download_url':'javascript:alert(1)'},student)['status'],400)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'download_url':'https://user:secret@example.com/file.zip'},student)['status'],400)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'download_url':''},student)['status'],400)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'published':False},student)['status'],200)
        self.assertEqual(self.request('/api/skills',cookie=other)['body']['skills'],[])
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'id':9999},student)['status'],404)
