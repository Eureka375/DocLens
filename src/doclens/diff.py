from collections.abc import Callable, Sequence
from difflib import SequenceMatcher

from .documents import no_cancel
from .models import Change, Comparison, Snapshot, Span

# Bound the quadratic scope of SequenceMatcher even for adversarial repetitions.
BLOCK_PAIR_LIMIT = 240_000
CHAR_PAIR_LIMIT = 160_000


def _operations(left: Sequence[str], right: Sequence[str], pair_limit: int,
                check_cancelled: Callable[[], None]):
    prefix = 0
    shorter = min(len(left), len(right))
    while prefix < shorter and left[prefix] == right[prefix]:
        prefix += 1
    a, b = len(left), len(right)
    while a > prefix and b > prefix and left[a - 1] == right[b - 1]:
        a -= 1
        b -= 1
    check_cancelled()
    if a == b == prefix:
        return (), False
    if a == prefix:
        return (("insert", prefix, a, prefix, b),), False
    if b == prefix:
        return (("delete", prefix, a, prefix, b),), False
    if (a - prefix) * (b - prefix) > pair_limit:
        return (("replace", prefix, a, prefix, b),), True
    operations = SequenceMatcher(None, left[prefix:a], right[prefix:b], autojunk=False).get_opcodes()
    return tuple((kind, i + prefix, j + prefix, k + prefix, l + prefix)
                 for kind, i, j, k, l in operations if kind != "equal"), False


def _block_span(snapshot: Snapshot, start: int, end: int) -> tuple[Span, str]:
    blocks = snapshot.blocks
    if start == end:
        if start < len(blocks):
            return Span(blocks[start].span.start, blocks[start].span.start), f"{blocks[start].location}前"
        return Span(len(snapshot.text), len(snapshot.text)), "文末" if snapshot.text else "空文档"
    location = blocks[start].location
    if end - start > 1:
        location += f" 至 {blocks[end - 1].location}"
    return Span(blocks[start].span.start, blocks[end - 1].span.end), location


def compare(left: Snapshot, right: Snapshot, check_cancelled: Callable[[], None] = no_cancel) -> Comparison:
    check_cancelled()
    if left.text == right.text:
        return Comparison((), False)
    operations, coarse = _operations([b.text for b in left.blocks], [b.text for b in right.blocks],
                                     BLOCK_PAIR_LIMIT, check_cancelled)
    changes = []
    for kind, i, j, k, l in operations:
        check_cancelled()
        a, left_location = _block_span(left, i, j)
        b, right_location = _block_span(right, k, l)
        if kind == "replace":
            edits, approximate = _operations(left.text[a.start:a.end], right.text[b.start:b.end],
                                              CHAR_PAIR_LIMIT, check_cancelled)
            coarse |= approximate
            left_edits = tuple(Span(a.start + start, a.start + end) for _, start, end, _, _ in edits if start < end)
            right_edits = tuple(Span(b.start + start, b.start + end) for _, _, _, start, end in edits if start < end)
        else:
            left_edits = (a,) if a.start < a.end else ()
            right_edits = (b,) if b.start < b.end else ()
        changes.append(Change(kind, a, b, left_location, right_location, left_edits, right_edits))
    return Comparison(tuple(changes), coarse)
