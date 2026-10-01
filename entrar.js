'use strict';
const preview=document.documentElement.dataset.preview==='true';
document.getElementById(preview?'login-preview':'login-form').hidden=false;
document.getElementById('login-form').addEventListener('submit',async e=>{
  e.preventDefault();const form=e.currentTarget,button=form.querySelector('button'),error=document.getElementById('login-error');button.disabled=true;error.textContent='';
  try{const fields=new FormData(form);const response=await fetch('api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:fields.get('email'),password:fields.get('password')})});const data=await response.json();if(!response.ok)throw new Error(data.error||'Não foi possível entrar.');location.assign('aluno.html');}catch(err){error.textContent=err.message;}finally{button.disabled=false;}
});
