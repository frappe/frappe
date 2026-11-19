// How well a text holds a lowercased query: the shell's one rule for its searches, with no fuzzy matching.

/** 0 when the text starts with the query, 1 when a later word does, 2 inside a word, `null` when absent. */
export function matchTier(text: string, needle: string): 0 | 1 | 2 | null {
	const haystack = text.toLowerCase();
	let best: 1 | 2 | null = null;
	for (let at = haystack.indexOf(needle); at >= 0; at = haystack.indexOf(needle, at + 1)) {
		if (at === 0) return 0;
		if (isWordStart(haystack, at)) return 1;
		best = 2;
	}
	return best;
}

function isWordStart(text: string, at: number) {
	return !/[\p{L}\p{N}]/u.test(text[at - 1]);
}
