/* Interactive Windows desktop design prototype. AI output is scripted. */
(() => {
    'use strict';

    const params = new URLSearchParams(location.search);
    const longScene = params.get('scenario') === 'long' || document.body.dataset.scenario === 'long';
    const scenario = longScene ? window.LONG_DEMO : window.DEMO;
    const {project, documents, keywords} = scenario;
    const {matchRanges, tokenDiff} = window.KeywordCompare;
    const $ = selector => document.querySelector(selector);
    const all = selector => Array.from(document.querySelectorAll(selector));
    const escape = value => String(value).replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[char]));
    const page = document.body.dataset.page === 'desktop' ? 'compare' : document.body.dataset.page;
    const storageKey = 'doclens-keyword-design-04' + (longScene ? '-long' : '');
    const titles = {
        workspace: '项目与文档', library: '文档库', compare: '关键词比较',
        evidence: '证据阅读', notes: '研究笔记', share: '导出与共享'
    };
    const paths = {
        workspace: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>',
        compare: '<path d="M8 3 5 21M19 3l-3 18M3 8h19M2 16h19"/>',
        notes: '<path d="M5 3h14v14l-4 4H5zM15 21v-5h4M8 8h8M8 12h8"/>',
        share: '<path d="M12 16V3M7 8l5-5 5 5M4 14v7h16v-7"/>',
        search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
        arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
        plus: '<path d="M12 5v14M5 12h14"/>',
        cloud: '<path d="M8 18H7a4 4 0 1 1 1-8 5 5 0 0 1 10 1 3.5 3.5 0 0 1-1 7H8z"/>',
        book: '<path d="M12 5v15M3 4h4c2 0 4 1 5 2 1-1 3-2 5-2h4v14h-5c-2 0-3 1-4 2-1-1-2-2-4-2H3z"/>',
        close: '<path d="m6 6 12 12M6 18 18 6"/>',
        check: '<path d="m4 12 5 5L20 6"/>'
    };

    function icon(name) {
        return `<svg class="icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
    }

    const defaultNote = {
        id: 'sample', title: 'ResNet 的两种用法',
        body: '对比表征研究用 ResNet 做编码器，训练 50 轮。轻量视觉编码提到的 100 轮来自相关工作。引用两段原文时，应保留各自的实验主体。',
        citations: [{doc: 'a', block: 1, term: 'ResNet'}, {doc: 'b', block: 1, term: 'ResNet'}]
    };
    if (longScene) {
        defaultNote.title = '第 8 章实验设置核对';
        defaultNote.body = 'A 记录本文实验的 50 轮，B 转述相关工作的 100 轮。比较时应保留两段各自的主体。';
        defaultNote.citations = scenario.pair.map(key => refFor(key, keywords[0]));
    }
    const defaults = {keywords, active: keywords[0], scope: documents.map(doc => doc.id), notes: [defaultNote], noteId: 'sample'};
    const state = loadState();
    const requestedView = params.get('view') || document.body.dataset.view;
    let mode = ['diff', 'ai'].includes(requestedView) ? requestedView : 'source';
    let pair = scenario.pair?.slice() || [null, null];
    let analysis = null;
    let noteDirty = false;
    let previewDoc = documents[0];
    let toastTimer;
    const displayedHits = new Map();
    const hitPageSize = 8;
    const maxAnalysisBlocks = 20;

    function loadState() {
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey));
            return {...structuredClone(defaults), ...saved};
        } catch {
            return structuredClone(defaults);
        }
    }

    function persist() {
        try {
            localStorage.setItem(storageKey, JSON.stringify(state));
            return true;
        } catch {
            notify('此浏览器无法保存，请下载 Markdown 保留笔记。');
            return false;
        }
    }

    function notify(message) {
        const region = $('#status-message');
        if (!region) return;
        region.textContent = message;
        region.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { region.hidden = true; }, 3600);
    }

    function button(text, action, {style = '', glyph = '', attrs = ''} = {}) {
        return `<button type="button" class="dl-btn ${style}" data-action="${action}" ${attrs}>${glyph ? icon(glyph) : ''}${text}</button>`;
    }

    function link(text, target, style = '', glyph = '') {
        return `<a class="dl-btn ${style}" href="${escape(route(target))}">${glyph ? icon(glyph) : ''}${text}</a>`;
    }

    function route(target) {
        if (!longScene || !/^(workspace|library|compare|desktop|evidence|notes|share)\.html(?:[?#]|$)/.test(target)) return target;
        const [base, anchor] = target.split('#');
        return `${base}${base.includes('?') ? '&' : '?'}scenario=long${anchor ? `#${anchor}` : ''}`;
    }

    function badge(text, style = '') {
        return `<span class="badge-label ${style}">${escape(text)}</span>`;
    }

    function documentFor(id) {
        return documents.find(doc => doc.id === id);
    }

    function refFor(value, term = state.active) {
        if (!/^[a-d]:\d+$/.test(value || '')) return null;
        const [doc, block] = value.split(':');
        const index = Number(block);
        return documentFor(doc)?.blocks[index] ? {doc, block: index, term} : null;
    }

    function blockFor(ref) {
        return documentFor(ref.doc)?.blocks[ref.block];
    }

    function refKey(ref) {
        return `${ref.doc}:${ref.block}`;
    }

    function sourceUrl(ref) {
        const query = new URLSearchParams({doc: ref.doc, block: ref.block, term: ref.term});
        return `evidence.html?${query}#block-${ref.block}`;
    }

    function matches(term = state.active) {
        return documents.filter(doc => state.scope.includes(doc.id)).map(doc => ({
            doc,
            refs: doc.blocks.flatMap((block, index) => matchRanges(block.text, term).length
                ? [{doc: doc.id, block: index, term}] : [])
        }));
    }

    function highlight(text, term) {
        let output = '';
        let last = 0;
        for (const [start, end] of matchRanges(text, term)) {
            output += escape(text.slice(last, start)) + `<mark class="keyword-mark">${escape(text.slice(start, end))}</mark>`;
            last = end;
        }
        return output + escape(text.slice(last));
    }

    function normalizePair(groups) {
        const available = groups.flatMap(group => group.refs);
        const valid = value => available.some(ref => refKey(ref) === value);
        if (!valid(pair[0])) {
            const first = available.find(ref => ref.doc !== pair[1]?.[0]);
            pair[0] = first ? refKey(first) : null;
        }
        if (!valid(pair[1]) || pair[1]?.[0] === pair[0]?.[0]) {
            const other = available.find(ref => ref.doc !== pair[0]?.[0]);
            pair[1] = other ? refKey(other) : null;
        }
    }

    const nav = ['workspace', 'compare', 'notes', 'share'];
    const activePage = {library: 'workspace', evidence: 'compare'}[page] || page;

    function shell() {
        return `<div class="app"><aside class="sidebar">
            <a class="brand" href="${route('workspace.html')}"><span class="brand-icon"><img src="assets/vendor/layout-dashboard.svg" alt=""></span>DocLens</a>
            <div class="project-label"><span class="project-initial">研</span><div><strong>${project}</strong><small>本地项目</small></div></div>
            <nav aria-label="主导航">${nav.map(item => `<a href="${route(`${item}.html`)}" ${item === activePage ? 'aria-current="page"' : ''}>${icon(item)}${titles[item]}</a>`).join('')}</nav>
            <div class="sidebar-foot"><span class="online-dot"></span>Windows 桌面原型<a href="${longScene ? 'compare.html' : 'long.html'}">${longScene ? '切回简短示例' : '打开长文档案例'}</a><a href="index.html">界面总览</a></div>
        </aside><main>
            <header class="titlebar"><span>研究工作区 <span class="breadcrumb-divider">/</span> ${titles[page]}</span><span class="prototype-label">${longScene ? '合成长文档' : '合成示例'}</span></header>
            <div class="content" id="content"></div>
        </main></div><div id="status-message" role="status" class="toast-message" hidden></div><dialog id="dialog"></dialog>`;
    }

    function pageHeader(title, description, actions = '') {
        return `<header class="page-heading"><div><h1>${title}</h1><p>${description}</p></div>${actions ? `<div class="actions">${actions}</div>` : ''}</header>`;
    }

    function workspace() {
        return `${pageHeader('项目与文档', '整理项目资料并选择参与比较的文档。', link('打开关键词比较', 'compare.html', 'primary', 'arrow'))}
            <section class="workspace-intro"><div><div class="section-label">当前项目</div><h2>${project}</h2><p>围绕 ResNet 和 CIFAR-10 核对各篇实验设置，整理带原文引用的比较笔记。</p></div>
            <div class="workspace-stats"><div><strong>${documents.length}</strong><span>篇文档</span></div><div><strong>${state.keywords.length}</strong><span>个关键词</span></div><div><strong>${state.notes.length}</strong><span>条笔记</span></div></div></section>
            ${longScene ? `<p class="long-project-hint"><a class="dl-btn" href="sample-documents/视觉编码实验记录A.md" download>下载长文档 A</a><a class="dl-btn" href="sample-documents/视觉编码文献记录B.md" download>下载长文档 B</a></p>` : ''}
            <section class="panel"><div class="panel-header"><h2>项目文档</h2>${link('导入与预览', 'library.html', '', 'plus')}</div>${documentRows()}</section>`;
    }

    function documentRows({preview = false} = {}) {
        return documents.map(doc => `<div class="document-row"><span class="format-icon format-${doc.format.toLowerCase()}">${doc.format}</span>
            <div class="grow"><strong>${doc.name}</strong><small>${doc.blocks.length} 个文本块${doc.status === '部分提取' ? ' · 部分上下文缺失' : ''}</small></div>
            ${badge(doc.status, doc.status === '部分提取' ? 'amber' : 'green')}
            ${preview ? button('预览', 'preview-doc', {attrs: `data-doc="${doc.id}"`}) : link('查看正文', sourceUrl({doc: doc.id, block: 0, term: ''}))}</div>`).join('');
    }

    function library() {
        return `${pageHeader('文档库', '预览提取正文并核对逐份解析状态。', link('回到项目', 'workspace.html'))}
            <div class="library-grid"><section class="panel"><div class="panel-header"><h2>项目文档</h2>${button('选择文件', 'file-select', {style: 'primary', glyph: 'plus'})}<input id="file-input" type="file" accept=".pdf,.docx,.md,.markdown,.txt" multiple hidden></div>
            <p class="panel-inset muted">可临时预览本地 MD/TXT。${longScene ? '这里列出两份合成研究记录。' : '下方 PDF、DOCX 和解析状态使用合成示例。'}</p>${documentRows({preview: true})}<div id="import-results" aria-live="polite"></div></section>
            <section class="panel"><div class="panel-header"><h2>提取正文预览</h2></div><div class="paper" id="library-preview">${libraryPreview(previewDoc)}</div></section></div>`;
    }

    function libraryPreview(doc) {
        const initialBlocks = longScene ? doc.blocks.slice(0, 5) : doc.blocks;
        return `<h3>${doc.name}</h3>${longScene ? `<p class="muted">预览前 ${initialBlocks.length} 段，共 ${doc.blocks.length} 段。${link('打开章节阅读', sourceUrl({doc: doc.id, block: 0, term: ''}), 'quiet')}</p>` : ''}${initialBlocks.map(block => `<p>${escape(block.text)}</p>`).join('')}`;
    }

    function keywordList() {
        return `<aside class="panel keywords"><div class="panel-header"><h2>关键词</h2>${button('添加', 'keyword-add', {glyph: 'plus', style: 'quiet'})}</div>
            <div class="keyword-rows">${state.keywords.map(term => {
                const groups = matches(term);
                const count = groups.reduce((total, item) => total + item.refs.length, 0);
                return `<button type="button" class="keyword-row" data-action="keyword-select" data-term="${escape(term)}" aria-pressed="${term === state.active}"><strong>${escape(term)}</strong><small>${groups.filter(item => item.refs.length).length} 篇文档 · ${count} 个片段</small></button>`;
            }).join('') || '<p class="empty">添加关键词开始查找。</p>'}</div>
            ${state.active ? `<div class="keyword-tools">${button('编辑', 'keyword-edit', {style: 'quiet'})}${button('删除', 'keyword-remove', {style: 'quiet'})}</div>` : ''}
            <div class="keyword-hint">${icon('search')}按原词查找提取正文</div></aside>`;
    }

    function compare() {
        const groups = matches();
        normalizePair(groups);
        const hitDocs = groups.filter(group => group.refs.length).length;
        const hitBlocks = groups.reduce((total, group) => total + group.refs.length, 0);
        const corpusInfo = longScene ? `长文档案例 · ${documents.length} 篇 · ${documents.reduce((total, doc) => total + doc.blocks.length, 0)} 个段落` : '查找多篇文档中的原词，核对文字差异与使用语境。';
        return `${pageHeader('关键词比较', corpusInfo, button('选择文档', 'scope', {glyph: 'workspace'}))}
            <div class="compare-layout">${keywordList()}
            <section class="panel comparison"><div class="compare-title"><div><div class="section-label">当前关键词</div><h2>${escape(state.active || '请选择关键词')}</h2></div>
            <div class="count-summary"><strong>${hitDocs} / ${groups.length} 篇</strong>命中文档<span></span><strong>${hitBlocks} 个</strong>命中片段</div></div>
            <div class="mode-tabs" aria-label="比较视图">${[['source', '原文对照', 'book'], ['diff', '本地文本比较', 'compare'], ['ai', 'AI 分析用途', 'cloud']].map(([id, label, glyph]) =>
                button(label, 'mode', {glyph, attrs: `data-mode="${id}" aria-pressed="${mode === id}"`})).join('')}</div>
            ${mode === 'ai' ? aiView(groups) : sourceView(groups)}</section></div>`;
    }

    function pane(side, groups, diff = '') {
        const index = side === 'left' ? 0 : 1;
        const label = index === 0 ? '左侧' : '右侧';
        const current = refFor(pair[index]);
        const options = groups.map(({doc, refs}) => `<optgroup label="${doc.name}">${refs.map(ref => {
            const block = blockFor(ref);
            return `<option value="${refKey(ref)}" ${refKey(ref) === pair[index] ? 'selected' : ''}>${block.section} / ${block.location}</option>`;
        }).join('')}</optgroup>`).join('');
        const doc = current && documentFor(current.doc);
        const block = current && blockFor(current);
        return `<article class="reading-pane"><header><span class="side-label">${label}片段</span>${doc ? `<span class="format-text">${doc.format}</span>` : ''}</header>
            <div class="pane-content">${doc ? `<h3>${doc.name}</h3>` : '<h3>选择一处原文片段</h3>'}
            <label class="visually-hidden" for="select-${side}">${label}原文片段</label><select id="select-${side}" data-side="${index}" class="select-clip"><option value="" ${current ? '' : 'selected'} disabled>选择${label}片段</option>${options}</select>
            ${block ? `<div class="paper excerpt"><div class="location">${block.section} <span> / </span> ${block.location}</div><p>${diff || highlight(block.text, state.active)}</p></div>
                <div class="pane-actions">${link('跳到原文', sourceUrl(current), 'quiet', 'book')}${button('加入笔记', 'cite', {style: 'quiet', glyph: 'notes', attrs: `data-ref="${refKey(current)}"`})}</div>` : '<p class="empty">当前没有可用于这一侧的片段。</p>'}</div></article>`;
    }

    function sourceView(groups) {
        const left = refFor(pair[0]);
        const right = refFor(pair[1]);
        const showingDiff = mode === 'diff';
        const diff = showingDiff && left && right ? tokenDiff(blockFor(left).text, blockFor(right).text) : null;
        const diffText = entries => entries.map(entry => entry.state === 'same'
            ? highlight(entry.text, state.active)
            : `<mark class="mark-${entry.state}">${escape(entry.text)}</mark>`).join('');
        const identical = diff && blockFor(left).text === blockFor(right).text;
        const legend = showingDiff ? `<div class="mode-hint"><span><span class="online-dot"></span>离线 Diff</span>${identical ? '<span>所选片段内容一致</span>' : diff ? '<span class="legend"><i class="mark-left"></i>仅左侧 <i class="mark-right"></i>仅右侧 <i class="keyword-mark"></i>关键词</span>' : '<span>请选择两篇文档的片段</span>'}</div>`
            : '<div class="mode-hint"><span>从两篇文档各选一段原文</span><span class="legend"><i class="keyword-mark"></i>原词命中</span></div>';
        return `${legend}<div class="reading-grid">${pane('left', groups, diff ? diffText(diff.left) : '')}${pane('right', groups, diff ? diffText(diff.right) : '')}</div>
            <div class="source-list"><h3>按文档浏览命中</h3>${groups.map(group => `<details class="source-group" data-group="${group.doc.id}">${sourceGroup(group)}</details>`).join('') || '<p class="empty">选择可读文档后查看结果。</p>'}</div>`;
    }

    function sourceGroup({doc, refs}) {
        const limit = displayedHits.get(doc.id) || hitPageSize;
        return `<summary><span>${doc.name}</span><span>${refs.length ? `${refs.length} 个片段` : '当前提取文本未找到'}${doc.status === '部分提取' ? ' · 部分提取' : ''}</span></summary>
            ${refs.slice(0, limit).map(ref => `<div class="source-row"><div><small>${blockFor(ref).section} · ${blockFor(ref).location}</small><p>${highlight(blockFor(ref).text, state.active)}</p></div>${link('查看', sourceUrl(ref))}</div>`).join('')}
            ${refs.length > limit ? `<div class="more-hits" data-limit="${limit}"><span>已显示 ${limit} / ${refs.length} 个片段</span>${button(`再显示 ${Math.min(refs.length - limit, hitPageSize)} 个`, 'more-hits', {attrs: `data-doc="${doc.id}"`})}</div>` : ''}`;
    }

    function aiView(groups) {
        const items = groups.flatMap(group => group.refs);
        return `<div class="ai-top"><div><strong>联网分析</strong><p>${analysis ? '预设演示结果。打开引文可以核对来源。' : '先选择要发送的命中片段，再确认分析范围。'}</p></div>
            <div class="actions">${button('模型设置', 'model-settings')}${button('预览发送范围', 'ai-preview', {style: 'primary', glyph: 'cloud', attrs: items.length ? '' : 'disabled'})}</div></div>
            ${analysis ? analysisView(groups) : `<div class="ai-empty">${icon('cloud')}<h3>${items.length ? '等待确认片段' : '当前没有可分析的命中片段'}</h3><p>正式版需要联网和云端 API。本原型使用预设结果，不发送内容。</p></div>`}`;
    }

    function analysisView(groups) {
        const known = ['resnet', 'cifar-10'].includes(state.active.toLowerCase());
        const summaryRefs = scenario.pair || ['a:1', 'b:1'];
        const hasComparison = known && summaryRefs.every(key => analysis.includes(key));
        const summary = hasComparison ? `<div class="ai-summary"><h3>跨文档摘要</h3><p>${scenario.summary || '在已选片段中，对比表征研究描述本文实验，轻量视觉编码转述相关工作。'}</p><div class="actions">${link('文档 A 引文', sourceUrl(refFor(summaryRefs[0])), 'quiet')}${link('文档 B 引文', sourceUrl(refFor(summaryRefs[1])), 'quiet')}</div></div>` : '';
        return `<div class="analysis-results">${summary}${groups.map(({doc, refs}) => {
            const included = refs.filter(ref => analysis.includes(refKey(ref)));
            return `<section class="ai-result"><header><div><h3>${doc.name}</h3><small>命中 ${refs.length} · 提交 ${included.length} · 完成 ${included.length}</small></div>${included.length ? badge(included.length < refs.length ? '部分覆盖' : '演示完成', 'blue') : badge(refs.length ? '未提交' : '未命中')}</header>
                ${included.map(ref => {
                    const block = blockFor(ref);
                    const verdict = known && block.verdict ? block.verdict : '无法确定';
                    const tint = {'本文采用': 'green', '背景或相关工作提及': 'blue', '明确未采用': 'rose', '无法确定': 'amber'}[verdict];
                    return `<div class="ai-finding">${badge(verdict, tint)}<p>${known && block.reason ? block.reason : '此片段没有预设用途判断，请核对原文。'}</p><blockquote>${highlight(block.text, state.active)}</blockquote><div class="actions">${link('核对引文', sourceUrl(ref), 'quiet', 'book')}${button('加入笔记', 'cite', {style: 'quiet', glyph: 'notes', attrs: `data-ref="${refKey(ref)}"`})}</div></div>`;
                }).join('')}</section>`;
        }).join('')}</div>`;
    }

    function evidence() {
        const requested = refFor(`${params.get('doc')}:${params.get('block')}`, params.get('term') || '');
        const current = requested || refFor(scenario.pair?.[0] || 'a:1', keywords[0]);
        const doc = documentFor(current.doc);
        const block = blockFor(current);
        const sections = doc.blocks.reduce((result, item, i) => {
            if (!result.some(section => section.name === item.section)) result.push({name: item.section, index: i});
            return result;
        }, []);
        return `${pageHeader('证据阅读', `${doc.name} · 提取正文`, link('返回关键词比较', 'compare.html'))}
            <div class="evidence-grid"><aside class="panel"><div class="panel-header"><h2>章节导航</h2>${longScene ? badge(`${sections.length} 章`) : ''}</div><nav class="chapter-nav" aria-label="章节">${sections.map(section => `<a href="${longScene ? escape(route(sourceUrl({doc: doc.id, block: section.index, term: current.term}))) : `#block-${section.index}`}" ${section.name === block.section ? 'aria-current="location"' : ''}>${section.name}</a>`).join('')}</nav></aside>
            <article class="panel document-paper ${longScene ? 'long-paper' : ''}"><div class="section-label">${doc.format} 提取正文${longScene ? ` · 当前章节：${block.section}` : ''}</div><h2>${doc.name}</h2>${doc.blocks.map((item, i) => longScene && item.section !== block.section ? '' : `<section id="block-${i}" class="document-block ${i === current.block ? 'target-block' : ''}"><h3>${i === 0 || doc.blocks[i - 1].section !== item.section ? item.section : ''}</h3><small>${item.location}</small><p>${i === current.block ? highlight(item.text, current.term) : escape(item.text)}</p></section>`).join('')}</article>
            <aside class="panel"><div class="panel-header"><h2>定位片段</h2></div><div class="panel-inset"><small>${block.section} / ${block.location}</small><blockquote>${highlight(block.text, current.term)}</blockquote>${button('加入笔记', 'cite', {style: 'primary', glyph: 'notes', attrs: `data-ref="${refKey(current)}" data-term="${escape(current.term)}"`})}</div></aside></div>`;
    }

    function selectedNote() {
        return state.notes.find(note => note.id === state.noteId);
    }

    function notes() {
        const note = selectedNote();
        return `${pageHeader('研究笔记', '记录跨文档判断，保存可以回跳的原文引用。', button('新建笔记', 'note-add', {style: 'primary', glyph: 'plus'}))}
            <div class="notes-grid"><aside class="panel"><div class="panel-header"><h2>全部笔记</h2><span class="muted">${state.notes.length}</span></div>${state.notes.map(item =>
                button(escape(item.title || '未命名笔记') + `<small>${item.citations.length} 条引用</small>`, 'note-select', {style: 'note-select', attrs: `data-id="${item.id}" aria-pressed="${item.id === state.noteId}"`})).join('')}</aside>
            ${note ? `<section class="panel"><div class="panel-header"><h2>Markdown 编辑</h2><span class="muted" id="note-status">${noteDirty ? '未保存' : '已保存'}</span></div><div class="panel-inset">
            <label for="note-title">标题</label><input id="note-title" class="input" value="${escape(note.title)}" maxlength="120">
            <label for="note-body">正文</label><textarea id="note-body" class="input" rows="11" maxlength="20000">${escape(note.body)}</textarea>
            <div class="actions">${button('保存笔记', 'note-save', {style: 'primary', glyph: 'check'})}${button('导出 Markdown', 'note-export')}${button('删除笔记', 'note-delete', {style: 'quiet'})}</div></div></section>
            <aside class="panel"><div class="panel-header"><h2>关联引用</h2>${badge(`${note.citations.length} 条`)}</div>${note.citations.map((ref, index) => `<div class="citation-row"><strong>${documentFor(ref.doc).name}</strong><small>${blockFor(ref).section} · ${blockFor(ref).location}</small><blockquote>${escape(blockFor(ref).text)}</blockquote><div class="actions">${link('查看原文', sourceUrl(ref), 'quiet', 'book')}${button('移除引用', 'citation-remove', {style: 'quiet', attrs: `data-index="${index}"`})}</div></div>`).join('') || '<p class="empty">从原文或分析结果加入引用。</p>'}</aside>` : '<div class="panel empty">新建一条笔记，或从原文加入引用。</div>'}</div>`;
    }

    function share() {
        return `${pageHeader('导出与共享', '确认接收者将收到的笔记、引用和正文。')}
            <div class="share-grid"><section class="panel"><div class="panel-header"><h2>Markdown 报告</h2>${badge('便于阅读', 'green')}</div>
            <div class="panel-inset"><p>包含项目关键词、研究笔记和已关联的片段。接收者可在 Markdown 阅读器点击引文链接。</p>${button('下载 Markdown', 'report-export', {style: 'primary', glyph: 'share'})}</div></section>
            <section class="panel"><div class="panel-header"><h2>离线共享包</h2>${badge('演示格式', 'blue')}</div><div class="panel-inset"><p>包含报告和 ${documents.length} 篇合成文档的提取正文，以及已保存的笔记。</p>
            <label class="checkbox-label"><input id="include-originals" type="checkbox">附带 ${documents.length} 份示例原始文本</label><div class="callout">即使关闭此选项，共享包仍包含提取正文与笔记。</div>
            <details open class="package-preview"><summary>查看文件清单</summary><pre id="package-list">project.json   项目与提取正文\nreport.md      笔记与引文\nmanifest.json  内容清单\nREADME.txt     阅读说明</pre></details>
            ${button('下载演示 ZIP', 'zip-export', {style: 'primary', glyph: 'share'})}<p class="muted small mt-3 mb-0">演示包可解压阅读，正式项目导入由桌面应用实现。</p></div></section></div>`;
    }

    const views = {workspace, library, compare, evidence, notes, share};

    function render() {
        $('#content').innerHTML = views[page]();
    }

    function openDialog(title, body, confirm, label) {
        const dialog = $('#dialog');
        dialog.innerHTML = `<form id="dialog-form"><header><h2>${title}</h2>${button('关闭', 'dialog-close', {style: 'quiet'})}</header><div class="dialog-body">${body}</div><footer>${button('取消', 'dialog-close')}<button class="dl-btn primary" type="submit">${label}</button></footer></form>`;
        $('#dialog-form').addEventListener('submit', event => {
            event.preventDefault();
            if (confirm(new FormData(event.currentTarget)) === false) return;
            dialog.close();
        });
        dialog.showModal();
    }

    function editKeyword(editing) {
        const title = editing ? '编辑关键词' : '添加关键词';
        openDialog(title, `<label for="term-input">文档中的原词或短语</label><input class="input" id="term-input" name="term" maxlength="80" required value="${editing ? escape(state.active) : ''}" placeholder="例如 CIFAR-10" autofocus><p class="muted small mt-2" id="term-error" role="status"></p>`, data => {
            const term = data.get('term').trim();
            const otherTerms = editing ? state.keywords.filter(item => item !== state.active) : state.keywords;
            if (!term || otherTerms.some(item => item.toLowerCase() === term.toLowerCase())) {
                $('#term-error').textContent = term ? '该关键词已在列表中。' : '请输入一个词或短语。';
                return false;
            }
            if (editing) state.keywords = state.keywords.map(item => item === state.active ? term : item);
            else state.keywords.push(term);
            selectKeyword(term);
            return true;
        }, '保存关键词');
    }

    function selectKeyword(term) {
        state.active = term;
        pair = term === keywords[0] ? scenario.pair?.slice() || [null, null] : [null, null];
        displayedHits.clear();
        analysis = null;
        persist();
        render();
    }

    function chooseScope() {
        openDialog('选择参与比较的文档', documents.map(doc =>
            `<label class="checkbox-label"><input type="checkbox" name="doc" value="${doc.id}" ${state.scope.includes(doc.id) ? 'checked' : ''}>${doc.name}${doc.status === '部分提取' ? ' · 部分提取' : ''}</label>`).join(''), data => {
            state.scope = data.getAll('doc');
            analysis = null;
            persist();
            render();
        }, '应用范围');
    }

    function previewAnalysis() {
        const items = matches().flatMap(group => group.refs);
        if (!items.length) return;
        const selectedByDefault = longScene ? new Set(pair.filter(Boolean)) : new Set(items.map(refKey));
        const selectionRows = refs => refs.map(ref =>
            `<label class="send-item"><input type="checkbox" name="clip" value="${refKey(ref)}" ${selectedByDefault.has(refKey(ref)) ? 'checked' : ''}><span><strong>${documentFor(ref.doc).name}</strong><small>${blockFor(ref).section} · ${blockFor(ref).location}</small><span>${escape(blockFor(ref).text)}</span></span></label>`).join('');
        const rows = longScene ? selectionRows(items.filter(ref => selectedByDefault.has(refKey(ref)))) + `<details class="more-clips"><summary>展开其余 ${items.length - selectedByDefault.size} 个命中，按需勾选</summary>${selectionRows(items.filter(ref => !selectedByDefault.has(refKey(ref))))}</details>` : selectionRows(items);
        openDialog('确认分析范围', `<p class="callout">演示接收方：示例 API。正式版将在确认后联网发送，本次不会发送内容。</p>
            <p class="selection-summary" aria-live="polite" id="ai-selection-summary">已选 ${selectedByDefault.size} / ${items.length} 个命中片段 · 每次最多 ${maxAnalysisBlocks} 个</p>
            ${rows}<p id="send-error" role="status"></p>`, data => {
            const selected = data.getAll('clip');
            if (!selected.length || selected.length > maxAnalysisBlocks) {
                $('#send-error').textContent = selected.length ? `已超过 ${maxAnalysisBlocks} 个片段，请缩小范围。` : '至少选择一个片段。';
                return false;
            }
            analysis = selected;
            render();
            notify('已载入预设分析结果。');
            return true;
        }, '确认并查看演示结果');
    }

    function newNote() {
        const note = {id: String(Date.now()), title: '未命名笔记', body: '', citations: []};
        state.notes.push(note);
        state.noteId = note.id;
        return note;
    }

    function cite(ref) {
        if (!ref) return;
        const note = selectedNote() || newNote();
        if (note.citations.some(item => refKey(item) === refKey(ref))) {
            notify('当前笔记已包含这处引用。');
            return;
        }
        note.citations.push(ref);
        if (persist()) notify(`已加入笔记「${note.title}」。`);
    }

    function saveNote() {
        const note = selectedNote();
        note.title = $('#note-title').value.trim() || '未命名笔记';
        note.body = $('#note-body').value;
        if (persist()) {
            noteDirty = false;
            render();
            notify('笔记已保存。');
        }
    }

    function mayLeaveNote() {
        return !noteDirty || window.confirm('放弃当前未保存的编辑？');
    }

    function noteMarkdown(note) {
        const id = index => `source-${note.id}-${index + 1}`;
        const links = note.citations.map((ref, index) => `[${documentFor(ref.doc).name}](#${id(index)})`).join('、');
        const references = note.citations.map((ref, index) => `<a id="${id(index)}"></a>\n\n${documentFor(ref.doc).name} · ${blockFor(ref).section} · ${blockFor(ref).location}\n\n> ${blockFor(ref).text}`).join('\n\n');
        return `## ${note.title}\n\n${note.body}\n\n${links ? `引用：${links}\n\n${references}` : ''}`;
    }

    function report() {
        return `# ${project}\n\n合成演示资料。\n\n关键词：${state.keywords.join('、')}\n\n${state.notes.map(noteMarkdown).join('\n\n')}`;
    }

    function download(filename, content, type) {
        const url = URL.createObjectURL(new Blob([content], {type}));
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        anchor.click();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
        notify('文件已生成，请查看浏览器下载。');
    }

    function exportPackage() {
        const originals = $('#include-originals').checked;
        const entries = [
            ['README.txt', 'DocLens 合成示例共享包。打开 report.md 阅读。此包采用原型格式。'],
            ['manifest.json', JSON.stringify({schema: 'doclens-ui-demo/2', synthetic: true, originals, documents: documents.length}, null, 2)],
            ['project.json', JSON.stringify({project, keywords: state.keywords, notes: state.notes, documents: documents.map(doc => ({
                ...doc, blocks: doc.blocks.map(({section, location, text}) => ({section, location, text}))
            }))}, null, 2)],
            ['report.md', report()]
        ];
        if (originals) documents.forEach(doc => entries.push([`originals/${doc.id}.md`, doc.blocks.map(block => block.text).join('\n\n')]));
        download('DocLens-共享演示.zip', window.createStoredZip(entries), 'application/zip');
    }

    const actions = {
        'keyword-add': () => editKeyword(false),
        'keyword-edit': () => editKeyword(true),
        'keyword-select': element => selectKeyword(element.dataset.term),
        'keyword-remove': () => openDialog('删除关键词', `<p>从列表移除「${escape(state.active)}」。已保存的引用仍可查看。</p>`, () => {
            state.keywords = state.keywords.filter(item => item !== state.active);
            selectKeyword(state.keywords[0] || '');
        }, '删除'),
        scope: chooseScope,
        'more-hits': element => {
            const group = matches().find(item => item.doc.id === element.dataset.doc);
            const currentLimit = displayedHits.get(group.doc.id) || hitPageSize;
            displayedHits.set(group.doc.id, currentLimit + hitPageSize);
            const panel = element.closest('details');
            panel.innerHTML = sourceGroup(group);
            (panel.querySelector('[data-action="more-hits"]') || panel.querySelector('summary')).focus({preventScroll: true});
        },
        mode: element => { mode = element.dataset.mode; render(); },
        'ai-preview': previewAnalysis,
        'model-settings': () => openDialog('云端模型设置', `<p class="callout">原型使用示例配置。请在正式应用配置服务与凭据。</p>
            <label for="demo-api">API 地址</label><input class="input mb-3" id="demo-api" value="https://api.example.invalid/v1/chat/completions" readonly>
            <label for="demo-model">模型</label><input class="input" id="demo-model" value="用途分析示例模型" readonly>`, () => {}, '关闭设置'),
        'dialog-close': () => $('#dialog').close(),
        'file-select': () => $('#file-input').click(),
        'preview-doc': element => { previewDoc = documentFor(element.dataset.doc); $('#library-preview').innerHTML = libraryPreview(previewDoc); },
        cite: element => cite(refFor(element.dataset.ref, element.dataset.term ?? state.active)),
        'note-add': () => { if (mayLeaveNote()) { noteDirty = false; newNote(); persist(); render(); } },
        'note-select': element => { if (mayLeaveNote()) { noteDirty = false; state.noteId = element.dataset.id; persist(); render(); } },
        'note-save': saveNote,
        'note-delete': () => openDialog('删除笔记', '<p>删除当前演示笔记和它的关联引用？</p>', () => {
            state.notes = state.notes.filter(note => note.id !== state.noteId);
            state.noteId = state.notes[0]?.id || '';
            noteDirty = false;
            persist();
            render();
        }, '删除笔记'),
        'citation-remove': element => {
            selectedNote().citations.splice(Number(element.dataset.index), 1);
            element.closest('.citation-row').remove();
            all('[data-action="citation-remove"]').forEach((control, index) => { control.dataset.index = index; });
            $('.notes-grid aside:last-child .badge-label').textContent = `${selectedNote().citations.length} 条`;
            $('.note-select[aria-pressed=true] small').textContent = `${selectedNote().citations.length} 条引用`;
            persist();
        },
        'note-export': () => download('DocLens-笔记.md', noteMarkdown({...selectedNote(), title: $('#note-title').value, body: $('#note-body').value}), 'text/markdown'),
        'report-export': () => download('DocLens-研究报告.md', report(), 'text/markdown'),
        'zip-export': exportPackage
    };

    document.body.innerHTML = shell();
    if (params.get('sample') === '1' && mode === 'ai') analysis = matches().flatMap(group => group.refs.slice(0, 1)).map(refKey);
    render();
    if (page === 'evidence' && location.hash) requestAnimationFrame(() => document.getElementById(location.hash.slice(1))?.scrollIntoView({block: 'nearest'}));

    document.addEventListener('click', event => {
        const element = event.target.closest('[data-action]');
        if (element) actions[element.dataset.action]?.(element);
    });

    document.addEventListener('input', event => {
        if (['note-title', 'note-body'].includes(event.target.id)) {
            noteDirty = true;
            $('#note-status').textContent = '未保存';
        }
    });

    document.addEventListener('change', async event => {
        const element = event.target;
        if (element.matches('[data-side]')) {
            const side = Number(element.dataset.side);
            pair[side] = element.value;
            if (pair[side][0] === pair[1 - side]?.[0]) pair[1 - side] = null;
            render();
            $(`#${element.id}`).focus();
        }
        if (element.id === 'include-originals') {
            const list = $('#package-list');
            const base = list.textContent.split('\noriginals/')[0];
            list.textContent = base + (element.checked ? `\noriginals/     ${documents.length} 份示例文本` : '');
        }
        if (element.name === 'clip') {
            const selected = all('#dialog [name="clip"]:checked').length;
            const total = all('#dialog [name="clip"]').length;
            $('#ai-selection-summary').textContent = `已选 ${selected} / ${total} 个命中片段 · 每次最多 ${maxAnalysisBlocks} 个`;
            $('#send-error').textContent = '';
        }
        if (element.id === 'file-input') await previewLocalFiles(element.files);
    });

    async function previewLocalFiles(files) {
        const messages = [];
        for (const file of files) {
            if (!/\.(txt|md|markdown)$/i.test(file.name)) {
                messages.push(`${file.name}：正式桌面应用解析，当前可查看下方预置示例。`);
                continue;
            }
            if (file.size > 10 * 1024 * 1024) {
                messages.push(`${file.name}：文件超过 10 MiB。`);
                continue;
            }
            try {
                const content = new TextDecoder('utf-8', {fatal: true}).decode(await file.arrayBuffer());
                if ([...content].length > 100000) {
                    messages.push(`${file.name}：正文超过 100,000 字符。`);
                    continue;
                }
                $('#library-preview').innerHTML = `<h3>${escape(file.name)}</h3><pre class="local-preview">${escape(content)}</pre>`;
                messages.push(`${file.name}：临时预览，不加入合成比较数据。`);
            } catch {
                messages.push(`${file.name}：无法读取为 UTF-8 文本。`);
            }
        }
        $('#import-results').textContent = messages.join('\n');
    }

    window.addEventListener('beforeunload', event => {
        if (!noteDirty) return;
        event.preventDefault();
        event.returnValue = '';
    });
})();
