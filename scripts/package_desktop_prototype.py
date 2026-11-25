"""Package only the reviewed design deliverables; excludes application data/build caches."""
from pathlib import Path
import hashlib
import json
import zipfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/desktop-prototype'
EXAMPLE = ROOT / 'examples/desktop-prototype'
VALIDATION = ROOT / 'docs/validation/keyword-prototype'
DESIGN_FILES = [
    ROOT / 'docs/design/keyword-research-mvp.md',
    ROOT / 'docs/design/desktop-prototype/关键词研究版设计说明.md',
    ROOT / 'docs/design/multi-document-mvp.md',
    ROOT / 'docs/design/desktop-prototype/需求规格.md',
]

class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ('src', 'href') and v and not v.startswith(('#', 'http:', 'https:', 'data:')):
                self.paths.append(v.split('?')[0].split('#')[0])

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pages = sorted(EXAMPLE.glob('*.html'))
    for page in pages:
        parser = Resources()
        parser.feed(page.read_text(encoding='utf-8'))
        for resource in parser.paths:
            assert (page.parent / resource).is_file(), (page, resource)
    checks = json.loads((VALIDATION / 'browser-checks.json').read_text(encoding='utf-8'))
    assert checks['results'] and not checks['errors'] and not checks['requests']
    assert all(item['pass'] for item in checks['results'])
    exports = json.loads((VALIDATION / 'export-checks.json').read_text(encoding='utf-8'))
    assert len(exports) == 2 and all(x['crc_ok'] for x in exports)
    files = sorted(p for directory in [EXAMPLE, VALIDATION] for p in directory.rglob('*') if p.is_file())
    files += DESIGN_FILES
    files += [ROOT / 'scripts/validate_desktop_prototype.mjs', Path(__file__).resolve()]
    target = OUT / 'DocLens-Desktop-Design-v1.1.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('START-HERE.txt', (
            'DocLens 关键词研究桌面原型 v1.1\n\n'
            '打开 examples/desktop-prototype/index.html 查看八个界面。\n'
            '打开 examples/desktop-prototype/desktop.html 连续操作。\n'
            '新版需求：docs/design/keyword-research-mvp.md\n'
            '检查与截图：docs/validation/keyword-prototype/\n\n'
            '全部研究内容和 AI 结果均为合成示例。\n'
            '运行说明见 examples/desktop-prototype/README.md。\n'
        ))
        for p in files:
            archive.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files) + 1
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / 'DocLens-Desktop-Design-v1.1.sha256').write_text(digest + '  ' + target.name + '\n', encoding='utf-8')
    print(json.dumps({'file': str(target), 'bytes': target.stat().st_size, 'files': len(files)+1, 'htmlPages': len(pages), 'sha256': digest}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
