"""Read-only page previews, with conservative links to snapshot evidence."""

from collections import Counter
from bisect import bisect_left
from collections.abc import Callable, Sequence
from contextlib import closing
import ctypes
from hashlib import sha256
import math
import os
from pathlib import Path
import subprocess
from threading import Lock
import time

import pypdfium2 as pdfium
import pypdfium2.raw as raw

from .documents import no_cancel, read_document_bytes
from .models import Change, Snapshot

PDFIUM_LOCK = Lock()
MAX_PREVIEW_PAGES = 80
MAX_PIXELS = 60_000_000
MAX_PREVIEW_TEXT = 150_000
MAX_DISK_BYTES = 120 * 1024 * 1024
COLORS = {'left': '#ed5a49', 'right': '#35a360', 'move': '#4589dc'}


class PreviewError(Exception):
    pass


def _export_word(source: Path, destination: Path, check_cancelled: Callable[[], None]) -> None:
    if os.name != 'nt':
        raise PreviewError('Word 原貌预览需要 Windows 和本机 Microsoft Word。')
    check_cancelled()
    pid_file = source.with_suffix('.pid')
    pid_file.unlink(missing_ok=True)
    cancel_file = source.with_suffix('.cancel')
    cancel_file.unlink(missing_ok=True)
    shell = Path(os.environ['SYSTEMROOT']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = [str(shell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
               '-File', str(Path(__file__).with_name('word_preview.ps1')),
               '-Source', str(source), '-Destination', str(destination), '-PidFile', str(pid_file),
               '-CancelFile', str(cancel_file)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    word_handle = None
    # Word is isolated by the helper before a PID is published. Keep a native
    # handle so timeout cleanup cannot accidentally target a reused PID.
    with source.with_suffix('.log').open('wb') as log, subprocess.Popen(
        command, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW
    ) as process:
        try:
            deadline = time.monotonic() + 90
            while process.poll() is None:
                if word_handle is None and pid_file.exists():
                    word_handle = kernel.OpenProcess(0x0001 | 0x00100000, False,
                                                     int(pid_file.read_text()))
                check_cancelled()
                if time.monotonic() > deadline:
                    raise PreviewError('Word 转换超时，请关闭文档提示框后重试或使用文字视图。')
                time.sleep(0.1)
            check_cancelled()
            if process.returncode or not destination.is_file():
                raise PreviewError('无法生成 Word 原貌。请确认已安装并激活 Microsoft Word，可先使用文字视图。')
        finally:
            if process.poll() is None or process.returncode:
                cancel_file.touch()
                # Give the helper a bounded chance to run its COM finally block.
                grace = time.monotonic() + 2
                while process.poll() is None and time.monotonic() < grace:
                    if word_handle is None and pid_file.exists():
                        word_handle = kernel.OpenProcess(0x0001 | 0x00100000, False,
                                                         int(pid_file.read_text()))
                    time.sleep(0.1)
                if word_handle:
                    kernel.TerminateProcess(word_handle, 1)
                if process.poll() is None:
                    process.terminate()
                    process.wait(10)
            if word_handle:
                kernel.CloseHandle(word_handle)


def _canonical(text: str) -> str:
    return ''.join(c for c in text if not c.isspace())


def _page_rect(page, width, height, box):
    left, bottom, right, top = box
    points = []
    for x, y in ((left, bottom), (right, top)):
        dx, dy = ctypes.c_int(), ctypes.c_int()
        raw.FPDF_PageToDevice(page.raw, 0, 0, width, height, 0, x, y,
                              ctypes.byref(dx), ctypes.byref(dy))
        points.append((dx.value / width, dy.value / height))
    x0, x1 = sorted(max(0., min(1., p[0])) for p in points)
    y0, y1 = sorted(max(0., min(1., p[1])) for p in points)
    return x0, y0, x1 - x0, y1 - y0


def _render(data: bytes, directory: Path, check_cancelled):
    pages, glyphs, letters = [], [], []
    pixels = disk = 0
    # PDFium (including destruction of its helper objects) is not thread-safe.
    with PDFIUM_LOCK, pdfium.PdfDocument(data) as document:
        if len(document) > MAX_PREVIEW_PAGES:
            raise PreviewError(f'原貌预览最多 {MAX_PREVIEW_PAGES} 页，请使用文字视图或拆分文件。')
        for index in range(len(document)):
            check_cancelled()
            with closing(document[index]) as page:
                width, height = page.get_size()
                if not (math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0):
                    raise PreviewError('PDF 页面尺寸无效。')
                scale = min(1.5, 1600 / width, 2200 / height)
                pixels += math.ceil(width * scale) * math.ceil(height * scale)
                if pixels > MAX_PIXELS:
                    raise PreviewError('原貌预览超过图像总量上限，请使用文字视图。')
                bitmap = page.render(scale=scale)
                try:
                    image_path = directory / f'page-{index + 1}.png'
                    with bitmap.to_pil() as image:
                        image.save(image_path)
                    image_width, image_height = bitmap.width, bitmap.height
                finally:
                    bitmap.close()
                disk += image_path.stat().st_size
                if disk > MAX_DISK_BYTES:
                    raise PreviewError('原貌预览超过临时存储上限。')
                pages.append({'source': image_path.as_uri(), 'width': image_width,
                              'height': image_height, 'marks': [], 'anchors': [], 'page': index + 1})
                with closing(page.get_textpage()) as textpage:
                    count = textpage.count_chars()
                    if count + len(letters) > MAX_PREVIEW_TEXT:
                        raise PreviewError('原貌预览超过文字坐标上限。')
                    for char_index in range(count):
                        if char_index % 256 == 0:
                            check_cancelled()
                        value = raw.FPDFText_GetUnicode(textpage.raw, char_index)
                        if not value or value > 0x10ffff or 0xd800 <= value <= 0xdfff:
                            continue
                        character = chr(value)
                        if character.isspace():
                            continue
                        box = textpage.get_charbox(char_index)
                        glyphs.append((index, _page_rect(page, image_width, image_height, box)))
                        letters.append(character)
    return pages, ''.join(letters), glyphs


def _mark(pages, glyphs, indices, group, color):
    # Merge neighboring glyphs on a line to keep QML models small.
    for index in indices:
        page, (x, y, width, height) = glyphs[index]
        if width <= 0 or height <= 0:
            continue
        marks = pages[page]['marks']
        if marks:
            previous = marks[-1]
            if (previous['group'] == group and abs(previous['y'] - y) < 0.004
                    and abs(previous['height'] - height) < 0.005
                    and 0 <= x - previous['x'] - previous['width'] < 0.008):
                previous['width'] = x + width - previous['x']
                continue
        marks.append({'x': x, 'y': y, 'width': width, 'height': height,
                      'group': group, 'color': color})


def build_preview(snapshot: Snapshot, changes: Sequence[Change], side: str, directory: Path,
                  check_cancelled: Callable[[], None] = no_cancel) -> dict:
    check_cancelled()
    if snapshot.path.suffix.lower() not in ('.pdf', '.docx'):
        return {'pages': [], 'warning': ''}
    data = read_document_bytes(snapshot.path)
    if sha256(data).hexdigest() != snapshot.sha256:
        raise PreviewError('文件在比对后发生变化，请重新比对。')
    directory = directory.absolute()
    directory.mkdir(parents=True, exist_ok=True)
    if snapshot.path.suffix.lower() == '.docx':
        source = directory / 'source.docx'
        source.write_bytes(data)
        destination = directory / 'preview.pdf'
        _export_word(source, destination, check_cancelled)
        data = destination.read_bytes()
        if len(data) > MAX_DISK_BYTES:
            raise PreviewError('Word 预览超过存储上限。')
    try:
        pages, text, glyphs = _render(data, directory, check_cancelled)
    except (pdfium.PdfiumError, ValueError, OverflowError) as exc:
        raise PreviewError('无法渲染文档页面，请使用文字视图。') from exc
    mapping = {}
    counts = Counter(_canonical(b.text) for b in snapshot.blocks)
    for block_index, block in enumerate(snapshot.blocks):
        check_cancelled()
        token = _canonical(block.text)
        if not token or counts[token] != 1:
            continue
        start = text.find(token)
        if start < 0:
            continue
        if text.find(token, start + 1) >= 0:
            # A short table-cell value may also occur inside a body sentence.
            # Accept only an exact, unique neighborhood in the same document.
            before = ''.join(_canonical(b.text) for b in snapshot.blocks[max(0, block_index - 2):block_index])
            after = ''.join(_canonical(b.text) for b in snapshot.blocks[block_index + 1:block_index + 3])
            context = before + token + after
            context_start = text.find(context)
            if context_start < 0 or text.find(context, context_start + 1) >= 0:
                continue
            start = context_start + len(before)
        n = start
        for offset, character in enumerate(block.text):
            if not character.isspace():
                mapping[block.span.start + offset] = n
                n += 1
    missing = 0
    mapped_positions = sorted(mapping)
    for group, change in enumerate(changes):
        check_cancelled()
        edits = getattr(change, side + '_edits')
        if not edits and pages:
            boundary = getattr(change, side)
            if mapped_positions:
                rank = min(bisect_left(mapped_positions, boundary.start), len(mapped_positions) - 1)
                page, (x, y, _, _) = glyphs[mapping[mapped_positions[rank]]]
            else:
                page, x, y = 0, 0., 0.
            pages[page]['anchors'].append({'group': group, 'x': x, 'y': y})
        for span in edits:
            positions = [i for i in range(span.start, span.end) if not snapshot.text[i].isspace()]
            if not positions or any(i not in mapping for i in positions):
                missing += 1
                continue
            _mark(pages, glyphs, [mapping[i] for i in positions], group,
                  COLORS['move'] if change.kind == 'move' else COLORS[side])
    return {'pages': pages, 'warning': '部分差异无法可靠定位到页面，请切换文字视图核对。' if missing else ''}
