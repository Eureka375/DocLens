"""Offline research snapshots. Evidence always refers to immutable extracted text."""
import base64
from bisect import bisect_right
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import os
from uuid import uuid4
from zipfile import ZipFile, BadZipFile, ZIP_DEFLATED

from .documents import DocumentError, read_document_bytes, parse_snapshot, no_cancel

LIMIT = 100 * 1024 * 1024
TERMS = {
    '数据集': {'MNIST': ['MNIST'], 'CIFAR-10': ['CIFAR-10', 'CIFAR10'],
            'ImageNet': ['ImageNet', 'Image Net'], 'SQuAD': ['SQuAD'],
            'GLUE': ['GLUE'], 'COCO': ['COCO', 'MS COCO']},
    '方法': {'BERT': ['BERT'], 'ResNet': ['ResNet', 'ResNet-50', 'ResNet50'],
           'Transformer': ['Transformer', 'Transformers'],
           'SVM': ['SVM', 'support vector machine', '支持向量机'],
           'Random Forest': ['Random Forest', '随机森林'],
           'CNN': ['CNN', 'convolutional neural network', '卷积神经网络']},
}
PATTERNS = [(kind, name, re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(
    re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')(?![A-Za-z0-9_])', re.I))
    for kind, items in TERMS.items() for name, aliases in items.items()]
MENTION = '仅提及或待核对'
USE = '使用线索'
NEGATIVE = '否定使用'
PRIORITY = {USE: 0, NEGATIVE: 1, MENTION: 2}
CLAUSE_BREAK = re.compile(r'[.!?。！？;；,，\n]|\b(?:but|while|whereas)\b|\band\s+(?=(?:we|our|they|prior|do|does|did|not|never|mention|discuss|use|adopt|employ)\b)|但是|但|而', re.I)
MAX_EVIDENCE = 10_000


def _atomic(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _state(text, section, start, end):
    # Caller supplies one clause; only preceding cues can govern this entity.
    clause = text
    prefix = text[:start]
    if re.search(r'related work|references|相关工作|参考文献', section + ' ' + clause, re.I):
        return MENTION
    if re.search(r'instead of|rather than|而非|而不是', clause, re.I):
        return MENTION
    if re.search(r'\b(?:do(?:es)? not|did not|not|never|without)\b.{0,30}\b(?:use|used|using|adopt|apply|employ)|\bnot\s*$|未(?:使用|采用)|不(?:使用|采用)', prefix, re.I):
        return NEGATIVE
    if re.search(r'\b(?:mention|discuss)\w*\b|提及|讨论', prefix, re.I):
        return MENTION
    if re.search(r'\b(?:we|our (?:model|method|study))\b.{0,35}\b(?:use[ds]?|using|adopt\w*|employ\w*|train\w*|evaluat\w*|test\w*)\b|(?:本文|我们|本研究).{0,20}(?:使用|采用|训练|评估)|(?:使用|采用).{0,10}(?:数据集|模型)', prefix, re.I):
        return USE
    return MENTION


class ResearchProject:
    def __init__(self, name='未命名研究'):
        self.name = name[:200] or '未命名研究'
        self.documents = []
        self.notes = []
        self.originals = {}
        self._evidence_cache = None
        self._matrix_cache = None

    def document(self, identifier):
        return next(d for d in self.documents if d['id'] == identifier)

    def import_files(self, paths, check_cancelled=no_cancel):
        issues = []
        for path in paths:
            check_cancelled()
            path = Path(path)
            try:
                if len(self.documents) >= 50:
                    raise ValueError('项目最多50份文档。')
                raw = read_document_bytes(path)
                digest = sha256(raw).hexdigest()
                if any(d['sha256'] == digest for d in self.documents):
                    restored = digest not in self.originals
                    self.originals[digest] = raw
                    issues.append(f'{path.name}：' + ('已恢复缺失原文，保留笔记关联。' if restored else '重复内容，已跳过。'))
                    continue
                snapshot = parse_snapshot(path, raw, 'utf-8', check_cancelled)
                if sum(len(d['text']) for d in self.documents) + len(snapshot.text) > 1_000_000:
                    raise ValueError('项目正文超过100万字符。')
                blocks = [dict(text=b.text, start=b.span.start, end=b.span.end,
                               location=b.location, kind=b.kind, level=b.heading_level,
                               section=list(b.section_path)) for b in snapshot.blocks]
                self.documents.append(dict(id=digest, name=path.name, sha256=digest,
                    text=snapshot.text, blocks=blocks, warnings=list(snapshot.warnings)))
                self.originals[digest] = raw
                self._evidence_cache = self._matrix_cache = None
                issues.extend(f'{path.name}：{w}' for w in snapshot.warnings)
            except (DocumentError, OSError, ValueError) as exc:
                issues.append(f'{path.name}：{exc}')
        return issues

    def evidence(self):
        if self._evidence_cache is not None:
            return self._evidence_cache
        result = []
        for d in self.documents:
            for b in d['blocks']:
                boundaries = list(CLAUSE_BREAK.finditer(b['text']))
                starts = [0] + [m.end() for m in boundaries]
                ends = [m.start() for m in boundaries] + [len(b['text'])]
                for kind, term, pattern in PATTERNS:
                    for match in pattern.finditer(b['text']):
                        if len(result) >= MAX_EVIDENCE:
                            raise ValueError('项目命中超过10000条证据，请缩小文档集合。')
                        start, end = b['start'] + match.start(), b['start'] + match.end()
                        index = bisect_right(starts, match.start()) - 1
                        low, high = starts[index], ends[index]
                        low, high = max(low, match.start()-200), min(high, match.end()+100)
                        result.append(dict(id=f"{d['id']}-{start}-{end}-{term.replace(' ', '-')}", document=d['id'],
                            kind=kind, term=term, start=start, end=end, quote=match[0],
                            context=b['text'], blockStart=b['start'], location=b['location'], section=' / '.join(b['section']),
                            state=_state(b['text'][low:high], ' / '.join(b['section']), match.start()-low, match.end()-low)))
        self._evidence_cache = result
        return result

    def matrix(self):
        if self._matrix_cache is not None:
            return self._matrix_cache
        evidence = self.evidence()
        grouped = {}
        for e in evidence:
            grouped.setdefault((e['term'], e['document']), []).append(e)
        rows = []
        for kind, term in sorted({(e['kind'], e['term']) for e in evidence}):
            cells = []
            for d in self.documents:
                matches = grouped.get((term, d['id']), [])
                cells.append(dict(document=d['id'], state=min((e['state'] for e in matches),
                    key=PRIORITY.get) if matches else '未发现', count=len(matches)))
            rows.append(dict(kind=kind, term=term, common=sum(c['count'] > 0 for c in cells) >= 2, cells=cells))
        self._matrix_cache = rows
        return rows

    def save_note(self, identifier, text, evidence=''):
        if not text.strip() or len(text) > 20_000:
            raise ValueError('笔记需为1至20000字符。')
        if evidence and evidence not in {e['id'] for e in self.evidence()}:
            raise ValueError('关联证据已失效。')
        identifier = identifier or uuid4().hex
        note = next((n for n in self.notes if n['id'] == identifier), None)
        if note is not None:
            note.update(text=text, evidence=evidence)
        else:
            if len(self.notes) >= 500:
                raise ValueError('项目最多500条笔记。')
            self.notes.append(dict(id=identifier, text=text, evidence=evidence))
        return identifier

    def delete_note(self, identifier):
        self.notes = [n for n in self.notes if n['id'] != identifier]

    def remove_document(self, identifier):
        self.documents = [d for d in self.documents if d['id'] != identifier]
        self.originals.pop(identifier, None)
        self._evidence_cache = self._matrix_cache = None
        valid = {e['id'] for e in self.evidence()}
        for n in self.notes:
            if n['evidence'] not in valid:
                n['evidence'] = ''

    def _data(self, originals=False):
        data = dict(version=1, name=self.name, documents=self.documents, notes=self.notes)
        if originals:
            data['originals'] = {k: base64.b64encode(v).decode('ascii') for k, v in self.originals.items()}
        return json.dumps(data, ensure_ascii=False).encode('utf-8')

    def save(self, path):
        data = self._data(True)
        if len(data) > LIMIT:
            raise ValueError('项目文件超过100 MiB上限。')
        _atomic(path, data)

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > LIMIT:
            raise ValueError('项目或共享包超过100 MiB上限。')
        try:
            originals = {}
            if path.suffix.lower() == '.zip':
                with ZipFile(path) as z:
                    infos = z.infolist()
                    names = [i.filename for i in infos]
                    if len(infos) > 55 or len(names) != len(set(names)) or sum(i.file_size for i in infos) > LIMIT:
                        raise ValueError('共享包条目重复或超过限制。')
                    if any('..' in PurePosixPath(n).parts or '\\' in n or PurePosixPath(n).is_absolute() for n in names):
                        raise ValueError('共享包含无效路径。')
                    data = json.loads(z.read('project.json'))
                    for n in names:
                        if n.startswith('originals/'):
                            originals[PurePosixPath(n).name.split('.')[0]] = z.read(n)
            else:
                data = json.loads(path.read_bytes())
            p = cls._validate(data)
            stored = data.get('originals', {})
            if not isinstance(stored, dict):
                raise ValueError('无效原文索引。')
            originals.update({k: base64.b64decode(v, validate=True) for k, v in stored.items()})
            known = {d['id'] for d in p.documents}
            for key, raw in originals.items():
                if key not in known or sha256(raw).hexdigest() != key or len(raw) > 10 * 1024 * 1024:
                    raise ValueError('原文校验失败。')
            p.originals = originals
            p.matrix()
            return p
        except (KeyError, TypeError, StopIteration, BadZipFile, UnicodeError, OverflowError, RecursionError) as exc:
            raise ValueError('无效项目或共享包。') from exc

    @classmethod
    def _validate(cls, data):
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('不支持的项目格式版本。')
        if not isinstance(data.get('name'), str) or not 1 <= len(data['name']) <= 200:
            raise ValueError('无效项目名称。')
        p = cls(data['name'])
        docs = data.get('documents')
        if not isinstance(docs, list) or len(docs) > 50:
            raise ValueError('无效文档列表。')
        ids = set()
        total = 0
        for d in docs:
            if not isinstance(d, dict) or not all(isinstance(d.get(k), str) for k in ('id', 'sha256', 'name', 'text')):
                raise ValueError('无效文档。')
            if not re.fullmatch('[a-f0-9]{64}', d['id']) or d['id'] != d['sha256'] or d['id'] in ids:
                raise ValueError('无效或重复文档ID。')
            ids.add(d['id'])
            if len(d['text']) > 100_000 or len(d['name']) > 255 or '/' in d['name'] or '\\' in d['name']:
                raise ValueError('文档超限或名称无效。')
            if not isinstance(d.get('warnings'), list) or not all(isinstance(w, str) for w in d['warnings']):
                raise ValueError('无效解析警告。')
            blocks = d.get('blocks')
            if not isinstance(blocks, list) or len(blocks) > 100_001:
                raise ValueError('无效结构。')
            cursor = 0
            for b in blocks:
                if not isinstance(b, dict) or not all(isinstance(b.get(k), str) for k in ('text', 'location', 'kind')):
                    raise ValueError('无效文本块。')
                if type(b.get('start')) is not int or type(b.get('end')) is not int or b['start'] != cursor or b['end'] != cursor + len(b['text']) or d['text'][cursor:b['end']] != b['text']:
                    raise ValueError('证据区间与正文不匹配。')
                if not isinstance(b.get('section'), list) or not all(isinstance(s, str) for s in b['section']):
                    raise ValueError('无效章节。')
                cursor = b['end'] + 1
            if '\n'.join(b['text'] for b in blocks) != d['text']:
                raise ValueError('结构与正文不匹配。')
            total += len(d['text'])
        if total > 1_000_000:
            raise ValueError('项目正文超过限制。')
        p.documents = docs
        notes = data.get('notes')
        if not isinstance(notes, list) or len(notes) > 500:
            raise ValueError('无效笔记列表。')
        for n in notes:
            if not isinstance(n, dict) or not all(isinstance(n.get(k), str) for k in ('id', 'text', 'evidence')) or not re.fullmatch('[a-f0-9]{32}', n['id']) or any(x['id'] == n['id'] for x in p.notes):
                raise ValueError('无效笔记。')
            p.save_note(n['id'], n['text'], n['evidence'])
        return p

    def markdown(self):
        from html import escape
        safe = lambda s: escape(str(s)).replace('|', '&#124;').replace('\n', '<br>')
        lines = [f'# {safe(self.name)}', '', '使用线索需人工核对；未发现不代表不存在。共享报告含提取正文和笔记。', '',
                 '| 类别 / 共同项 | ' + ' | '.join(safe(d['name']) for d in self.documents) + ' |',
                 '| --- | ' + ' | '.join('---' for d in self.documents) + ' |']
        for row in self.matrix():
            lines.append('| ' + safe(row['kind'] + ' / ' + row['term'] + ('（共同）' if row['common'] else '')) + ' | ' + ' | '.join(safe(c['state']) + f" ({c['count']})" for c in row['cells']) + ' |')
        lines += ['', '## 笔记']
        for n in self.notes:
            lines += ['', safe(n['text']), f"[关联证据](#e-{n['evidence']})" if n['evidence'] else '无关联证据']
        lines += ['', '## 证据']
        for e in self.evidence():
            # Bound repeated context; full source text is exported once below.
            offset = e['start'] - e['blockStart']
            context = e['context'][max(0, offset-120):offset+len(e['quote'])+180]
            lines += ['', f'<a id="e-{e["id"]}"></a>', f"**{safe(e['term'])} · {safe(self.document(e['document'])['name'])} · {safe(e['location'])} · {safe(e['state'])}**", '', '> ' + safe(context)]
        for d in self.documents:
            lines += ['', f"## {safe(d['name'])}", '', '；'.join(safe(w) for w in d['warnings'])]
            for i, b in enumerate(d['blocks']):
                if b['kind'] == 'heading':
                    lines.append(f"- [{safe(b['text'])}](#d-{d['id']}-{i})")
            for i, b in enumerate(d['blocks']):
                lines += ['', f'<a id="d-{d["id"]}-{i}"></a>', safe(b['text'])]
        return '\n'.join(lines) + '\n'

    def export_bundle(self, path, include_originals=False):
        from io import BytesIO
        if include_originals and len(self.originals) != len(self.documents):
            raise ValueError('部分原文不可用，请重新导入原文或取消附带原文。')
        output = BytesIO()
        data, report = self._data(), self.markdown().encode('utf-8')
        expanded = len(data) + len(report) + (sum(len(v) for v in self.originals.values()) if include_originals else 0)
        if expanded > LIMIT:
            raise ValueError('共享包解压后超过100 MiB上限。')
        with ZipFile(output, 'w', ZIP_DEFLATED) as z:
            z.writestr('project.json', data)
            z.writestr('report.md', report)
            if include_originals:
                for d in self.documents:
                    z.writestr(f"originals/{d['id']}{Path(d['name']).suffix}", self.originals[d['id']])
        if len(output.getvalue()) > LIMIT:
            raise ValueError('共享包超过100 MiB上限。')
        _atomic(path, output.getvalue())
