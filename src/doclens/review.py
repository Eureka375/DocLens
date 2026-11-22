"""Review annotations and a standalone, escaped HTML comparison report."""

from html import escape
from bisect import bisect_right
import os
from pathlib import Path
import re
import tempfile

from .models import Comparison, Snapshot

LABELS = {"insert": "新增", "delete": "删除", "replace": "修改", "move": "移动", "move_replace": "移动并修改"}
NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)*%?")
COVERAGE_NOTICE = "仅比较已提取正文文字；格式、图片、公式、页眉页脚等不在本次文字比较范围内。原貌显示不代表已比较全部可见内容。"


class ReviewSession:
    def __init__(self, left: Snapshot, right: Snapshot, comparison: Comparison):
        self.left, self.right, self.comparison = left, right, comparison
        self.annotations = [{"reviewed": False, "note": ""} for _ in comparison.changes]
        self._block_starts = {id(s): [b.span.start for b in s.blocks] for s in (left, right)}

    def update(self, index: int, *, reviewed: bool | None = None, note: str | None = None):
        if not 0 <= index < len(self.annotations):
            raise ValueError("无效的差异编号。")
        if note is not None and len(note) > 2000:
            raise ValueError("每组备注最多2,000字符。")
        if reviewed is not None:
            self.annotations[index]["reviewed"] = bool(reviewed)
        if note is not None:
            self.annotations[index]["note"] = note

    def rows(self, kind="all", state="all", query="") -> list[dict]:
        result = []
        query = query.strip().casefold()
        for index, change in enumerate(self.comparison.changes):
            annotation = self.annotations[index]
            if kind != "all" and change.kind != kind:
                continue
            if state != "all" and annotation["reviewed"] != (state == "reviewed"):
                continue
            old = self.left.text[change.left.start:change.left.end]
            new = self.right.text[change.right.start:change.right.end]
            sections = []
            for snapshot, span in ((self.left, change.left), (self.right, change.right)):
                position = bisect_right(self._block_starts[id(snapshot)], span.start) - 1
                block = snapshot.blocks[position] if position >= 0 else None
                section = " / ".join(block.section_path) if block and span.start < block.span.end else ""
                if section and section not in sections:
                    sections.append(section)
            section = " → ".join(sections) or "未识别章节"
            if query and query not in (section + "\n" + old + "\n" + new + "\n" + annotation["note"]).casefold():
                continue
            result.append({"index": index, "kind": change.kind, "label": LABELS[change.kind],
                           "section": section, "old": old, "new": new,
                           "oldLocation": change.left_location, "newLocation": change.right_location,
                           "numbersChanged": NUMBER.findall(old) != NUMBER.findall(new), **annotation})
        return result

    def export_html(self, path: Path, findings, coverage: dict[int, str]):
        path = Path(path)
        if path.suffix.lower() != ".html" or path.resolve() in {self.left.path.resolve(), self.right.path.resolve()}:
            raise ValueError("请另存为HTML报告，不能覆盖输入文档。")
        e = escape
        parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
                 '<meta name="viewport" content="width=device-width, initial-scale=1">',
                 '<title>DocLens 审阅报告</title><style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:32px auto;padding:0 20px;color:#243e35}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;padding:12px;background:#f3f6f4}article{border-top:1px solid #bbb;padding:18px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}.note{white-space:pre-wrap}a{color:#24624b}@media(max-width:650px){.pair{display:block}}</style>',
                 '<h1>DocLens 审阅报告</h1>', f'<p>{e(self.left.path.name)} → {e(self.right.path.name)}</p>',
                 f'<p>原文件摘要：{e(self.left.sha256)} / {e(self.right.sha256)}</p>',
                 f'<p>{e(COVERAGE_NOTICE)}</p>']
        for snapshot in (self.left, self.right):
            for warning in snapshot.warnings:
                parts.append(f'<p>{e(snapshot.path.name)}：{e(warning)}</p>')
        if self.comparison.used_coarse_matching:
            parts.append('<p>部分区域使用粗匹配，请核对完整原文。</p>')
        rows = self.rows()
        parts.append(f'<p>共{len(rows)}组，已核对{sum(r["reviewed"] for r in rows)}组。核对状态为人工标记，不代表AI判断正确。</p>')
        parts.append('<nav>' + ' · '.join(f'<a href="#D{r["index"] + 1}">第{r["index"] + 1}组</a>' for r in rows) + '</nav>')
        for row in rows:
            index = row["index"]
            parts.extend([f'<article id="D{index + 1}"><h2>第{index + 1}组 · {e(row["label"])} · {"已核对" if row["reviewed"] else "待核对"}</h2>',
                          f'<p>{e(row["section"])} · AI：{e(coverage.get(index, "未分析"))}</p>',
                          '<div class="pair">',
                          f'<div><h3>原文 · {e(row["oldLocation"])}</h3><pre>{e(row["old"])}</pre></div>',
                          f'<div><h3>新版 · {e(row["newLocation"])}</h3><pre>{e(row["new"])}</pre></div></div>',
                          f'<p class="note">人工备注：{e(row["note"])}</p>'])
            for finding in findings:
                if any(item.change_index == index for item in finding.evidence):
                    parts.append(f'<p>AI变化解释：{e(finding.summary)}</p><p>AI可能影响（需核对）：{e(finding.impact)}</p>')
                    parts.append('<p>证据：' + ' · '.join(f'<a href="#D{item.change_index + 1}">{e(item.id)}</a>' for item in finding.evidence) + '</p>')
            parts.append('</article>')
        parts.append('</html>')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix="doclens-report-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write("\n".join(parts))
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
