/* Optional visitor questionnaire, stored in the website database; email is separate. */
(() => {
 'use strict';
 const dismissedKey='lf-profile-dismissed-v1',answeredKey='lf-profile-answered-v1';
 const read=(store,key)=>{try{return store.getItem(key);}catch{return null;}};
 const write=(store,key,value)=>{try{store.setItem(key,value);}catch{/* Browsing remains available without storage. */}};
 const options=(name,type,values)=>values.map(([value,label])=>'<label class="lf-profile-choice"><input type="'+type+'" name="'+name+'" value="'+value+'"><span>'+label+'</span></label>').join('');
 const dialog=document.createElement('dialog');dialog.className='lf-profile';dialog.id='visitor-profile';dialog.setAttribute('aria-labelledby','lf-profile-title');dialog.setAttribute('aria-describedby','lf-profile-intro');
 dialog.innerHTML="<header class=\"lf-profile-header\"><p class=\"lf-profile-kicker\">LUÍS FERNANDO • FORMAÇÃO EM IA</p><button type=\"button\" class=\"lf-profile-close\" aria-label=\"Fechar formulário\">×</button></header><div class=\"lf-profile-content\"><h2 id=\"lf-profile-title\">Como você quer usar IA?</h2><p id=\"lf-profile-intro\" class=\"lf-profile-intro\">Três perguntas rápidas. Responder é opcional.</p><form id=\"lf-profile-form\"><fieldset><legend>1. Por que quer aprender?</legend><div class=\"lf-profile-options\"><label class=\"lf-profile-choice\"><input type=\"radio\" name=\"motivation\" value=\"curiosidade\"><span>Curiosidade ou hobby</span></label><label class=\"lf-profile-choice\"><input type=\"radio\" name=\"motivation\" value=\"trabalho\"><span>Facilitar meu trabalho</span></label><label class=\"lf-profile-choice\"><input type=\"radio\" name=\"motivation\" value=\"negocio\"><span>Melhorar meu negócio</span></label></div></fieldset><fieldset><legend>2. Qual IA quer aprender?</legend><div class=\"lf-profile-options\"><label class=\"lf-profile-choice\"><input type=\"radio\" name=\"ai\" value=\"chatgpt\"><span>ChatGPT</span></label><label class=\"lf-profile-choice\"><input type=\"radio\" name=\"ai\" value=\"claude\"><span>Claude</span></label><label class=\"lf-profile-choice\"><input type=\"radio\" name=\"ai\" value=\"orientacao\"><span>Ainda não sei, quero orientação</span></label></div></fieldset><fieldset><legend>3. O que quer aprender a fazer?</legend><p class=\"lf-profile-note\">Pode escolher mais de uma opção.</p><div class=\"lf-profile-options\"><label class=\"lf-profile-choice\"><input type=\"checkbox\" name=\"interests\" value=\"dia_a_dia\"><span>Usar IA no dia a dia</span></label><label class=\"lf-profile-choice\"><input type=\"checkbox\" name=\"interests\" value=\"conteudo\"><span>Criar conteúdos</span></label><label class=\"lf-profile-choice\"><input type=\"checkbox\" name=\"interests\" value=\"indicadores\"><span>Indicadores e dados</span></label><label class=\"lf-profile-choice\"><input type=\"checkbox\" name=\"interests\" value=\"automacao\"><span>Automatizar tarefas</span></label><label class=\"lf-profile-choice\"><input type=\"checkbox\" name=\"interests\" value=\"sistemas\"><span>Sites, sistemas ou agentes</span></label><label class=\"lf-profile-choice\"><input type=\"checkbox\" name=\"interests\" value=\"possibilidades\"><span>Descobrir possibilidades</span></label></div></fieldset><details class=\"lf-profile-more\"><summary>Quer contar mais? (opcional)</summary><label class=\"lf-profile-label\" for=\"lf-profession\">Sua profissão ou área</label><input id=\"lf-profession\" name=\"profession\" type=\"text\" maxlength=\"120\" placeholder=\"Ex.: técnico de informática\"><label class=\"lf-profile-label\" for=\"lf-dream\">Uma ideia ou sonho com IA</label><textarea id=\"lf-dream\" name=\"dream\" maxlength=\"600\" placeholder=\"Por diversão, para o trabalho ou negócio.\"></textarea></details><div class=\"lf-profile-honey\" aria-hidden=\"true\"><label>Site<input name=\"website\" type=\"text\" tabindex=\"-1\" autocomplete=\"off\"></label></div><p class=\"lf-profile-note\">As respostas ajudam Luís Fernando a planejar as aulas. Não é uma matrícula.</p><p class=\"lf-profile-status\" role=\"alert\"></p><div class=\"lf-profile-actions\"><button type=\"button\" class=\"lf-profile-secondary\" data-skip>Prefiro explorar o site</button><button type=\"submit\" class=\"lf-profile-primary\" data-send>Enviar respostas →</button></div></form><a class=\"lf-profile-expert\" href=\"https://wa.me/5598981432271?text=Ol%C3%A1%2C%20Lu%C3%ADs%20Fernando.%20Prefiro%20conversar%20diretamente%20sobre%20a%20forma%C3%A7%C3%A3o%20em%20IA.\" target=\"_blank\" rel=\"noopener\"><span>Não quero responder o formulário</span><strong>Falar com o especialista Luís Fernando →</strong></a><section class=\"lf-profile-success\" hidden><p>Obrigado! Suas respostas foram registradas e vão ajudar a preparar as formações.</p><button type=\"button\" class=\"lf-profile-primary\" data-done>Explorar o site</button></section></div>";
 document.body.append(dialog);
 const form=dialog.querySelector('form'),status=dialog.querySelector('[role=alert]'),send=dialog.querySelector('[data-send]');
 let enabled=false,busy=false,previousFocus=null,requestId=null;
 const close=()=>{dialog.close();document.body.classList.remove('lf-profile-open');write(sessionStorage,dismissedKey,'1');if(previousFocus?.isConnected)previousFocus.focus();};
 const open=()=>{if(!enabled||dialog.open)return;previousFocus=document.activeElement;dialog.showModal();document.body.classList.add('lf-profile-open');dialog.querySelector('.lf-profile-close').focus();};
 dialog.querySelector('.lf-profile-expert').addEventListener('click',close);
 dialog.querySelector('.lf-profile-close').onclick=close;dialog.querySelector('[data-skip]').onclick=close;dialog.querySelector('[data-done]').onclick=close;
 dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});
 dialog.addEventListener('close',()=>document.body.classList.remove('lf-profile-open'));
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;
  const f=new FormData(form);if(!f.get('motivation')||!f.get('ai')||!f.getAll('interests').length){status.textContent='Marque seu motivo, a IA e pelo menos um interesse. A opção “Ainda não sei” também vale.';return;}
  const bytes=new Uint8Array(16);if(!requestId){crypto.getRandomValues(bytes);requestId=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');}
  busy=true;send.disabled=true;send.textContent='Enviando…';status.textContent='';
  try{
   const response=await fetch('perfil-visitante.php',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:requestId,motivation:f.get('motivation'),occupation:'outro',profession:f.get('profession').trim(),ai:f.get('ai'),interests:f.getAll('interests'),dream:f.get('dream').trim(),website:f.get('website')})});
   let result;try{result=await response.json();}catch{throw new Error('Não foi possível enviar agora. Suas respostas continuam aqui; tente novamente.');}
   if(!response.ok||!result.ok)throw new Error(result.error||'Não foi possível enviar. Tente novamente.');
   write(localStorage,answeredKey,'1');form.hidden=true;dialog.querySelector('.lf-profile-success').hidden=false;dialog.querySelector('[data-done]').focus();
  }catch(error){status.textContent=error.message;}
  finally{busy=false;send.disabled=false;send.textContent='Enviar respostas →';}
 });
 async function init(){
  try{
   const response=await fetch('perfil-visitante.php?config=1',{credentials:'same-origin',headers:{Accept:'application/json'}});
   if(!response.ok)return;const config=await response.json();enabled=config.enabled===true;if(!enabled)return;
   const footer=document.querySelector('footer');if(footer){const reopen=document.createElement('button');reopen.type='button';reopen.className='lf-profile-reopen';reopen.textContent='Conte o que você quer aprender com IA';reopen.onclick=open;footer.append(document.createElement('br'),reopen);}
   if(!read(sessionStorage,dismissedKey)&&!read(localStorage,answeredKey))setTimeout(()=>{if(!document.querySelector('dialog[open]'))open();},1200);
  }catch{/* A missing backend never blocks browsing or opens a non-working questionnaire. */}
 }
 init();
})();
