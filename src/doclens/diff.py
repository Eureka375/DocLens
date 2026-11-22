from bisect import bisect_left
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from difflib import SequenceMatcher

from .alignment import expose_moves, refine_replacements
from .edited_moves import recover_edited_moves
from .documents import no_cancel
from .models import Change, Comparison, Snapshot, Span

# Bound the quadratic scope of SequenceMatcher even for adversarial repetitions.
BLOCK_PAIR_LIMIT = 240_000
CHAR_PAIR_LIMIT = 160_000
Operation = tuple[str, int, int, int, int]


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


def _block_operations(left: list[str], right: list[str], check_cancelled: Callable[[], None]):
    operations, coarse = _operations(left, right, BLOCK_PAIR_LIMIT, check_cancelled)
    if not coarse:
        return operations, False
    _, i, j, k, l = operations[0]
    anchors = _ordered_anchors(left[i:j], right[k:l])
    if not anchors:
        return operations, True
    # Never let many bounded subregions add up to unbounded quadratic work.
    pair_budget = 4 * BLOCK_PAIR_LIMIT
    a, b = i, k
    matches = []
    fallback = False
    for x, y in [(i + x, k + y) for x, y in anchors] + [(j, l)]:
        if a < x or b < y:
            pairs = (x - a) * (y - b)
            limit = min(pair_budget, BLOCK_PAIR_LIMIT)
            gap, approximate = _operations(left[a:x], right[b:y], limit, check_cancelled)
            matches.extend((kind, p + a, q + a, r + b, s + b) for kind, p, q, r, s in gap)
            fallback |= approximate
            if pairs <= limit:
                pair_budget -= pairs
        a, b = x + 1, y + 1
    return tuple(matches), fallback


def _with_moves(operations: Sequence[Operation], left: list[str], right: list[str],
                check_cancelled: Callable[[], None]) -> Iterator[Operation]:
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
             if deleted[text] != inserted[text]}
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


def compare(left: Snapshot, right: Snapshot, check_cancelled: Callable[[], None] = no_cancel) -> Comparison:
    check_cancelled()
    if left.text == right.text:
        return Comparison((), False)
    left_blocks, right_blocks = [b.text for b in left.blocks], [b.text for b in right.blocks]
    operations, coarse = _block_operations(left_blocks, right_blocks, check_cancelled)
    operations = refine_replacements(operations, left_blocks, right_blocks, check_cancelled)
    operations = expose_moves(operations, left_blocks, right_blocks, check_cancelled)
    changes = []
    operations = tuple(_with_moves(operations, left_blocks, right_blocks, check_cancelled))
    # Ordinary aligned 1:1 replacements cannot cross a stable anchor.
    # Skip the global anchor walk on this common fast path.
    if any(kind in ("insert", "delete", "move") or i != k or j != l
           for kind, i, j, k, l in operations):
        operations = recover_edited_moves(operations, left_blocks, right_blocks,
                                          _ordered_anchors(left_blocks, right_blocks), check_cancelled)
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
        else:
            left_edits = (a,) if a.start < a.end else ()
            right_edits = (b,) if b.start < b.end else ()
        changes.append(Change(kind, a, b, left_location, right_location, left_edits, right_edits))
    return Comparison(tuple(changes), coarse)
