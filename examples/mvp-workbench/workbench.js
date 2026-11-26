/* Local, synthetic interaction prototype. No embedding or model inference is performed. */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clone = x => JSON.parse(JSON.stringify(x));
  const key = 'doclens-workbench-prototype-v1';
  const initial = () => ({schema:'doclens-workbench-demo/1', docs:clone(window.DOC_DEMO), dimensions:clone(window.MATRIX_DEMO), noteTitle:'训练设置与实验主体核对', noteBody:'# 比较要点\n\nA 与 C 都使用 ResNet-50 和 CIFAR-10，但训练轮次不同。\n\nB 的相关工作中提到 100 轮，本文实际使用 MobileNetV3，训练 80 轮。不能把他人的设置当作本文设置。\n\n- 核对实验主体\n- 保留数据集与训练预算\n- 不直接据准确率判断方法优劣', citations:[{doc:'a',block:1}], reviews:{}, stale:false, missing:false, offline:true});
  let db = initial(), storageOK = true;
  try { const stored = localStorage.getItem(key); if (stored) db = validate(JSON.parse(stored)); } catch { storageOK = false; }
  let page = 'matrix', side = 'evidence', selected = {doc:'a',block:1,field:'训练轮次',highlight:'50 epochs'};
  let searchMode = 'keyword', query = 'ResNet-50', searched = false, level = 'entity', discoverMode = 'auto';
  let selection = 'epochs:a', reader = 'a', readerBlock = 1, saveTimer, toastTimer, taskTimer;
  let sourceTask = '', relatedScope = ['a','b','c'], activeNoteSaved = true;
  let jobs = [{id:1,name:'自定义维度比较',status:'已完成',progress:100}];
  const labels = {project:'项目工作台',library:'文档库',search:'跨文档检索',discover:'关联发现',matrix:'结构化比较',version:'版本比对',notes:'研究笔记',settings:'系统设置',reader:'原文阅读',tasks:'后台任务'};
  const paths = {
    project:'M3 4h18v16H3zM3 9h18M9 9v11', library:'M5 3h10l4 4v14H5zM15 3v5h5M8 12h8M8 16h6',
    search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0', discover:'M7 7l10 1M7 7l5 11M17 8l-5 10M9 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0M20 8a2 2 0 1 1-4 0 2 2 0 0 1 4 0M14 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
    matrix:'M3 4h18v16H3zM3 10h18M10 4v16M16 4v16',version:'M4 4h6v16H4zM14 4h6v16h-6zM6 9h2M16 14h2',
    notes:'M4 3h16v14l-4 4H4zM15 21v-5h5M8 8h8M8 12h6',settings:'M4 7h16M4 17h16M8 4v6M16 14v6',
    plus:'M12 4v16M4 12h16',close:'M6 6l12 12M6 18L18 6',check:'M4 12l5 5L20 6',book:'M12 5v16M3 4h4l5 2 5-2h4v15h-5l-4 2-4-2H3z',
    panel:'M3 4h18v16H3zM15 4v16',export:'M12 16V3M7 8l5-5 5 5M4 14v7h16v-7',clock:'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
    shield:'M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 12l3 3 5-6',link:'M9 15l6-6M9 7l2-2a5 5 0 0 1 7 7l-2 2M8 10l-2 2a5 5 0 0 0 7 7l2-2'
  };
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.library}"/></svg>`;
  const doc = id => db.docs.find(d => d.id === id);
  const refKey = r => `${r.doc}:${r.block}`;
  const badge = (text,cls='') => `<span class="tag ${cls}">${esc(text)}</span>`;
  function validate(x) {
    if (x.schema !== 'doclens-workbench-demo/1' || !Array.isArray(x.docs) || !Array.isArray(x.dimensions) || !Array.isArray(x.citations) || !x.reviews || typeof x.reviews !== 'object') throw Error('不是此原型支持的演示包');
    if (x.docs.length < 4 || x.docs.length > 30 || x.dimensions.length > 10 || x.citations.length > 100 || typeof x.noteBody !== 'string' || x.noteBody.length > 20000 || typeof x.noteTitle !== 'string' || x.noteTitle.length > 100) throw Error('演示包字段或数量超限');
    const ids = new Set();
    for (const d of x.docs) {
      if (!/^[a-z0-9-]{1,50}$/.test(d.id) || ids.has(d.id) || typeof d.title !== 'string' || d.title.length > 150 || typeof d.format !== 'string' || !Array.isArray(d.sections) || d.sections.length > 50) throw Error('文档结构无效');
      ids.add(d.id);
      for (const s of d.sections) if (typeof s.title !== 'string' || typeof s.text !== 'string' || s.text.length > 100000) throw Error('正文结构无效');
    }
    if (!['a','b','c','d'].every(id=>ids.has(id))) throw Error('演示基准文档不完整');
    for (const r of x.dimensions) if (!/^[a-z0-9-]{1,50}$/.test(r.id) || typeof r.title !== 'string' || r.title.length>100 || !Array.isArray(r.values) || !Array.isArray(r.blocks) || !Array.isArray(r.status) || r.values.length!==3 || r.blocks.length!==3 || r.status.length!==3 || !r.values.every(v=>typeof v==='string' && v.length<500) || !r.status.every(v=>typeof v==='string' && v.length<100) || !r.blocks.every((v,i)=>v===null || (Number.isInteger(v)&&v>=0&&v<x.docs.find(d=>d.id===['a','b','c'][i]).sections.length))) throw Error('比较维度结构无效');
    for (const r of x.citations) if (!Number.isInteger(r.block) || r.block<0 || !x.docs.find(d=>d.id===r.doc)?.sections[r.block]) throw Error('笔记引用无效');
    x.offline = x.offline !== false; x.stale = !!x.stale; x.missing = !!x.missing;
    return x;
  }
  function save() { try { localStorage.setItem(key, JSON.stringify(db)); storageOK = true; activeNoteSaved = true; } catch { storageOK = false; activeNoteSaved = false; } updateStatus(); }
  function toast(message) { $('#toast').textContent = message; $('#toast').style.display='block'; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('#toast').style.display='none',3200); }
  function updateStatus() { const el = $('#save-status'); if(el) el.textContent = storageOK ? (activeNoteSaved?'已保存到此浏览器':'正在保存笔记…') : '本地保存不可用，请导出备份'; }
  function navigate(next) { if (!labels[next]) return; page=next; render(); }
  const navButton = (p,label) => `<button data-page="${p}" class="${page===p?'active':''}" title="${labels[p]}" aria-label="${labels[p]}" ${page===p?'aria-current="page"':''}>${icon(p)}<span>${label}</span></button>`;
  function render() {
    const old = $('.shell'); const classes=old ? old.className : 'shell';
    $('#app').innerHTML = `<div class="${classes}">
      <header class="titlebar"><div class="wordmark"><span class="logo">D</span>DocLens</div><span class="divider"></span><span class="project-name">视觉表征学习研究</span>${badge('交互原型 · 合成资料','blue')}<div class="right row"><button class="quiet compact" data-action="toggle-resources" title="折叠或展开资源面板">${icon('panel')}</button><button class="quiet compact" data-action="toggle-evidence" title="折叠或展开证据面板">${icon('book')}</button><button class="compact" data-action="share">${icon('export')} 导出与分享</button></div></header>
      <div class="body"><nav class="rail" aria-label="主要功能">${navButton('project','项目')}${navButton('library','文档')}${navButton('search','检索')}${navButton('discover','关联')}${navButton('matrix','比较')}${navButton('notes','笔记')}<div class="bottom">${navButton('settings','设置')}</div></nav>
      <aside class="resources"><div class="resource-heading"><strong>研究资源</strong><small>当前项目</small></div><div class="project-card"><strong>视觉表征学习研究</strong><br><span>${db.docs.length} 份文档 · 本地项目</span></div><div class="resource-label">文档库 <button class="quiet compact" data-action="import" aria-label="导入文档">${icon('plus')}</button></div>${db.docs.map(d=>`<button class="doc-link" data-reader="${esc(d.id)}"><span class="file-type ${esc(d.format)}">${esc(d.format)}</span><span><span class="name">${esc(d.title)}</span><small>${esc(d.author)} · ${esc(d.year)}</small></span></button>`).join('')}<div class="resource-label" style="margin-top:23px">分析任务 ${badge('3')}</div>${['search','discover','matrix','version'].map(p=>`<button class="task-link ${page===p?'active':''}" data-page="${p}">${icon(p)} ${labels[p]}</button>`).join('')}<div class="resource-label" style="margin-top:23px">研究成果</div><button class="task-link" data-page="notes">${icon('notes')} 训练设置核对笔记</button><div class="resource-foot">${icon('shield')} 本地优先<br>示例分析无需网络连接<br><button class="quiet compact" data-action="toggle-resources">折叠资源面板</button></div></aside>
      <main class="workspace"><div class="tabs">${['matrix','search','discover','reader','notes'].map(p=>`<button data-page="${p}" class="${page===p?'active':''}">${icon(p)} ${labels[p]}</button>`).join('')}</div><div id="main-view" style="display:contents">${view()}</div></main>
      <aside class="evidence" aria-label="统一证据面板"><div class="resize-handle" title="拖动调整证据面板宽度"></div><div class="side-tabs">${[['evidence','原文证据'],['outline','章节'],['note','笔记']].map(([k,l])=>`<button data-side="${k}" class="${side===k?'active':''}">${l}</button>`).join('')}<button class="quiet" style="margin-left:auto" data-action="toggle-evidence" aria-label="关闭证据面板">×</button></div><div class="side-content">${sideView()}</div></aside></div>
      <footer class="statusbar"><span><i class="circle"></i>${db.offline?'离线模式':'外部服务演示模式'}</span><span id="save-status"></span><span class="optional">${db.stale?'1 项结果待更新':'结果绑定导入版本'}</span><span class="push"></span><button data-page="tasks">${icon('clock')} 后台任务 ${jobs.filter(j=>j.status==='执行中').length || ''}</button><span>原型 v1.0</span></footer></div>`;
    updateStatus(); wireResize();
    if(page==='reader') setTimeout(()=>document.querySelector(`[data-block="${readerBlock}"]`)?.scrollIntoView({block:'center'}),30);
  }
  function heading(title,desc,tools='') { return `<header class="workspace-head"><div class="crumb">视觉表征学习研究 / ${labels[page]}</div><h1>${title}</h1><p>${desc}</p>${tools?`<div class="toolbar">${tools}</div>`:''}</header>`; }
  function view() {
    if(page==='matrix') return matrixView();
    if(page==='search') return searchView();
    if(page==='discover') return discoveryView();
    if(page==='reader') return readerView();
    if(page==='library') return libraryView();
    if(page==='notes') return notesView();
    if(page==='version') return versionView();
    if(page==='settings') return settingsView();
    if(page==='tasks') return tasksView();
    return projectView();
  }
  function matrixView() {
    return heading('把研究放在一起比较','选择单元格，在右侧核对原文与实验主体。',`<button data-action="scope">${icon('library')} 3 份比较文档</button><button data-action="dimension">${icon('plus')} 添加比较维度</button><span class="push"></span>${badge(db.stale?'待更新':'示例结果',db.stale?'amber':'blue')}<button data-action="edit-cell">编辑所选结果</button><button class="primary" data-action="run-matrix">${db.stale?'重新分析':'开始比较'}</button>`) + `<div class="content">${sourceTask?`<div class="notice">由${esc(sourceTask)}转换，已复用文档范围与来源。新任务不会覆盖原任务。</div>`:''}${db.stale?`<div class="notice amber">检测到来源变化，当前结果已标记过期。旧结果继续保留，由你决定是否重新分析。<button class="quiet compact" data-action="missing-source">演示旧原文不可用</button></div>`:''}<div class="section-line"><div class="row"><h2>文献比较矩阵</h2>${badge(`${db.dimensions.length} 个维度`)}</div><small>示例数据 · 点击查看证据</small></div><div class="matrix-wrap"><table class="matrix"><thead><tr><th>比较维度<small>自定义提取目标</small></th>${['a','b','c'].map(id=>`<th>${esc(doc(id).title)}<small>${esc(doc(id).author)} · ${doc(id).year}</small></th>`).join('')}</tr></thead><tbody>${db.dimensions.map(r=>`<tr><td>${esc(r.title)}<small>${esc(r.type)}</small></td>${['a','b','c'].map((id,i)=>`<td><button class="cell ${selection===`${r.id}:${id}`?'selected':''}" data-cell="${r.id}:${id}"><span>${esc(r.values[i])}</span><small><i class="dot"></i>${esc(r.status[i])}${r.blocks[i]!==null?' · 原文证据':''}</small></button></td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="insight">${icon('link')}<div><h3>共同点与差异</h3><p>A 与 C 均采用 ResNet-50 和 CIFAR-10，训练轮次分别为 50 与 200。B 的相关工作提及 ResNet-50，本文采用的是 MobileNetV3。实验条件不同，不能仅凭准确率数值判断优劣。</p></div></div><div class="row"><button class="quiet compact" data-action="to-search">按所选维度继续检索</button><button class="quiet compact" data-action="note-result">保存比较要点到笔记</button></div></div>`;
  }
  function searchHits() {
    const ids = relatedScope.length ? relatedScope : db.docs.map(d=>d.id);
    if(searchMode==='semantic') return /训练|epoch|train|预算|轮次|设置/i.test(query) ? ['a','b','c'].filter(id=>ids.includes(id)).map(id=>({doc:id,block:id==='b'?2:1})) : [];
    const q=query.trim().toLowerCase(); if(!q) return [];
    return db.docs.filter(d=>ids.includes(d.id)).flatMap(d=>d.sections.flatMap((s,i)=>s.text.toLowerCase().includes(q)?[{doc:d.id,block:i}]:[]));
  }
  function searchView() {
    const hits=searchHits();
    return heading('从文档里找回答','关键词查找可实际运行；语义模式演示“训练预算”查询的预置召回。',`<form id="search-form" class="search-box"><input id="query" aria-label="检索词或自然语言" value="${esc(query)}" placeholder="输入关键词或描述想找的内容"><button class="primary" type="submit">${icon('search')} 检索</button></form><div class="segmented"><button data-search-mode="keyword" class="${searchMode==='keyword'?'active':''}">关键词</button><button data-search-mode="semantic" class="${searchMode==='semantic'?'active':''}">语义检索 · 示例</button></div><button data-action="scope">范围：${relatedScope.length} 份文档</button><span class="push"></span><button data-action="search-to-discover">转为关联发现</button><button data-action="search-to-matrix">转为结构化比较</button>`) + `<div class="content"><div class="section-line"><h2>${hits.length} 条相关片段</h2><small>${searchMode==='semantic'?'预置语义结果，未运行向量模型':'按文档与原文顺序'} · 索引演示</small></div>${!hits.length?`<div class="notice">${searchMode==='semantic'?'此原型没有该查询的语义示例。可尝试“训练预算”，或切换关键词查找。':'没有找到对应文字，请修改关键词或扩大文档范围。'}</div>`:''}${hits.map((r,i)=>`<article class="result"><div class="row">${badge(doc(r.doc).format)}<small>${esc(doc(r.doc).title)} / ${esc(doc(r.doc).sections[r.block].title)}</small></div><h3>${searchMode==='semantic'?'与训练预算相关的实验设置':esc(query)+' 的原文片段'}</h3><p class="snippet">${highlight(doc(r.doc).sections[r.block].text,searchMode==='keyword'?query:'epochs')}</p><div class="actions"><button class="compact" data-evidence="${refKey(r)}">查看原文证据</button><button class="compact quiet" data-cite="${refKey(r)}">加入笔记</button>${r.doc==='b'&&r.block===1?badge('相关工作提及','amber'):badge('待人工核对')}</div></article>`).join('')}</div>`;
  }
  function discoveryView() {
    const content={same:{title:'共享的实验描述',desc:'A、C 的文本片段都包含 “We evaluate”，仅相同短语不足以构成研究关联。此卡演示文本匹配后的人工作业。',members:['a','c'],block:1,status:'相同短语 · 需排除通用表达'},similar:{title:'都讨论了实际部署评估的不足',desc:'A 提到尚未测试高分辨率与部署延迟，B 提到尚未在真实移动设备测延迟。相关语义来自预置示例，不等于相同结论。',members:['a','b'],block:3,status:'相似内容 · 待人工确认'},entity:{title:'ResNet-50',desc:'A、C 在本文实验中使用；B 仅在相关工作中提及，并明确未在本文实验中采用。共同出现不能一律归为共同使用。',members:['a','b','c'],block:1,status:'研究方法 · 已关联 3 份文档'},topic:{title:'视觉表征与受限训练预算',desc:'这组资料都讨论视觉编码，但研究主体、数据集与训练轮次不同。主题为示例归纳，一个文档可以属于多个主题。',members:['a','b','c'],block:0,status:'基础主题 · 允许多主题'}}[level];
    return heading('发现文档之间的联系','从相同文本到共同主题，逐层展开证据。',`<button class="primary" data-action="run-discovery">开始发现</button><button data-action="discover-to-matrix">转为结构化比较</button><span class="push"></span>${badge('预置发现结果','blue')}`) + `<div class="content"><div class="mode-grid"><button class="mode-option ${discoverMode==='auto'?'active':''}" data-discover-mode="auto"><strong>自动发现</strong><small>只选择文档，发现潜在共同点</small></button><button class="mode-option ${discoverMode==='directed'?'active':''}" data-discover-mode="directed"><strong>定向发现</strong><small>选择文档及要发现的关联类型</small></button></div><div class="level-tabs">${[['same','相同文本'],['similar','相似内容'],['entity','共同实体'],['topic','基础主题']].map(([k,l])=>`<button class="${level===k?'active':''}" data-level="${k}">${l}</button>`).join('')}</div><article class="relation">${badge(content.status,'blue')}<h3>${content.title}</h3><p>${content.desc}</p><div class="members">${content.members.map(id=>`<span class="tag">${esc(doc(id).title)}</span>`).join('')}</div><div class="row"><button class="compact" data-evidence="a:${content.block}">核对原文</button><button class="compact" data-action="confirm-relation">确认关联</button><button class="quiet compact" data-action="correct-relation">修正关联</button></div></article>${level==='entity'?`<article class="relation">${badge('数据集 · 共同使用','green')}<h3>CIFAR-10</h3><p>A、C 用于本文实验。B 实际使用 CIFAR-100；二者不合并为同一实体。</p><div class="row"><button class="compact" data-evidence="c:1">核对实验设置</button><button class="quiet compact" data-cite="c:1">加入笔记</button></div></article>`:''}<div class="notice">关联候选、主题和语义角色使用合成资料预置，人工操作可以试用。正式能力及准确性需通过 E03 验证。</div></div>`;
  }
  function libraryView() { return heading('项目文档','管理研究来源，保留版本与解析范围。',`<button class="primary" data-action="import">${icon('plus')} 导入 MD / TXT</button><button data-action="import-help">PDF / DOCX 导入说明</button><button data-action="change-source">演示文档更新</button>`) + `<div class="content"><div class="section-line"><h2>${db.docs.length} 份文档</h2>${badge(db.stale?'检测到变化':'已解析的示例快照',db.stale?'amber':'green')}</div><table class="library-table"><thead><tr><th>文档名称</th><th>格式</th><th>解析状态</th><th>操作</th></tr></thead><tbody>${db.docs.map(d=>`<tr><td><strong>${esc(d.title)}</strong><br><small>${esc(d.author)}</small></td><td>${esc(d.format)}</td><td>${badge(d.id==='a'&&db.stale?'已变化 · 结果过期':d.format==='PDF'||d.format==='DOCX'?'示例正文':'可阅读',d.id==='a'&&db.stale?'amber':'green')}</td><td><button class="compact" data-reader="${esc(d.id)}">阅读</button></td></tr>`).join('')}</tbody></table><div class="notice" style="margin-top:24px">PDF / DOCX 当前展示合成提取正文；真实解析、PDF 原貌及章节识别需接入正式应用。本原型可导入 UTF-8 的 MD / TXT，在文档库阅读与关键词检索。</div></div>`; }
  function readerView() {
    const d=doc(reader)||db.docs[0];
    return heading(esc(d.title),'保留分析任务，在同一工作环境中核对原文。',`<button data-page="matrix">返回比较矩阵</button><button data-action="show-outline">章节导航</button>${badge(d.format)}${badge('导入版本 v1')}`)+`<div class="content reading"><h2>${esc(d.title)}</h2><small>${esc(d.author)} · ${esc(d.year)} · ${d.format==='PDF'||d.format==='DOCX'?'合成提取文本，非原貌':'文本阅读'}</small>${d.id==='a'&&db.missing?'<div class="notice amber">旧版本原文不可定位。历史结果仍保留，不能跳转新版替代。</div>':d.sections.map((s,i)=>`<section data-block="${i}" class="${i===readerBlock?'target':''}"><h3>${esc(s.title)}</h3><p>${esc(s.text)}</p><button class="compact quiet" data-cite="${d.id}:${i}">摘录到笔记</button></section>`).join('')}</div>`;
  }
  function notesView() { return heading('把发现整理为研究笔记','Markdown 与多来源证据一起保存，支持继续编辑。',`<button data-action="new-note">新建笔记</button><button data-action="download-md">导出 Markdown</button><span class="push"></span>${badge(`${db.citations.length} 条证据`,'blue')}`)+`<div class="content note-editor"><input id="note-title" value="${esc(db.noteTitle)}" aria-label="笔记标题"><textarea id="note-body" aria-label="Markdown 笔记正文">${esc(db.noteBody)}</textarea><div class="note-counter">在此浏览器自动保存；分享前请确认正文与证据内容。</div><h3 style="margin-top:26px">关联证据</h3>${db.citations.map(r=>`<div class="citation"><div class="row between"><strong>${esc(doc(r.doc).title)} / ${esc(doc(r.doc).sections[r.block].title)}</strong><button class="quiet compact" data-evidence="${refKey(r)}">查看原文</button></div>${esc(doc(r.doc).sections[r.block].text)}</div>`).join('')}</div>`; }
  function versionView() { return heading('查看新旧版本的变化','复用已有版本比对工作流；此处演示预置的文本修订。',`<button data-action="quick-diff">临时快速比对</button><button data-action="version-evidence">定位变化证据</button><span class="push"></span>${badge('示例版本 v1 / v2','blue')}`)+`<div class="content"><div class="diff-grid"><div class="diff-column"><h3>旧版本 v1 / 3.1 实验设置</h3>We use ResNet-50 as the backbone and train it for <del>50 epochs</del>.<br><br>The classification accuracy reaches <del>91.5%</del>.</div><div class="diff-column"><h3>新版本 v2 / 3.1 实验设置</h3>We use ResNet-50 as the backbone and train it for <ins>100 epochs</ins>.<br><br>The classification accuracy reaches <ins>92.1%</ins>.</div></div><div class="insight">${icon('version')}<div><h3>2 处数值修改</h3><p>训练轮次 50 → 100，准确率 91.5% → 92.1%。数值变化由合成示例给出，不据此推断因果或研究有效性。</p></div></div><button data-action="note-diff">保存变化摘要到笔记</button></div>`; }
  function projectView() { return heading('继续你的研究','以研究项目组织文档、分析任务与成果。',`<button class="primary" data-page="library">导入与管理文档</button><button data-action="quick-diff">临时快速比对</button><button data-action="import-bundle">导入分享包</button>`)+`<div class="content"><div class="overview-intro"><small>当前研究项目</small><h2>视觉表征学习研究</h2><p class="muted">从不同论文的模型、数据与训练设置出发，建立可核对的比较。</p><div class="row">${badge(`${db.docs.length} 份文档`)}${badge('1 条研究笔记')}${badge(db.stale?'有结果待更新':'历史成果已保存',db.stale?'amber':'green')}</div></div><div class="quick-list">${[['search','跨文档检索','从术语或自然语言出发，找到原文片段'],['discover','关联发现','发现共同实体、相似内容与基础主题'],['matrix','结构化比较','自定义维度，把多篇资料放进同一矩阵']].map(([p,t,d])=>`<button data-page="${p}">${icon(p)}<div><strong>${t}</strong><small>${d}</small></div></button>`).join('')}</div><h3>最近任务</h3>${jobs.map(j=>`<div class="row between" style="padding:12px 0"><span>${esc(j.name)}</span>${badge(j.status,j.status==='已完成'?'green':'blue')}</div>`).join('')}</div>`; }
  function settingsView() { return heading('让资料保持在你的控制之下','外部服务始终需要明确授权，本原型不会发送任何文档。')+`<div class="content"><div class="setting-row"><div class="grow"><h3>离线模式</h3><p>管理、阅读、关键词查找、笔记和导出可本地使用。</p></div><input type="checkbox" id="offline-toggle" aria-label="离线模式" ${db.offline?'checked':''}></div><div class="setting-row"><div class="grow"><h3>本地模型</h3><p>4B / 8B 为待实验候选；原型未加载模型。</p></div>${badge('未接入')}</div><div class="setting-row"><div class="grow"><h3>外部服务授权</h3><p>先查看实际范围，再决定是否发送。没有静默回退。</p></div><button data-action="external-preview">查看授权流程</button></div><div class="setting-row"><div class="grow"><h3>本地数据与恢复</h3><p>演示笔记存于当前浏览器，建议导出分享包备份。</p></div><button data-action="share">导出备份</button></div><div class="setting-row"><div class="grow"><h3>重置演示项目</h3><p>清除本原型的笔记、导入文本和人工状态，不影响桌面应用。</p></div><button data-action="reset">重置</button></div><div class="notice" style="margin-top:24px">本地语义检索、开放实体、主题与自定义提取尚需 E01–E05 技术验证；当前界面展示操作方式，不表示已经实现完整 MVP。</div></div>`; }
  function tasksView() { return heading('后台任务','取消与失败重试均为本地交互演示，历史结果继续保留。',`<button data-action="demo-failure">演示一次任务失败</button>`)+`<div class="content">${jobs.map(j=>`<article class="job"><div class="row between"><h3>${esc(j.name)}</h3>${badge(j.status,j.status==='执行失败'?'amber':j.status==='已完成'?'green':'blue')}</div><div class="progress"><span style="width:${j.progress}%"></span></div><div class="row between"><small>${j.progress}% · ${j.status==='执行失败'?'模拟模型不可用；可重试，不覆盖旧结果':'预置演示，不执行模型推理'}</small>${j.status==='执行中'?`<button class="compact" data-cancel="${j.id}">取消任务</button>`:['已取消','执行失败'].includes(j.status)?`<button class="compact" data-retry="${j.id}">重试</button>`:''}</div></article>`).join('')}</div>`; }
  function highlight(text,term) { if(!term) return esc(text); const i=text.toLowerCase().indexOf(term.toLowerCase()); return i<0?esc(text):esc(text.slice(0,i))+`<mark>${esc(text.slice(i,i+term.length))}</mark>`+esc(text.slice(i+term.length)); }
  function sideView() {
    const d=doc(selected.doc)||doc('a'), s=d.sections[selected.block];
    if(side==='outline') return `<div class="source-label">${esc(d.title)} · 章节导航</div>${d.sections.map((s,i)=>`<button class="task-link" data-outline="${d.id}:${i}">${esc(s.title)}</button>`).join('')}`;
    if(side==='note') return `<div class="side-notes"><h3>${esc(db.noteTitle)}</h3><p>${esc(db.noteBody.slice(0,180))}</p><button data-page="notes">继续编辑笔记</button><p>${db.citations.length} 条来源证据</p></div>`;
    if(selected.block===null || !s) return `<div class="source-label">${esc(selected.field)}</div><h3>未找到可引用的原文</h3><p class="muted small">保留缺失状态，不用其他文档的内容补齐。可以按这个维度继续检索。</p><button data-action="to-search">继续检索</button>`;
    const review=db.reviews[refKey(selected)];
    if(d.id==='a'&&db.missing) return `<div class="source-label">历史证据</div>${badge('证据失效','amber')}<h3 style="margin-top:20px">旧版本原文不可定位</h3><p class="small">历史结果仍然保存。旧源文件已被覆盖或删除，不能用新版中的相近文字代替原位置。</p><button data-action="restore-source">恢复演示旧版</button>`;
    return `<div class="source-label">比较维度 / ${esc(selected.field || '原文摘录')}</div>${badge('导入版本 v1','blue')}<h2 class="source-title">${esc(d.title)}</h2><div class="source-meta">${esc(d.author)} · ${d.year}<br>${esc(s.title)} · 正文块 ${selected.block+1}<br>使用真实的合成文本区间</div><div class="quote">${highlight(s.text,selected.highlight)}</div><div class="source-actions"><button data-action="open-original">${icon('book')} 打开原文</button><button data-action="cite-current">${icon('plus')} 加入笔记</button></div><div class="source-status">${icon('check')} 引文存在于当前示例快照</div><div class="review-box"><h3>这段原文支持当前判断吗？</h3><div class="row"><button class="compact ${review==='confirmed'?'primary':''}" data-review="confirmed">确认支持</button><button class="compact ${review==='rejected'?'primary':''}" data-review="rejected">不支持</button></div><p>${review==='confirmed'?'已记录人工确认；原始机器结果仍保留。':review==='rejected'?'已标记不支持，建议修正结果或更换证据。':'引用存在不代表结论正确，请核对主体、实验条件与上下文。'}</p></div>`;
  }
  function selectEvidence(id,block,field='原文摘录',term='') { if(!doc(id)?.sections[block]) return; selected={doc:id,block,field,highlight:term}; side='evidence'; $('.shell')?.classList.remove('evidence-hidden'); render(); if(innerWidth<=760) $('.evidence').classList.add('mobile-open'); }
  function addCitation(id,block) { if(!doc(id)?.sections[block]) return; if(!db.citations.some(r=>r.doc===id&&r.block===block)) db.citations.push({doc:id,block}); save(); toast('已加入研究笔记，保留文档与原文来源'); }
  function modal(title,body,footer='') { $('#dialog').innerHTML=`<div class="modal-head"><h2 id="dialog-title">${title}</h2><button class="quiet compact" data-action="close-dialog" aria-label="关闭对话框">${icon('close')}</button></div><div class="modal-body">${body}</div><div class="modal-foot"><button data-action="close-dialog">取消</button>${footer}</div>`; $('#dialog').showModal(); }
  const close = () => $('#dialog').close();
  function shareModal() { modal('导出与分享',`<p>分享包包含文档提取正文、研究笔记、人工状态和比较结果，即使不含 PDF / DOCX 文件，也可能包含敏感内容。</p><div class="notice">本包使用独立演示格式，仅供此原型重新导入，不兼容正式 DocLens 项目。</div><label class="checkline"><input id="share-ack" type="checkbox">我已核对包内正文与笔记，允许导出。</label><div class="row"><button data-action="download-md">Markdown</button><button data-action="download-csv">比较矩阵 CSV</button></div><p class="section-caption">不附原始 PDF / DOCX，不包含密钥和个人绝对路径。</p>`,`<button class="primary" data-action="download-bundle">导出演示分享包</button>`); }
  function runTask(name,fail=false) {
    if(jobs.some(j=>j.status==='执行中')) { toast('已有演示任务执行中，可在后台任务中取消'); return; }
    const job={id:Date.now(),name,status:'执行中',progress:0}; jobs.unshift(job); page='tasks'; render();
    clearInterval(taskTimer); taskTimer=setInterval(()=>{ if(job.status!=='执行中') return clearInterval(taskTimer); job.progress=Math.min(100,job.progress+10); if(fail&&job.progress>=50){job.status='执行失败';clearInterval(taskTimer);} else if(job.progress===100){job.status='已完成';clearInterval(taskTimer); toast('演示任务完成，预置结果已可查看；未运行真实模型');} if(page==='tasks') render(); },400);
  }
  function markdown() { return `# ${db.noteTitle}\n\n> DocLens 交互原型；合成资料与预置分析，不是模型实测结果。\n\n${db.noteBody}\n\n## 来源证据\n\n`+db.citations.map(r=>`### ${doc(r.doc).title} / ${doc(r.doc).sections[r.block].title}\n\n${doc(r.doc).sections[r.block].text}\n`).join('\n'); }
  function download(name,data,type='text/plain;charset=utf-8') { const url=URL.createObjectURL(data instanceof Blob?data:new Blob([data],{type})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000); }
  function openCell(value) { const [row,id]=value.split(':'), r=db.dimensions.find(r=>r.id===row), i=['a','b','c'].indexOf(id); if(!r||i<0)return; selection=value;selected={doc:id,block:r.blocks[i],field:r.title,highlight:r.values[i]};side='evidence';render();if(innerWidth<=760)$('.evidence').classList.add('mobile-open'); }
  document.addEventListener('click',event=>{
    const target=event.target.closest('button'); if(!target)return;
    if(target.dataset.page) return navigate(target.dataset.page);
    if(target.dataset.reader) {reader=target.dataset.reader;readerBlock=0;return navigate('reader');}
    if(target.dataset.side){side=target.dataset.side;return render();}
    if(target.dataset.cell)return openCell(target.dataset.cell);
    if(target.dataset.evidence){const[id,b]=target.dataset.evidence.split(':');return selectEvidence(id,+b);}
    if(target.dataset.cite){const[id,b]=target.dataset.cite.split(':');return addCitation(id,+b);}
    if(target.dataset.outline){const[id,b]=target.dataset.outline.split(':');reader=id;readerBlock=+b;return navigate('reader');}
    if(target.dataset.review){db.reviews[refKey(selected)]=target.dataset.review;save();render();return;}
    if(target.dataset.searchMode){searchMode=target.dataset.searchMode;if(searchMode==='semantic')query='不同论文的训练预算有哪些差异';return render();}
    if(target.dataset.level){level=target.dataset.level;return render();}
    if(target.dataset.discoverMode){discoverMode=target.dataset.discoverMode;return render();}
    if(target.dataset.cancel){const j=jobs.find(j=>j.id===+target.dataset.cancel);if(j)j.status='已取消';clearInterval(taskTimer);render();return toast('任务已取消，旧结果保持可查看');}
    if(target.dataset.retry){const j=jobs.find(j=>j.id===+target.dataset.retry);return runTask(j.name+' · 重试');}
    const action=target.dataset.action;
    if(action==='close-dialog')return close();
    if(action==='toggle-resources')return $('.shell').classList.toggle('sidebar-hidden');
    if(action==='toggle-evidence'){if(innerWidth<=760)return $('.evidence').classList.toggle('mobile-open');return $('.shell').classList.toggle('evidence-hidden');}
    if(action==='share')return shareModal();
    if(action==='import')return $('#import-files').click();
    if(action==='import-bundle')return $('#import-bundle').click();
    if(action==='scope')return modal('选择分析范围',`<p>检索与关联任务可以复用文档范围；比较矩阵使用 A、B、C 的合成示例。</p>${db.docs.map(d=>`<label class="checkline"><input type="checkbox" name="scope" value="${d.id}" ${relatedScope.includes(d.id)?'checked':''}>${esc(d.title)}</label>`).join('')}`,`<button class="primary" data-action="save-scope">使用所选范围</button>`);
    if(action==='save-scope'){const ids=$$('[name=scope]:checked').map(e=>e.value);if(!ids.length)return toast('至少选择一份文档');relatedScope=ids;close();render();return;}
    if(action==='open-original'){reader=selected.doc;readerBlock=selected.block;return navigate('reader');}
    if(action==='cite-current')return addCitation(selected.doc,selected.block);
    if(action==='show-outline'){side='outline';selected.doc=reader;return render();}
    if(action==='dimension')return modal('添加自定义比较维度',`<label class="field">维度名称<input id="dimension-name" maxlength="40" placeholder="例如：推理延迟"></label><label class="field">提取说明<textarea id="dimension-desc" rows="3" placeholder="说明要提取的信息、单位或多值规则"></textarea></label><p>本原型保存维度定义并增加“未找到”行。真实信息提取需接入已验证模型。</p>`,`<button class="primary" data-action="save-dimension">添加维度</button>`);
    if(action==='save-dimension'){const name=$('#dimension-name').value.trim();if(!name)return toast('请输入维度名称');if(db.dimensions.length>=10)return toast('当前演示最多 10 个维度');db.dimensions.push({id:'custom-'+Date.now(),title:name,type:'自定义',description:$('#dimension-desc').value.slice(0,1000),values:['未找到','未找到','未找到'],blocks:[null,null,null],status:['未找到','未找到','未找到']});save();close();return navigate('matrix');}
    if(action==='edit-cell'){const[row,id]=selection.split(':'),r=db.dimensions.find(r=>r.id===row),i=['a','b','c'].indexOf(id);return modal('人工修正比较结果',`<p>${esc(r.title)} / ${esc(doc(id).title)}</p><label class="field">显示值<input id="edited-value" maxlength="200" value="${esc(r.values[i])}"></label><p>人工修正会单独标记；现有原文证据不因编辑而更改。</p>`,`<button class="primary" data-action="save-cell">保存修正</button>`);}
    if(action==='save-cell'){const[row,id]=selection.split(':'),r=db.dimensions.find(r=>r.id===row),i=['a','b','c'].indexOf(id);const value=$('#edited-value').value.trim();if(!value)return toast('请填入结果或明确写“未找到”');r.values[i]=value;r.status[i]='人工修正';save();close();return render();}
    if(action==='run-matrix')return runTask('结构化比较 · 预置演示');
    if(action==='run-discovery')return runTask(`${discoverMode==='auto'?'自动':'定向'}关联发现 · 预置演示`);
    if(action==='demo-failure')return runTask('信息提取失败示例',true);
    if(action==='change-source'){db.stale=true;save();navigate('matrix');return toast('已演示检测到文档变化，结果标记待更新，旧快照仍保留');}
    if(action==='missing-source'){db.missing=true;save();selected.doc='a';selected.block=1;return render();}
    if(action==='restore-source'){db.missing=false;save();return render();}
    if(action==='to-search'){query=selected.field||'训练轮次';sourceTask='结构化比较';return navigate('search');}
    if(action==='search-to-discover'){sourceTask='跨文档检索';return navigate('discover');}
    if(action==='search-to-matrix'){sourceTask='跨文档检索';return navigate('matrix');}
    if(action==='discover-to-matrix'){sourceTask='关联发现';return navigate('matrix');}
    if(action==='note-result'){db.noteBody+='\n\n## 比较要点\nA 与 C 都使用 ResNet-50 与 CIFAR-10，但训练轮次不同；B 使用 MobileNetV3。请结合各自实验条件核对。';addCitation('a',1);addCitation('c',1);save();return navigate('notes');}
    if(action==='note-diff'){db.noteBody+='\n\n## 版本变化（合成演示）\n训练轮次 50 → 100，准确率 91.5% → 92.1%。这不是因果结论。';save();return navigate('notes');}
    if(action==='new-note')return modal('替换当前演示笔记',`<p>原型只保存一条可编辑笔记。请先导出当前笔记，确认后将创建空白笔记，不影响正式应用。</p>`,`<button class="primary" data-action="confirm-new-note">创建空白笔记</button>`);
    if(action==='confirm-new-note'){db.noteTitle='未命名研究笔记';db.noteBody='';db.citations=[];save();close();return render();}
    if(action==='download-md')return download('DocLens-研究笔记.md',markdown());
    if(action==='download-csv'){const cell=x=>{let s=String(x);if(/^[=+\-@\t\r]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};return download('DocLens-比较矩阵.csv','\ufeff'+[['比较维度',...['a','b','c'].map(id=>doc(id).title)],...db.dimensions.map(r=>[r.title,...r.values])].map(r=>r.map(cell).join(',')).join('\r\n'),'text/csv;charset=utf-8');}
    if(action==='download-bundle'){if(!$('#share-ack').checked)return toast('请先核对并确认分享内容');download('DocLens-演示分享包.zip',window.createStoredZip([['manifest.json',JSON.stringify(db,null,2)],['report.md',markdown()]]));toast('已导出演示包，可在项目工作台重新导入');return close();}
    if(action==='import-help')return modal('PDF / DOCX 解析边界','<p>原型展示预置的合成提取正文，不解析真实 PDF / DOCX。可在已有 DocLens 桌面版导入这些格式；新需求中的解析质量与定位需 E01 验证。</p><p>此处可导入 UTF-8 MD / TXT 体验阅读与关键词查找。</p>');
    if(action==='quick-diff')return modal('临时快速比对','<p>无需创建完整项目即可选择新旧版本。当前原型使用合成的两个版本展示双栏差异，不运行正式 Diff 算法。</p>',`<button class="primary" data-action="open-version">查看示例比对</button>`);
    if(action==='open-version'){close();return navigate('version');}
    if(action==='version-evidence')return selectEvidence('a',1,'旧版本训练轮次','50 epochs');
    if(action==='confirm-relation'){db.reviews['relation:'+level]='confirmed';save();return toast('已记录人工确认；预置机器结果仍保留');}
    if(action==='correct-relation')return modal('修正关联',`<label class="field">修正说明<textarea id="relation-correction" rows="4">${esc(db.reviews['correction:'+level]||'')}</textarea></label>`,`<button class="primary" data-action="save-relation">保存修正</button>`);
    if(action==='save-relation'){db.reviews['correction:'+level]=$('#relation-correction').value.slice(0,2000);save();close();return toast('已保存人工修正说明');}
    if(action==='external-preview'){if(db.offline)return modal('当前处于离线模式','<p>离线模式阻止外部服务。可在设置中关闭离线模式，体验授权确认流程；原型仍不会发出网络请求。</p>');return modal('外部分析：发送前确认',`<p>接收方：示例服务（未配置真实地址）<br>模型：示例模型<br>范围：1 份文档、1 个正文块</p><div class="quote">${esc(doc('a').sections[1].text)}</div><p>只演示授权交互；确认后不会发送正文、调用模型或产生费用。</p>`,`<button class="primary" data-action="external-confirm">演示确认发送</button>`);}
    if(action==='external-confirm'){close();return toast('授权流程已演示；没有发送任何网络请求');}
    if(action==='reset')return modal('重置原型数据','<p>将清除本原型的笔记、导入文本、维度与人工状态。请先导出需要保留的内容。</p>',`<button class="primary" data-action="confirm-reset">确认重置</button>`);
    if(action==='confirm-reset'){db=initial();selected={doc:'a',block:1,field:'训练轮次',highlight:'50 epochs'};selection='epochs:a';save();close();return navigate('matrix');}
  });
  document.addEventListener('submit',e=>{if(e.target.id==='search-form'){e.preventDefault();query=$('#query').value.trim();searched=true;render();}});
  document.addEventListener('input',e=>{if(['note-title','note-body'].includes(e.target.id)){db[e.target.id==='note-title'?'noteTitle':'noteBody']=e.target.value.slice(0,e.target.id==='note-title'?100:20000);activeNoteSaved=false;updateStatus();clearTimeout(saveTimer);saveTimer=setTimeout(save,600);}});
  document.addEventListener('change',e=>{if(e.target.id==='offline-toggle'){db.offline=e.target.checked;save();render();}});
  $('#import-files').addEventListener('change',async e=>{
    let count=0;
    for(const f of e.target.files){if(!/\.(md|markdown|txt)$/i.test(f.name)||f.size>500000||db.docs.length>=30){toast('仅支持不超过 500KB 的 MD/TXT，演示最多 30 份');continue;}
      const text=await f.text(); if(db.docs.some(d=>d.title===f.name&&d.sections[0]?.text===text)){toast('已跳过重复文件');continue;}
      db.docs.push({id:'local-'+Date.now()+'-'+count,title:f.name,author:'本地导入',year:'当前',format:/\.txt$/i.test(f.name)?'TXT':'MD',sections:[{title:'导入正文',text:text.slice(0,100000)}]});count++;
    }save();e.target.value='';navigate('library');toast(`已导入 ${count} 份文本，最多预览前 100,000 字符`);
  });
  $('#import-bundle').addEventListener('change',async e=>{
    const file=e.target.files[0];e.target.value='';if(!file)return;
    try{
      if(file.size>2000000)throw Error('演示包最大 2MB');
      const bytes=new Uint8Array(await file.arrayBuffer()),v=new DataView(bytes.buffer),decoder=new TextDecoder('utf-8',{fatal:true});let offset=0,entries=new Map();
      while(offset+30<=bytes.length&&v.getUint32(offset,true)===0x04034b50){
        const method=v.getUint16(offset+8,true),flags=v.getUint16(offset+6,true),size=v.getUint32(offset+18,true),nameLen=v.getUint16(offset+26,true),extra=v.getUint16(offset+28,true),body=offset+30+nameLen+extra;
        if(method!==0||(flags&9)||size>1500000||body+size>bytes.length)throw Error('仅支持本原型导出的未压缩演示包');
        const name=decoder.decode(bytes.slice(offset+30,offset+30+nameLen));
        if(!['manifest.json','report.md'].includes(name)||entries.has(name))throw Error('包内条目无效或重复');
        entries.set(name,decoder.decode(bytes.slice(body,body+size)));offset=body+size;
      }
      if(entries.size!==2||offset+4>bytes.length||v.getUint32(offset,true)!==0x02014b50)throw Error('包不完整');
      const imported=validate(JSON.parse(entries.get('manifest.json')));
      modal('导入演示成果',`<p>包含 ${imported.docs.length} 份提取正文、1 条笔记、${imported.citations.length} 条引用。确认将替换本原型当前演示项目；可先取消并导出备份。</p>`,`<button class="primary" id="apply-import">确认导入</button>`);
      $('#apply-import').onclick=()=>{db=imported;selected={doc:'a',block:1,field:'训练轮次',highlight:'50 epochs'};save();close();navigate('project');toast('演示包已导入；未执行包内任何指令');};
    }catch(error){toast('导入失败，当前项目保留：'+error.message);}
  });
  function wireResize(){const handle=$('.resize-handle');handle.onpointerdown=e=>{handle.setPointerCapture(e.pointerId);handle.onpointermove=ev=>{if(ev.buttons)$('.shell').style.setProperty('--evidence',Math.min(450,Math.max(250,innerWidth-ev.clientX))+'px');};handle.onpointerup=()=>handle.onpointermove=null;};}
  window.addEventListener('pagehide',()=>{clearTimeout(saveTimer);save();});
  window.prototypeDebug={getState:()=>clone(db),getJobs:()=>clone(jobs)};
  render();
})();
