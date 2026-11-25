// Usage: node scripts/validate_keyword_prototype.mjs (Windows + Microsoft Edge)
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'docs/validation/keyword-prototype');
const build = path.join(root, 'build/keyword-prototype');
await fs.mkdir(output, {recursive: true});
await fs.mkdir(build, {recursive: true});
const run = await fs.mkdtemp(path.join(build, 'run-'));
const downloads = path.join(run, 'downloads');
await fs.mkdir(downloads);
const edge = spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1', `--user-data-dir=${run}`, 'about:blank'
], {windowsHide: true, stdio: 'ignore'});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const results = [];
const errors = [];
const requests = [];
let socket;
let id = 0;
const pending = new Map();

function c(method, params = {}) {
    return new Promise((resolve, reject) => {
        const commandId = ++id;
        const timeout = setTimeout(() => {
            pending.delete(commandId);
            reject(new Error(`Timeout: ${method}`));
        }, 12000);
        pending.set(commandId, {resolve, reject, timeout});
        socket.send(JSON.stringify({id: commandId, method, params}));
    });
}

async function evaluate(expression) {
    const response = await c('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text);
    return response.result.value;
}

async function waitFor(expression) {
    for (let attempt = 0; attempt < 45; attempt++) {
        if (await evaluate(expression)) return;
        await sleep(75);
    }
    throw new Error(`Page condition did not become true: ${expression}`);
}

async function open(page, query = '') {
    const url = new URL(pathToFileURL(path.join(root, 'examples/desktop-prototype', `${page}.html`)));
    url.search = query;
    await c('Page.navigate', {url: url.href});
    await waitFor(`location.href === ${JSON.stringify(url.href)} && document.readyState === 'complete' && !!document.querySelector('.app, iframe')`);
}

async function check(name, expression) {
    const pass = Boolean(await evaluate(expression));
    results.push({name, pass});
    if (!pass) throw new Error(`Check failed: ${name}`);
}

async function shot(name) {
    const {data} = await c('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
    await fs.writeFile(path.join(output, `${name}.png`), Buffer.from(data, 'base64'));
}

async function connect() {
    let tab;
    for (let attempt = 0; attempt < 60; attempt++) {
        try {
            const [port] = (await fs.readFile(path.join(run, 'DevToolsActivePort'), 'utf8')).split(/\s+/);
            const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
            tab = tabs.find(item => item.type === 'page');
            if (tab) break;
        } catch { /* Edge starts asynchronously. */ }
        await sleep(200);
    }
    if (!tab) throw new Error('Edge debugging endpoint unavailable');
    socket = new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
        socket.addEventListener('open', resolve, {once: true});
        socket.addEventListener('error', reject, {once: true});
    });
    socket.addEventListener('message', event => {
        const message = JSON.parse(event.data);
        const waiting = pending.get(message.id);
        if (waiting) {
            clearTimeout(waiting.timeout);
            pending.delete(message.id);
            if (message.error) waiting.reject(new Error(JSON.stringify(message.error)));
            else waiting.resolve(message.result);
        }
        if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description);
        if (message.method === 'Log.entryAdded' && message.params.entry.level === 'error') errors.push(message.params.entry.text);
        if (message.method === 'Network.requestWillBeSent' && /^https?:/.test(message.params.request.url)) requests.push(message.params.request.url);
    });
    for (const name of ['Page', 'Runtime', 'Log', 'Network']) await c(`${name}.enable`);
    await c('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: downloads});
}

const select = (selector, value) => evaluate(`{
    const control = document.querySelector(${JSON.stringify(selector)});
    control.value = ${JSON.stringify(value)};
    control.dispatchEvent(new Event('change', {bubbles:true}));
}`);
const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
const fill = (selector, value) => evaluate(`document.querySelector(${JSON.stringify(selector)}).value = ${JSON.stringify(value)}`);

try {
    await connect();
    const views = [
        ['workspace', '', 'workspace'], ['library', '', 'library'], ['compare', '', 'compare'],
        ['compare', 'view=diff', 'diff'], ['compare', 'view=ai&sample=1', 'ai-results'],
        ['evidence', '', 'evidence'], ['notes', '', 'notes'], ['share', '', 'share']
    ];
    for (const [width, height] of [[1280, 800], [1440, 900], [1920, 1080]]) {
        await c('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
        for (const [page, query, name] of views) {
            await open(page, query);
            await check(`${name} ${width}x${height}: styled page without horizontal overflow`,
                `document.documentElement.scrollWidth <= ${width} && getComputedStyle(document.querySelector('.app')).display === 'grid'`);
            if (width === 1440 || name === 'diff') await shot(`${name}-${width}`);
        }
    }
    await c('Emulation.setDeviceMetricsOverride', {width: 1440, height: 900, deviceScaleFactor: 1, mobile: false});
    await open('desktop');
    await check('primary navigation has the four research pages', `document.querySelectorAll('.sidebar nav a').length === 4 && !document.querySelector('.matrix')`);
    await check('literal term boundaries and case handling', `KeywordCompare.matchRanges('ResNet resnet ResNet50 ResNet-50', 'ResNet').length === 2 && KeywordCompare.matchRanges('CIFAR-100', 'CIFAR-10').length === 0`);
    await check('localized diff can highlight numeric changes', `KeywordCompare.tokenDiff('50 轮','100 轮').left[0].text === '50'`);
    await click('[data-action="keyword-add"]');
    await fill('#term-input', '不存在术语');
    await click('#dialog-form [type="submit"]');
    await check('new keyword displays no match', `document.querySelector('.count-summary').textContent.includes('0 个') && document.querySelectorAll('.reading-pane .empty').length === 2`);
    await click('[data-action="keyword-edit"]');
    await fill('#term-input', 'ResNet-50');
    await click('#dialog-form [type="submit"]');
    await check('edited term picks its own literal hit', `document.querySelector('.count-summary').textContent.includes('1 个')`);
    await click('[data-action="keyword-remove"]');
    await click('#dialog-form [type="submit"]');
    await check('keyword removed', `!document.querySelector('[data-term="ResNet-50"]')`);
    await click('[data-action="scope"]');
    await evaluate(`document.querySelector('[name=doc][value=d]').checked = false`);
    await click('#dialog-form [type="submit"]');
    await check('document scope narrows the keyword counts and source list', `document.querySelector('.count-summary').textContent.includes('3 / 3 篇') && document.querySelectorAll('.source-group').length === 3`);
    await click('[data-action="scope"]');
    await evaluate(`document.querySelector('[name=doc][value=d]').checked = true`);
    await click('#dialog-form [type="submit"]');
    await click('[data-mode="diff"]');
    await check('diff in the UI marks both 50 and 100', `Array.from(document.querySelectorAll('mark.mark-left')).some(mark=>mark.textContent.includes('50')) && Array.from(document.querySelectorAll('mark.mark-right')).some(mark=>mark.textContent.includes('100'))`);
    await select('#select-right', 'c:1');
    await check('change selected document and fragment', `document.querySelectorAll('.reading-pane h3')[1].textContent.includes('注意力基线')`);
    await click('[data-mode="ai"]');
    await click('[data-action="ai-preview"]');
    await click('#dialog footer [data-action="dialog-close"]');
    await check('cancel closes preview without generating results', `!document.querySelector('dialog').open && !document.querySelector('.analysis-results')`);
    await click('[data-action="ai-preview"]');
    await check('confirmation shows exact original selected excerpts', `document.querySelector('dialog').open && document.querySelectorAll('.send-item').length===5 && document.querySelector('dialog').textContent.includes(DEMO.documents[0].blocks[1].text)`);
    await shot('ai-confirm-1440');
    await evaluate(`document.querySelector('[name=clip][value="a:2"]').checked = false`);
    await click('#dialog-form [type="submit"]');
    await check('AI demo shows four evidence labels and partial coverage', `['本文采用','背景或相关工作提及','明确未采用','无法确定','部分覆盖'].every(label=>document.querySelector('.analysis-results').textContent.includes(label))`);
    await check('summary cites both sources', `document.querySelectorAll('.ai-summary a[href^="evidence.html"]').length === 2`);
    await click('.ai-result:nth-of-type(3) [data-action="cite"]');
    await check('adding a third citation gives feedback', `document.querySelector('#status-message').textContent.includes('已加入笔记')`);
    await open('notes');
    await check('multiple sources survive navigation', `document.querySelectorAll('.citation-row').length === 3`);
    await fill('#note-body', '验证样例：保存的多来源比较笔记。');
    await click('[data-action="note-save"]');
    await c('Page.reload');
    await waitFor(`document.querySelector('#note-body')?.value.includes('验证样例')`);
    await check('note persists after reload', `document.querySelector('#note-body').value.includes('保存的多来源')`);
    await click('.citation-row:last-child a');
    await waitFor(`location.pathname.endsWith('evidence.html') && !!document.querySelector('.target-block')`);
    await check('citation opens the correct original block', `document.querySelector('.target-block').textContent.includes('本研究未采用 ResNet')`);
    await open('library');
    const fixture = path.join(run, 'preview.md');
    await fs.writeFile(fixture, '# 本地示例\n<script>不执行</script>', 'utf8');
    const {root: dom} = await c('DOM.getDocument');
    const {nodeId} = await c('DOM.querySelector', {nodeId: dom.nodeId, selector: '#file-input'});
    await c('DOM.setFileInputFiles', {nodeId, files: [fixture]});
    await waitFor(`document.querySelector('#import-results').textContent.includes('临时预览')`);
    await check('temporary local preview treats markup as text', `document.querySelector('#library-preview').textContent.includes('<script>不执行</script>') && !document.querySelector('#library-preview script')`);
    await open('share');
    await check('original documents are unchecked by default', `!document.querySelector('#include-originals').checked`);
    await click('[data-action="report-export"]');
    await click('[data-action="zip-export"]');
    await sleep(600);
    await fs.copyFile(path.join(downloads, 'DocLens-共享演示.zip'), path.join(build, 'without-originals.zip'));
    await fs.unlink(path.join(downloads, 'DocLens-共享演示.zip'));
    await click('#include-originals');
    await check('share manifest updates when originals are included', `document.querySelector('#package-list').textContent.includes('originals/')`);
    await click('[data-action="zip-export"]');
    await sleep(600);
    await fs.copyFile(path.join(downloads, 'DocLens-共享演示.zip'), path.join(build, 'with-originals.zip'));
    await fs.copyFile(path.join(downloads, 'DocLens-研究报告.md'), path.join(build, 'report.md'));
    await open('index');
    await check('index has eight independent iframe boards', `document.querySelectorAll('iframe[title]').length === 8`);
    await shot('index-1440');
    results.push({name: 'no runtime errors and no remote requests', pass: !errors.length && !requests.length});
} finally {
    await fs.writeFile(path.join(output, 'browser-checks.json'), JSON.stringify({browser: 'Microsoft Edge headless', results, errors, requests}, null, 2));
    if (socket?.readyState === WebSocket.OPEN) {
        try { await c('Browser.close'); } catch { /* Process may close before reply. */ }
        socket.close();
    }
    edge.kill();
}

console.log(JSON.stringify({checks: results.length, failures: results.filter(result => !result.pass), errors, requests}, null, 2));
if (results.some(result => !result.pass)) process.exitCode = 1;
