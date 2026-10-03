/* Optional visitor questionnaire, stored in the website database; email is separate. */
(() => {
 'use strict';
 const dismissedKey='lf-profile-dismissed-v1',answeredKey='lf-profile-answered-v1';
 const read=(store,key)=>{try{return store.getItem(key);}catch{return null;}};
 const write=(store,key,value)=>{try{store.setItem(key,value);}catch{/* Browsing remains available without storage. */}};
 const options=(name,type,values)=>values.map(([value,label])=>'<label class="lf-profile-choice"><input type="'+type+'" name="'+name+'" value="'+value+'"><span>'+label+'</span></label>').join('');
 const dialog=document.createElement('dialog');dialog.className='lf-profile';dialog.id='visitor-profile';dialog.setAttribute('aria-labelledby','lf-profile-title');dialog.setAttribute('aria-describedby','lf-profile-intro');
 dialog.innerHTML='<header class="lf-profile-header"><p class="lf-profile-kicker">LUÍS FERNANDO • FORMAÇÃO EM IA</p><button type="button" class="lf-profile-close" aria-label="Fechar formulário">×</button></header><div class="lf-profile-content"><h2 id="lf-profile-title">O que você quer descobrir com IA?</h2><p id="lf-profile-intro" class="lf-profile-intro">Quatro perguntas rápidas para conhecer seus interesses. Responder é opcional: você pode fechar e explorar o site.</p><form id="lf-profile-form"><p class="lf-profile-progress" aria-live="polite"></p><section class="lf-profile-step" data-step="0"><fieldset><legend>1. Por que você quer aprender IA?</legend><div class="lf-profile-options">'+options('motivation','radio',[['curiosidade','Curiosidade ou hobby'],['trabalho','Facilitar meu trabalho'],['negocio','Criar uma solução ou melhorar meu negócio']])+'</div></fieldset><fieldset><legend>2. O que você faz hoje?</legend><div class="lf-profile-options">'+options('occupation','radio',[['empresa','Trabalho em uma empresa'],['empreendedor','Sou empreendedor'],['autonomo','Sou autônomo'],['estudante','Estudo'],['outro','Outra situação']])+'</div></fieldset><label class="lf-profile-label" for="lf-profession">Sua profissão ou área <span class="lf-profile-note">(opcional)</span></label><input id="lf-profession" name="profession" type="text" maxlength="120" placeholder="Ex.: engenharia, vendas, estudante"></section><section class="lf-profile-step" data-step="1" hidden><fieldset><legend>3. Qual IA você quer aprender?</legend><div class="lf-profile-options">'+options('ai','radio',[['chatgpt','ChatGPT'],['claude','Claude'],['gemini','Gemini'],['outra','Outra IA'],['orientacao','Ainda não sei, quero orientação']])+'</div></fieldset><fieldset><legend>4. O que você mais gostaria de fazer?</legend><p class="lf-profile-note">Pode marcar mais de uma opção.</p><div class="lf-profile-options">'+options('interests','checkbox',[['dia_a_dia','Usar IA no dia a dia'],['conteudo','Criar conteúdos'],['indicadores','Analisar dados e indicadores'],['automacao','Automatizar tarefas'],['sistemas','Criar sites, sistemas ou agentes'],['possibilidades','Descobrir as possibilidades']])+'</div></fieldset><label class="lf-profile-label" for="lf-dream">Tem alguma ideia ou sonho que gostaria de realizar com IA? <span class="lf-profile-note">(opcional)</span></label><textarea id="lf-dream" name="dream" maxlength="600" placeholder="Pode ser por diversão, para o trabalho ou para seu negócio."></textarea><p class="lf-profile-note">Ao enviar, você compartilha suas respostas com Luís Fernando para planejar as formações. Não é uma matrícula. Não inclua informações confidenciais.</p></section><div class="lf-profile-honey" aria-hidden="true"><label>Site<input name="website" type="text" tabindex="-1" autocomplete="off"></label></div><p class="lf-profile-status" role="alert"></p><div class="lf-profile-actions"><button type="button" class="lf-profile-secondary" data-back hidden>Voltar</button><button type="button" class="lf-profile-secondary" data-skip>Prefiro explorar o site</button><button type="button" class="lf-profile-primary" data-next>Continuar →</button><button type="submit" class="lf-profile-primary" data-send hidden>Enviar respostas →</button></div></form><a class="lf-profile-expert" href="https://wa.me/5598981432271?text=Ol%C3%A1%2C%20Lu%C3%ADs%20Fernando.%20Prefiro%20conversar%20diretamente%20sobre%20a%20forma%C3%A7%C3%A3o%20em%20IA." target="_blank" rel="noopener"><span>Não quero responder o formulário</span><strong>Falar com o especialista Luís Fernando →</strong></a><section class="lf-profile-success" hidden><p>Obrigado! Suas respostas foram registradas e vão ajudar a preparar as formações.</p><button type="button" class="lf-profile-primary" data-done>Explorar o site</button></section></div>';
 document.body.append(dialog);
 const form=dialog.querySelector('form'),status=dialog.querySelector('[role=alert]'),steps=[...dialog.querySelectorAll('[data-step]')],next=dialog.querySelector('[data-next]'),send=dialog.querySelector('[data-send]'),back=dialog.querySelector('[data-back]');
 let enabled=false,step=0,busy=false,previousFocus=null,requestId=null;
 const setStep=n=>{step=n;steps.forEach((s,i)=>s.hidden=i!==n);next.hidden=n===1;send.hidden=n===0;back.hidden=n===0;dialog.querySelector('.lf-profile-progress').textContent='Etapa '+(n+1)+' de 2';status.textContent='';dialog.scrollTop=0;};
 setStep(0);
 const close=()=>{dialog.close();document.body.classList.remove('lf-profile-open');write(sessionStorage,dismissedKey,'1');if(previousFocus?.isConnected)previousFocus.focus();};
 const open=()=>{if(!enabled||dialog.open)return;previousFocus=document.activeElement;dialog.showModal();document.body.classList.add('lf-profile-open');dialog.querySelector('.lf-profile-close').focus();};
 dialog.querySelector('.lf-profile-expert').addEventListener('click',close);
 dialog.querySelector('.lf-profile-close').onclick=close;dialog.querySelector('[data-skip]').onclick=close;dialog.querySelector('[data-done]').onclick=close;
 dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});
 dialog.addEventListener('close',()=>document.body.classList.remove('lf-profile-open'));
 next.onclick=()=>{if(!form.querySelector('[name=motivation]:checked')||!form.querySelector('[name=occupation]:checked')){status.textContent='Marque seu motivo e o que você faz hoje para continuar. Você também pode fechar o formulário.';return;}setStep(1);steps[1].querySelector('input').focus();};
 back.onclick=()=>{setStep(0);steps[0].querySelector('input').focus();};
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;
  const f=new FormData(form);if(!f.get('ai')||!f.getAll('interests').length){status.textContent='Escolha a IA e pelo menos um interesse. A opção “Ainda não sei” também vale.';return;}
  const bytes=new Uint8Array(16);if(!requestId){crypto.getRandomValues(bytes);requestId=[...bytes].map(b=>b.toString(16).padStart(2,'0')).join('');}
  busy=true;send.disabled=true;send.textContent='Enviando…';status.textContent='';
  try{
   const response=await fetch('perfil-visitante.php',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:requestId,motivation:f.get('motivation'),occupation:f.get('occupation'),profession:f.get('profession').trim(),ai:f.get('ai'),interests:f.getAll('interests'),dream:f.get('dream').trim(),website:f.get('website')})});
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
