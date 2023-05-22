// LICENSE
//
//	 This software is dual-licensed to the public domain and under the following
//	 license: you are granted a perpetual, irrevocable license to copy, modify,
//	 publish, and distribute this file as you see fit.
//
// VERSION
//	 0.1.0	(2016-03-28)	Initial release
//
// AUTHOR
//	 Forrest Smith
//
// CONTRIBUTORS
//	 J�rgen Tjern� - async helper
//	 Anurag Awasthi - updated to 0.2.0

const SEQUENTIAL_BONUS = 25; // bonus for adjacent matches
const SEPARATOR_BONUS = 30; // bonus if match occurs after a separator
const CAMEL_BONUS = 30; // bonus if match is uppercase and prev is lower
const FIRST_LETTER_BONUS = 15; // bonus if the first letter is matched

const LEADING_LETTER_PENALTY = -5; // penalty applied for every letter in str before the first match
const MAX_LEADING_LETTER_PENALTY = -15; // maximum penalty for leading letters
const UNMATCHED_LETTER_PENALTY = -1;

/**
 * Does a fuzzy search to find pattern inside a string.
 * @param {*} pattern string				pattern to search for
 * @param {*} str string    				string which is being searched
 * @returns [boolean, number]   			a boolean which tells if pattern was
 *											found or not and a search score
 */
export function fuzzy_match(pattern, str) {
	const recursion_count = 0;
	const recursion_limit = 10;
	const matches = [];
	const max_matches = 256;

	return fuzzy_match_recursive(
		pattern,
		str,
		0 /* pattern_cur_index */,
		0 /* str_curr_index */,
		null /* src_matches */,
		matches,
		max_matches,
		0 /* next_match */,
		recursion_count,
		recursion_limit
	);
}

function fuzzy_match_recursive(
	pattern,
	str,
	pattern_cur_index,
	str_curr_index,
	src_matches,
	matches,
	max_matches,
	next_match,
	recursion_count,
	recursion_limit
) {
	let out_score = 0;

	// Return if recursion limit is reached.
	if (++recursion_count >= recursion_limit) {
		return [false, out_score];
	}

	// Return if we reached ends of strings.
	if (pattern_cur_index === pattern.length || str_curr_index === str.length) {
		return [false, out_score];
	}

	// Recursion params
	let recursive_match = false;
	let best_recursive_matches = [];
	let best_recursive_score = 0;

	// Loop through pattern and str looking for a match.
	let first_match = true;
	while (pattern_cur_index < pattern.length && str_curr_index < str.length) {
		// Match found.
		if (pattern[pattern_cur_index].toLowerCase() === str[str_curr_index].toLowerCase()) {
			if (next_match >= max_matches) {
				return [false, out_score];
			}

			if (first_match && src_matches) {
				matches = [...src_matches];
				first_match = false;
			}

			const recursive_matches = [];
			const [matched, recursive_score] = fuzzy_match_recursive(
				pattern,
				str,
				pattern_cur_index,
				str_curr_index + 1,
				matches,
				recursive_matches,
				max_matches,
				next_match,
				recursion_count,
				recursion_limit
			);

			if (matched) {
				// Pick best recursive score.
				if (!recursive_match || recursive_score > best_recursive_score) {
					best_recursive_matches = [...recursive_matches];
					best_recursive_score = recursive_score;
				}
				recursive_match = true;
			}

			matches[next_match++] = str_curr_index;
			++pattern_cur_index;
		}
		++str_curr_index;
	}

	const matched = pattern_cur_index === pattern.length;

	if (matched) {
		out_score = 100;

		// Apply leading letter penalty
		let penalty = LEADING_LETTER_PENALTY * matches[0];
		penalty = penalty < MAX_LEADING_LETTER_PENALTY ? MAX_LEADING_LETTER_PENALTY : penalty;
		out_score += penalty;

		//Apply unmatched penalty
		const unmatched = str.length - next_match;
		out_score += UNMATCHED_LETTER_PENALTY * unmatched;

		// Apply ordering bonuses
		for (let i = 0; i < next_match; i++) {
			const curr_idx = matches[i];

			if (i > 0) {
				const prev_idx = matches[i - 1];
				if (curr_idx == prev_idx + 1) {
					out_score += SEQUENTIAL_BONUS;
				}
			}

			// Check for bonuses based on neighbor character value.
			if (curr_idx > 0) {
				// Camel case
				const neighbor = str[curr_idx - 1];
				const curr = str[curr_idx];
				if (neighbor !== neighbor.toUpperCase() && curr !== curr.toLowerCase()) {
					out_score += CAMEL_BONUS;
				}
				const is_neighbour_separator = neighbor == "_" || neighbor == " ";
				if (is_neighbour_separator) {
					out_score += SEPARATOR_BONUS;
				}
			} else {
				// First letter
				out_score += FIRST_LETTER_BONUS;
			}
		}

		// Return best result
		if (recursive_match && (!matched || best_recursive_score > out_score)) {
			// Recursive score is better than "this"
			matches = [...best_recursive_matches];
			out_score = best_recursive_score;
			return [true, out_score];
		} else if (matched) {
			// "this" score is better than recursive
			return [true, out_score];
		} else {
			return [false, out_score];
		}
	}
	return [false, out_score];
}
