"""Conservative heading recognition; display text and source offsets stay intact."""

from dataclasses import replace
import re

from .models import TextBlock

ACADEMIC_TITLES = {
    "abstract", "introduction", "methods", "materials and methods", "results",
    "discussion", "conclusion", "conclusions", "references", "acknowledgements",
    "摘要", "关键词", "引言", "实验方法", "实验结果", "讨论", "结论", "参考文献", "致谢",
}
NUMBERED_TITLES = ACADEMIC_TITLES | {
    "background", "related work", "methodology", "experimental setup", "experiments",
    "dataset", "datasets", "data", "evaluation", "evaluation methods", "ablation study",
    "limitations", "future work", "方法", "数据", "数据集", "评价方法", "实验设置", "实验",
    "结果", "研究背景", "相关工作", "研究方法", "局限性", "未来工作",
}


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
    if text.casefold() in ACADEMIC_TITLES:
        return 1, text
    # Number syntax alone cannot distinguish an outline from a quantity.
    # Infer only known academic titles; unknown outlines remain literal paragraphs.
    match = re.fullmatch(r"([1-9]|1\d|20)((?:\.[1-9]\d?){0,5})\s+([^。！？；.!?;=]+)", text)
    if match and len(text) <= 80 and match[3].strip().casefold() in NUMBERED_TITLES:
        return 1 + match[2].count("."), text
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
