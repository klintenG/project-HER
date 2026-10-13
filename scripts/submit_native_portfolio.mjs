// One explicit live studio submission, invoked only by the opted-in smoke tool.
// Its scoped response travels over a captured subprocess pipe, never a log/file.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const input=JSON.parse(readFileSync(0,'utf8'));
assert.equal(input.site,'https://klinteng.com');
assert.equal(typeof input.text,'string');assert.ok(input.text.length<6000);
const {default:puppeteer}=await import(pathToFileURL(process.env.PUPPETEER_MODULE||'/private/tmp/her-browser/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js'));
const browser=await puppeteer.launch({headless:true,executablePath:process.env.PORTFOLIO_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try{
 const page=await browser.newPage();await page.setViewport({width:1440,height:1000});
 const response=await page.goto(input.site+'/projects/project-her/#studio',{waitUntil:'domcontentloaded',timeout:60000});assert.equal(response.status(),200);
 await page.waitForFunction(()=>document.querySelector('#her-status')?.textContent==='Ready to create',{timeout:120000});
 await page.type('#her-input',input.text);
 await page.select('#her-duration',String(input.target_duration));
 await page.$eval('.her-advanced',e=>e.open=true);
 await page.select('#her-source','supplied');
 const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/portfolio/jobs',{timeout:180000});
 await page.click('#her-generate');const created=await pending;
 assert.equal(created.status(),202,'Live studio job creation was rejected; no new submission was attempted.');
 const accepted=await created.json();assert.match(accepted.job_id,/^[a-f0-9]{32}$/);assert.match(accepted.access_token,/^[a-f0-9]{64}$/);
 await page.waitForFunction(id=>JSON.parse(sessionStorage.getItem('project-her-job-v1')||'null')?.jobId===id,{timeout:10000},accepted.job_id);
 assert.ok(page.url().startsWith(input.site+'/projects/project-her/'));
 process.stdout.write(JSON.stringify(accepted));
}finally{await browser.close();}
