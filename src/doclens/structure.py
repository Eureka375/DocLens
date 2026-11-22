"""Conservative heading recognition; display text and source offsets stay intact."""

from dataclasses import replace
import re

from .models import TextBlock


def heading(text: str) -> tuple[int, str] | None:
    text = text.strip()
    if not text or len(text) > 100:
        return None
    match = re.fullmatch(r"(#{1,6})\s+(.+?)(?:\s+#+)?", text)
    if match:
        return len(match[1]), match[2]
    match = re.fullmatch(r"第[一二三四五六七八九十百零〇\d]+([章节])\s*([^。！？；]+)", text)
    if match:
        return (1 if match[1] == "章" else 2), text
    return None


def annotate(blocks: list[TextBlock], *, infer_headings: bool) -> tuple[TextBlock, ...]:
    stack: list[tuple[int, str]] = []
    result = []
    for block in blocks:
        level, title = block.heading_level, block.text.strip()
        if infer_headings and not block.table_path:
            detected = heading(block.text)
            if detected:
                level, title = detected
        # Headings inside tables are local content, not document section boundaries.
        if level is not None and not block.table_path:
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            block = replace(block, kind="heading", heading_level=level)
        result.append(replace(block, section_path=tuple(title for _, title in stack)))
    return tuple(result)
