'use strict';
const login=document.getElementById('login-form'),recovery=document.getElementById('forgot-form');
const adminAccess=document.getElementById('admin-access'),otp=document.getElementById('otp');
function updateAccessMode(){
 const admin=adminAccess.open;
 document.getElementById('access-title').textContent=admin?'ACESSO DO ADMINISTRADOR':'ACESSO À PLATAFORMA';
 document.getElementById('access-description').textContent=admin?'Entre com sua conta administrativa e o código do autenticador.':'Entre com seu e-mail e senha de acesso.';
 document.getElementById('login-label').textContent=admin?'Entrar no painel administrativo':'Entrar na plataforma';
 document.getElementById('access-note-title').textContent=admin?'Acesso exclusivo do administrador.':'Acesso para alunos e administrador.';
 otp.required=admin;
}
adminAccess.addEventListener('toggle',updateAccessMode);
updateAccessMode();
async function request(path,data){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let j;try{j=await r.json();}catch{throw new Error('Não foi possível conectar ao serviço de login. Tente novamente; se persistir, verifique a configuração da plataforma.');}if(!r.ok)throw new Error(j.error||'Não foi possível continuar.');return j;}
document.getElementById('show-password').onclick=e=>{const p=document.getElementById('password'),show=p.type==='password';p.type=show?'text':'password';e.target.textContent=show?'Ocultar':'Mostrar';e.target.setAttribute('aria-pressed',show);e.target.setAttribute('aria-label',show?'Ocultar senha':'Mostrar senha');};
document.getElementById('forgot').onclick=()=>{login.hidden=true;recovery.hidden=false;document.getElementById('recovery-email').value=document.getElementById('email').value;document.getElementById('recovery-email').focus();};
document.getElementById('back-login').onclick=()=>{login.hidden=false;recovery.hidden=true;};
login.onsubmit=async e=>{e.preventDefault();const b=login.querySelector('[type=submit]'),error=document.getElementById('login-error');b.disabled=true;error.textContent='';try{const f=new FormData(login),j=await request('api/login',{email:f.get('email'),password:f.get('password'),otp:f.get('otp')});const role=j.user?.role;if(role!=='admin'&&role!=='student')throw new Error('O serviço de login não informou um perfil válido.');if(adminAccess.open&&role!=='admin')throw new Error('Esta conta está cadastrada como aluno. O acesso administrativo precisa ser verificado.');location.assign(role==='admin'?'admin.html':'aluno.html');}catch(err){error.textContent=err.message;}finally{b.disabled=false;}};
recovery.onsubmit=async e=>{e.preventDefault();const b=recovery.querySelector('[type=submit]'),m=document.getElementById('recovery-message');b.disabled=true;m.textContent='';try{m.textContent=(await request('api/forgot-password',{email:new FormData(recovery).get('email')})).message;}catch(err){m.textContent=err.message;}finally{b.disabled=false;}};
