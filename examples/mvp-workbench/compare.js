/* Literal matching and token diff for the synthetic prototype documents. */
(() => {
    const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    function matchRanges(text, keyword) {
        if (!keyword) return [];
        const leading = /^[A-Za-z0-9]/.test(keyword) ? '(?<![A-Za-z0-9_-])' : '';
        const trailing = /[A-Za-z0-9]$/.test(keyword) ? '(?![A-Za-z0-9_-])' : '';
        const pattern = new RegExp(leading + escapeRegExp(keyword) + trailing, 'gi');
        return Array.from(text.matchAll(pattern), match => [match.index, match.index + match[0].length]);
    }

    function tokenDiff(leftText, rightText) {
        const tokenize = text => text.match(/[A-Za-z0-9_]+(?:[-.][A-Za-z0-9_]+)*|\s+|[^]/gu) || [];
        const left = tokenize(leftText);
        const right = tokenize(rightText);
        const lengths = Array.from({length: left.length + 1}, () => new Uint16Array(right.length + 1));
        for (let i = left.length - 1; i >= 0; i--) {
            for (let j = right.length - 1; j >= 0; j--) {
                lengths[i][j] = left[i] === right[j]
                    ? lengths[i + 1][j + 1] + 1
                    : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
            }
        }
        const output = {left: [], right: []};
        function append(side, text, state) {
            const last = output[side].at(-1);
            if (last?.state === state) last.text += text;
            else output[side].push({text, state});
        }
        let i = 0;
        let j = 0;
        while (i < left.length || j < right.length) {
            if (i < left.length && j < right.length && left[i] === right[j]) {
                append('left', left[i++], 'same');
                append('right', right[j++], 'same');
            } else if (i < left.length && (j === right.length || lengths[i + 1][j] >= lengths[i][j + 1])) {
                append('left', left[i++], 'left');
            } else {
                append('right', right[j++], 'right');
            }
        }
        return output;
    }

    window.KeywordCompare = {matchRanges, tokenDiff};
})();
