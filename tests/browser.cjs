const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const browser=await chromium.launch();fs.mkdirSync('browser-results',{recursive:true});
 const widths=[320,360,390,430,600,768,820,1024,1440]; let checks=0;
 for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:width>=820?600:900}}),page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const path of ['entrar.html','ativar.html','redefinir.html','index.html','planos.html','checkout.html?curso=basica','checkout.html?curso=avancada']){
   await page.goto('http://127.0.0.1:8080/'+path);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Horizontal overflow ${path} ${width}`);checks++;
   if(path.startsWith('checkout.html')){
    await page.locator('#availability').waitFor({state:'visible'});
    assert(await page.locator('h1').isVisible());
    assert(await page.locator('.teacher img').evaluate(el=>el.complete&&el.naturalWidth>0));
    const configResponse=await page.request.get('http://127.0.0.1:8080/api/payments/config');
    const config=configResponse.ok()?await configResponse.json():null;
    const course=path.includes('avancada')?'avancada':'basica';
    const expectedAmount=config?.products?.[course]?.amount??(course==='avancada'?169900:99700);
    assert.equal(await page.locator('#product-price').textContent(),(expectedAmount/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}));
    await page.locator('#buyer-name').fill('Teste matrícula');await page.locator('#buyer-email').fill('checkout@example.com');
    await page.locator('#buyer-cpf').fill('12345678909');await page.locator('#buyer-phone').fill('11999999999');
    await page.locator('[name=accepted]').check();await page.locator('#pay-button').click();
    assert(await page.locator('#checkout-error').textContent().then(t=>t.includes('sendo preparado')));
    await page.screenshot({path:`browser-results/checkout-${path.includes('avancada')?'advanced':'basic'}-${width}.png`,fullPage:true});checks+=4;
   }
   if(path==='entrar.html'){
    const input=await page.locator('#email').boundingBox();assert(input.width>=240&&input.x>=0&&input.x+input.width<=width);
    await page.locator('#show-password').click();assert.equal(await page.locator('#password').getAttribute('type'),'text');
    await page.locator('#forgot').click();assert(await page.locator('#forgot-form').isVisible());
    await page.locator('#back-login').click();assert(await page.locator('#login-form').isVisible());
    await page.screenshot({path:`browser-results/login-${width}.png`,fullPage:true});
   }
   if(path==='planos.html')await page.screenshot({path:`browser-results/plans-${width}.png`,fullPage:true});
   if(path==='index.html'){
    await page.screenshot({path:`browser-results/home-${width}.png`,fullPage:true});
    const button=page.locator('.certificate-copy .certificate-open');await button.click();
    assert(await page.locator('#certificate-dialog').isVisible());
    assert(await page.locator('#certificate-dialog img').evaluate(el=>el.complete&&el.naturalWidth===1600));
    await page.locator('#certificate-zoom').click();assert.equal(await page.locator('#certificate-zoom').getAttribute('aria-pressed'),'true');
    await page.locator('#certificate-zoom').click();
    await page.screenshot({path:`browser-results/certificate-${width}.png`});
    await page.keyboard.press('Escape');assert(!(await page.locator('#certificate-dialog').isVisible()));
    assert(await button.evaluate(el=>el===document.activeElement));checks+=5;
   }
  }
  // Reloads must retain invitation/reset tokens until a successful submission.
  for(const action of ['ativar','redefinir']){
   const token='a'.repeat(64);let received;
   await page.route('**/api/'+(action==='ativar'?'activate':'reset-password'),r=>{received=r.request().postDataJSON();return r.fulfill({json:{ok:true}})});
   await page.goto('http://127.0.0.1:8080/'+action+'.html#'+token);await page.reload();
   await page.locator('#password').fill('123456');await page.locator('#confirm').fill('123456');await page.locator('#access-form [type=submit]').click();
   await page.getByText('Senha salva. Você já pode entrar com seu e-mail.').waitFor();assert.equal(received.token,token);assert.equal(new URL(page.url()).hash,'');checks+=2;
  }
  // Private order status remains available after refresh, without touching PagBank.
  let calls=0;const reference='b'.repeat(32),key='c'.repeat(64);
  await page.route('**/api/payments/status',r=>{calls++;return r.fulfill({json:{course:'basica',amount:99700,state:'WAITING',environment:'production'}})});
  await page.goto('http://127.0.0.1:8080/checkout.html?curso=basica#pedido='+reference+'&chave='+key);
  await page.getByRole('heading',{name:'Aguardando a confirmação'}).waitFor();await page.reload();await page.getByRole('heading',{name:'Aguardando a confirmação'}).waitFor();assert.equal(calls,2);checks+=2;
  await page.route('**/api/session',r=>r.fulfill({json:{authenticated:false}}));await page.goto('http://127.0.0.1:8080/checkout.html?teste=admin');
  await page.getByText('Entre como administrador para acessar o teste de R$ 1,00.').waitFor();assert(await page.locator('#pay-button').isDisabled());checks++;
  assert.deepEqual(errors,[],`Browser errors at ${width}`);await context.close();
 }
 // Skills UI: deterministic fixtures; server authorization is verified by integration tests.
 for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:width>=820?600:900}}),page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let items=[{id:1,title:'Painel de indicadores',category:'Dados',description:'Analise dados com critérios claros.',version:'1.0',platform:'claude',download_url:'https://example.com/skill.zip',source_url:'https://example.com/docs',install_command:'',published:true,updated:1770000000}];
  let role='student';
  await page.route('**/api/session',r=>r.fulfill({json:{authenticated:true,csrf:'fixture',user:{name:'Aluno de teste',role}}}));
  await page.route('**/api/progress',r=>r.fulfill({json:{completed:[]}}));
  await page.route('**/catalogo.json?*',r=>r.fulfill({json:JSON.parse(fs.readFileSync('catalogo.json','utf8'))}));
  await page.route('**/api/skills',r=>r.fulfill({json:{skills:items.filter(s=>s.published)}}));
  await page.route('**/api/admin/students',r=>r.fulfill({json:{students:[{id:1,name:'Aluno '+ 'A'.repeat(110),email:'aluno@example.com',active:1,courses:'["basica"]'}],invitations:[]}}));
  await page.route('**/api/admin/payments/settings',r=>r.fulfill({json:{configured:false,enabled:false,environment:'sandbox'}}));
  await page.route('**/api/admin/payments/orders',r=>r.fulfill({json:{orders:[]}}));
  await page.route('**/api/admin/skills',r=>{if(r.request().method()==='GET')return r.fulfill({json:{skills:items}});const data=r.request().postDataJSON();if(data.id)items=items.map(s=>s.id===data.id?{...s,...data}:s);else items.push({...data,id:2,updated:1770000000});return r.fulfill({json:{ok:true,id:data.id||2}});});
  await page.route('**/aluno.html',r=>r.fulfill({contentType:'text/html',body:fs.readFileSync('aluno.html','utf8')}));
  await page.goto('http://127.0.0.1:8080/aluno.html#skills');
  await page.locator('#skill-search').waitFor();assert.equal(await page.locator('.skill-card').count(),1);
  await page.locator('#skill-search').fill('inexistente');assert.equal(await page.locator('.skill-card').count(),0);
  await page.locator('#skill-search').fill('indicadores');assert.equal(await page.locator('.skill-card').count(),1);
  assert.equal(await page.getByRole('link',{name:'Baixar ZIP para Claude'}).getAttribute('href'),'https://example.com/skill.zip');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`browser-results/skills-student-${width}.png`,fullPage:true});
  for(const view of ['visao','cursos','materiais','progresso','curso/basica','aula/ia-generativa']){
   await page.goto('http://127.0.0.1:8080/aluno.html#'+view);await page.locator('#student-main h1').waitFor();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Student ${view} overflow ${width}`);checks++;
  }
  await page.route('**/respostas-visitantes.html',r=>r.fulfill({contentType:'text/html',body:fs.readFileSync('respostas-visitantes.html','utf8')}));
  for(const extension of ['js','css'])await page.route('**/respostas-visitantes.'+extension,r=>r.fulfill({contentType:extension==='js'?'text/javascript':'text/css',body:fs.readFileSync('respostas-visitantes.'+extension,'utf8')}));
  await page.route('**/perfil-visitante.php?responses=1',r=>r.fulfill({json:{responses:[{created:1770000000,answers:{motivation:'trabalho',occupation:'autonomo',profession:'P'.repeat(120),ai:'claude',interests:['automacao'],dream:'D'.repeat(1000)}}]}}));
  await page.goto('http://127.0.0.1:8080/respostas-visitantes.html');await page.locator('.response-card').waitFor();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));checks++;
  role='admin';await page.route('**/admin.html',r=>r.fulfill({contentType:'text/html',body:fs.readFileSync('admin.html','utf8')}));
  await page.goto('http://127.0.0.1:8080/admin.html');await page.locator('[data-skill-edit]').waitFor();
  await page.locator('[data-skill-edit]').click();assert.equal(await page.locator('[name=title]').inputValue(),'Painel de indicadores');
  await page.locator('[name=title]').fill('Painel atualizado');await page.locator('#skill-form [type=submit]').click();
  await page.getByText('Skill salva. As publicadas já ficam disponíveis aos alunos.').waitFor();
  assert(items.some(s=>s.title==='Painel atualizado'));
  await page.locator('[data-skill-toggle]').click();await page.getByText('Skill retirada da biblioteca.',{exact:true}).waitFor();assert(!items[0].published);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`browser-results/skills-admin-${width}.png`,fullPage:true});
  await page.route('**/api/admin/payments/test',r=>r.fulfill({json:{enabled:true,environment:'production',products:{admin_test:{name:'Teste administrativo de pagamento',amount:100,hours:0,modules:0}}}}));
  await page.goto('http://127.0.0.1:8080/checkout.html?teste=admin');await page.getByText('Teste em produção: será cobrado R$ 1,00 real. Cartão em 1x ou Pix.').waitFor();
  assert.equal(await page.locator('#product-price').textContent(),(1).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}));assert(await page.getByText('Em 1x',{exact:true}).isVisible());assert(await page.locator('.included').isHidden());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:`browser-results/admin-payment-${width}.png`,fullPage:true});checks+=4;
  assert.deepEqual(errors,[]);checks+=10;await context.close();
 }
 await browser.close();console.log(`${checks} browser checks passed across ${widths.join(', ')}px`);
})().catch(e=>{console.error(e);process.exit(1)});
