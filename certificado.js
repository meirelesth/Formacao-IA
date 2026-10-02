"use strict";
const certificateDialog=document.getElementById('certificate-dialog');
let certificateTrigger;
function closeCertificate(){certificateDialog.close();}
document.querySelectorAll('.certificate-open').forEach(button=>button.addEventListener('click',()=>{certificateTrigger=button;certificateDialog.showModal();document.body.classList.add('certificate-modal-open');document.getElementById('certificate-close').focus();}));
document.getElementById('certificate-close').addEventListener('click',closeCertificate);
certificateDialog.addEventListener('click',event=>{if(event.target===certificateDialog){const r=certificateDialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)closeCertificate();}});
certificateDialog.addEventListener('close',()=>{document.body.classList.remove('certificate-modal-open');document.querySelector('.certificate-view').classList.remove('zoomed');const z=document.getElementById('certificate-zoom');z.setAttribute('aria-pressed','false');z.textContent='Ampliar detalhes +';certificateTrigger?.focus();});
document.getElementById('certificate-zoom').addEventListener('click',event=>{const zoom=document.querySelector('.certificate-view').classList.toggle('zoomed');event.currentTarget.setAttribute('aria-pressed',String(zoom));event.currentTarget.textContent=zoom?'Ajustar à tela −':'Ampliar detalhes +';});
