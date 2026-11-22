"""Conservative detection of edited paragraphs that were also relocated.

Only unmatched unique-enough paragraphs crossing an unchanged in-order anchor
are eligible. A changed paragraph at the same logical position is not a move.
Ambiguous and large regions keep the original insert/delete/replace behavior.
"""

from bisect import bisect_left
from collections.abc import Callable, Sequence
from difflib import SequenceMatcher

Operation = tuple[str, int, int, int, int]
MAX_CANDIDATES = 100
MAX_PAIR_CELLS = 6_000
MAX_SIMILARITY_WORK = 2_000_000  # Upper bound on summed len(a) * len(b) comparisons
MIN_LENGTH = 16
MAX_LENGTH = 1200
MIN_RATIO = 0.86
MIN_MARGIN = 0.08


def _runs(values: list[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    result = []
    start = previous = values[0]
    for value in values[1:]:
        if value != previous + 1:
            result.append((start, previous + 1))
            start = value
        previous = value
    result.append((start, previous + 1))
    return result


def recover_edited_moves(operations: Sequence[Operation], left: list[str], right: list[str],
                         anchors: Sequence[tuple[int, int]],
                         check_cancelled: Callable[[], None],
                         may_pair: Callable[[int, int], bool] | None = None) -> tuple[Operation, ...]:
    """Yield move_replace for high-confidence moved-and-edited one-block pairs.

    Position evidence is an unchanged unique anchor crossed by the candidate.
    A mutual-best text match with a margin against alternatives is required.
    """
    source_owner: dict[int, int] = {}
    dest_owner: dict[int, int] = {}
    for op_id, (kind, i, j, k, l) in enumerate(operations):
        check_cancelled()
        if kind in ("delete", "replace"):
            source_owner.update((x, op_id) for x in range(i, j))
        if kind in ("insert", "replace"):
            dest_owner.update((x, op_id) for x in range(k, l))
    if not anchors or not source_owner or not dest_owner:
        return tuple(operations)
    sources = [x for x in source_owner if MIN_LENGTH <= len(left[x]) <= MAX_LENGTH and left[x].strip()]
    dests = [x for x in dest_owner if MIN_LENGTH <= len(right[x]) <= MAX_LENGTH and right[x].strip()]
    if (len(sources) > MAX_CANDIDATES or len(dests) > MAX_CANDIDATES
            or len(sources) * len(dests) > MAX_PAIR_CELLS):
        return tuple(operations)
    anchor_left = [a for a, _ in anchors]

    def crossed(i: int, j: int) -> bool:
        pos = bisect_left(anchor_left, i)
        return ((pos > 0 and anchors[pos - 1][1] > j)
                or (pos < len(anchors) and anchors[pos][1] < j))

    scores: dict[tuple[int, int], float] = {}
    work = 0
    for i in sources:
        check_cancelled()
        for j in dests:
            if (source_owner[i] == dest_owner[j] or left[i] == right[j]
                    or not crossed(i, j) or (may_pair is not None and not may_pair(i, j))):
                continue
            if min(len(left[i]), len(right[j])) / max(len(left[i]), len(right[j])) < 0.80:
                continue
            work += len(left[i]) * len(right[j])
            if work > MAX_SIMILARITY_WORK:
                return tuple(operations)  # Conservative bounded fallback.
            score = SequenceMatcher(None, left[i], right[j], autojunk=False).ratio()
            if score >= MIN_RATIO:
                scores[i, j] = score
    if not scores:
        return tuple(operations)
    moves = {}
    for (i, j), score in sorted(scores.items(), key=lambda x: (-x[1], x[0])):
        check_cancelled()
        rivals = [v for (a, b), v in scores.items() if (a == i and b != j) or (b == j and a != i)]
        if score - max(rivals, default=0.0) < MIN_MARGIN:
            continue
        if i not in moves and j not in moves.values():
            moves[i] = j
    if not moves:
        return tuple(operations)
    moved_right = set(moves.values())
    result: list[Operation] = []
    for kind, i, j, k, l in operations:
        check_cancelled()
        if kind not in ("insert", "delete", "replace"):
            result.append((kind, i, j, k, l))
            continue
        old_remaining = _runs([x for x in range(i, j) if x not in moves])
        new_remaining = _runs([x for x in range(k, l) if x not in moved_right])
        if kind == "replace" and len(old_remaining) == len(new_remaining) == 1:
            a, b = old_remaining[0]
            c, d = new_remaining[0]
            if left[a:b] != right[c:d]:
                result.append(("replace", a, b, c, d))
        else:
            result.extend(("delete", a, b, k, k) for a, b in old_remaining)
            result.extend(("insert", i, i, c, d) for c, d in new_remaining)
        for source in range(i, j):
            if source in moves:
                dest = moves[source]
                result.append(("move_replace", source, source + 1, dest, dest + 1))
    return tuple(result)
