// Offline browser contract checks: all API calls intercepted, no generation/provider use.
import assert from 'node:assert/strict';
import {readFileSync,mkdirSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const modulePath=process.env.PUPPETEER_MODULE;
const driver=await import(modulePath?pathToFileURL(modulePath).href:'puppeteer');
const puppeteer=driver.puppeteer||driver.default;
const base=process.env.HER_SITE_URL||'http://127.0.0.1:7861';
const chrome=process.env.PORTFOLIO_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const samplePath=process.env.HER_SAMPLE_PATH;
assert.ok(samplePath,'HER_SAMPLE_PATH must point at an approved local MP4 fixture');
const sample=readFileSync(samplePath);
const screenshots=process.env.SCREENSHOT_DIR||'/private/tmp/her-creator-qa';mkdirSync(screenshots,{recursive:true});
const profile=mkdtempSync(path.join(tmpdir(),'her-creator-'));
const browser=await puppeteer.launch({headless:true,executablePath:chrome,userDataDir:profile});
try {
 let requests=0;
 for(const width of [320,375,430,768,1024,1440]){
  const page=await browser.newPage();const errors=[];const payloads=[];let reply='pending';
  page.on('pageerror',e=>errors.push(e.message));
  await page.setRequestInterception(true);
  page.on('request',request=>{
   const url=new URL(request.url());
   if(url.pathname==='/api/generate'){
    requests++;payloads.push(JSON.parse(request.postData()));
    return request.respond({status:200,contentType:'application/json',body:JSON.stringify(reply==='quota'?{error:'Demo limit reached (2 attempts per visitor per day).'}:{job_id:'test-job'})});
   }
   if(url.pathname==='/api/progress/test-job'){
    if(reply==='pending') return request.respond({status:200,contentType:'text/event-stream',body:'event: progress\ndata: {"stage":"research","label":"Researching","index":2,"total":9,"progress_pct":0.25,"status":"running"}\n\n'});
    const result=reply==='success'?{success:true,title:'Approved test video',video_url:'/output/browser-test.mp4'}:reply==='invalid'?{success:true,video_url:'javascript:alert(1)'}:{error:'News generation cancelled.',status:'cancelled'};
    return request.respond({status:200,contentType:'text/event-stream',body:'event: done\ndata: '+JSON.stringify(result)+'\n\n'});
   }
   if(url.pathname==='/output/browser-test.mp4') return request.respond({status:200,contentType:'video/mp4',body:sample});
   if(url.pathname.startsWith('/api/')) return request.respond({status:200,contentType:'application/json',body:'{"status":"running"}'});
   if(request.method()!=='GET') return request.abort();
   return request.continue();
  });
  await page.setViewport({width,height:1000});
  await page.goto(base,{waitUntil:'networkidle2'});
  assert.equal(payloads.length,0,'Generation on load');
  assert.ok(await page.$eval('#stateIdle',e=>!e.classList.contains('d-none')));
  assert.ok(await page.$eval('#btnDownloadMp4',e=>e.hidden&&!e.hasAttribute('href')));
  assert.equal(await page.$eval('.creator-advanced',e=>e.open),false,'Advanced open by default');
  assert.ok(await page.$eval('.app-header a[href="https://klinteng.com/projects/project-her/"]',e=>!!e),'Safe return link');
  await page.click('#btnGenerate');assert.equal(payloads.length,0,'Empty input submitted');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'promptInput');
  await page.type('#promptInput','A supplied account for a browser-only contract check.');
  await page.click('#btnGenerate');
  await page.waitForFunction(()=>document.getElementById('stage-research')?.classList.contains('running')).catch(async error=>{console.log(await page.evaluate(()=>({status:document.getElementById('pipelineStatusText').textContent,feedback:document.getElementById('creatorFeedback').textContent,failure:document.getElementById('failureMessage').textContent})), errors, payloads);throw error;});
  assert.equal(payloads[0].ui_profile,'editorial_studio');
  assert.equal(payloads[0].content_mode,'news');assert.equal(payloads[0].renderer,'remotion');
  assert.equal(payloads[0].visual_preset,'reference_editorial');assert.equal(payloads[0].tts_provider,'replicate');
  assert.ok(await page.$eval('#btnDownloadMp4',e=>e.hidden));
  assert.ok(await page.$eval('#pipelineProgressBar',e=>parseFloat(e.style.width)>0&&parseFloat(e.style.width)<100));
  await page.reload({waitUntil:'networkidle2'});
  await page.focus('.creator-advanced summary');await page.keyboard.press('Enter');
  assert.ok(await page.$eval('.creator-advanced',e=>e.open),'Keyboard disclosure failed');
  await page.select('#creatorFormat','horizontal');
  await page.type('#promptInput','A story');
  const before=payloads.length;await page.click('#btnGenerate');
  assert.equal(payloads.length,before,'Invalid editorial format submitted');
  assert.ok(await page.$eval('#creatorFeedback',e=>!e.hidden&&e.textContent.includes('vertical')));
  await page.select('#creatorFormat','vertical');await page.select('#creatorDuration','30');
  await page.select('#creatorSource','supplied');await page.select('#creatorAssets','ai');reply='success';
  await page.click('#btnGenerate');
  await page.waitForFunction(()=>!document.getElementById('stateCompleted').classList.contains('d-none'));
  assert.equal(payloads.at(-1).ui_profile,'creator');assert.equal(payloads.at(-1).target_duration,30);
  assert.equal(payloads.at(-1).news_source_policy,'supplied');assert.equal(payloads.at(-1).editorial_assets,'ai');
  assert.ok(await page.$eval('#btnDownloadMp4',e=>!e.hidden&&e.href.includes('/output/browser-test.mp4')));
  assert.equal(await page.$eval('#metricResolution',e=>e.textContent),'Resolution not reported');
  assert.equal(await page.$eval('#metricRenderTime',e=>e.textContent),'Processing time not reported');
  assert.equal(await page.$eval('#resultVideoPlayer',v=>v.autoplay),false);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'stateCompleted');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),`Overflow ${width}`);
  await page.reload({waitUntil:'networkidle2'});reply='invalid';
  await page.type('#promptInput','A story');await page.focus('#btnGenerate');await page.keyboard.press('Enter');
  await page.waitForFunction(()=>!document.getElementById('stateFailed').hidden).catch(async error=>{console.log('Invalid artifact failure',await page.evaluate(()=>({status:document.getElementById('pipelineStatusText').textContent,feedback:document.getElementById('creatorFeedback').textContent,failure:document.getElementById('failureMessage').textContent,button:document.getElementById('btnGenerate').disabled,input:document.getElementById('promptInput').value,active:document.activeElement.id,hit:(()=>{const b=document.getElementById('btnGenerate').getBoundingClientRect();return {rect:b.toJSON(),hit:document.elementFromPoint(b.x+b.width/2,b.y+b.height/2)?.outerHTML}})()})),errors,payloads);throw error;});
  assert.ok(await page.$eval('#btnDownloadMp4',e=>e.hidden));
  await page.click('#stateFailed button');reply='quota';await page.click('#btnGenerate');
  await page.waitForFunction(()=>document.getElementById('failureMessage').textContent.includes('limit reached'));
  await page.click('#stateFailed button');reply='cancelled';await page.click('#btnGenerate');
  await page.waitForFunction(()=>document.getElementById('failureTitle').textContent==='Generation cancelled');
  await page.click('#stateFailed button');
  await page.focus('.creator-advanced summary');await page.keyboard.press('Tab');await page.keyboard.down('Shift');await page.keyboard.press('Tab');await page.keyboard.up('Shift');
  assert.ok(await page.$eval('.creator-advanced summary',e=>e.matches(':focus-visible')&&getComputedStyle(e).outlineStyle!=='none'));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),`Idle overflow ${width}`);
  assert.equal(errors.length,0,errors.join(';'));
  if([375,1440].includes(width)) await page.screenshot({path:path.join(screenshots,`creator-${width}.png`),fullPage:true});
  await page.close();
 }
 const reduced=await browser.newPage();await reduced.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
 await reduced.goto(base,{waitUntil:'domcontentloaded'});
 assert.equal(await reduced.$eval('.idle-icon-ring',e=>getComputedStyle(e).animationName),'none');await reduced.close();
 console.log(`PASS: 6 viewport checks; default/custom request contracts, validation, SSE progress, playable result, unsafe output rejection, quota/cancellation, keyboard/focus, reduced motion. ${requests} intercepted fixture submissions; no real jobs.`);
}finally{await browser.close();rmSync(profile,{recursive:true,force:true});}
