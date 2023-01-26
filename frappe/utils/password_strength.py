# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from zxcvbn import zxcvbn
from zxcvbn.scoring import ALL_UPPER, START_UPPER

import frappe
from frappe import _


def test_password_strength(password, user_inputs=None):
	"""Wrapper around zxcvbn.password_strength"""
	if len(password) > 128:
		# zxcvbn takes forever when checking long, random passwords.
		# repetion patterns or user inputs in the first 128 characters
		# will still be checked.
		password = password[:128]

	result = zxcvbn(password, user_inputs)
	result["feedback"] = get_feedback(result.get("score"), result.get("sequence"))
	return result


# NOTE: code modified for frappe translations
# -------------------------------------------
# feedback functionality code from https://github.com/sans-serif/python-zxcvbn/blob/master/zxcvbn/feedback.py
# see license for feedback code at https://github.com/sans-serif/python-zxcvbn/blob/master/LICENSE.txt
# -------------------------------------------

# Default feedback value
default_feedback = {
	"warning": "",
	"suggestions": [
		_("Use a few words, avoid common phrases."),
		_("No need for symbols, digits, or uppercase letters."),
	],
}


def get_feedback(score, sequence):
	"""
	Returns the feedback dictionary consisting of ("warning","suggestions") for the given sequences.
	"""
	global default_feedback
	minimum_password_score = int(
		frappe.db.get_single_value("System Settings", "minimum_password_score") or 2
	)

	# Starting feedback
	if len(sequence) == 0:
		return default_feedback

	# No feedback if score is good or great
	if score >= minimum_password_score:
		return dict({"warning": "", "suggestions": []})

	# Tie feedback to the longest match for longer sequences
	longest_match = max(sequence, key=lambda seq: len(seq.get("token", "")))

	# Get feedback for this match
	feedback = get_match_feedback(longest_match, len(sequence) == 1)

	# If no concrete feedback returned, give more general feedback
	if not feedback:
		feedback = {
			"warning": "",
			"suggestions": [_("Better add a few more letters or another word")],
		}
	return feedback


def get_match_feedback(match, is_sole_match):
	"""
	Returns feedback as a dictionary for a certain match
	"""

	def fun_bruteforce():
		# Define a number of functions that are used in a look up dictionary
		return None

	def fun_dictionary():
		# If the match is of type dictionary, call specific function
		return get_dictionary_match_feedback(match, is_sole_match)

	def fun_spatial():
		feedback = {
			"warning": _("Short keyboard patterns are easy to guess"),
			"suggestions": [_("Make use of longer keyboard patterns")],
		}

		if match.get("turns") == 1:
			feedback = {
				"warning": _("Straight rows of keys are easy to guess"),
				"suggestions": [_("Try to use a longer keyboard pattern with more turns")],
			}

		return feedback

	def fun_repeat():
		feedback = {
			"warning": _('Repeats like "abcabcabc" are only slightly harder to guess than "abc"'),
			"suggestions": [_("Try to avoid repeated words and characters")],
		}
		if match.get("repeated_char") and len(match.get("repeated_char")) == 1:
			feedback = {
				"warning": _('Repeats like "aaa" are easy to guess'),
				"suggestions": [_("Let's avoid repeated words and characters")],
			}
		return feedback

	def fun_sequence():
		return {
			"suggestions": [_("Avoid sequences like abc or 6543 as they are easy to guess")],
		}

	def fun_regex():
		if match["regex_name"] == "recent_year":
			return {
				"warning": _("Recent years are easy to guess."),
				"suggestions": [_("Avoid recent years."), _("Avoid years that are associated with you.")],
			}

	def fun_date():
		return {
			"warning": _("Dates are often easy to guess."),
			"suggestions": [_("Avoid dates and years that are associated with you.")],
		}

	# Dictionary that maps pattern names to funtions that return feedback
	patterns = {
		"bruteforce": fun_bruteforce,
		"dictionary": fun_dictionary,
		"spatial": fun_spatial,
		"repeat": fun_repeat,
		"sequence": fun_sequence,
		"regex": fun_regex,
		"date": fun_date,
		"year": fun_date,
	}
	pattern_fn = patterns.get(match["pattern"])
	if pattern_fn:
		return pattern_fn()


def get_dictionary_match_feedback(match, is_sole_match):
	"""
	Returns feedback for a match that is found in a dictionary
	"""
	warning = ""
	suggestions = []

	# If the match is a common password
	if match.get("dictionary_name") == "passwords":
		if is_sole_match and not match.get("l33t_entropy"):
			if match.get("rank") <= 10:
				warning = _("This is a top-10 common password.")
			elif match.get("rank") <= 100:
				warning = _("This is a top-100 common password.")
			else:
				warning = _("This is a very common password.")
		else:
			warning = _("This is similar to a commonly used password.")

	# If the match is a common english word
	elif match.get("dictionary_name") == "english":
		if is_sole_match:
			warning = _("A word by itself is easy to guess.")

	# If the match is a common surname/name
	elif match.get("dictionary_name") in ["surnames", "male_names", "female_names"]:
		if is_sole_match:
			warning = _("Names and surnames by themselves are easy to guess.")
		else:
			warning = _("Common names and surnames are easy to guess.")

	word = match.get("token")
	# Variations of the match like UPPERCASES
	if START_UPPER.match(word):
		suggestions.append(_("Capitalization doesn't help very much."))
	elif ALL_UPPER.match(word):
		suggestions.append(_("All-uppercase is almost as easy to guess as all-lowercase."))

	# Match contains l33t speak substitutions
	if match.get("l33t_entropy"):
		suggestions.append(_("Predictable substitutions like '@' instead of 'a' don't help very much."))

	return {"warning": warning, "suggestions": suggestions}
