from string.templatelib import Interpolation, Template

import frappe


def _(msg, lang: str | None = None, context: str | None = None) -> str:
	"""Return translated string in current lang, if exists.
	Usage:
	        _('Change')
	        _('Change', context='Coins')
	"""

	if isinstance(msg, Template):
		return _translate_template(msg, lang=lang, context=context)

	from frappe.translate import get_all_translations
	from frappe.utils import is_html, strip_html_tags

	if not hasattr(frappe.local, "lang"):
		frappe.local.lang = lang or "en"

	if not lang:
		lang = frappe.local.lang

	non_translated_string = msg

	if is_html(msg):
		msg = strip_html_tags(msg)

	# msg should always be unicode
	msg = frappe.as_unicode(msg).strip()

	translated_string = ""

	all_translations = get_all_translations(lang)
	if context:
		string_key = f"{msg}:{context}"
		translated_string = all_translations.get(string_key)

	if not translated_string:
		translated_string = all_translations.get(msg)

	return translated_string or non_translated_string


def _lt(msg: str, lang: str | None = None, context: str | None = None):
	"""Lazily translate a string.


	This function returns a "lazy string" which when casted to string via some operation applies
	translation first before casting.

	This is only useful for translating strings in global scope or anything that potentially runs
	before `frappe.init()`

	Note: Result is not guaranteed to equivalent to pure strings for all operations.
	"""
	from frappe.types.lazytranslatedstring import _LazyTranslate

	return _LazyTranslate(msg, lang, context)


def set_user_lang(user: str, user_language: str | None = None) -> None:
	"""Guess and set user language for the session. `frappe.local.lang`"""
	from frappe.translate import get_user_lang

	frappe.local.lang = get_user_lang(user) or user_language


def _translate_template(tpl: Template, lang: str | None = None, context: str | None = None) -> str:
	source_string, rendered_values = _template_to_positional(tpl)
	translated = _(source_string, lang=lang, context=context)
	return translated.format(*rendered_values)


def _template_to_positional(tpl: Template) -> tuple[str, tuple[str, ...]]:
	parts = []
	rendered_values = []

	static_parts = tpl.strings
	interpolations = tpl.interpolations

	for i, static_part in enumerate(static_parts):
		parts.append(static_part)

		if i < len(interpolations):
			parts.append(f"{{{len(rendered_values)}}}")
			rendered_values.append(_render_interpolation(interpolations[i]))

	return "".join(parts), tuple(rendered_values)


def _render_interpolation(interp: Interpolation) -> str:
	value = interp.value

	if interp.conversion == "r":
		value = repr(value)
	elif interp.conversion == "s":
		value = str(value)
	elif interp.conversion == "a":
		value = ascii(value)

	if interp.format_spec:
		return format(value, interp.format_spec)

	return str(value)
