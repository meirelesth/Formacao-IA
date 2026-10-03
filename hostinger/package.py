"""Builds an upload package without secrets, server code or private lessons in public_html."""
from pathlib import Path
import shutil, argparse, json, zipfile
ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=True)
public=output/'public_html';private=output/'formacao-private'
public.mkdir(exist_ok=True);private.mkdir(exist_ok=True)
names=['checkout.html','checkout.css','checkout.js','perfil-visitante-lib.php','respostas-visitantes.html','respostas-visitantes.css','respostas-visitantes.js','perfil-visitante.php','perfil-visitante.css','perfil-visitante.js','index.html','entrar.html','ativar.html','redefinir.html','aluno.html','admin.html','planos.html','styles.css','portfolio.css','planos.css','login.css','aluno.css','certificado.css','app.js','aluno.js','entrar.js','acesso.js','admin.js','certificado.js','favicon.ico']
for name in names:shutil.copy2(ROOT/name,public/name)
shutil.copytree(ROOT/'assets',public/'assets',dirs_exist_ok=True)
(public/'materiais').mkdir(exist_ok=True);shutil.copy2(ROOT/'materiais/Portfolio_Formacao_IA_VIP.pdf',public/'materiais/Portfolio_Formacao_IA_VIP.pdf')
for name in ['lf-router.php','.htaccess']:shutil.copy2(ROOT/'hostinger/public'/name,public/name)
shutil.copytree(ROOT/'hostinger/app',private/'app',dirs_exist_ok=True)
shutil.copytree(ROOT/'materiais',private/'materiais',dirs_exist_ok=True)
(private/'materiais/Portfolio_Formacao_IA_VIP.pdf').unlink(missing_ok=True)
shutil.copy2(ROOT/'catalogo.json',private/'catalogo.json')
for name in ['skills-catalog.json','skills-packages.json','CENTRAL-LICENSE.txt']:shutil.copy2(ROOT/'server'/name,private/name)
for name in ['schema.sql','config.example.php','cron.php','composer.json']:shutil.copy2(ROOT/'hostinger'/name,private/name)
if (ROOT/'hostinger/composer.lock').exists():shutil.copy2(ROOT/'hostinger/composer.lock',private/'composer.lock')
if (ROOT/'hostinger/vendor').exists():shutil.copytree(ROOT/'hostinger/vendor',private/'vendor',dirs_exist_ok=True)
shutil.copy2(ROOT/'docs/HOSTINGER.md',output/'LEIA-ANTES-DE-INSTALAR.md')
for name in ['config.php','.env','.installed']:assert not(private/name).exists(),f'Unexpected secret/config: {name}'
assert not(public/'catalogo.json').exists();assert not(public/'server').exists();assert not(public/'materiais/aulas').exists()
zip_path=output.parent/'Formacao-IA-Hostinger.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for f in sorted(output.rglob('*')):
  if f.is_file():z.write(f,f.relative_to(output))
print(json.dumps({'zip':str(zip_path),'size':zip_path.stat().st_size,'files':len(list(output.rglob('*')))}))


