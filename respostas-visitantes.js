(() => {
 'use strict';
 const labels={curiosidade:'Curiosidade ou hobby',trabalho:'Facilitar meu trabalho',negocio:'Criar uma solução ou melhorar meu negócio',empresa:'Trabalho em uma empresa',empreendedor:'Empreendedor',autonomo:'Autônomo',estudante:'Estudante',outro:'Outra situação',chatgpt:'ChatGPT',claude:'Claude',gemini:'Gemini',outra:'Outra IA',orientacao:'Quero orientação',dia_a_dia:'Usar IA no dia a dia',conteudo:'Criar conteúdos',indicadores:'Analisar dados e indicadores',automacao:'Automatizar tarefas',sistemas:'Criar sites, sistemas ou agentes',possibilidades:'Descobrir possibilidades'};
 const status=document.getElementById('responses-status'),list=document.getElementById('responses-list');
 fetch('perfil-visitante.php?responses=1',{credentials:'same-origin',headers:{Accept:'application/json'}}).then(async r=>{
  let j;try{j=await r.json();}catch{throw new Error('A consulta aguarda a configuração do servidor.');}
  if(!r.ok)throw new Error(j.error||'Não foi possível consultar.');
  for(const response of j.responses){
   const card=document.createElement('article');card.className='response-card';
   const title=document.createElement('h2');title.textContent=new Date(response.created*1000).toLocaleString('pt-BR',{timeZone:'America/Fortaleza'});card.append(title);
   const a=response.answers,dl=document.createElement('dl');
   for(const [key,value] of [['Motivo',labels[a.motivation]],['Situação profissional',labels[a.occupation]],['Profissão ou área',a.profession||'Não informada'],['IA desejada',labels[a.ai]],['Interesses',a.interests.map(i=>labels[i]).join(', ')],['Ideia ou sonho',a.dream||'Não informado']]){
    const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value;dl.append(dt,dd);
   }
   card.append(dl);list.append(card);
  }
  status.textContent=j.responses.length?j.responses.length+' respostas exibidas.':'Ainda não há respostas registradas.';
 }).catch(e=>{status.textContent=e.message;});
})();
