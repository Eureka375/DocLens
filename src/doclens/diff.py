from bisect import bisect_left
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from difflib import SequenceMatcher
import re

from .alignment import expose_moves, refine_replacements
from .edited_moves import recover_edited_moves
from .documents import no_cancel
from .models import Change, Comparison, Snapshot, Span

# Bound the quadratic scope of SequenceMatcher even for adversarial repetitions.
BLOCK_PAIR_LIMIT = 240_000
CHAR_PAIR_LIMIT = 160_000
Operation = tuple[str, int, int, int, int]
WORD_TOKEN = re.compile(r"\d+(?:\.\d+)*|[^\W\d_\u3400-\u9fff]+|\s+|.", re.UNICODE)


def _word_edits(left: str, right: str, a: int, b: int, check_cancelled):
    tokens = [[m for m in WORD_TOKEN.finditer(text)] for text in (left, right)]
    operations, coarse = _operations([m.group() for m in tokens[0]], [m.group() for m in tokens[1]],
                                      CHAR_PAIR_LIMIT, check_cancelled)
    edits = [[], []]
    for _, i, j, k, l in operations:
        for side, start, end, offset in ((0, i, j, a), (1, k, l, b)):
            if start < end:
                edits[side].append(Span(offset + tokens[side][start].start(),
                                        offset + tokens[side][end - 1].end()))
    return tuple(edits[0]), tuple(edits[1]), coarse


def _operations(left: Sequence[str], right: Sequence[str], pair_limit: int,
                check_cancelled: Callable[[], None], work_budget: list[int] | None = None):
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
    cost = (a - prefix) * (b - prefix)
    limit = min(pair_limit, work_budget[0]) if work_budget is not None else pair_limit
    if cost > limit:
        return (("replace", prefix, a, prefix, b),), True
    if work_budget is not None:
        work_budget[0] -= cost
    operations = SequenceMatcher(None, left[prefix:a], right[prefix:b], autojunk=False).get_opcodes()
    return tuple((kind, i + prefix, j + prefix, k + prefix, l + prefix)
                 for kind, i, j, k, l in operations if kind != "equal"), False


def _ordered_anchors(left: list[str], right: list[str]) -> list[tuple[int, int]]:
    """Get the longest in-order chain of exact, unique, nonblank matches."""
    left_counts, right_counts = Counter(left), Counter(right)
    right_indices = {text: k for k, text in enumerate(right) if right_counts[text] == 1}
    pairs = [(i, right_indices[text]) for i, text in enumerate(left)
             if left_counts[text] == 1 and text in right_indices and text.strip()]
    tails: list[int] = []
    endpoints: list[int] = []
    parents: list[int] = []
    for pair_index, (_, k) in enumerate(pairs):
        rank = bisect_left(tails, k)
        parents.append(endpoints[rank - 1] if rank else -1)
        if rank == len(tails):
            tails.append(k)
            endpoints.append(pair_index)
        else:
            tails[rank] = k
            endpoints[rank] = pair_index
    chain = []
    current = endpoints[-1] if endpoints else -1
    while current >= 0:
        chain.append(pairs[current])
        current = parents[current]
    return chain[::-1]


def _block_operations(left: list[str], right: list[str], check_cancelled: Callable[[], None],
                      work_budget: list[int] | None = None):
    if work_budget is None:
        work_budget = [4 * BLOCK_PAIR_LIMIT]
    operations, coarse = _operations(left, right, BLOCK_PAIR_LIMIT, check_cancelled, work_budget)
    if not coarse:
        return operations, False
    _, i, j, k, l = operations[0]
    anchors = _ordered_anchors(left[i:j], right[k:l])
    if not anchors:
        return operations, True
    # Never let many bounded subregions add up to unbounded quadratic work.
    a, b = i, k
    matches = []
    fallback = False
    for x, y in [(i + x, k + y) for x, y in anchors] + [(j, l)]:
        if a < x or b < y:
            gap, approximate = _operations(left[a:x], right[b:y], BLOCK_PAIR_LIMIT,
                                           check_cancelled, work_budget)
            matches.extend((kind, p + a, q + a, r + b, s + b) for kind, p, q, r, s in gap)
            fallback |= approximate
        a, b = x + 1, y + 1
    return tuple(matches), fallback


def _with_moves(operations: Sequence[Operation], left: list[str], right: list[str],
                check_cancelled: Callable[[], None],
                may_pair: Callable[[int, int], bool] | None = None) -> Iterator[Operation]:
    kinds = {operation[0] for operation in operations}
    if not {"insert", "delete"} <= kinds:
        yield from operations
        return
    left_counts, right_counts = Counter(left), Counter(right)
    deleted, inserted = {}, {}
    for kind, i, j, k, l in operations:
        check_cancelled()
        if kind == "delete":
            deleted.update((left[n], n) for n in range(i, j) if left_counts[left[n]] == 1 and left[n].strip())
        elif kind == "insert":
            inserted.update((right[n], n) for n in range(k, l) if right_counts[right[n]] == 1 and right[n].strip())
    pairs = {deleted[text]: inserted[text] for text in deleted.keys() & inserted.keys()
             if deleted[text] != inserted[text]
             and (may_pair is None or may_pair(deleted[text], inserted[text]))}
    if not pairs:
        yield from operations
        return
    destinations = set(pairs.values())
    for kind, i, j, k, l in operations:
        check_cancelled()
        if kind == "delete":
            start = i
            for n in range(i, j):
                if n in pairs:
                    if start < n:
                        yield "delete", start, n, k, k
                    dest = pairs[n]
                    yield "move", n, n + 1, dest, dest + 1
                    start = n + 1
            if start < j:
                yield "delete", start, j, k, k
        elif kind == "insert":
            start = k
            for n in range(k, l):
                if n in destinations:
                    if start < n:
                        yield "insert", i, i, start, n
                    start = n + 1
            if start < l:
                yield "insert", i, i, start, l
        else:
            yield kind, i, j, k, l


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


def _structured_operations(left: Snapshot, right: Snapshot, check_cancelled: Callable[[], None]):
    a, b = [block.text for block in left.blocks], [block.text for block in right.blocks]
    # Non-headings share an empty key and cannot become unique anchors.
    def keys(snapshot):
        return [repr(block.section_path) if block.kind == "heading" else "" for block in snapshot.blocks]

    anchors = _ordered_anchors(keys(left), keys(right))
    if not anchors:
        return _block_operations(a, b, check_cancelled)
    operations = []
    coarse = False
    budget = [4 * BLOCK_PAIR_LIMIT]
    i = k = 0
    for j, l in anchors + [(len(a), len(b))]:
        check_cancelled()
        gap, approximate = _block_operations(a[i:j], b[k:l], check_cancelled, budget)
        operations.extend((kind, x + i, y + i, z + k, w + k) for kind, x, y, z, w in gap)
        coarse |= approximate
        # Matching paths normally have identical headings. Preserve literal
        # changes (e.g. Markdown marker spacing) even when the title is equal.
        if j < len(a) and a[j] != b[l]:
            operations.append(("replace", j, j + 1, l, l + 1))
        i, k = j + 1, l + 1
    return tuple(operations), coarse


def _paragraph_changes(operations: Sequence[Operation], left: Snapshot, right: Snapshot,
                       check_cancelled: Callable[[], None]) -> Iterator[Operation]:
    # Split only confident one-to-one paragraph edits. Splits, merges and
    # unrelated replacements retain their complete region as evidence.
    budget = 4 * CHAR_PAIR_LIMIT
    for operation in operations:
        kind, i, j, k, l = operation
        if kind != "replace" or j - i != l - k or j - i <= 1:
            yield operation
            continue
        pairs = list(zip(left.blocks[i:j], right.blocks[k:l]))
        aligned = True
        for a, b in pairs:
            check_cancelled()
            cost = len(a.text) * len(b.text)
            if (not a.text.strip() or not b.text.strip() or a.kind != b.kind
                    or a.table_path != b.table_path or cost > min(CHAR_PAIR_LIMIT, budget)):
                aligned = False
                break
            budget -= cost
            if SequenceMatcher(None, a.text, b.text, autojunk=False).ratio() < 0.45:
                aligned = False
                break
        if aligned:
            for offset in range(j - i):
                yield "replace", i + offset, i + offset + 1, k + offset, k + offset + 1
        else:
            yield operation


def compare(left: Snapshot, right: Snapshot, check_cancelled: Callable[[], None] = no_cancel) -> Comparison:
    check_cancelled()
    if left.text == right.text:
        return Comparison((), False)
    left_blocks, right_blocks = [b.text for b in left.blocks], [b.text for b in right.blocks]
    operations, coarse = _structured_operations(left, right, check_cancelled)
    changes = []
    operations = tuple(_paragraph_changes(operations, left, right, check_cancelled))
    operations = refine_replacements(operations, left_blocks, right_blocks, check_cancelled)
    # Structured documents have explicit section paths. Never convert two
    # unrelated sections' deletions/additions into a move merely because
    # the text is equal or superficially similar.
    def same_section(i: int, j: int) -> bool:
        return left.blocks[i].section_path == right.blocks[j].section_path

    operations = expose_moves(operations, left_blocks, right_blocks, check_cancelled, same_section)
    operations = tuple(_with_moves(operations, left_blocks, right_blocks, check_cancelled, same_section))
    if any(kind in ("insert", "delete", "move") or i != k or j != l
           for kind, i, j, k, l in operations):
        operations = recover_edited_moves(operations, left_blocks, right_blocks,
                                          _ordered_anchors(left_blocks, right_blocks), check_cancelled,
                                          same_section)
    for kind, i, j, k, l in operations:
        check_cancelled()
        a, left_location = _block_span(left, i, j)
        b, right_location = _block_span(right, k, l)
        if kind in ("replace", "move_replace"):
            edits, approximate = _operations(left.text[a.start:a.end], right.text[b.start:b.end],
                                              CHAR_PAIR_LIMIT, check_cancelled)
            coarse |= approximate
            left_edits = tuple(Span(a.start + start, a.start + end) for _, start, end, _, _ in edits if start < end)
            right_edits = tuple(Span(b.start + start, b.start + end) for _, _, _, start, end in edits if start < end)
            left_words, right_words, approximate = _word_edits(
                left.text[a.start:a.end], right.text[b.start:b.end], a.start, b.start, check_cancelled)
            coarse |= approximate
        else:
            left_edits = (a,) if a.start < a.end else ()
            right_edits = (b,) if b.start < b.end else ()
            left_words, right_words = left_edits, right_edits
        changes.append(Change(kind, a, b, left_location, right_location, left_edits, right_edits,
                              left_words, right_words))
    return Comparison(tuple(changes), coarse)
