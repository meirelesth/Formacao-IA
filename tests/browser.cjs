const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const browser=await chromium.launch();fs.mkdirSync('browser-results',{recursive:true});
 const widths=[320,360,390,430,768,1440]; let checks=0;
 for(const width of widths){
  const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const path of ['entrar.html','ativar.html','redefinir.html','index.html']){
   await page.goto('http://127.0.0.1:8080/'+path);await page.waitForLoadState('networkidle');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Horizontal overflow ${path} ${width}`);checks++;
   if(path==='entrar.html'){
    const input=await page.locator('#email').boundingBox();assert(input.width>=240&&input.x>=0&&input.x+input.width<=width);
    await page.locator('#show-password').click();assert.equal(await page.locator('#password').getAttribute('type'),'text');
    await page.locator('#forgot').click();assert(await page.locator('#forgot-form').isVisible());
    await page.locator('#back-login').click();assert(await page.locator('#login-form').isVisible());
    await page.screenshot({path:`browser-results/login-${width}.png`,fullPage:true});
   }
   if(path==='index.html'){
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
  assert.deepEqual(errors,[],`Browser errors at ${width}`);await context.close();
 }
 await browser.close();console.log(`${checks} browser checks passed across ${widths.join(', ')}px`);
})().catch(e=>{console.error(e);process.exit(1)});
