"""Package only the reviewed design deliverables; excludes application data/build caches."""
from pathlib import Path
import hashlib
import json
import zipfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/desktop-prototype'
DIRS = ['examples/desktop-prototype', 'docs/design/desktop-prototype', 'docs/validation/desktop-prototype']

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
    pages = sorted((ROOT / DIRS[0]).glob('*.html'))
    for page in pages:
        parser = Resources()
        parser.feed(page.read_text(encoding='utf-8'))
        for resource in parser.paths:
            assert (page.parent / resource).is_file(), (page, resource)
    checks = json.loads((ROOT / DIRS[2] / 'browser-checks.json').read_text(encoding='utf-8'))
    assert not checks['errors'] and all(x['pass'] for x in checks['results'])
    exports = json.loads((ROOT / DIRS[2] / 'export-checks.json').read_text(encoding='utf-8'))
    assert len(exports) == 2 and all(x['crc_ok'] for x in exports)
    files = sorted(p for directory in DIRS for p in (ROOT / directory).rglob('*') if p.is_file())
    files += [ROOT / 'scripts/validate_desktop_prototype.mjs', Path(__file__).resolve()]
    target = OUT / 'DocLens-Desktop-Design-v1.0.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('START-HERE.txt', 'DocLens 桌面设计原型 v1.0\n\n打开 examples/desktop-prototype/index.html 查看全部界面。\n打开 examples/desktop-prototype/desktop.html 连续操作。\n需求、设计与 Prompt：docs/design/desktop-prototype/\n检查与截图：docs/validation/desktop-prototype/\n\n全部研究内容为合成示例；非生产后端。\n运行说明见 examples/desktop-prototype/README.md。\n')
        for p in files:
            archive.write(p, p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files) + 1
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / 'SHA256SUMS.txt').write_text(digest + '  ' + target.name + '\n', encoding='utf-8')
    print(json.dumps({'file': str(target), 'bytes': target.stat().st_size, 'files': len(files)+1, 'htmlPages': len(pages), 'sha256': digest}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
