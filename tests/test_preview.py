from hashlib import sha256

import pytest

from doclens.documents import read_document
from doclens.diff import compare
from doclens.preview import PreviewError, build_preview
from test_pdf import write_pdf


def test_pdf_preview_has_pages_and_numeric_highlights(tmp_path):
    paths = [tmp_path / 'old.pdf', tmp_path / 'new.pdf']
    for path, number in zip(paths, ('14', '7')):
        write_pdf(path, [('Agreement',), (f'Deadline: {number} days',)])
    left, right = map(read_document, paths)
    result = compare(left, right)
    output = build_preview(left, result.changes, 'left', tmp_path / 'preview')
    assert len(output['pages']) == 2
    assert output['pages'][1]['marks']
    assert not output['pages'][0]['marks']
    assert output['pages'][1]['marks'][0]['group'] == 0
    assert paths[0].read_bytes() and sha256(paths[0].read_bytes()).hexdigest() == left.sha256
    for page in output['pages']:
        assert page['width'] > 0 and page['height'] > 0
        for mark in page['marks']:
            assert 0 <= mark['x'] <= 1 and 0 <= mark['y'] <= 1
            assert mark['width'] > 0 and mark['height'] > 0


def test_preview_rejects_changed_source_and_checks_cancel(tmp_path):
    path = tmp_path / 'old.pdf'
    write_pdf(path, [('Agreement',)])
    snapshot = read_document(path)
    write_pdf(path, [('Changed',)])
    with pytest.raises(PreviewError, match='变化'):
        build_preview(snapshot, (), 'left', tmp_path / 'changed')
    def stop():
        raise InterruptedError
    with pytest.raises(InterruptedError):
        build_preview(snapshot, (), 'left', tmp_path / 'cancel', stop)


def test_ambiguous_repeated_text_is_not_guessed(tmp_path):
    a, b = tmp_path / 'a.pdf', tmp_path / 'b.pdf'
    write_pdf(a, [('Repeated 100', 'Repeated 100')])
    write_pdf(b, [('Repeated 200', 'Repeated 100')])
    left, right = map(read_document, (a, b))
    preview = build_preview(left, compare(left, right).changes, 'left', tmp_path / 'repeat')
    assert preview['warning']
    assert not any(page['marks'] for page in preview['pages'])


def test_preview_keeps_rotated_page_rectangles_inside_image(tmp_path):
    a, b = tmp_path / 'a.pdf', tmp_path / 'b.pdf'
    write_pdf(a, [('Deadline 14 days',)], rotate_page=0)
    write_pdf(b, [('Deadline 7 days',)], rotate_page=0)
    left, right = map(read_document, (a, b))
    preview = build_preview(left, compare(left, right).changes, 'left', tmp_path / 'rotation')
    assert preview['pages'][0]['marks']
    assert all(m['x'] + m['width'] <= 1.01 and m['y'] + m['height'] <= 1.01
               for m in preview['pages'][0]['marks'])


def test_whitespace_change_reports_no_page_location(tmp_path):
    a, b = tmp_path / 'a.pdf', tmp_path / 'b.pdf'
    write_pdf(a, [('Deadline: 14 days',)])
    write_pdf(b, [('Deadline:  14 days',)])
    left, right = map(read_document, (a, b))
    assert build_preview(right, compare(left, right).changes, 'right', tmp_path / 'space')['warning']


def test_word_failure_preserves_source(tmp_path, monkeypatch):
    from docx import Document
    import doclens.preview as preview
    path = tmp_path / 'source.docx'
    doc = Document(); doc.add_paragraph('Original'); doc.save(path)
    original = path.read_bytes()
    def unavailable(*args):
        raise PreviewError('Word unavailable')
    monkeypatch.setattr(preview, '_export_word', unavailable)
    with pytest.raises(PreviewError, match='Word unavailable'):
        build_preview(read_document(path), (), 'left', tmp_path / 'failed')
    assert path.read_bytes() == original


def test_preview_page_limit_does_not_render_partial_result(tmp_path, monkeypatch):
    import doclens.preview as preview
    monkeypatch.setattr(preview, 'MAX_PREVIEW_PAGES', 1)
    path = tmp_path / 'large.pdf'; write_pdf(path, [('First',), ('Second',)])
    with pytest.raises(PreviewError, match='1'):
        build_preview(read_document(path), (), 'left', tmp_path / 'large')


def test_insert_has_navigation_anchor_on_unchanged_side(tmp_path):
    a, b = tmp_path / 'a.pdf', tmp_path / 'b.pdf'
    write_pdf(a, [('Deadline 14 days',), ('Tail stable',)])
    write_pdf(b, [('Deadline 7 days',), ('Tail stable', 'Inserted clause')])
    left, right = map(read_document, (a, b))
    p = build_preview(left, compare(left, right).changes, 'left', tmp_path / 'anchors')
    assert any(mark['group'] == 1 for mark in p['pages'][1]['anchors'])


def test_word_can_cancel_before_pid_is_published(tmp_path, monkeypatch):
    import doclens.preview as preview
    class Function:
        def __call__(self, *args): return None
    class Kernel:
        OpenProcess = Function(); TerminateProcess = Function(); CloseHandle = Function()
    class Process:
        returncode = None
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def poll(self): return self.returncode
        def terminate(self): self.returncode = -1
        def wait(self, *args): return self.returncode
    process = Process()
    clock = iter(range(0, 200, 2))
    monkeypatch.setattr(preview.ctypes, 'WinDLL', lambda *a, **k: Kernel())
    monkeypatch.setattr(preview.subprocess, 'Popen', lambda *a, **k: process)
    monkeypatch.setattr(preview.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(preview.time, 'sleep', lambda _: None)
    calls = 0
    def cancel():
        nonlocal calls
        calls += 1
        if calls > 1: raise InterruptedError
    with pytest.raises(InterruptedError):
        preview._export_word(tmp_path / 'input.docx', tmp_path / 'output.pdf', cancel)
    assert calls == 2 and process.returncode == -1
