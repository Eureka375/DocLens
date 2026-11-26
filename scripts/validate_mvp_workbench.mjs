// Run with Node 22+ on Windows with Microsoft Edge installed. All pages are local.
import {spawn} from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const output=path.join(root,'docs/validation/mvp-workbench');
const build=path.join(root,'build/mvp-workbench');
await fs.mkdir(output,{recursive:true}); await fs.mkdir(build,{recursive:true});
const run=await fs.mkdtemp(path.join(build,'run-'));
const downloads=path.join(run,'downloads'); await fs.mkdir(downloads);
const edge=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',[
  '--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
  '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',`--user-data-dir=${run}`,'about:blank'
],{windowsHide:true,stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const checks=[],errors=[],requests=[]; const pending=new Map(); let socket,id=0;
function c(method,params={}) { return new Promise((resolve,reject)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error('Timeout: '+method));},15000);pending.set(n,{resolve,reject,timer});socket.send(JSON.stringify({id:n,method,params}));}); }
async function ev(expression){const r=await c('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;}
async function wait(expression){for(let i=0;i<65;i++){if(await ev(expression))return;await sleep(100);}throw Error('Condition timed out: '+expression);}
async function check(name,expression){const pass=!!await ev(expression);checks.push({name,pass});if(!pass)throw Error('Failed: '+name);}
const click=selector=>ev(`document.querySelector(${JSON.stringify(selector)}).click()`);
const fill=(selector,value)=>ev(`{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('input',{bubbles:true}));}`);
const go=p=>click(`[data-page="${p}"]`);
async function shot(name){const r=await c('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(output,name+'.png'),Buffer.from(r.data,'base64'));}
async function setFile(selector,file){const {root:dom}=await c('DOM.getDocument');const {nodeId}=await c('DOM.querySelector',{nodeId:dom.nodeId,selector});await c('DOM.setFileInputFiles',{nodeId,files:[file]});}
let failure;
try {
  let tab;
  for(let i=0;i<70;i++){try{const [port]=(await fs.readFile(path.join(run,'DevToolsActivePort'),'utf8')).split(/\s+/);tab=(await(await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(t=>t.type==='page');if(tab)break;}catch{} await sleep(150);}
  if(!tab)throw Error('Edge debugging endpoint unavailable');
  socket=new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  socket.addEventListener('message',e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.exception?.description||m.params.exceptionDetails.text);if(m.method==='Log.entryAdded'&&m.params.entry.level==='error')errors.push(m.params.entry.text);if(m.method==='Network.requestWillBeSent'&&/^https?:/.test(m.params.request.url))requests.push(m.params.request.url);});
  for(const name of ['Page','Runtime','Log','Network'])await c(name+'.enable');
  await c('Page.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});
  await c('Page.navigate',{url:pathToFileURL(path.join(root,'examples/mvp-workbench/index.html')).href});
  await wait(`!!document.querySelector('.shell')`);
  for(const [width,height] of [[1280,800],[1440,900],[1920,1080],[720,900]]){
    await c('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
    for(const page of ['project','library','matrix','search','discover','version','notes','settings','tasks']){
      await go(page);
      await check(`${page}: ${width}px no page overflow`,`document.documentElement.scrollWidth<=${width} && document.querySelector('.workspace').getBoundingClientRect().right<=innerWidth+1`);
      if(width===1440&&['matrix','search','discover','project','notes','version'].includes(page))await shot(page+'-1440');
    }
  }
  await c('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  await go('matrix');await click('[data-cell="epochs:c"]');
  await check('matrix cell opens correct evidence',`document.querySelector('.source-title').textContent.includes('对照实验')&&document.querySelector('.quote').textContent.includes('200 epochs')`);
  await click('[data-review="confirmed"]');
  await check('manual confirmation is stored',`prototypeDebug.getState().reviews['c:1']==='confirmed'`);
  await click('[data-action="cite-current"]');
  await check('multi-source citations retained',`prototypeDebug.getState().citations.length===2`);
  await click('[data-action="open-original"]');
  await check('evidence opens original block',`document.querySelector('[data-block="1"]').classList.contains('target')&&document.querySelector('.reading').textContent.includes('200 epochs')`);
  await go('matrix');await click('[data-action="dimension"]');await fill('#dimension-name','推理延迟');await click('[data-action="save-dimension"]');
  await check('custom dimension preserves missing status',`prototypeDebug.getState().dimensions.at(-1).title==='推理延迟'&&prototypeDebug.getState().dimensions.at(-1).status.every(x=>x==='未找到')`);
  await click('[data-cell="epochs:a"]');await click('[data-action="edit-cell"]');await fill('#edited-value','50 epochs（人工复核）');await click('[data-action="save-cell"]');
  await check('manual matrix edit retains source evidence',`prototypeDebug.getState().dimensions[2].status[0]==='人工修正'&&document.querySelector('.quote').textContent.includes('50 epochs')`);
  await go('search');await fill('#query','MobileNetV3');await ev(`document.querySelector('#search-form').requestSubmit()`);
  await check('actual literal search finds correct document',`document.querySelectorAll('.result').length===1&&document.querySelector('.result').textContent.includes('MobileNetV3')`);
  await click('[data-search-mode="semantic"]');
  await check('semantic mode is explicitly preset',`document.querySelector('.section-line').textContent.includes('预置语义结果')&&document.querySelectorAll('.result').length===3`);
  await click('[data-action="search-to-matrix"]');
  await check('task conversion retains source task',`document.querySelector('.notice').textContent.includes('跨文档检索')`);
  await go('notes');await fill('#note-title','浏览器验证笔记');await fill('#note-body','# 已核对\n\nA 与 C 的训练设置不同。');await sleep(800);
  await c('Page.reload');await wait(`!!document.querySelector('.shell')`);await go('notes');
  await check('notes and citations survive reload',`document.querySelector('#note-title').value==='浏览器验证笔记'&&document.querySelector('#note-body').value.includes('训练设置不同')&&prototypeDebug.getState().citations.length===2`);
  await go('library');await click('[data-action="change-source"]');
  await check('source change marks results stale',`prototypeDebug.getState().stale&&document.querySelector('.notice.amber')`);
  await click('[data-action="missing-source"]');
  await check('unavailable historical evidence never maps to new text',`prototypeDebug.getState().missing&&document.querySelector('.side-content').textContent.includes('旧版本原文不可定位')&&!document.querySelector('.side-content .quote')`);
  await shot('stale-evidence-1440');await click('[data-action="restore-source"]');
  await go('matrix');await click('[data-action="run-matrix"]');await click('[data-cancel]');
  await check('task cancellation retains old results',`prototypeDebug.getJobs()[0].status==='已取消'&&prototypeDebug.getState().dimensions[2].values[0].includes('人工复核')`);
  await click('[data-retry]');await wait(`prototypeDebug.getJobs()[0].status==='已完成'`);
  await check('retry finishes as a separate run',`prototypeDebug.getJobs().some(j=>j.status==='已取消')&&prototypeDebug.getJobs()[0].name.includes('重试')`);
  await click('[data-action="demo-failure"]');await wait(`prototypeDebug.getJobs()[0].status==='执行失败'`);await shot('tasks-1440');
  await go('settings');await click('[data-action="external-preview"]');
  await check('offline mode blocks external workflow',`document.querySelector('#dialog').textContent.includes('阻止外部服务')`);await click('[data-action="close-dialog"]');
  await ev(`{const c=document.querySelector('#offline-toggle');c.checked=false;c.dispatchEvent(new Event('change',{bubbles:true}));}`);await click('[data-action="external-preview"]');
  await check('authorization previews exact text and no real send',`document.querySelector('#dialog .quote').textContent.includes('50 epochs')&&document.querySelector('#dialog').textContent.includes('不会发送正文')`);
  await shot('authorization-1440');await click('[data-action="external-confirm"]');
  const sample=path.join(run,'sample.md');await fs.writeFile(sample,'# 本地验证\n\n星河编码器用于合成测试。','utf8');await setFile('#import-files',sample);await wait(`prototypeDebug.getState().docs.length===5`);
  await check('actual Markdown import can be read',`prototypeDebug.getState().docs.at(-1).sections[0].text.includes('星河编码器')`);
  await click('[data-action="share"]');await ev(`document.querySelector('#share-ack').checked=true`);await click('[data-action="download-bundle"]');
  const archive=path.join(downloads,'DocLens-演示分享包.zip');for(let i=0;i<50;i++){try{await fs.access(archive);break;}catch{}await sleep(100);}await fs.access(archive);
  await setFile('#import-bundle',archive);await wait(`!!document.querySelector('#apply-import')`);await click('#apply-import');
  await check('share ZIP roundtrip preserves note and imported text',`prototypeDebug.getState().noteTitle==='浏览器验证笔记'&&prototypeDebug.getState().docs.length===5`);
  const bad=path.join(run,'bad.zip');await fs.writeFile(bad,'invalid archive');await setFile('#import-bundle',bad);await sleep(250);
  await check('bad package preserves current project',`prototypeDebug.getState().docs.length===5&&document.querySelector('#toast').textContent.includes('导入失败')`);
  await click('[data-action="share"]');await click('[data-action="download-md"]');await click('[data-action="download-csv"]');await sleep(400);await click('[data-action="close-dialog"]');
  const names=await fs.readdir(downloads);checks.push({name:'Markdown CSV and ZIP downloads exist',pass:['DocLens-研究笔记.md','DocLens-比较矩阵.csv','DocLens-演示分享包.zip'].every(n=>names.includes(n))});
  // Reset all changes for the final representative screenshot.
  await go('settings');await click('[data-action="reset"]');await click('[data-action="confirm-reset"]');await go('matrix');
  await ev(`document.querySelector('#toast').style.display='none'`);await shot('matrix-1440');
  await check('all demo evidence source spans are real',`prototypeDebug.getState().dimensions.every(r=>r.blocks.every((b,i)=>b===null||!!prototypeDebug.getState().docs.find(d=>d.id===['a','b','c'][i]).sections[b].text))`);
  checks.push({name:'no runtime errors or remote requests',pass:!errors.length&&!requests.length});
} catch(error) { failure=error.stack;console.error(failure); }
finally {
  await fs.writeFile(path.join(output,'browser-checks.json'),JSON.stringify({browser:'Microsoft Edge headless (local files)',checks,errors,requests,failure:failure||null},null,2));
  if(socket?.readyState===WebSocket.OPEN){try{await c('Browser.close');}catch{}socket.close();}edge.kill();
}
console.log(JSON.stringify({checks:checks.length,failed:checks.filter(c=>!c.pass),errors,remoteRequests:requests.length},null,2));
if(failure||checks.some(c=>!c.pass))process.exitCode=1;
