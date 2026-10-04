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
        self.assertFalse(any(s['title']=='Skill de teste' for s in self.request('/api/skills',cookie=student)['body']['skills']))
        self.assertEqual(sum(s['title']=='Skill de teste' for s in self.request('/api/admin/skills',cookie=student)['body']['skills']),1)
        update={**payload,'id':id,'published':True}
        self.assertEqual(self.request('/api/admin/skills','PUT',update,student)['status'],200)
        other,_=self.login('b@example.com','senha-local-654321')
        self.assertEqual(next(s for s in self.request('/api/skills',cookie=other)['body']['skills'] if s['title']=='Skill de teste')['id'],id)
        self.assertEqual(self.request('/api/skills','PUT',update,other)['status'],403)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'download_url':'javascript:alert(1)'},student)['status'],400)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'download_url':'https://user:secret@example.com/file.zip'},student)['status'],400)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'download_url':''},student)['status'],400)
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'published':False},student)['status'],200)
        self.assertFalse(any(s['title']=='Skill de teste' for s in self.request('/api/skills',cookie=other)['body']['skills']))
        self.assertEqual(self.request('/api/admin/skills','PUT',{**update,'id':9999},student)['status'],404)

    def test_import_download_and_unpublish_persist(self):
        import io, zipfile
        student,token=self.login()
        skills=self.request('/api/skills',cookie=student)['body']['skills']
        self.assertEqual(sum(s['platform']=='catalog' for s in skills),1172)
        packages=[s for s in skills if s['download_url'].startswith('/api/skills/')]
        self.assertEqual(len(packages),126)
        target=next(s for s in packages if s['title']=='Documentos do Word (DOCX)')
        url=target['download_url']
        self.assertEqual(self.request(url)['status'],401)
        download=self.request(url,cookie=student)
        self.assertEqual(download['status'],200)
        archive=zipfile.ZipFile(io.BytesIO(download['body']))
        self.assertIn('docx/SKILL.md',archive.namelist())
        self.assertEqual(self.request('/api/skills/bundle/download',cookie=student)['status'],403)
        with self.app.connect() as db: db.execute("UPDATE users SET role='admin' WHERE email='a@example.com'")
        self.assertEqual(self.request('/api/admin/skills','PUT',{**target,'csrf':token,'published':False},student)['status'],200)
        self.assertEqual(self.request(url,cookie=student)['status'],404)
        self.assertFalse(any(s['id']==target['id'] for s in self.request('/api/skills',cookie=student)['body']['skills']))
        self.assertEqual(self.request('/api/skills/bundle/download',cookie=student)['status'],200)

    def test_company_skills_removed_from_existing_database_and_archives(self):
        import base64, io, json, re, zipfile
        from pathlib import Path
        source=json.loads((Path(__file__).parent/'skills-catalog.json').read_text())
        packages=json.loads((Path(__file__).parent/'skills-packages.json').read_text())
        pattern=re.compile(r'jacar[eé]|jhc',re.I)
        self.assertEqual(len(source['excluded_skill_ids']),15)
        self.assertEqual(len(source['skills']),1298)
        self.assertFalse(pattern.search(json.dumps(source['skills'],ensure_ascii=False)))
        for package in packages.values():
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(package['base64']))) as archive:
                for name in archive.namelist():
                    if not name.endswith('/'):
                        self.assertFalse(pattern.search(name),name)
                        self.assertFalse(pattern.search(archive.read(name).decode('utf8',errors='ignore')),name)
        student,_=self.login()
        self.request('/api/skills',cookie=student)
        # Simulate a production DB that already imported the catalog but retained older company rows.
        with self.app.connect() as db:
            for id in source['excluded_skill_ids']:
                db.execute('INSERT INTO skills(id,title,category,description,version,platform,download_url,source_url,install_command,published,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    [id,'Retirada','Dados','Conteúdo anterior','1.0','claude-code',f'/api/skills/{id}/download','','',1,1])
        with self.app.connect() as db:db.execute("UPDATE users SET role='admin' WHERE email='a@example.com'")
        visible=self.request('/api/admin/skills',cookie=student)['body']['skills']
        self.assertEqual(len(visible),1298)
        for id in source['excluded_skill_ids']:
            self.assertEqual(self.request(f'/api/skills/{id}/download',cookie=student)['status'],404)

    def test_ptbr_packages_and_existing_catalog_migration(self):
        import base64, io, json, re, zipfile
        from pathlib import Path
        source=json.loads((Path(__file__).parent/'skills-catalog.json').read_text())
        packages=json.loads((Path(__file__).parent/'skills-packages.json').read_text())
        self.assertEqual(source['locale'],'pt-BR')
        for key,package in packages.items():
            if key=='bundle':continue
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(package['base64']))) as archive:
                skills=[n for n in archive.namelist() if n.endswith('SKILL.md')]
                self.assertTrue(skills)
                for name in skills:
                    text=archive.read(name).decode('utf8')
                    self.assertTrue(text.startswith('---\n'))
                    self.assertIn('## Idioma obrigatório: português do Brasil (PT-BR)',text)
                    self.assertIn('Responda sempre em português do Brasil.',text)
                    interface=archive.read(name.rsplit('/',1)[0]+'/agents/openai.yaml').decode('utf8')
                    self.assertIn('português do Brasil',interface)
                    self.assertIn('display_name:',interface)
        student,token=self.login()
        self.request('/api/skills',cookie=student)
        target=next(s for s in source['skills'] if s['title']=='Agentes de IA no n8n')
        with self.app.connect() as db:
            db.execute('UPDATE skills SET title=?,description=?,published=0 WHERE id=?',['n8n-n8n-agents','Design n8n AI agents the right way.',target['id']])
            db.execute('DELETE FROM skills_imports WHERE version=?',(source['import_version'],))
            db.execute("UPDATE users SET role='admin' WHERE email='a@example.com'")
        visible=self.request('/api/admin/skills',cookie=student)['body']['skills']
        migrated=next(s for s in visible if s['id']==target['id'])
        self.assertEqual(migrated['title'],target['title'])
        self.assertEqual(migrated['description'],target['description'])
        self.assertFalse(migrated['published'])
        with self.app.connect() as db:db.execute('UPDATE skills SET title=? WHERE id=?',['Minha edição em português',target['id']])
        visible=self.request('/api/admin/skills',cookie=student)['body']['skills']
        self.assertEqual(next(s for s in visible if s['id']==target['id'])['title'],'Minha edição em português')
