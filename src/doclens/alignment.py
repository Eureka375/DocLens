"""Conservative paragraph alignment helpers for the existing diff pipeline.

Never infer a semantic move from mere similarity: moves require an exact,
globally unique block occurring in unmatched regions on *both* sides.
"""

from collections import Counter
from collections.abc import Callable, Sequence
from difflib import SequenceMatcher

Operation = tuple[str, int, int, int, int]
ALIGNMENT_CELLS = 1_200
ALIGNMENT_TEXT_LIMIT = 12_000
BLOCK_CHAR_LIMIT = 1_200
MIN_SIMILARITY = 0.66


def _similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if min(len(left), len(right)) < 6:
        return 0.0
    if max(len(left), len(right)) > BLOCK_CHAR_LIMIT:
        return 0.0
    if min(len(left), len(right)) / max(len(left), len(right)) < 0.55:
        return 0.0
    # Avoid expensive character comparisons for entirely unrelated paragraphs.
    if not (set(left) & set(right)):
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def refine_replacements(operations: Sequence[Operation], left: list[str], right: list[str],
                        check_cancelled: Callable[[], None]) -> tuple[Operation, ...]:
    """Split large replace regions around strong in-order paragraph matches.

    Does not turn unrelated blocks into forced one-to-one replacements, and
    leaves large/adversarial regions on the original bounded fallback path.
    A split or merge remains a replace (the public Change API is unchanged).
    """
    result: list[Operation] = []
    for kind, i, j, k, l in operations:
        check_cancelled()
        n, m = j - i, l - k
        if (kind != "replace" or n * m > ALIGNMENT_CELLS or min(n, m) < 2
                or sum(map(len, left[i:j])) + sum(map(len, right[k:l])) > ALIGNMENT_TEXT_LIMIT):
            result.append((kind, i, j, k, l))
            continue
        weights = [[0.0] * m for _ in range(n)]
        has_anchor = False
        for a in range(n):
            check_cancelled()
            for b in range(m):
                ratio = _similarity(left[i + a], right[k + b])
                if ratio >= MIN_SIMILARITY:
                    # Exact in-order matches receive the highest weight.
                    weights[a][b] = 1.0 + ratio
                    has_anchor = True
        if not has_anchor:
            result.append((kind, i, j, k, l))
            continue
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        for a in range(n - 1, -1, -1):
            for b in range(m - 1, -1, -1):
                dp[a][b] = max(dp[a + 1][b], dp[a][b + 1],
                               weights[a][b] + dp[a + 1][b + 1] if weights[a][b] else 0.0)
        anchors = []
        a = b = 0
        while a < n and b < m:
            score = weights[a][b] + dp[a + 1][b + 1]
            if weights[a][b] and score >= dp[a + 1][b] - 1e-9 and score >= dp[a][b + 1] - 1e-9:
                anchors.append((i + a, k + b))
                a += 1
                b += 1
            elif dp[a + 1][b] >= dp[a][b + 1]:
                a += 1
            else:
                b += 1

        def gap(a0: int, a1: int, b0: int, b1: int) -> None:
            if a0 == a1 and b0 == b1:
                return
            label = "insert" if a0 == a1 else "delete" if b0 == b1 else "replace"
            result.append((label, a0, a1, b0, b1))

        a0, b0 = i, k
        for a, b in anchors:
            gap(a0, a, b0, b)
            if left[a] != right[b]:
                result.append(("replace", a, a + 1, b, b + 1))
            a0, b0 = a + 1, b + 1
        gap(a0, j, b0, l)
    return tuple(result)


def _runs(indices: list[int]) -> list[tuple[int, int]]:
    if not indices:
        return []
    result = []
    start = previous = indices[0]
    for index in indices[1:]:
        if index != previous + 1:
            result.append((start, previous + 1))
            start = index
        previous = index
    result.append((start, previous + 1))
    return result


def expose_moves(operations: Sequence[Operation], left: list[str], right: list[str],
                 check_cancelled: Callable[[], None]) -> tuple[Operation, ...]:
    """Expose unique exact moves hidden inside a replace plus a separate edit.

    The existing move reconciler can then replace matching delete/insert
    pairs with a single move. Never consume a block twice or create a span
    crossing an extracted moved paragraph.
    """
    left_owner, right_owner = {}, {}
    for op_id, (kind, i, j, k, l) in enumerate(operations):
        check_cancelled()
        left_owner.update((index, op_id) for index in range(i, j))
        right_owner.update((index, op_id) for index in range(k, l))
    lc, rc = Counter(left), Counter(right)
    right_unique = {text: i for i, text in enumerate(right)
                    if rc[text] == 1 and text.strip()}
    pairs = {}
    for i in left_owner:
        text = left[i]
        j = right_unique.get(text)
        if (j is not None and lc[text] == 1 and j in right_owner
                and i != j and left_owner[i] != right_owner[j]):
            pairs[i] = j
    if not pairs:
        return tuple(operations)
    destinations = set(pairs.values())
    result = []
    for kind, i, j, k, l in operations:
        check_cancelled()
        if kind != "replace" or not (any(n in pairs for n in range(i, j))
                                     or any(n in destinations for n in range(k, l))):
            result.append((kind, i, j, k, l))
            continue
        remaining_left = _runs([n for n in range(i, j) if n not in pairs])
        remaining_right = _runs([n for n in range(k, l) if n not in destinations])
        # Only produce a replace when both residual sides are contiguous.
        # Otherwise retain independent exact spans rather than crossing a move.
        if len(remaining_left) == len(remaining_right) == 1:
            a, b = remaining_left[0]
            c, d = remaining_right[0]
            if not (b == a + 1 and d == c + 1 and left[a] == right[c]):
                result.append(("replace", a, b, c, d))
        else:
            result.extend(("delete", a, b, k, k) for a, b in remaining_left)
            result.extend(("insert", i, i, c, d) for c, d in remaining_right)
        result.extend(("delete", n, n + 1, k, k) for n in range(i, j) if n in pairs)
        result.extend(("insert", i, i, n, n + 1) for n in range(k, l) if n in destinations)
    return tuple(result)
